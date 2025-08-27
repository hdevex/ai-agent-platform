"""Tests for database models."""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_agent_platform.models.agent import (
    Agent,
    AgentStatus,
    AgentTask,
    AgentType,
    ToolRegistry,
)
from ai_agent_platform.models.base import (
    AuditMixin,
    TimestampMixin,
    UUIDMixin,
)


class TestTimestampMixin:
    """Test timestamp mixin functionality."""

    def test_timestamp_fields(self):
        """Test that timestamp fields are properly configured."""

        # Create a mock model class for testing
        class TestModel(TimestampMixin):
            pass

        model = TestModel()

        # Check that fields exist
        assert hasattr(model, "created_at")
        assert hasattr(model, "updated_at")


class TestUUIDMixin:
    """Test UUID mixin functionality."""

    def test_uuid_generation(self):
        """Test UUID generation."""

        class TestModel(UUIDMixin):
            pass

        model = TestModel()
        assert hasattr(model, "id")


class TestAuditMixin:
    """Test audit mixin functionality."""

    def test_audit_fields(self):
        """Test audit fields."""

        class TestModel(AuditMixin):
            pass

        model = TestModel()

        # Check audit fields exist
        assert hasattr(model, "created_by")
        assert hasattr(model, "updated_by")
        assert hasattr(model, "is_deleted")
        assert hasattr(model, "deleted_at")
        assert hasattr(model, "deleted_by")
        assert hasattr(model, "version")

    def test_mark_deleted(self):
        """Test soft delete functionality."""

        class TestModel(AuditMixin):
            def __init__(self):
                self.is_deleted = False
                self.deleted_at = None
                self.deleted_by = None

        model = TestModel()
        model.mark_deleted("test_user")

        assert model.is_deleted is True
        assert model.deleted_at is not None
        assert model.deleted_by == "test_user"

    def test_update_version(self):
        """Test version updating."""

        class TestModel(AuditMixin):
            def __init__(self):
                self.id = uuid.uuid4()
                self.version = "1"

        model = TestModel()
        original_version = model.version
        model.update_version()

        assert model.version != original_version
        assert len(model.version) == 16


class TestAgentModel:
    """Test Agent model."""

    def test_agent_creation(self):
        """Test agent model creation."""
        agent = Agent(
            name="Test Agent",
            description="A test agent",
            agent_type=AgentType.EXCEL_PROCESSOR,
            status=AgentStatus.CREATED,
        )

        assert agent.name == "Test Agent"
        assert agent.agent_type == AgentType.EXCEL_PROCESSOR
        assert agent.status == AgentStatus.CREATED
        assert agent.memory_limit_mb == 512  # default value

    def test_can_execute_task(self):
        """Test task execution capability check."""
        # Ready agent
        agent = Agent(
            name="Test Agent",
            agent_type=AgentType.CUSTOM,
            status=AgentStatus.READY,
            is_deleted=False,
        )
        assert agent.can_execute_task() is True

        # Deleted agent
        agent.is_deleted = True
        assert agent.can_execute_task() is False

        # Error status agent
        agent.is_deleted = False
        agent.status = AgentStatus.ERROR
        assert agent.can_execute_task() is False

    def test_safe_configuration(self):
        """Test configuration sanitization."""
        agent = Agent(
            name="Test Agent",
            agent_type=AgentType.CUSTOM,
            configuration={
                "timeout": 300,
                "api_keys": {"openai": "secret"},
                "passwords": {"db": "secret"},
                "normal_setting": "value",
            },
        )

        safe_config = agent.get_safe_configuration()

        assert "timeout" in safe_config
        assert "normal_setting" in safe_config
        assert "api_keys" not in safe_config
        assert "passwords" not in safe_config

    def test_to_dict(self):
        """Test model serialization."""
        agent = Agent(
            name="Test Agent", agent_type=AgentType.CUSTOM, created_by="test_user"
        )

        # Without sensitive data
        agent_dict = agent.to_dict(include_sensitive=False)
        assert "name" in agent_dict
        assert "agent_type" in agent_dict
        assert "created_by" not in agent_dict

        # With sensitive data
        agent_dict = agent.to_dict(include_sensitive=True)
        assert "created_by" in agent_dict


class TestAgentTask:
    """Test AgentTask model."""

    def test_task_creation(self):
        """Test task creation."""
        task = AgentTask(
            agent_id=uuid.uuid4(),
            task_type="excel_analysis",
            input_data={"file_path": "/test.xlsx"},
            status="pending",
        )

        assert task.task_type == "excel_analysis"
        assert task.status == "pending"
        assert task.input_data["file_path"] == "/test.xlsx"


class TestToolRegistry:
    """Test ToolRegistry model."""

    def test_tool_creation(self):
        """Test tool registry entry creation."""
        tool = ToolRegistry(
            tool_name="excel_reader",
            tool_category="file_processor",
            description="Read Excel files",
            version="1.0.0",
            is_public=True,
            security_level="standard",
        )

        assert tool.tool_name == "excel_reader"
        assert tool.is_public is True
        assert tool.security_level == "standard"
