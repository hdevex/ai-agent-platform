"""
Agent-related database models.
"""

from enum import Enum
from typing import Any, Dict

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import BaseModel, SecureDataMixin


class AgentStatus(str, Enum):
    """Agent status enumeration."""

    CREATED = "created"
    BUILDING = "building"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    TERMINATED = "terminated"


class AgentType(str, Enum):
    """Agent type enumeration."""

    EXCEL_PROCESSOR = "excel_processor"
    PDF_ANALYZER = "pdf_analyzer"
    DOCUMENT_GENERATOR = "document_generator"
    FINANCIAL_CALCULATOR = "financial_calculator"
    DATA_CONVERTER = "data_converter"
    CUSTOM = "custom"


class Agent(BaseModel, SecureDataMixin):
    """Agent model with security features."""

    __tablename__ = "agents"

    # Basic Information
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    agent_type = Column(String(50), nullable=False, index=True)
    version = Column(String(50), default="1.0.0", nullable=False)

    # Status and Configuration
    status = Column(String(20), default=AgentStatus.CREATED, nullable=False, index=True)
    configuration = Column(JSON, nullable=True)
    capabilities = Column(JSON, nullable=True)  # List of capabilities

    # PRD Information
    prd_content = Column(Text, nullable=True)  # Original PRD content
    prd_hash = Column(String(64), nullable=True, index=True)  # PRD content hash

    # Resource Limits
    memory_limit_mb = Column(Integer, default=512, nullable=False, server_default="512")
    timeout_seconds = Column(Integer, default=300, nullable=False, server_default="300")
    max_concurrent_tasks = Column(
        Integer, default=1, nullable=False, server_default="1"
    )

    # Relationships
    tasks = relationship(
        "AgentTask", back_populates="agent", cascade="all, delete-orphan"
    )
    deployments = relationship("AgentDeployment", back_populates="agent")

    # Indexes for performance
    __table_args__ = (
        Index("ix_agent_type_status", "agent_type", "status"),
        Index("ix_agent_created_status", "created_at", "status"),
    )

    def can_execute_task(self) -> bool:
        """Check if agent can execute new tasks."""
        return (
            self.status in [AgentStatus.READY, AgentStatus.RUNNING]
            and not self.is_deleted
        )

    def get_safe_configuration(self) -> Dict[str, Any]:
        """Get configuration without sensitive data."""
        if not self.configuration:
            return {}

        # Remove sensitive keys
        safe_config = self.configuration.copy()
        sensitive_keys = ["api_keys", "passwords", "secrets", "tokens"]

        for key in sensitive_keys:
            safe_config.pop(key, None)

        return safe_config


class AgentTask(BaseModel):
    """Agent task execution model."""

    __tablename__ = "agent_tasks"

    # Task Information
    agent_id = Column(
        UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True
    )
    task_type = Column(String(100), nullable=False, index=True)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)

    # Execution Details
    status = Column(String(20), default="pending", nullable=False, index=True)
    started_at = Column(String, nullable=True)  # ISO timestamp
    completed_at = Column(String, nullable=True)  # ISO timestamp
    error_message = Column(Text, nullable=True)

    # Performance Metrics
    execution_time_ms = Column(Integer, nullable=True)
    memory_used_mb = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)

    # Relationships
    agent = relationship("Agent", back_populates="tasks")

    # Indexes
    __table_args__ = (
        Index("ix_task_agent_status", "agent_id", "status"),
        Index("ix_task_created_status", "created_at", "status"),
    )


class AgentDeployment(BaseModel):
    """Agent deployment tracking."""

    __tablename__ = "agent_deployments"

    # Deployment Information
    agent_id = Column(
        UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True
    )
    deployment_name = Column(String(255), nullable=False)
    environment = Column(String(50), nullable=False)  # development, staging, production

    # Deployment Configuration
    endpoint_url = Column(String(500), nullable=True)
    api_key = Column(String(255), nullable=True)  # For accessing deployed agent

    # Status
    status = Column(String(20), default="pending", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Health Monitoring
    last_health_check = Column(String, nullable=True)  # ISO timestamp
    health_status = Column(String(20), default="unknown", nullable=False)

    # Relationships
    agent = relationship("Agent", back_populates="deployments")

    # Indexes
    __table_args__ = (
        Index("ix_deployment_agent_env", "agent_id", "environment"),
        Index("ix_deployment_active", "is_active", "status"),
    )


class ToolRegistry(BaseModel):
    """Universal tool registry."""

    __tablename__ = "tool_registry"

    # Tool Information
    tool_name = Column(String(255), nullable=False, unique=True, index=True)
    tool_category = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    version = Column(String(50), default="1.0.0", nullable=False)

    # Tool Configuration
    tool_config = Column(JSON, nullable=True)
    required_capabilities = Column(JSON, nullable=True)  # List of required capabilities

    # Access Control
    is_public = Column(Boolean, default=True, nullable=False)
    allowed_agent_types = Column(JSON, nullable=True)  # Allowed agent types

    # Security Classification
    security_level = Column(
        String(20), default="standard", nullable=False
    )  # standard, restricted
    requires_approval = Column(Boolean, default=False, nullable=False)

    # Indexes
    __table_args__ = (
        Index("ix_tool_category_public", "tool_category", "is_public"),
        Index("ix_tool_security", "security_level", "requires_approval"),
    )
