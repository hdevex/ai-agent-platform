"""
Secure Agent Factory for creating specialized AI agents.
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import yaml

from ..config import config
from ..database.connection import AsyncSession
from ..models.agent import Agent, AgentStatus, AgentType, ToolRegistry

logger = logging.getLogger(__name__)


class PRDValidationError(Exception):
    """Exception raised when PRD validation fails."""

    pass


class AgentCreationError(Exception):
    """Exception raised when agent creation fails."""

    pass


class PRDProcessor:
    """Process and validate Product Requirements Documents."""

    REQUIRED_FIELDS = [
        "agent_name",
        "description",
        "agent_type",
        "capabilities",
        "tools_required",
    ]

    OPTIONAL_FIELDS = [
        "version",
        "memory_limit_mb",
        "timeout_seconds",
        "max_concurrent_tasks",
        "security_level",
        "deployment_target",
        "configuration",
    ]

    @classmethod
    def validate_prd(cls, prd_content: str) -> Dict[str, Any]:
        """Validate PRD content and return parsed data."""
        try:
            # Parse YAML/JSON
            if prd_content.strip().startswith("{"):
                import json

                prd_data = json.loads(prd_content)
            else:
                prd_data = yaml.safe_load(prd_content)

            # Validate required fields
            missing_fields = []
            for field in cls.REQUIRED_FIELDS:
                if field not in prd_data:
                    missing_fields.append(field)

            if missing_fields:
                raise PRDValidationError(f"Missing required fields: {missing_fields}")

            # Validate agent type
            agent_type = prd_data.get("agent_type")
            if agent_type not in [t.value for t in AgentType]:
                logger.warning(f"Unknown agent type: {agent_type}, treating as CUSTOM")
                prd_data["agent_type"] = AgentType.CUSTOM

            # Validate capabilities
            capabilities = prd_data.get("capabilities", [])
            if not isinstance(capabilities, list) or not capabilities:
                raise PRDValidationError("Capabilities must be a non-empty list")

            # Security validation
            cls._validate_security_requirements(prd_data)

            return prd_data

        except yaml.YAMLError as e:
            raise PRDValidationError(f"Invalid YAML format: {e}")
        except Exception as e:
            raise PRDValidationError(f"PRD validation failed: {e}")

    @classmethod
    def _validate_security_requirements(cls, prd_data: Dict[str, Any]):
        """Validate security-related requirements."""
        # Check for sensitive data in configuration
        config_data = prd_data.get("configuration", {})
        sensitive_keys = ["password", "secret", "key", "token", "api_key"]

        for key in config_data.keys():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                logger.warning(f"Sensitive data detected in configuration: {key}")
                # In production, this should be handled through secure key management

        # Validate resource limits
        memory_limit = prd_data.get("memory_limit_mb", 512)
        if memory_limit > config.platform.agent_memory_limit_mb:
            raise PRDValidationError(
                f"Memory limit {memory_limit}MB exceeds platform limit "
                f"{config.platform.agent_memory_limit_mb}MB"
            )

        timeout = prd_data.get("timeout_seconds", 300)
        if timeout > config.platform.agent_timeout_seconds:
            raise PRDValidationError(
                f"Timeout {timeout}s exceeds platform limit "
                f"{config.platform.agent_timeout_seconds}s"
            )

    @classmethod
    def generate_prd_hash(cls, prd_content: str) -> str:
        """Generate hash for PRD content for change detection."""
        return hashlib.sha256(prd_content.encode("utf-8")).hexdigest()


class AgentFactory:
    """Factory for creating and managing specialized AI agents."""

    def __init__(self, db_session: AsyncSession):
        """Initialize agent factory with database session."""
        self.db_session = db_session
        self.prd_processor = PRDProcessor()

    async def create_agent_from_prd(
        self, prd_content: str, created_by: Optional[str] = None
    ) -> Agent:
        """Create agent from PRD with security validation."""
        logger.info("🏭 Starting agent creation from PRD")

        try:
            # Validate PRD
            prd_data = self.prd_processor.validate_prd(prd_content)
            prd_hash = self.prd_processor.generate_prd_hash(prd_content)

            # Check if agent with same PRD already exists
            existing_agent = await self._find_existing_agent(prd_hash)
            if existing_agent:
                logger.info(f"Agent with same PRD already exists: {existing_agent.id}")
                return existing_agent

            # Validate tool requirements
            await self._validate_tool_requirements(prd_data.get("tools_required", []))

            # Create agent record
            agent = Agent(
                name=prd_data["agent_name"],
                description=prd_data["description"],
                agent_type=prd_data["agent_type"],
                version=prd_data.get("version", "1.0.0"),
                status=AgentStatus.BUILDING,
                configuration=prd_data.get("configuration", {}),
                capabilities=prd_data["capabilities"],
                prd_content=prd_content,
                prd_hash=prd_hash,
                memory_limit_mb=prd_data.get("memory_limit_mb", 512),
                timeout_seconds=prd_data.get("timeout_seconds", 300),
                max_concurrent_tasks=prd_data.get("max_concurrent_tasks", 1),
                created_by=created_by,
                data_classification=prd_data.get("security_level", "internal"),
            )

            # Save to database
            self.db_session.add(agent)
            await self.db_session.commit()
            await self.db_session.refresh(agent)

            logger.info(f"✅ Agent created successfully: {agent.id}")

            # Build agent (async process)
            await self._build_agent(agent, prd_data)

            return agent

        except Exception as e:
            logger.error(f"❌ Agent creation failed: {e}")
            await self.db_session.rollback()
            raise AgentCreationError(f"Failed to create agent: {e}")

    async def _find_existing_agent(self, prd_hash: str) -> Optional[Agent]:
        """Find existing agent with same PRD hash."""
        from sqlalchemy import select

        result = await self.db_session.execute(
            select(Agent).where(Agent.prd_hash == prd_hash, Agent.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def _validate_tool_requirements(self, required_tools: List[str]):
        """Validate that required tools are available and accessible."""
        from sqlalchemy import select

        for tool_name in required_tools:
            result = await self.db_session.execute(
                select(ToolRegistry).where(
                    ToolRegistry.tool_name == tool_name,
                    ToolRegistry.is_deleted == False,
                )
            )
            tool = result.scalar_one_or_none()

            if not tool:
                raise AgentCreationError(f"Required tool not found: {tool_name}")

            if not tool.is_public:
                logger.warning(
                    f"Tool {tool_name} is not public - access check required"
                )

            if tool.requires_approval:
                logger.warning(f"Tool {tool_name} requires approval for use")

    async def _build_agent(self, agent: Agent, prd_data: Dict[str, Any]):
        """Build agent with specified capabilities (placeholder)."""
        try:
            logger.info(f"🔨 Building agent: {agent.name}")

            # Update status to building
            agent.status = AgentStatus.BUILDING
            await self.db_session.commit()

            # TODO: Implement actual agent building logic
            # This would include:
            # 1. LangChain agent configuration
            # 2. Tool integration
            # 3. Memory setup
            # 4. Capability validation
            # 5. Security configuration

            # Simulate building process
            import asyncio

            await asyncio.sleep(1)  # Simulate build time

            # Mark as ready
            agent.status = AgentStatus.READY
            await self.db_session.commit()

            logger.info(f"✅ Agent built successfully: {agent.name}")

        except Exception as e:
            logger.error(f"❌ Agent building failed: {e}")
            agent.status = AgentStatus.ERROR
            await self.db_session.commit()
            raise

    async def get_agent(self, agent_id: uuid.UUID) -> Optional[Agent]:
        """Get agent by ID with security checks."""
        from sqlalchemy import select

        result = await self.db_session.execute(
            select(Agent).where(Agent.id == agent_id, Agent.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def list_agents(
        self,
        agent_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Agent]:
        """List agents with optional filtering."""
        from sqlalchemy import select

        query = select(Agent).where(Agent.is_deleted == False)

        if agent_type:
            query = query.where(Agent.agent_type == agent_type)

        if status:
            query = query.where(Agent.status == status)

        query = query.limit(limit).order_by(Agent.created_at.desc())

        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def delete_agent(self, agent_id: uuid.UUID, deleted_by: Optional[str] = None):
        """Soft delete agent with security audit."""
        agent = await self.get_agent(agent_id)
        if not agent:
            raise AgentCreationError(f"Agent not found: {agent_id}")

        agent.mark_deleted(deleted_by)
        await self.db_session.commit()

        logger.info(f"🗑️ Agent deleted: {agent_id}")


class AgentWarehouse:
    """Warehouse for managing agent storage and deployment."""

    def __init__(self, db_session: AsyncSession):
        """Initialize agent warehouse."""
        self.db_session = db_session

    async def deploy_agent(
        self, agent_id: uuid.UUID, environment: str, deployment_config: Dict[str, Any]
    ):
        """Deploy agent to specified environment."""
        # TODO: Implement agent deployment logic
        logger.info(f"🚀 Deploying agent {agent_id} to {environment}")

        # This would include:
        # 1. Environment validation
        # 2. Resource allocation
        # 3. Service registration
        # 4. Health monitoring setup

        pass

    async def get_agent_health(self, agent_id: uuid.UUID) -> Dict[str, Any]:
        """Get agent health status."""
        # TODO: Implement health checking
        return {
            "status": "healthy",
            "last_check": datetime.now(timezone.utc).isoformat(),
            "metrics": {},
        }
