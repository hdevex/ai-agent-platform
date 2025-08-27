"""
Universal Tool Registry with access controls and security.
"""

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from ..database.connection import AsyncSession
from ..models.agent import AgentType, ToolRegistry

logger = logging.getLogger(__name__)


class ToolCategory(str, Enum):
    """Tool categories for organization."""

    FILE_PROCESSOR = "file_processor"
    DATA_ANALYZER = "data_analyzer"
    GENERATOR = "generator"
    INTEGRATION = "integration"
    SECURITY = "security"
    UTILITY = "utility"


class ToolSecurityLevel(str, Enum):
    """Security levels for tools."""

    PUBLIC = "public"  # Available to all agents
    RESTRICTED = "restricted"  # Requires explicit permission
    INTERNAL = "internal"  # Platform internal use only
    CLASSIFIED = "classified"  # Highest security level


class ToolAccessError(Exception):
    """Exception raised when tool access is denied."""

    pass


class UniversalToolRegistry:
    """Registry for managing universal tools with security controls."""

    def __init__(self, db_session: AsyncSession):
        """Initialize tool registry."""
        self.db_session = db_session
        self._tool_cache: Dict[str, Any] = {}
        self._initialized = False

    async def initialize(self):
        """Initialize registry with built-in tools."""
        if self._initialized:
            return

        logger.info("🔧 Initializing Universal Tool Registry")

        # Register built-in tools
        await self._register_builtin_tools()

        self._initialized = True
        logger.info("✅ Tool Registry initialized")

    async def _register_builtin_tools(self):
        """Register built-in platform tools."""
        builtin_tools = [
            {
                "tool_name": "excel_reader",
                "tool_category": ToolCategory.FILE_PROCESSOR,
                "description": "Read and parse Excel files (xlsx, xls)",
                "version": "1.0.0",
                "tool_config": {
                    "supported_formats": ["xlsx", "xls", "csv"],
                    "max_file_size_mb": 50,
                    "max_rows": 100000,
                },
                "required_capabilities": ["file_processing"],
                "is_public": True,
                "security_level": ToolSecurityLevel.PUBLIC,
                "requires_approval": False,
            },
            {
                "tool_name": "pdf_analyzer",
                "tool_category": ToolCategory.FILE_PROCESSOR,
                "description": "Extract and analyze content from PDF files",
                "version": "1.0.0",
                "tool_config": {
                    "supported_formats": ["pdf"],
                    "max_file_size_mb": 100,
                    "extract_images": True,
                    "extract_tables": True,
                },
                "required_capabilities": ["file_processing", "text_extraction"],
                "is_public": True,
                "security_level": ToolSecurityLevel.PUBLIC,
                "requires_approval": False,
            },
            {
                "tool_name": "financial_calculator",
                "tool_category": ToolCategory.DATA_ANALYZER,
                "description": "Perform financial calculations and analysis",
                "version": "1.0.0",
                "tool_config": {
                    "supported_calculations": [
                        "variance_analysis",
                        "ratio_analysis",
                        "trend_analysis",
                        "budget_comparison",
                    ],
                    "precision": 4,
                    "currency_support": True,
                },
                "required_capabilities": [
                    "mathematical_operations",
                    "financial_analysis",
                ],
                "is_public": True,
                "security_level": ToolSecurityLevel.PUBLIC,
                "requires_approval": False,
            },
            {
                "tool_name": "report_generator",
                "tool_category": ToolCategory.GENERATOR,
                "description": "Generate various types of reports and documents",
                "version": "1.0.0",
                "tool_config": {
                    "output_formats": ["pdf", "docx", "html", "json"],
                    "template_support": True,
                    "chart_generation": True,
                },
                "required_capabilities": ["document_generation"],
                "is_public": True,
                "security_level": ToolSecurityLevel.PUBLIC,
                "requires_approval": False,
            },
            {
                "tool_name": "database_connector",
                "tool_category": ToolCategory.INTEGRATION,
                "description": "Connect to various databases securely",
                "version": "1.0.0",
                "tool_config": {
                    "supported_databases": ["postgresql", "mysql", "sqlite"],
                    "connection_pooling": True,
                    "query_timeout": 30,
                },
                "required_capabilities": ["database_access"],
                "is_public": False,
                "allowed_agent_types": [
                    AgentType.FINANCIAL_CALCULATOR,
                    AgentType.DATA_CONVERTER,
                ],
                "security_level": ToolSecurityLevel.RESTRICTED,
                "requires_approval": True,
            },
            {
                "tool_name": "api_client",
                "tool_category": ToolCategory.INTEGRATION,
                "description": "Make secure API calls to external services",
                "version": "1.0.0",
                "tool_config": {
                    "supported_protocols": ["http", "https"],
                    "timeout_seconds": 30,
                    "retry_attempts": 3,
                    "rate_limiting": True,
                },
                "required_capabilities": ["api_integration"],
                "is_public": False,
                "allowed_agent_types": [AgentType.CUSTOM],
                "security_level": ToolSecurityLevel.RESTRICTED,
                "requires_approval": True,
            },
        ]

        for tool_data in builtin_tools:
            await self._register_tool_if_not_exists(tool_data)

    async def _register_tool_if_not_exists(self, tool_data: Dict[str, Any]):
        """Register tool if it doesn't already exist."""
        from sqlalchemy import select

        result = await self.db_session.execute(
            select(ToolRegistry).where(ToolRegistry.tool_name == tool_data["tool_name"])
        )
        existing_tool = result.scalar_one_or_none()

        if not existing_tool:
            tool = ToolRegistry(**tool_data)
            self.db_session.add(tool)
            await self.db_session.commit()
            logger.info(f"📦 Registered tool: {tool_data['tool_name']}")

    async def get_available_tools(
        self,
        agent_type: Optional[str] = None,
        category: Optional[str] = None,
        security_clearance: str = "public",
    ) -> List[ToolRegistry]:
        """Get available tools based on agent type and security clearance."""
        from sqlalchemy import select

        query = select(ToolRegistry).where(ToolRegistry.is_deleted == False)

        # Filter by category
        if category:
            query = query.where(ToolRegistry.tool_category == category)

        # Apply security filtering
        if security_clearance == "public":
            query = query.where(
                ToolRegistry.is_public == True,
                ToolRegistry.security_level == ToolSecurityLevel.PUBLIC,
            )
        elif security_clearance == "restricted":
            query = query.where(
                ToolRegistry.security_level.in_(
                    [ToolSecurityLevel.PUBLIC, ToolSecurityLevel.RESTRICTED]
                )
            )

        # Filter by agent type if tool has restrictions
        if agent_type:
            # This would need more complex SQL - simplified for now
            pass

        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_tool(self, tool_name: str) -> Optional[ToolRegistry]:
        """Get specific tool by name."""
        from sqlalchemy import select

        result = await self.db_session.execute(
            select(ToolRegistry).where(
                ToolRegistry.tool_name == tool_name, ToolRegistry.is_deleted == False
            )
        )
        return result.scalar_one_or_none()

    async def check_tool_access(
        self, tool_name: str, agent_type: str, security_clearance: str = "public"
    ) -> bool:
        """Check if agent has access to specific tool."""
        tool = await self.get_tool(tool_name)
        if not tool:
            return False

        # Check public access
        if tool.is_public and tool.security_level == ToolSecurityLevel.PUBLIC:
            return True

        # Check security clearance
        security_levels = {
            "public": [ToolSecurityLevel.PUBLIC],
            "restricted": [ToolSecurityLevel.PUBLIC, ToolSecurityLevel.RESTRICTED],
            "internal": [
                ToolSecurityLevel.PUBLIC,
                ToolSecurityLevel.RESTRICTED,
                ToolSecurityLevel.INTERNAL,
            ],
        }

        allowed_levels = security_levels.get(
            security_clearance, [ToolSecurityLevel.PUBLIC]
        )
        if tool.security_level not in allowed_levels:
            return False

        # Check agent type restrictions
        if tool.allowed_agent_types and agent_type not in tool.allowed_agent_types:
            return False

        return True

    async def request_tool_access(
        self, tool_name: str, agent_id: str, justification: str
    ) -> Dict[str, Any]:
        """Request access to restricted tool."""
        tool = await self.get_tool(tool_name)
        if not tool:
            raise ToolAccessError(f"Tool not found: {tool_name}")

        if not tool.requires_approval:
            return {"status": "approved", "message": "Tool does not require approval"}

        # TODO: Implement approval workflow
        logger.info(f"🔐 Access requested for tool {tool_name} by agent {agent_id}")

        return {
            "status": "pending",
            "message": "Access request submitted for approval",
            "request_id": f"req_{tool_name}_{agent_id}",
            "estimated_approval_time": "24 hours",
        }

    def get_tool_implementation(self, tool_name: str) -> Optional[Any]:
        """Get actual tool implementation (cached)."""
        if tool_name in self._tool_cache:
            return self._tool_cache[tool_name]

        # TODO: Implement dynamic tool loading
        # This would load the actual tool implementation
        # based on the tool configuration

        return None

    async def register_custom_tool(
        self, tool_data: Dict[str, Any], created_by: Optional[str] = None
    ) -> ToolRegistry:
        """Register a new custom tool."""
        # Validate tool data
        required_fields = ["tool_name", "tool_category", "description", "version"]
        for field in required_fields:
            if field not in tool_data:
                raise ValueError(f"Missing required field: {field}")

        # Security validation
        if "security_level" not in tool_data:
            tool_data["security_level"] = ToolSecurityLevel.RESTRICTED

        if "requires_approval" not in tool_data:
            tool_data["requires_approval"] = True

        # Create tool record
        tool = ToolRegistry(**tool_data, created_by=created_by)
        self.db_session.add(tool)
        await self.db_session.commit()
        await self.db_session.refresh(tool)

        logger.info(f"🆕 Custom tool registered: {tool_data['tool_name']}")
        return tool


# Global tool registry instance (will be initialized with database session)
_tool_registry: Optional[UniversalToolRegistry] = None


def get_tool_registry() -> Optional[UniversalToolRegistry]:
    """Get global tool registry instance."""
    return _tool_registry


def set_tool_registry(registry: UniversalToolRegistry):
    """Set global tool registry instance."""
    global _tool_registry
    _tool_registry = registry
