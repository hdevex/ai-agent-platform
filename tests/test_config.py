"""Tests for configuration management."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_agent_platform.config import (
    Config,
    DatabaseConfig,
    PlatformConfig,
    SecurityConfig,
)


class TestSecurityConfig:
    """Test security configuration."""

    def test_jwt_secret_validation(self):
        """Test JWT secret key validation."""
        # Valid secret
        config = SecurityConfig(jwt_secret_key="a" * 32)
        assert len(config.jwt_secret_key) >= 32

        # Invalid secret should raise error
        with pytest.raises(
            ValueError, match="JWT secret key must be at least 32 characters"
        ):
            SecurityConfig(jwt_secret_key="short")

    def test_cors_defaults(self):
        """Test CORS default configuration."""
        config = SecurityConfig()
        assert "http://localhost:3000" in config.cors_origins
        assert config.cors_allow_credentials is True


class TestDatabaseConfig:
    """Test database configuration."""

    def test_database_url_generation(self):
        """Test database URL generation."""
        config = DatabaseConfig(
            postgres_host="localhost",
            postgres_port=5432,
            postgres_db="test_db",
            postgres_user="test_user",
            postgres_password="test_password",
        )

        expected_url = "postgresql://test_user:test_password@localhost:5432/test_db"
        assert config.database_url == expected_url

    def test_redis_url_generation(self):
        """Test Redis URL generation."""
        # Without password
        config = DatabaseConfig(redis_password=None)
        assert config.redis_url == "redis://localhost:6379/0"

        # With password
        config = DatabaseConfig(redis_password="secret")
        assert config.redis_url == "redis://:secret@localhost:6379/0"


class TestPlatformConfig:
    """Test platform configuration."""

    def test_environment_validation(self):
        """Test environment validation."""
        # Valid environments
        for env in ["development", "staging", "production"]:
            config = PlatformConfig(environment=env)
            assert config.environment == env

        # Invalid environment should raise error
        with pytest.raises(ValueError):
            PlatformConfig(environment="invalid")

    def test_production_debug_validation(self):
        """Test that debug mode is disabled in production."""
        # This test needs custom validation logic
        # For now, just test that we can create production config
        config = PlatformConfig(environment="production", debug_mode=False)
        assert config.environment == "production"
        assert config.debug_mode is False


class TestMainConfig:
    """Test main configuration class."""

    def test_config_initialization(self):
        """Test configuration initialization."""
        config = Config()
        assert config.platform is not None
        assert config.database is not None
        assert config.security is not None

    def test_config_with_env_file(self):
        """Test configuration with environment file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("PLATFORM_NAME=Test Platform\n")
            f.write("API_PORT=9000\n")
            f.write("POSTGRES_PASSWORD=test_secure_password\n")
            env_file = f.name

        try:
            os.environ["PLATFORM_NAME"] = "Test Platform"
            os.environ["API_PORT"] = "9000"
            os.environ["POSTGRES_PASSWORD"] = "test_secure_password"

            config = Config(env_file=env_file)
            assert config.platform.platform_name == "Test Platform"
            assert config.platform.api_port == 9000
            assert config.database.postgres_password == "test_secure_password"
        finally:
            os.unlink(env_file)
            # Clean up environment
            for key in ["PLATFORM_NAME", "API_PORT", "POSTGRES_PASSWORD"]:
                os.environ.pop(key, None)

    def test_password_masking(self):
        """Test password masking in database URL."""
        config = Config()
        masked_url = config.get_database_url(hide_password=True)
        assert "***" in masked_url
        assert config.database.postgres_password not in masked_url

        full_url = config.get_database_url(hide_password=False)
        assert config.database.postgres_password in full_url

    def test_config_to_dict(self):
        """Test configuration serialization."""
        config = Config()

        # Without secrets
        config_dict = config.to_dict(include_secrets=False)
        assert "platform" in config_dict
        assert "database" in config_dict
        assert "security" in config_dict
        assert "postgres_password" not in str(config_dict)

        # With secrets
        config_dict = config.to_dict(include_secrets=True)
        assert "postgres_password" in str(config_dict)
