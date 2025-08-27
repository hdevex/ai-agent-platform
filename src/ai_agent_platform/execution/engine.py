"""
Agent execution engine for task processing.
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.agent import Agent, AgentStatus
from ..llm.providers import get_llm_manager
from ..memory.context import get_context_manager
from ..rag.vector_store import get_rag_system
from ..tools.registry import UniversalToolRegistry

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionContext:
    """Execution context for agent tasks."""
    task_id: str
    agent_id: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class TaskResult:
    """Task execution result."""
    task_id: str
    status: TaskStatus
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    memory_used_mb: Optional[float] = None
    context_used: List[str] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)


class AgentExecutionEngine:
    """Central execution engine for agent tasks."""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.active_tasks: Dict[str, ExecutionContext] = {}
        self._task_lock = asyncio.Lock()
        
    async def execute_chat_task(
        self, 
        agent: Agent, 
        message: str,
        context: ExecutionContext,
        use_rag: bool = True,
        rag_collection: str = "default"
    ) -> TaskResult:
        """Execute a chat task with an agent."""
        start_time = time.time()
        
        try:
            # Register task
            await self._register_task(context)
            
            # Get required managers
            llm_manager = get_llm_manager()
            context_manager = get_context_manager()
            rag_system = get_rag_system()
            
            # Get or create agent memory
            agent_memory = context_manager.get_agent_memory(
                context.agent_id, context.session_id
            )
            
            # Prepare context and sources
            context_parts = []
            sources_used = []
            
            # Add RAG context if requested
            if use_rag:
                try:
                    rag_result = await rag_system.query(
                        message,
                        k=4,
                        collection_name=rag_collection,
                        include_sources=True,
                    )
                    
                    if rag_result["context_used"]:
                        context_parts.append(f"Relevant context:\n{rag_result['answer']}")
                        sources_used = rag_result["sources"]
                        
                except Exception as e:
                    logger.warning(f"RAG query failed: {e}")
            
            # Get conversation history
            history = await agent_memory.get_conversation_history()
            
            # Build messages for LLM
            messages = self._build_chat_messages(agent, message, history, context_parts)
            
            # Generate response
            response = await llm_manager.chat_completion(messages)
            
            # Store conversation in memory
            from langchain.schema import HumanMessage, AIMessage
            await agent_memory.add_message(HumanMessage(content=message))
            await agent_memory.add_message(AIMessage(content=response))
            
            # Save conversation turn
            await agent_memory.save_conversation_turn(
                user_message=message,
                agent_response=response,
                context_used=sources_used,
            )
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return TaskResult(
                task_id=context.task_id,
                status=TaskStatus.COMPLETED,
                output_data={
                    "response": response,
                    "sources": sources_used,
                    "context_used": len(context_parts) > 0,
                },
                execution_time_ms=execution_time,
                memory_used_mb=await self._estimate_memory_usage(agent_memory),
                context_used=[src.get("source", "") for src in sources_used],
            )
            
        except Exception as e:
            logger.error(f"Chat task execution failed: {e}")
            execution_time = int((time.time() - start_time) * 1000)
            
            return TaskResult(
                task_id=context.task_id,
                status=TaskStatus.FAILED,
                error_message=str(e),
                execution_time_ms=execution_time,
            )
            
        finally:
            await self._unregister_task(context.task_id)
    
    async def execute_tool_task(
        self,
        agent: Agent,
        task_type: str,
        input_data: Dict[str, Any],
        context: ExecutionContext,
    ) -> TaskResult:
        """Execute a tool-based task with an agent."""
        start_time = time.time()
        
        try:
            # Register task
            await self._register_task(context)
            
            # Get tool registry
            tool_registry = UniversalToolRegistry(self.db)
            await tool_registry.initialize()
            
            # Check if agent has access to required tools for this task
            required_tools = self._determine_required_tools(task_type, input_data)
            accessible_tools = []
            
            for tool_name in required_tools:
                has_access = await tool_registry.check_tool_access(
                    tool_name=tool_name,
                    agent_type=agent.agent_type,
                    security_clearance="public",  # TODO: Use agent's security clearance
                )
                if has_access:
                    accessible_tools.append(tool_name)
            
            if not accessible_tools:
                return TaskResult(
                    task_id=context.task_id,
                    status=TaskStatus.FAILED,
                    error_message=f"Agent does not have access to required tools: {required_tools}",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )
            
            # Execute task based on type
            if task_type == "data_analysis":
                result = await self._execute_data_analysis_task(input_data, accessible_tools)
            elif task_type == "content_generation":
                result = await self._execute_content_generation_task(agent, input_data)
            elif task_type == "code_review":
                result = await self._execute_code_review_task(input_data)
            else:
                # Generic task execution
                result = await self._execute_generic_task(agent, task_type, input_data)
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return TaskResult(
                task_id=context.task_id,
                status=TaskStatus.COMPLETED,
                output_data=result,
                execution_time_ms=execution_time,
                tools_used=accessible_tools,
            )
            
        except Exception as e:
            logger.error(f"Tool task execution failed: {e}")
            execution_time = int((time.time() - start_time) * 1000)
            
            return TaskResult(
                task_id=context.task_id,
                status=TaskStatus.FAILED,
                error_message=str(e),
                execution_time_ms=execution_time,
            )
            
        finally:
            await self._unregister_task(context.task_id)
    
    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get the current status of a task."""
        async with self._task_lock:
            context = self.active_tasks.get(task_id)
            return TaskStatus.RUNNING if context else None
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        async with self._task_lock:
            if task_id in self.active_tasks:
                # TODO: Implement actual task cancellation logic
                del self.active_tasks[task_id]
                logger.info(f"Task {task_id} cancelled")
                return True
            return False
    
    def _build_chat_messages(
        self, 
        agent: Agent, 
        message: str, 
        history: List[Any], 
        context_parts: List[str]
    ) -> List[Dict[str, str]]:
        """Build messages for LLM chat completion."""
        messages = []
        
        # System message with agent info
        system_content = f"""You are {agent.name}, a specialized AI agent.
Description: {agent.description}
Capabilities: {', '.join(agent.capabilities or [])}

You should respond helpfully and professionally, staying within your defined capabilities."""
        
        messages.append({"role": "system", "content": system_content})
        
        # Add conversation history (limited)
        for msg in history[-10:]:
            messages.append({
                "role": "user" if msg.type == "HumanMessage" else "assistant",
                "content": msg.content,
            })
        
        # Add RAG context if available
        if context_parts:
            context_message = {
                "role": "system",
                "content": "\n\n".join(context_parts),
            }
            messages.append(context_message)
        
        # Add current user message
        messages.append({"role": "user", "content": message})
        
        return messages
    
    def _determine_required_tools(self, task_type: str, input_data: Dict[str, Any]) -> List[str]:
        """Determine which tools are required for a task type."""
        tool_mapping = {
            "data_analysis": ["pandas_processor", "visualization_tool", "statistics_calculator"],
            "content_generation": ["text_generator", "template_engine"],
            "code_review": ["code_analyzer", "security_scanner", "linter"],
            "web_scraping": ["web_scraper", "html_parser"],
            "file_processing": ["file_processor", "document_parser"],
        }
        return tool_mapping.get(task_type, ["generic_processor"])
    
    async def _execute_data_analysis_task(
        self, input_data: Dict[str, Any], tools: List[str]
    ) -> Dict[str, Any]:
        """Execute a data analysis task."""
        # Placeholder implementation
        return {
            "analysis_type": "data_analysis",
            "input_processed": True,
            "tools_used": tools,
            "results": {
                "summary": "Data analysis completed successfully",
                "metrics": {"processed_records": len(input_data.get("data", []))},
            }
        }
    
    async def _execute_content_generation_task(
        self, agent: Agent, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a content generation task."""
        llm_manager = get_llm_manager()
        
        prompt = f"""As {agent.name}, generate content based on the following requirements:
        
Task: {input_data.get('task', 'Generate content')}
Requirements: {input_data.get('requirements', 'No specific requirements')}
Target audience: {input_data.get('audience', 'General audience')}
Tone: {input_data.get('tone', 'Professional')}
Length: {input_data.get('length', 'Medium')}

Please generate appropriate content that meets these requirements."""
        
        content = await llm_manager.completion(prompt)
        
        return {
            "task_type": "content_generation",
            "generated_content": content,
            "word_count": len(content.split()),
            "requirements_met": True,
        }
    
    async def _execute_code_review_task(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a code review task."""
        code = input_data.get("code", "")
        language = input_data.get("language", "python")
        
        # Placeholder implementation - would integrate with actual code analysis tools
        issues = []
        if "print(" in code:
            issues.append({
                "type": "style",
                "message": "Consider using logging instead of print statements",
                "line": 1,
                "severity": "low"
            })
        
        return {
            "task_type": "code_review",
            "language": language,
            "lines_reviewed": len(code.splitlines()),
            "issues_found": len(issues),
            "issues": issues,
            "overall_quality": "good" if len(issues) < 5 else "needs_improvement",
        }
    
    async def _execute_generic_task(
        self, agent: Agent, task_type: str, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a generic task using LLM."""
        llm_manager = get_llm_manager()
        
        prompt = f"""As {agent.name}, execute the following task:
        
Task Type: {task_type}
Input Data: {input_data}

Please process this task according to your capabilities and provide a structured response."""
        
        response = await llm_manager.completion(prompt)
        
        return {
            "task_type": task_type,
            "agent_response": response,
            "input_data_processed": True,
            "execution_method": "llm_processing",
        }
    
    async def _register_task(self, context: ExecutionContext):
        """Register a task as active."""
        async with self._task_lock:
            context.started_at = datetime.utcnow()
            self.active_tasks[context.task_id] = context
            logger.info(f"Task {context.task_id} registered for agent {context.agent_id}")
    
    async def _unregister_task(self, task_id: str):
        """Unregister a task."""
        async with self._task_lock:
            if task_id in self.active_tasks:
                context = self.active_tasks[task_id]
                context.completed_at = datetime.utcnow()
                del self.active_tasks[task_id]
                logger.info(f"Task {task_id} unregistered")
    
    async def _estimate_memory_usage(self, agent_memory) -> float:
        """Estimate memory usage for an agent."""
        # Placeholder implementation
        history = await agent_memory.get_conversation_history()
        return len(history) * 0.1  # Rough estimate: 0.1MB per message


# Singleton pattern for execution engine
_execution_engines: Dict[str, AgentExecutionEngine] = {}


def get_execution_engine(db_session: AsyncSession) -> AgentExecutionEngine:
    """Get or create an execution engine for a database session."""
    session_id = id(db_session)
    
    if session_id not in _execution_engines:
        _execution_engines[session_id] = AgentExecutionEngine(db_session)
    
    return _execution_engines[session_id]