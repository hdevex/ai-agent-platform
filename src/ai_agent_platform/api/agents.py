"""
Agent management API endpoints.
"""

import logging
import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.connection import get_db_session
from ..core.agent_factory import AgentFactory, AgentCreationError, PRDValidationError
from ..models.agent import Agent, AgentStatus
from ..execution.engine import get_execution_engine, ExecutionContext
from .schemas import (
    AgentCreateRequest,
    AgentResponse,
    AgentListResponse,
    AgentChatRequest,
    AgentChatResponse,
    AgentTaskRequest,
    AgentTaskResponse,
    PaginationParams,
    FilterParams,
    SuccessResponse,
    ErrorResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


def agent_to_response(agent: Agent) -> AgentResponse:
    """Convert Agent model to response schema."""
    return AgentResponse(
        id=str(agent.id),
        name=agent.name,
        description=agent.description,
        agent_type=agent.agent_type,
        version=agent.version,
        status=agent.status,
        capabilities=agent.capabilities,
        memory_limit_mb=agent.memory_limit_mb,
        timeout_seconds=agent.timeout_seconds,
        max_concurrent_tasks=agent.max_concurrent_tasks,
        created_at=agent.created_at.isoformat(),
        updated_at=agent.updated_at.isoformat(),
        can_execute=agent.can_execute_task(),
    )


@router.post("/", response_model=AgentResponse)
async def create_agent(
    request: AgentCreateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new agent from PRD."""
    try:
        logger.info(f"🏭 Creating agent from PRD")
        
        factory = AgentFactory(db)
        agent = await factory.create_agent_from_prd(
            prd_content=request.prd_content,
            created_by=request.created_by,
        )
        
        logger.info(f"✅ Agent created: {agent.id}")
        return agent_to_response(agent)
        
    except PRDValidationError as e:
        logger.error(f"❌ PRD validation failed: {e}")
        raise HTTPException(status_code=400, detail=f"PRD validation failed: {e}")
        
    except AgentCreationError as e:
        logger.error(f"❌ Agent creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Agent creation failed: {e}")
        
    except Exception as e:
        logger.error(f"❌ Unexpected error creating agent: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=AgentListResponse)
async def list_agents(
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: AsyncSession = Depends(get_db_session),
):
    """List agents with pagination and filtering."""
    try:
        factory = AgentFactory(db)
        
        agents = await factory.list_agents(
            agent_type=filters.agent_type,
            status=filters.status,
            limit=pagination.page_size,
        )
        
        # Convert to response format
        agent_responses = [agent_to_response(agent) for agent in agents]
        
        return AgentListResponse(
            agents=agent_responses,
            total_count=len(agent_responses),  # Simplified - in production, use separate count query
            page=pagination.page,
            page_size=pagination.page_size,
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to list agents: {e}")
        raise HTTPException(status_code=500, detail="Failed to list agents")


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Get agent by ID."""
    try:
        factory = AgentFactory(db)
        agent = await factory.get_agent(uuid.UUID(agent_id))
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        return agent_to_response(agent)
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid agent ID format")
        
    except Exception as e:
        logger.error(f"❌ Failed to get agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agent")


@router.delete("/{agent_id}", response_model=SuccessResponse)
async def delete_agent(
    agent_id: str,
    deleted_by: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_session),
):
    """Delete agent (soft delete)."""
    try:
        factory = AgentFactory(db)
        await factory.delete_agent(uuid.UUID(agent_id), deleted_by)
        
        return SuccessResponse(message="Agent deleted successfully")
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid agent ID format")
        
    except Exception as e:
        logger.error(f"❌ Failed to delete agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete agent")


@router.post("/{agent_id}/chat", response_model=AgentChatResponse)
async def chat_with_agent(
    agent_id: str,
    request: AgentChatRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Chat with an agent using the execution engine."""
    try:
        # Get agent
        factory = AgentFactory(db)
        agent = await factory.get_agent(uuid.UUID(agent_id))
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        if not agent.can_execute_task():
            raise HTTPException(status_code=400, detail="Agent cannot execute tasks")
        
        # Create execution context
        context = ExecutionContext(
            task_id=str(uuid.uuid4()),
            agent_id=agent_id,
            session_id=request.session_id,
            metadata=request.context or {},
        )
        
        # Get execution engine and execute chat task
        execution_engine = get_execution_engine(db)
        result = await execution_engine.execute_chat_task(
            agent=agent,
            message=request.message,
            context=context,
            use_rag=request.use_rag,
            rag_collection=request.rag_collection,
        )
        
        if result.status.value == "failed":
            raise HTTPException(status_code=500, detail=result.error_message)
        
        return AgentChatResponse(
            response=result.output_data["response"],
            session_id=request.session_id or str(uuid.uuid4()),
            sources=result.output_data.get("sources"),
            context_used=result.output_data.get("context_used", False),
            execution_time_ms=result.execution_time_ms,
        )
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid agent ID format")
        
    except Exception as e:
        logger.error(f"❌ Chat with agent failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/{agent_id}/tasks", response_model=AgentTaskResponse)
async def execute_agent_task(
    agent_id: str,
    request: AgentTaskRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Execute a task with an agent using the execution engine."""
    try:
        # Get agent
        factory = AgentFactory(db)
        agent = await factory.get_agent(uuid.UUID(agent_id))
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        if not agent.can_execute_task():
            raise HTTPException(status_code=400, detail="Agent cannot execute tasks")
        
        # Create execution context
        context = ExecutionContext(
            task_id=str(uuid.uuid4()),
            agent_id=agent_id,
            session_id=request.session_id,
            metadata={"timeout_override": request.timeout_seconds},
        )
        
        # Get execution engine and execute task
        execution_engine = get_execution_engine(db)
        result = await execution_engine.execute_tool_task(
            agent=agent,
            task_type=request.task_type,
            input_data=request.input_data,
            context=context,
        )
        
        return AgentTaskResponse(
            task_id=result.task_id,
            status=result.status.value,
            output_data=result.output_data,
            error_message=result.error_message,
            execution_time_ms=result.execution_time_ms,
            memory_used_mb=result.memory_used_mb,
            started_at=str(context.started_at.timestamp()) if context.started_at else str(time.time()),
            completed_at=str(context.completed_at.timestamp()) if context.completed_at else None,
        )
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid agent ID format")
        
    except Exception as e:
        logger.error(f"❌ Task execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Task execution failed: {str(e)}")


@router.get("/{agent_id}/health", response_model=dict)
async def get_agent_health(
    agent_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Get agent health status."""
    try:
        factory = AgentFactory(db)
        agent = await factory.get_agent(uuid.UUID(agent_id))
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        return {
            "agent_id": str(agent.id),
            "name": agent.name,
            "status": agent.status,
            "can_execute": agent.can_execute_task(),
            "health": "healthy" if agent.status == AgentStatus.READY else "degraded",
            "last_updated": agent.updated_at.isoformat(),
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid agent ID format")
        
    except Exception as e:
        logger.error(f"❌ Failed to get agent health: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agent health")