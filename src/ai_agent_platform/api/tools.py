"""
Tool registry API endpoints.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.connection import get_db_session
from ..tools.registry import UniversalToolRegistry
from .schemas import (
    ToolResponse,
    ToolListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["tools"])


def tool_to_response(tool) -> ToolResponse:
    """Convert tool model to response schema."""
    return ToolResponse(
        tool_name=tool.tool_name,
        tool_category=tool.tool_category,
        description=tool.description,
        version=tool.version,
        is_public=tool.is_public,
        security_level=tool.security_level,
        requires_approval=tool.requires_approval,
        tool_config=tool.tool_config,
    )


@router.get("/", response_model=ToolListResponse)
async def list_tools(
    category: Optional[str] = Query(None),
    security_clearance: str = Query("public"),
    db: AsyncSession = Depends(get_db_session),
):
    """List available tools."""
    try:
        registry = UniversalToolRegistry(db)
        await registry.initialize()
        
        tools = await registry.get_available_tools(
            category=category,
            security_clearance=security_clearance,
        )
        
        tool_responses = [tool_to_response(tool) for tool in tools]
        
        return ToolListResponse(
            tools=tool_responses,
            total_count=len(tool_responses),
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to list tools: {e}")
        raise HTTPException(status_code=500, detail="Failed to list tools")


@router.get("/{tool_name}", response_model=ToolResponse)
async def get_tool(
    tool_name: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Get tool by name."""
    try:
        registry = UniversalToolRegistry(db)
        await registry.initialize()
        
        tool = await registry.get_tool(tool_name)
        
        if not tool:
            raise HTTPException(status_code=404, detail="Tool not found")
        
        return tool_to_response(tool)
        
    except Exception as e:
        logger.error(f"❌ Failed to get tool: {e}")
        raise HTTPException(status_code=500, detail="Failed to get tool")


@router.post("/{tool_name}/request-access", response_model=dict)
async def request_tool_access(
    tool_name: str,
    agent_id: str = Query(...),
    justification: str = Query(...),
    db: AsyncSession = Depends(get_db_session),
):
    """Request access to a restricted tool."""
    try:
        registry = UniversalToolRegistry(db)
        await registry.initialize()
        
        result = await registry.request_tool_access(
            tool_name=tool_name,
            agent_id=agent_id,
            justification=justification,
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Failed to request tool access: {e}")
        raise HTTPException(status_code=500, detail="Failed to request access")


@router.get("/{tool_name}/check-access", response_model=dict)
async def check_tool_access(
    tool_name: str,
    agent_type: str = Query(...),
    security_clearance: str = Query("public"),
    db: AsyncSession = Depends(get_db_session),
):
    """Check if agent has access to tool."""
    try:
        registry = UniversalToolRegistry(db)
        await registry.initialize()
        
        has_access = await registry.check_tool_access(
            tool_name=tool_name,
            agent_type=agent_type,
            security_clearance=security_clearance,
        )
        
        return {
            "tool_name": tool_name,
            "agent_type": agent_type,
            "has_access": has_access,
            "security_clearance": security_clearance,
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to check tool access: {e}")
        raise HTTPException(status_code=500, detail="Failed to check access")