"""
Full system integration tests.
"""

import pytest
import uuid
import asyncio
from unittest.mock import AsyncMock, patch

from ai_agent_platform.config import config
from ai_agent_platform.core.agent_factory import AgentFactory
from ai_agent_platform.execution.engine import get_execution_engine, ExecutionContext
from ai_agent_platform.llm.providers import get_llm_manager
from ai_agent_platform.rag.vector_store import get_rag_system
from ai_agent_platform.tools.registry import UniversalToolRegistry
from ai_agent_platform.models.agent import Agent, AgentStatus


class TestFullSystemIntegration:
    """Test full system integration from PRD to execution."""
    
    @pytest.mark.asyncio
    async def test_complete_agent_lifecycle(self):
        """Test complete agent lifecycle from creation to execution."""
        # Mock database session
        mock_db = AsyncMock()
        
        # Step 1: Create agent from PRD
        prd_content = """
        Agent Name: DataAnalyst
        Agent Type: data_analyst
        Description: Specialized agent for data analysis and visualization
        Capabilities: data_processing, statistical_analysis, visualization, reporting
        Memory Limit: 1024
        Timeout: 600
        Max Concurrent Tasks: 3
        
        The agent should be able to:
        - Process CSV and JSON data files
        - Perform statistical analysis
        - Generate visualizations
        - Create summary reports
        """
        
        # Mock agent creation
        mock_agent = Agent(
            id=uuid.uuid4(),
            name="DataAnalyst",
            description="Specialized agent for data analysis and visualization",
            agent_type="data_analyst",
            version="1.0.0",
            status=AgentStatus.READY,
            capabilities=["data_processing", "statistical_analysis", "visualization", "reporting"],
            memory_limit_mb=1024,
            timeout_seconds=600,
            max_concurrent_tasks=3,
        )
        
        with patch("ai_agent_platform.core.agent_factory.AgentFactory") as mock_factory_class:
            mock_factory = AsyncMock()
            mock_factory.create_agent_from_prd.return_value = mock_agent
            mock_factory_class.return_value = mock_factory
            
            factory = AgentFactory(mock_db)
            agent = await factory.create_agent_from_prd(prd_content, "system")
        
        assert agent.name == "DataAnalyst"
        assert agent.agent_type == "data_analyst"
        assert "data_processing" in agent.capabilities
        assert agent.memory_limit_mb == 1024
        
        # Step 2: Add knowledge to RAG system
        rag_system = get_rag_system()
        
        test_documents = [
            "Data analysis involves examining datasets to draw conclusions about the information they contain.",
            "Statistical analysis helps identify trends, patterns, and relationships in data.",
            "Data visualization makes complex information accessible through charts and graphs."
        ]
        
        with patch.object(rag_system, 'add_text') as mock_add_text:
            mock_add_text.return_value = ["doc1", "doc2", "doc3"]
            
            for i, doc in enumerate(test_documents):
                await rag_system.add_text(
                    text=doc,
                    metadata={"source": f"knowledge_base_{i+1}.txt", "category": "data_analysis"},
                    collection_name="data_analysis"
                )
        
        # Step 3: Chat with agent (using RAG)
        execution_engine = get_execution_engine(mock_db)
        
        context = ExecutionContext(
            task_id=str(uuid.uuid4()),
            agent_id=str(agent.id),
            session_id="integration_test_session",
        )
        
        # Mock RAG query response
        mock_rag_response = {
            "answer": "Data analysis involves examining datasets to identify patterns and trends.",
            "sources": [{"source": "knowledge_base_1.txt", "content": "Data analysis definition..."}],
            "context_used": True,
            "num_sources": 1
        }
        
        # Mock LLM response
        mock_llm_response = "I can help you analyze your data. I specialize in statistical analysis, data processing, and creating visualizations. What kind of data would you like to analyze?"
        
        with patch.object(rag_system, 'query', return_value=mock_rag_response), \
             patch("ai_agent_platform.execution.engine.get_llm_manager") as mock_llm_mgr, \
             patch("ai_agent_platform.execution.engine.get_context_manager") as mock_ctx_mgr:
            
            # Mock LLM manager
            mock_llm_instance = AsyncMock()
            mock_llm_instance.chat_completion.return_value = mock_llm_response
            mock_llm_mgr.return_value = mock_llm_instance
            
            # Mock context manager
            mock_memory = AsyncMock()
            mock_memory.session_id = context.session_id
            mock_memory.get_conversation_history.return_value = []
            mock_ctx_manager.return_value.get_agent_memory.return_value = mock_memory
            
            chat_result = await execution_engine.execute_chat_task(
                agent=agent,
                message="Hi! Can you help me analyze some sales data?",
                context=context,
                use_rag=True,
                rag_collection="data_analysis"
            )
        
        assert chat_result.status.value == "completed"
        assert "analyze your data" in chat_result.output_data["response"]
        assert chat_result.output_data["context_used"] is True
        assert len(chat_result.output_data["sources"]) > 0
        
        # Step 4: Execute a data analysis task
        task_context = ExecutionContext(
            task_id=str(uuid.uuid4()),
            agent_id=str(agent.id),
            session_id=context.session_id,
        )
        
        input_data = {
            "data": [
                {"month": "Jan", "sales": 10000, "region": "North"},
                {"month": "Feb", "sales": 12000, "region": "North"},
                {"month": "Mar", "sales": 15000, "region": "North"},
                {"month": "Jan", "sales": 8000, "region": "South"},
                {"month": "Feb", "sales": 9000, "region": "South"},
                {"month": "Mar", "sales": 11000, "region": "South"},
            ],
            "analysis_type": "trend_analysis"
        }
        
        # Mock tool registry
        with patch("ai_agent_platform.execution.engine.UniversalToolRegistry") as mock_registry:
            mock_registry_instance = AsyncMock()
            mock_registry_instance.check_tool_access.return_value = True
            mock_registry.return_value = mock_registry_instance
            
            task_result = await execution_engine.execute_tool_task(
                agent=agent,
                task_type="data_analysis",
                input_data=input_data,
                context=task_context,
            )
        
        assert task_result.status.value == "completed"
        assert task_result.output_data["analysis_type"] == "data_analysis"
        assert task_result.output_data["input_processed"] is True
        assert task_result.execution_time_ms is not None
        
        # Step 5: Verify agent can handle multiple concurrent tasks
        contexts = [
            ExecutionContext(task_id=str(uuid.uuid4()), agent_id=str(agent.id))
            for _ in range(3)
        ]
        
        # Mock tools and execute tasks concurrently
        with patch("ai_agent_platform.execution.engine.UniversalToolRegistry") as mock_registry:
            mock_registry_instance = AsyncMock()
            mock_registry_instance.check_tool_access.return_value = True
            mock_registry.return_value = mock_registry_instance
            
            tasks = [
                execution_engine.execute_tool_task(
                    agent=agent,
                    task_type="data_analysis",
                    input_data={"data": [1, 2, 3], "analysis_type": f"concurrent_test_{i}"},
                    context=ctx,
                )
                for i, ctx in enumerate(contexts)
            ]
            
            results = await asyncio.gather(*tasks)
        
        # All tasks should complete successfully
        assert len(results) == 3
        for result in results:
            assert result.status.value == "completed"
            assert result.output_data["input_processed"] is True
    
    @pytest.mark.asyncio
    async def test_agent_with_tool_restrictions(self):
        """Test agent behavior with tool access restrictions."""
        mock_db = AsyncMock()
        
        # Create agent with limited capabilities
        restricted_agent = Agent(
            id=uuid.uuid4(),
            name="BasicAgent",
            description="Agent with basic capabilities only",
            agent_type="basic",
            version="1.0.0",
            status=AgentStatus.READY,
            capabilities=["chat", "simple_text_processing"],
            memory_limit_mb=256,
            timeout_seconds=120,
            max_concurrent_tasks=1,
        )
        
        execution_engine = get_execution_engine(mock_db)
        
        context = ExecutionContext(
            task_id=str(uuid.uuid4()),
            agent_id=str(restricted_agent.id),
        )
        
        # Try to execute a task requiring advanced tools
        advanced_input = {
            "data": "complex dataset requiring machine learning analysis",
            "analysis_type": "advanced_ml_analysis"
        }
        
        # Mock tool registry to deny access to advanced tools
        with patch("ai_agent_platform.execution.engine.UniversalToolRegistry") as mock_registry:
            mock_registry_instance = AsyncMock()
            mock_registry_instance.check_tool_access.return_value = False
            mock_registry.return_value = mock_registry_instance
            
            result = await execution_engine.execute_tool_task(
                agent=restricted_agent,
                task_type="advanced_ml_analysis",
                input_data=advanced_input,
                context=context,
            )
        
        assert result.status.value == "failed"
        assert "does not have access to required tools" in result.error_message
    
    @pytest.mark.asyncio
    async def test_system_resilience_llm_failure(self):
        """Test system resilience when LLM service fails."""
        mock_db = AsyncMock()
        
        agent = Agent(
            id=uuid.uuid4(),
            name="TestAgent",
            description="Test agent for resilience testing",
            agent_type="test",
            version="1.0.0",
            status=AgentStatus.READY,
            capabilities=["chat"],
        )
        
        execution_engine = get_execution_engine(mock_db)
        
        context = ExecutionContext(
            task_id=str(uuid.uuid4()),
            agent_id=str(agent.id),
        )
        
        # Mock LLM failure
        with patch("ai_agent_platform.execution.engine.get_llm_manager") as mock_llm_mgr, \
             patch("ai_agent_platform.execution.engine.get_context_manager") as mock_ctx_mgr:
            
            # Mock LLM manager failure
            mock_llm_instance = AsyncMock()
            mock_llm_instance.chat_completion.side_effect = Exception("LLM service unavailable")
            mock_llm_mgr.return_value = mock_llm_instance
            
            # Mock context manager
            mock_memory = AsyncMock()
            mock_memory.get_conversation_history.return_value = []
            mock_ctx_manager.return_value.get_agent_memory.return_value = mock_memory
            
            result = await execution_engine.execute_chat_task(
                agent=agent,
                message="Hello!",
                context=context,
                use_rag=False,
            )
        
        assert result.status.value == "failed"
        assert "LLM service unavailable" in result.error_message
        assert result.execution_time_ms is not None  # Should still track execution time
    
    @pytest.mark.asyncio
    async def test_multi_agent_coordination(self):
        """Test coordination between multiple agents."""
        mock_db = AsyncMock()
        
        # Create different types of agents
        data_agent = Agent(
            id=uuid.uuid4(),
            name="DataProcessor",
            description="Agent for data processing",
            agent_type="data_processor",
            version="1.0.0",
            status=AgentStatus.READY,
            capabilities=["data_processing", "file_handling"],
        )
        
        analysis_agent = Agent(
            id=uuid.uuid4(),
            name="Analyst",
            description="Agent for analysis tasks",
            agent_type="analyst", 
            version="1.0.0",
            status=AgentStatus.READY,
            capabilities=["statistical_analysis", "reporting"],
        )
        
        execution_engine = get_execution_engine(mock_db)
        
        # Step 1: Data processing agent processes raw data
        data_context = ExecutionContext(
            task_id=str(uuid.uuid4()),
            agent_id=str(data_agent.id),
            session_id="multi_agent_session",
        )
        
        raw_data = {
            "file_path": "/data/sales.csv",
            "processing_type": "clean_and_format"
        }
        
        with patch("ai_agent_platform.execution.engine.UniversalToolRegistry") as mock_registry:
            mock_registry_instance = AsyncMock()
            mock_registry_instance.check_tool_access.return_value = True
            mock_registry.return_value = mock_registry_instance
            
            data_result = await execution_engine.execute_tool_task(
                agent=data_agent,
                task_type="file_processing",
                input_data=raw_data,
                context=data_context,
            )
        
        assert data_result.status.value == "completed"
        
        # Step 2: Analysis agent analyzes processed data
        analysis_context = ExecutionContext(
            task_id=str(uuid.uuid4()),
            agent_id=str(analysis_agent.id),
            session_id="multi_agent_session",  # Same session for coordination
        )
        
        analysis_input = {
            "processed_data_id": data_result.task_id,  # Reference to previous task
            "analysis_type": "trend_analysis",
            "report_format": "summary"
        }
        
        with patch("ai_agent_platform.execution.engine.UniversalToolRegistry") as mock_registry:
            mock_registry_instance = AsyncMock()
            mock_registry_instance.check_tool_access.return_value = True
            mock_registry.return_value = mock_registry_instance
            
            analysis_result = await execution_engine.execute_tool_task(
                agent=analysis_agent,
                task_type="data_analysis",
                input_data=analysis_input,
                context=analysis_context,
            )
        
        assert analysis_result.status.value == "completed"
        assert analysis_result.output_data["analysis_type"] == "data_analysis"
        
        # Both agents should have completed their tasks successfully
        assert data_result.execution_time_ms is not None
        assert analysis_result.execution_time_ms is not None
    
    @pytest.mark.asyncio
    async def test_knowledge_base_integration(self):
        """Test integration with knowledge base through RAG."""
        mock_db = AsyncMock()
        
        # Create knowledge-worker agent
        knowledge_agent = Agent(
            id=uuid.uuid4(),
            name="KnowledgeWorker",
            description="Agent that uses organizational knowledge",
            agent_type="knowledge_worker",
            version="1.0.0",
            status=AgentStatus.READY,
            capabilities=["research", "knowledge_retrieval", "synthesis"],
        )
        
        # Step 1: Add domain knowledge to RAG
        rag_system = get_rag_system()
        
        knowledge_documents = [
            "Company policy: All data analysis must follow GDPR compliance requirements.",
            "Best practice: Use statistical significance testing for all A/B test results.",
            "Procedure: Data visualization should include confidence intervals for accuracy.",
            "Standard: All reports must be reviewed by a senior analyst before publication."
        ]
        
        with patch.object(rag_system, 'add_text') as mock_add_text:
            mock_add_text.return_value = [f"kb_doc_{i}" for i in range(len(knowledge_documents))]
            
            for i, doc in enumerate(knowledge_documents):
                await rag_system.add_text(
                    text=doc,
                    metadata={"source": f"company_kb_{i+1}.txt", "type": "policy"},
                    collection_name="company_knowledge"
                )
        
        # Step 2: Agent queries knowledge base
        execution_engine = get_execution_engine(mock_db)
        
        context = ExecutionContext(
            task_id=str(uuid.uuid4()),
            agent_id=str(knowledge_agent.id),
        )
        
        # Mock RAG query for company policies
        mock_rag_response = {
            "answer": "According to company policy, all data analysis must follow GDPR compliance requirements and include statistical significance testing.",
            "sources": [
                {"source": "company_kb_1.txt", "content": "GDPR compliance requirements..."},
                {"source": "company_kb_2.txt", "content": "Statistical significance testing..."}
            ],
            "context_used": True,
            "num_sources": 2
        }
        
        mock_llm_response = "Based on our company policies, I can help you ensure your analysis follows GDPR compliance and includes proper statistical testing. What specific analysis do you need help with?"
        
        with patch.object(rag_system, 'query', return_value=mock_rag_response), \
             patch("ai_agent_platform.execution.engine.get_llm_manager") as mock_llm_mgr, \
             patch("ai_agent_platform.execution.engine.get_context_manager") as mock_ctx_mgr:
            
            # Mock LLM manager
            mock_llm_instance = AsyncMock()
            mock_llm_instance.chat_completion.return_value = mock_llm_response
            mock_llm_mgr.return_value = mock_llm_instance
            
            # Mock context manager
            mock_memory = AsyncMock()
            mock_memory.session_id = context.session_id
            mock_memory.get_conversation_history.return_value = []
            mock_ctx_manager.return_value.get_agent_memory.return_value = mock_memory
            
            result = await execution_engine.execute_chat_task(
                agent=knowledge_agent,
                message="What should I know about running data analysis in our company?",
                context=context,
                use_rag=True,
                rag_collection="company_knowledge"
            )
        
        assert result.status.value == "completed"
        assert "GDPR compliance" in result.output_data["response"]
        assert "statistical testing" in result.output_data["response"]
        assert result.output_data["context_used"] is True
        assert len(result.output_data["sources"]) == 2


if __name__ == "__main__":
    pytest.main([__file__])