"""
Integration test configuration and fixtures.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

from ai_agent_platform.config import config


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def mock_db_session():
    """Create mock database session for testing."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def override_config():
    """Override configuration for testing."""
    # Store original values
    original_env = config.platform.environment
    original_log_level = config.platform.log_level
    
    # Set test values
    config.platform.environment = "testing"
    config.platform.log_level = "DEBUG"
    
    yield config
    
    # Restore original values
    config.platform.environment = original_env
    config.platform.log_level = original_log_level


@pytest.fixture
def mock_lm_studio_available():
    """Mock LM Studio as available for integration tests."""
    import httpx
    from unittest.mock import patch
    
    mock_response = httpx.Response(
        status_code=200,
        json={"data": [{"id": "openai/gpt-oss-20b", "object": "model"}]},
        request=httpx.Request("GET", "http://test.com")
    )
    
    with patch("httpx.AsyncClient.get", return_value=mock_response):
        yield


# Test markers for different test categories
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "live: marks tests that require live services"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )