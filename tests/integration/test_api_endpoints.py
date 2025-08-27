"""
Integration tests for API endpoints.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from ai_agent_platform.main import create_app
from ai_agent_platform.models.agent import Agent, AgentStatus
from ai_agent_platform.execution.engine import TaskResult, TaskStatus


@pytest.fixture
def test_app():
    """Create test FastAPI application."""
    return create_app()


@pytest.fixture
def test_client(test_app):
    """Create test client."""
    return TestClient(test_app)


@pytest.fixture
def mock_agent():
    """Create mock agent for testing."""
    return Agent(
        id=uuid.uuid4(),
        name="TestAgent",
        description="A test agent",
        agent_type="test",
        version="1.0.0",
        status=AgentStatus.READY,
        capabilities=["chat", "analysis"],
        memory_limit_mb=512,
        timeout_seconds=300,
        max_concurrent_tasks=5,
    )


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_basic_health_check(self, test_client):
        """Test basic health check endpoint."""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "platform" in data
        assert "version" in data
        assert "timestamp" in data
    
    def test_detailed_health_check_success(self, test_client):
        """Test detailed health check with healthy services."""
        # Mock all health checks to return healthy
        mock_llm_health = {"status": "healthy", "provider": "lm_studio"}
        mock_rag_health = {"status": "healthy", "collections": ["default"]}
        
        with patch("ai_agent_platform.main.get_llm_manager") as mock_llm_mgr, \
             patch("ai_agent_platform.main.get_db_engine") as mock_db_engine, \
             patch("ai_agent_platform.main.get_rag_system") as mock_rag:
            
            # Mock LLM manager
            mock_llm_instance = AsyncMock()
            mock_llm_instance.health_check.return_value = mock_llm_health
            mock_llm_mgr.return_value = mock_llm_instance
            
            # Mock database engine
            mock_engine = AsyncMock()
            mock_conn = AsyncMock()
            mock_engine.connect.return_value.__aenter__.return_value = mock_conn
            mock_db_engine.return_value = mock_engine
            
            # Mock RAG system
            mock_rag_instance = AsyncMock()
            mock_rag_instance.health_check.return_value = mock_rag_health
            mock_rag.return_value = mock_rag_instance
            
            response = test_client.get("/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["services"]["llm"]["status"] == "healthy"
        assert data["services"]["database"]["status"] == "healthy"
        assert data["services"]["rag"]["status"] == "healthy"
    
    def test_detailed_health_check_degraded(self, test_client):
        """Test detailed health check with some unhealthy services."""
        with patch("ai_agent_platform.main.get_llm_manager") as mock_llm_mgr:
            # Mock LLM manager failure
            mock_llm_mgr.side_effect = Exception("LLM service unavailable")
            
            response = test_client.get("/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["llm"]["status"] == "unhealthy"
        assert "LLM service unavailable" in data["services"]["llm"]["error"]


class TestAgentEndpoints:
    """Test agent management endpoints."""
    
    def test_create_agent_success(self, test_client):
        """Test successful agent creation."""
        prd_content = """
        Agent Name: TestAgent
        Agent Type: test_agent
        Description: A test agent for validation
        Capabilities: chat, analysis
        """
        
        request_data = {
            "prd_content": prd_content,
            "created_by": "test_user"
        }
        
        mock_agent = Agent(
            id=uuid.uuid4(),
            name="TestAgent",
            description="A test agent for validation",
            agent_type="test_agent",
            version="1.0.0",
            status=AgentStatus.READY,
            capabilities=["chat", "analysis"],
        )
        
        with patch("ai_agent_platform.api.agents.AgentFactory") as mock_factory:
            mock_factory_instance = AsyncMock()
            mock_factory_instance.create_agent_from_prd.return_value = mock_agent
            mock_factory.return_value = mock_factory_instance
            
            response = test_client.post("/api/agents/", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "TestAgent"
        assert data["agent_type"] == "test_agent"
        assert "chat" in data["capabilities"]
    
    def test_list_agents(self, test_client, mock_agent):
        """Test listing agents."""
        with patch("ai_agent_platform.api.agents.AgentFactory") as mock_factory:
            mock_factory_instance = AsyncMock()
            mock_factory_instance.list_agents.return_value = [mock_agent]
            mock_factory.return_value = mock_factory_instance
            
            response = test_client.get("/api/agents/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert len(data["agents"]) == 1
        assert data["agents"][0]["name"] == "TestAgent"
    
    def test_get_agent_success(self, test_client, mock_agent):
        """Test getting specific agent."""
        agent_id = str(mock_agent.id)
        
        with patch("ai_agent_platform.api.agents.AgentFactory") as mock_factory:
            mock_factory_instance = AsyncMock()
            mock_factory_instance.get_agent.return_value = mock_agent
            mock_factory.return_value = mock_factory_instance
            
            response = test_client.get(f"/api/agents/{agent_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "TestAgent"
        assert data["id"] == agent_id
    
    def test_get_agent_not_found(self, test_client):
        """Test getting non-existent agent."""
        agent_id = str(uuid.uuid4())
        
        with patch("ai_agent_platform.api.agents.AgentFactory") as mock_factory:
            mock_factory_instance = AsyncMock()
            mock_factory_instance.get_agent.return_value = None
            mock_factory.return_value = mock_factory_instance
            
            response = test_client.get(f"/api/agents/{agent_id}")
        
        assert response.status_code == 404
        assert "Agent not found" in response.json()["detail"]
    
    def test_chat_with_agent_success(self, test_client, mock_agent):
        """Test successful agent chat."""
        agent_id = str(mock_agent.id)
        chat_request = {
            "message": "Hello, how can you help me?",
            "session_id": "test_session",
            "use_rag": True,
            "rag_collection": "default"
        }
        
        # Mock execution result
        mock_result = TaskResult(
            task_id=str(uuid.uuid4()),
            status=TaskStatus.COMPLETED,
            output_data={
                "response": "I can help you with various tasks!",
                "sources": [{"source": "doc1.txt"}],
                "context_used": True,
            },
            execution_time_ms=150,
        )
        
        with patch("ai_agent_platform.api.agents.AgentFactory") as mock_factory, \
             patch("ai_agent_platform.api.agents.get_execution_engine") as mock_engine:
            
            # Mock factory
            mock_factory_instance = AsyncMock()
            mock_factory_instance.get_agent.return_value = mock_agent
            mock_factory.return_value = mock_factory_instance
            
            # Mock execution engine
            mock_engine_instance = AsyncMock()
            mock_engine_instance.execute_chat_task.return_value = mock_result
            mock_engine.return_value = mock_engine_instance
            
            response = test_client.post(f"/api/agents/{agent_id}/chat", json=chat_request)
        
        assert response.status_code == 200
        data = response.json()
        assert "help you with various tasks" in data["response"]
        assert data["context_used"] is True
        assert len(data["sources"]) > 0
        assert data["execution_time_ms"] == 150
    
    def test_execute_agent_task_success(self, test_client, mock_agent):
        """Test successful agent task execution."""
        agent_id = str(mock_agent.id)
        task_request = {
            "task_type": "data_analysis",
            "input_data": {"data": [1, 2, 3, 4, 5]},
            "session_id": "test_session"
        }
        
        # Mock execution result
        mock_result = TaskResult(
            task_id=str(uuid.uuid4()),
            status=TaskStatus.COMPLETED,
            output_data={
                "analysis_type": "data_analysis",
                "results": {"processed_records": 5},
                "input_processed": True,
            },
            execution_time_ms=200,
            memory_used_mb=25.5,
        )
        
        with patch("ai_agent_platform.api.agents.AgentFactory") as mock_factory, \
             patch("ai_agent_platform.api.agents.get_execution_engine") as mock_engine:
            
            # Mock factory
            mock_factory_instance = AsyncMock()
            mock_factory_instance.get_agent.return_value = mock_agent
            mock_factory.return_value = mock_factory_instance
            
            # Mock execution engine
            mock_engine_instance = AsyncMock()
            mock_engine_instance.execute_tool_task.return_value = mock_result
            mock_engine.return_value = mock_engine_instance
            
            response = test_client.post(f"/api/agents/{agent_id}/tasks", json=task_request)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["output_data"]["analysis_type"] == "data_analysis"
        assert data["execution_time_ms"] == 200
        assert data["memory_used_mb"] == 25.5


class TestRAGEndpoints:
    """Test RAG system endpoints."""
    
    def test_add_text_to_rag_success(self, test_client):
        """Test successful text addition to RAG."""
        request_data = {
            "text": "This is a test document for RAG system testing.",
            "metadata": {"source": "test", "type": "document"},
            "collection_name": "test_collection"
        }
        
        with patch("ai_agent_platform.api.rag.get_rag_system") as mock_rag:
            mock_rag_instance = AsyncMock()
            mock_rag_instance.add_text.return_value = ["doc_1", "doc_2"]
            mock_rag.return_value = mock_rag_instance
            
            response = test_client.post("/api/rag/add-text", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["chunks_created"] == 2
        assert data["collection_name"] == "test_collection"
        assert len(data["document_ids"]) == 2
    
    def test_query_rag_success(self, test_client):
        """Test successful RAG query."""
        request_data = {
            "question": "What is machine learning?",
            "k": 3,
            "collection_name": "default",
            "include_sources": True
        }
        
        mock_result = {
            "answer": "Machine learning is a subset of artificial intelligence...",
            "sources": [
                {"source": "ml_basics.txt", "content": "ML definition..."},
                {"source": "ai_overview.pdf", "content": "AI concepts..."}
            ],
            "context_used": True,
            "num_sources": 2
        }
        
        with patch("ai_agent_platform.api.rag.get_rag_system") as mock_rag:
            mock_rag_instance = AsyncMock()
            mock_rag_instance.query.return_value = mock_result
            mock_rag.return_value = mock_rag_instance
            
            response = test_client.post("/api/rag/query", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "Machine learning" in data["answer"]
        assert data["context_used"] is True
        assert data["num_sources"] == 2
        assert len(data["sources"]) == 2
    
    def test_rag_health_check(self, test_client):
        """Test RAG health check endpoint."""
        mock_health = {
            "status": "healthy",
            "collections": ["default", "test"],
            "total_documents": 150
        }
        
        with patch("ai_agent_platform.api.rag.get_rag_system") as mock_rag:
            mock_rag_instance = AsyncMock()
            mock_rag_instance.health_check.return_value = mock_health
            mock_rag.return_value = mock_rag_instance
            
            response = test_client.get("/api/rag/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert len(data["collections"]) == 2
        assert data["total_documents"] == 150


class TestToolEndpoints:
    """Test tool registry endpoints."""
    
    def test_list_tools_success(self, test_client):
        """Test successful tool listing."""
        mock_tools = [
            AsyncMock(
                tool_name="data_processor",
                tool_category="data",
                description="Process data files",
                version="1.0.0",
                is_public=True,
                security_level="public",
                requires_approval=False,
                tool_config={"max_file_size": "10MB"}
            ),
            AsyncMock(
                tool_name="content_generator",
                tool_category="content",
                description="Generate text content",
                version="2.0.0",
                is_public=True,
                security_level="public", 
                requires_approval=False,
                tool_config={"models": ["gpt", "claude"]}
            )
        ]
        
        with patch("ai_agent_platform.api.tools.UniversalToolRegistry") as mock_registry:
            mock_registry_instance = AsyncMock()
            mock_registry_instance.get_available_tools.return_value = mock_tools
            mock_registry.return_value = mock_registry_instance
            
            response = test_client.get("/api/tools/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2
        assert len(data["tools"]) == 2
        assert data["tools"][0]["tool_name"] == "data_processor"
        assert data["tools"][1]["tool_name"] == "content_generator"
    
    def test_get_tool_success(self, test_client):
        """Test successful tool retrieval."""
        tool_name = "data_processor"
        mock_tool = AsyncMock(
            tool_name=tool_name,
            tool_category="data",
            description="Process data files",
            version="1.0.0",
            is_public=True,
            security_level="public",
            requires_approval=False,
            tool_config={"max_file_size": "10MB"}
        )
        
        with patch("ai_agent_platform.api.tools.UniversalToolRegistry") as mock_registry:
            mock_registry_instance = AsyncMock()
            mock_registry_instance.get_tool.return_value = mock_tool
            mock_registry.return_value = mock_registry_instance
            
            response = test_client.get(f"/api/tools/{tool_name}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["tool_name"] == tool_name
        assert data["tool_category"] == "data"
        assert data["is_public"] is True
    
    def test_check_tool_access_success(self, test_client):
        """Test tool access checking."""
        tool_name = "data_processor"
        
        with patch("ai_agent_platform.api.tools.UniversalToolRegistry") as mock_registry:
            mock_registry_instance = AsyncMock()
            mock_registry_instance.check_tool_access.return_value = True
            mock_registry.return_value = mock_registry_instance
            
            response = test_client.get(
                f"/api/tools/{tool_name}/check-access?agent_type=data_analyst&security_clearance=public"
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["tool_name"] == tool_name
        assert data["agent_type"] == "data_analyst"
        assert data["has_access"] is True
        assert data["security_clearance"] == "public"


class TestRootEndpoint:
    """Test root API endpoint."""
    
    def test_root_endpoint(self, test_client):
        """Test root endpoint returns platform information."""
        response = test_client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "AI Agent Platform API"
        assert "version" in data
        assert "docs" in data


if __name__ == "__main__":
    pytest.main([__file__])