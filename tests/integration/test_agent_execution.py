"""
Integration tests for agent execution engine.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from ai_agent_platform.execution.engine import AgentExecutionEngine, ExecutionContext, TaskStatus
from ai_agent_platform.models.agent import Agent, AgentStatus
from ai_agent_platform.llm.providers import get_llm_manager
from ai_agent_platform.memory.context import get_context_manager
from ai_agent_platform.rag.vector_store import get_rag_system


@pytest.fixture
async def mock_agent():
    """Create a mock agent for testing."""
    return Agent(
        id=uuid.uuid4(),
        name="TestAgent",
        description="A test agent for integration testing",
        agent_type="test_agent",
        version="1.0.0",
        status=AgentStatus.READY,
        capabilities=["chat", "analysis", "content_generation"],
        memory_limit_mb=512,
        timeout_seconds=300,
        max_concurrent_tasks=5,
    )


@pytest.fixture
def execution_context():
    """Create an execution context for testing."""
    return ExecutionContext(
        task_id=str(uuid.uuid4()),
        agent_id=str(uuid.uuid4()),
        session_id="test_session",
        metadata={"test": True},
    )


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return AsyncMock(spec=AsyncSession)


class TestAgentExecutionEngine:
    """Test agent execution engine."""
    
    @pytest.fixture
    def execution_engine(self, mock_db_session):
        """Create execution engine for testing."""
        return AgentExecutionEngine(mock_db_session)
    
    @pytest.mark.asyncio
    async def test_execute_chat_task_success(self, execution_engine, mock_agent, execution_context):
        """Test successful chat task execution."""
        message = "Hello, how can you help me?"
        
        # Mock dependencies
        mock_llm_manager = AsyncMock()
        mock_llm_manager.chat_completion.return_value = "I can help you with various tasks!"
        
        mock_context_manager = AsyncMock()
        mock_agent_memory = AsyncMock()
        mock_agent_memory.session_id = "test_session"
        mock_agent_memory.get_conversation_history.return_value = []
        mock_context_manager.get_agent_memory.return_value = mock_agent_memory
        
        mock_rag_system = AsyncMock()
        mock_rag_system.query.return_value = {
            "answer": "Relevant context from RAG",
            "sources": [{"source": "doc1.txt", "content": "sample"}],
            "context_used": True,
            "num_sources": 1,
        }
        
        with patch("ai_agent_platform.execution.engine.get_llm_manager", return_value=mock_llm_manager), \
             patch("ai_agent_platform.execution.engine.get_context_manager", return_value=mock_context_manager), \
             patch("ai_agent_platform.execution.engine.get_rag_system", return_value=mock_rag_system):
            
            result = await execution_engine.execute_chat_task(
                agent=mock_agent,
                message=message,
                context=execution_context,
                use_rag=True,
                rag_collection="default"
            )
        
        assert result.status == TaskStatus.COMPLETED
        assert result.task_id == execution_context.task_id
        assert "help you with various tasks" in result.output_data["response"]
        assert result.output_data["context_used"] is True
        assert len(result.output_data["sources"]) > 0
        assert result.execution_time_ms is not None
        assert result.memory_used_mb is not None
    
    @pytest.mark.asyncio
    async def test_execute_chat_task_without_rag(self, execution_engine, mock_agent, execution_context):
        """Test chat task execution without RAG."""
        message = "Hello!"
        
        # Mock dependencies
        mock_llm_manager = AsyncMock()
        mock_llm_manager.chat_completion.return_value = "Hello! How are you?"
        
        mock_context_manager = AsyncMock()
        mock_agent_memory = AsyncMock()
        mock_agent_memory.session_id = "test_session"
        mock_agent_memory.get_conversation_history.return_value = []
        mock_context_manager.get_agent_memory.return_value = mock_agent_memory
        
        with patch("ai_agent_platform.execution.engine.get_llm_manager", return_value=mock_llm_manager), \
             patch("ai_agent_platform.execution.engine.get_context_manager", return_value=mock_context_manager):
            
            result = await execution_engine.execute_chat_task(
                agent=mock_agent,
                message=message,
                context=execution_context,
                use_rag=False
            )
        
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["context_used"] is False
        assert result.output_data["sources"] == []
    
    @pytest.mark.asyncio
    async def test_execute_tool_task_data_analysis(self, execution_engine, mock_agent, execution_context):
        """Test data analysis tool task execution."""
        task_type = "data_analysis"
        input_data = {"data": [1, 2, 3, 4, 5], "analysis_type": "summary"}
        
        # Mock tool registry
        mock_tool_registry = AsyncMock()
        mock_tool_registry.check_tool_access.return_value = True
        
        with patch("ai_agent_platform.execution.engine.UniversalToolRegistry", return_value=mock_tool_registry):
            result = await execution_engine.execute_tool_task(
                agent=mock_agent,
                task_type=task_type,
                input_data=input_data,
                context=execution_context,
            )
        
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["analysis_type"] == "data_analysis"
        assert result.output_data["input_processed"] is True
        assert len(result.tools_used) > 0
    
    @pytest.mark.asyncio
    async def test_execute_tool_task_content_generation(self, execution_engine, mock_agent, execution_context):
        """Test content generation tool task execution."""
        task_type = "content_generation"
        input_data = {
            "task": "Write a blog post",
            "requirements": "About AI agents",
            "tone": "professional",
            "length": "medium"
        }
        
        # Mock LLM manager
        mock_llm_manager = AsyncMock()
        mock_llm_manager.completion.return_value = "AI agents are revolutionizing how we work..."
        
        # Mock tool registry
        mock_tool_registry = AsyncMock()
        mock_tool_registry.check_tool_access.return_value = True
        
        with patch("ai_agent_platform.execution.engine.UniversalToolRegistry", return_value=mock_tool_registry), \
             patch("ai_agent_platform.execution.engine.get_llm_manager", return_value=mock_llm_manager):
            
            result = await execution_engine.execute_tool_task(
                agent=mock_agent,
                task_type=task_type,
                input_data=input_data,
                context=execution_context,
            )
        
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["task_type"] == "content_generation"
        assert "revolutionizing" in result.output_data["generated_content"]
        assert result.output_data["word_count"] > 0
    
    @pytest.mark.asyncio
    async def test_execute_tool_task_no_access(self, execution_engine, mock_agent, execution_context):
        """Test tool task execution when agent has no tool access."""
        task_type = "data_analysis"
        input_data = {"data": [1, 2, 3]}
        
        # Mock tool registry - no access
        mock_tool_registry = AsyncMock()
        mock_tool_registry.check_tool_access.return_value = False
        
        with patch("ai_agent_platform.execution.engine.UniversalToolRegistry", return_value=mock_tool_registry):
            result = await execution_engine.execute_tool_task(
                agent=mock_agent,
                task_type=task_type,
                input_data=input_data,
                context=execution_context,
            )
        
        assert result.status == TaskStatus.FAILED
        assert "does not have access to required tools" in result.error_message
    
    @pytest.mark.asyncio
    async def test_execute_chat_task_llm_failure(self, execution_engine, mock_agent, execution_context):
        """Test chat task execution with LLM failure."""
        message = "Hello!"
        
        # Mock LLM failure
        mock_llm_manager = AsyncMock()
        mock_llm_manager.chat_completion.side_effect = Exception("LLM service unavailable")
        
        mock_context_manager = AsyncMock()
        mock_agent_memory = AsyncMock()
        mock_agent_memory.get_conversation_history.return_value = []
        mock_context_manager.get_agent_memory.return_value = mock_agent_memory
        
        with patch("ai_agent_platform.execution.engine.get_llm_manager", return_value=mock_llm_manager), \
             patch("ai_agent_platform.execution.engine.get_context_manager", return_value=mock_context_manager):
            
            result = await execution_engine.execute_chat_task(
                agent=mock_agent,
                message=message,
                context=execution_context,
                use_rag=False
            )
        
        assert result.status == TaskStatus.FAILED
        assert "LLM service unavailable" in result.error_message
    
    @pytest.mark.asyncio
    async def test_task_registration_and_status(self, execution_engine, execution_context):
        """Test task registration and status checking."""
        # Register task
        await execution_engine._register_task(execution_context)
        
        # Check status
        status = await execution_engine.get_task_status(execution_context.task_id)
        assert status == TaskStatus.RUNNING
        
        # Unregister task
        await execution_engine._unregister_task(execution_context.task_id)
        
        # Check status again
        status = await execution_engine.get_task_status(execution_context.task_id)
        assert status is None
    
    @pytest.mark.asyncio
    async def test_cancel_task(self, execution_engine, execution_context):
        """Test task cancellation."""
        # Register task
        await execution_engine._register_task(execution_context)
        
        # Cancel task
        cancelled = await execution_engine.cancel_task(execution_context.task_id)
        assert cancelled is True
        
        # Check status
        status = await execution_engine.get_task_status(execution_context.task_id)
        assert status is None
        
        # Try to cancel non-existent task
        cancelled = await execution_engine.cancel_task("non-existent-task")
        assert cancelled is False


class TestExecutionEngineIntegration:
    """Test execution engine integration with other components."""
    
    @pytest.mark.asyncio
    async def test_execute_code_review_task(self):
        """Test code review task execution."""
        db_session = AsyncMock(spec=AsyncSession)
        engine = AgentExecutionEngine(db_session)
        
        agent = Agent(
            id=uuid.uuid4(),
            name="CodeReviewer",
            description="Code review specialist",
            agent_type="code_reviewer",
            version="1.0.0",
            status=AgentStatus.READY,
            capabilities=["code_review", "security_analysis"],
        )
        
        context = ExecutionContext(
            task_id=str(uuid.uuid4()),
            agent_id=str(agent.id),
        )
        
        input_data = {
            "code": "def hello_world():\n    print('Hello, World!')\n    return True",
            "language": "python"
        }
        
        # Mock tool registry
        mock_tool_registry = AsyncMock()
        mock_tool_registry.check_tool_access.return_value = True
        
        with patch("ai_agent_platform.execution.engine.UniversalToolRegistry", return_value=mock_tool_registry):
            result = await engine.execute_tool_task(
                agent=agent,
                task_type="code_review",
                input_data=input_data,
                context=context,
            )
        
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["task_type"] == "code_review"
        assert result.output_data["language"] == "python"
        assert result.output_data["lines_reviewed"] > 0
        assert "issues" in result.output_data
    
    @pytest.mark.asyncio
    async def test_generic_task_execution(self):
        """Test generic task execution using LLM."""
        db_session = AsyncMock(spec=AsyncSession)
        engine = AgentExecutionEngine(db_session)
        
        agent = Agent(
            id=uuid.uuid4(),
            name="GeneralAgent",
            description="General purpose agent",
            agent_type="general",
            version="1.0.0",
            status=AgentStatus.READY,
            capabilities=["general_tasks"],
        )
        
        context = ExecutionContext(
            task_id=str(uuid.uuid4()),
            agent_id=str(agent.id),
        )
        
        # Mock LLM manager
        mock_llm_manager = AsyncMock()
        mock_llm_manager.completion.return_value = "Task completed successfully with custom logic."
        
        # Mock tool registry
        mock_tool_registry = AsyncMock()
        mock_tool_registry.check_tool_access.return_value = True
        
        with patch("ai_agent_platform.execution.engine.UniversalToolRegistry", return_value=mock_tool_registry), \
             patch("ai_agent_platform.execution.engine.get_llm_manager", return_value=mock_llm_manager):
            
            result = await engine.execute_tool_task(
                agent=agent,
                task_type="custom_analysis",
                input_data={"query": "Analyze market trends"},
                context=context,
            )
        
        assert result.status == TaskStatus.COMPLETED
        assert result.output_data["task_type"] == "custom_analysis"
        assert "completed successfully" in result.output_data["agent_response"]
        assert result.output_data["execution_method"] == "llm_processing"


if __name__ == "__main__":
    pytest.main([__file__])