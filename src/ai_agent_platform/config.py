"""
Secure configuration management for AI Agent Platform.
"""

import os
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings


class SecurityConfig(BaseSettings):
    """Security-related configuration."""

    jwt_secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    api_key_enabled: bool = False
    api_key: Optional[str] = None

    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    cors_allow_credentials: bool = True

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v):
        if len(v) < 32:
            raise ValueError("JWT secret key must be at least 32 characters")
        return v


class DatabaseConfig(BaseSettings):
    """Database configuration."""

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "ai_agent_platform"
    postgres_user: str = "agent_platform"
    postgres_password: str = Field("secure_password_here", min_length=8)

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None

    db_pool_size: int = 10
    db_max_overflow: int = 20
    redis_pool_size: int = 10

    @property
    def database_url(self) -> str:
        """Generate secure database URL."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """Generate secure Redis URL."""
        password_part = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{password_part}{self.redis_host}:{self.redis_port}/{self.redis_db}"


class PlatformConfig(BaseSettings):
    """Main platform configuration."""

    platform_name: str = "AI Agent Platform"
    platform_version: str = "1.0.0"
    environment: str = Field(
        "development", pattern="^(development|staging|production)$"
    )

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    debug_mode: bool = False

    # Logging
    log_level: str = Field("INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    log_format: str = Field("json", pattern="^(json|text)$")
    log_file: str = "./logs/platform.log"

    # Agent Configuration
    max_concurrent_agents: int = Field(10, ge=1, le=100)
    agent_timeout_seconds: int = Field(300, ge=30, le=3600)
    agent_memory_limit_mb: int = Field(512, ge=256, le=4096)

    # Performance
    max_request_size_mb: int = Field(100, ge=1, le=1000)
    request_timeout_seconds: int = Field(60, ge=10, le=300)
    cache_ttl_seconds: int = Field(3600, ge=60, le=86400)

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        # Note: Cannot access other fields in field validators in Pydantic v2
        # This validation should be done at the model level
        return v


class Config:
    """Main configuration class with security validations."""

    def __init__(self, env_file: Optional[str] = None):
        """Initialize configuration with optional environment file."""
        self.env_file = env_file or ".env"
        self._load_config()
        self._validate_security()

    def _load_config(self):
        """Load configuration from environment."""
        # Load from .env file if it exists
        env_path = Path(self.env_file)
        if env_path.exists():
            # Use dotenv if available, otherwise load manually
            try:
                from dotenv import load_dotenv

                load_dotenv(env_path)
            except ImportError:
                self._load_env_manually(env_path)

        # Initialize configuration sections
        self.platform = PlatformConfig()
        self.database = DatabaseConfig()
        self.security = SecurityConfig()

    def _load_env_manually(self, env_path: Path):
        """Manually load environment variables from file."""
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip("\"'")

    def _validate_security(self):
        """Perform security validations."""
        # Check for insecure defaults in production
        if self.platform.environment == "production":
            if self.platform.debug_mode:
                raise ValueError("Debug mode must be disabled in production")

            if self.database.postgres_password == "secure_password_here":
                raise ValueError("Default database password detected in production")

            if len(self.security.jwt_secret_key) < 32:
                raise ValueError("JWT secret key too short for production")

    def get_database_url(self, hide_password: bool = True) -> str:
        """Get database URL with optional password masking."""
        if hide_password:
            return self.database.database_url.replace(
                self.database.postgres_password, "***"
            )
        return self.database.database_url

    def to_dict(self, include_secrets: bool = False) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        config_dict = {
            "platform": self.platform.model_dump(),
            "database": self.database.model_dump(
                exclude={"postgres_password"} if not include_secrets else set()
            ),
            "security": self.security.model_dump(
                exclude={"jwt_secret_key", "api_key"} if not include_secrets else set()
            ),
        }
        return config_dict


# Global configuration instance
config = Config()
