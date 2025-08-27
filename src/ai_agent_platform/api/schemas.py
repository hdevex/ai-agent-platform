"""
Pydantic schemas for API requests and responses.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
import uuid
from datetime import datetime


# Agent Management Schemas
class AgentCreateRequest(BaseModel):
    """Request schema for creating an agent."""
    prd_content: str = Field(..., description="Product Requirements Document content")
    created_by: Optional[str] = Field(None, description="User who created the agent")


class AgentResponse(BaseModel):
    """Response schema for agent information."""
    id: str
    name: str
    description: Optional[str]
    agent_type: str
    version: str
    status: str
    capabilities: Optional[List[str]]
    memory_limit_mb: int
    timeout_seconds: int
    max_concurrent_tasks: int
    created_at: str
    updated_at: str
    can_execute: bool


class AgentListResponse(BaseModel):
    """Response schema for agent list."""
    agents: List[AgentResponse]
    total_count: int
    page: int
    page_size: int


# Agent Execution Schemas
class ChatMessage(BaseModel):
    """Chat message schema."""
    role: str = Field(..., description="Message role: user, assistant, system")
    content: str = Field(..., description="Message content")


class AgentChatRequest(BaseModel):
    """Request schema for agent chat."""
    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    use_rag: bool = Field(True, description="Whether to use RAG for context retrieval")
    rag_collection: str = Field("default", description="RAG collection to search")


class AgentChatResponse(BaseModel):
    """Response schema for agent chat."""
    response: str = Field(..., description="Agent response")
    session_id: str = Field(..., description="Session ID")
    sources: Optional[List[Dict[str, Any]]] = Field(None, description="RAG sources used")
    context_used: bool = Field(False, description="Whether additional context was used")
    execution_time_ms: int = Field(..., description="Response generation time")


class AgentTaskRequest(BaseModel):
    """Request schema for agent task execution."""
    task_type: str = Field(..., description="Type of task to execute")
    input_data: Dict[str, Any] = Field(..., description="Task input data")
    session_id: Optional[str] = Field(None, description="Session ID")
    timeout_seconds: Optional[int] = Field(None, description="Task timeout override")


class AgentTaskResponse(BaseModel):
    """Response schema for agent task execution."""
    task_id: str
    status: str
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    execution_time_ms: Optional[int]
    memory_used_mb: Optional[int]
    started_at: str
    completed_at: Optional[str]


# RAG Schemas
class RAGAddTextRequest(BaseModel):
    """Request schema for adding text to RAG."""
    text: str = Field(..., description="Text to add")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Text metadata")
    collection_name: str = Field("default", description="Collection to add to")


class RAGAddFileRequest(BaseModel):
    """Request schema for adding file to RAG."""
    file_path: str = Field(..., description="Path to file")
    metadata: Optional[Dict[str, Any]] = Field(None, description="File metadata")
    collection_name: str = Field("default", description="Collection to add to")


class RAGQueryRequest(BaseModel):
    """Request schema for RAG query."""
    question: str = Field(..., description="Question to ask")
    k: int = Field(4, description="Number of relevant documents to retrieve")
    collection_name: str = Field("default", description="Collection to search")
    include_sources: bool = Field(True, description="Whether to include source information")


class RAGQueryResponse(BaseModel):
    """Response schema for RAG query."""
    answer: str
    sources: List[Dict[str, Any]]
    context_used: bool
    num_sources: int


class RAGAddResponse(BaseModel):
    """Response schema for RAG add operations."""
    document_ids: List[str]
    chunks_created: int
    collection_name: str


# Tool Registry Schemas
class ToolResponse(BaseModel):
    """Response schema for tool information."""
    tool_name: str
    tool_category: str
    description: Optional[str]
    version: str
    is_public: bool
    security_level: str
    requires_approval: bool
    tool_config: Optional[Dict[str, Any]]


class ToolListResponse(BaseModel):
    """Response schema for tool list."""
    tools: List[ToolResponse]
    total_count: int


# Health Check Schemas
class HealthResponse(BaseModel):
    """Response schema for health checks."""
    status: str
    timestamp: float
    components: Optional[Dict[str, Any]]


class DetailedHealthResponse(BaseModel):
    """Response schema for detailed health checks."""
    status: str
    platform: Dict[str, str]
    services: Dict[str, Any]
    configuration: Dict[str, Any]
    timestamp: float


# Error Response Schema
class ErrorResponse(BaseModel):
    """Response schema for errors."""
    error: str
    detail: Optional[str]
    error_code: Optional[str]
    timestamp: str


# Generic Response Schemas
class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None


class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=100, description="Items per page")


class FilterParams(BaseModel):
    """Filter parameters for listings."""
    agent_type: Optional[str] = Field(None, description="Filter by agent type")
    status: Optional[str] = Field(None, description="Filter by status")
    search: Optional[str] = Field(None, description="Search query")


# WebSocket Schemas
class WSMessage(BaseModel):
    """WebSocket message schema."""
    type: str = Field(..., description="Message type")
    data: Dict[str, Any] = Field(..., description="Message data")
    session_id: Optional[str] = Field(None, description="Session ID")


class WSResponse(BaseModel):
    """WebSocket response schema."""
    type: str
    data: Dict[str, Any]
    timestamp: str
    session_id: Optional[str] = None