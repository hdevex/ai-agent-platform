"""
Secure database connection management.
"""

import logging
from collections.abc import AsyncGenerator
from typing import Optional

import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from ..config import config

logger = logging.getLogger(__name__)

# SQLAlchemy Base
Base = declarative_base()

# Global database engine and session maker
engine: Optional[object] = None
AsyncSessionLocal: Optional[async_sessionmaker] = None
redis_pool: Optional[redis.ConnectionPool] = None


async def init_database():
    """Initialize database connection with security measures."""
    global engine, AsyncSessionLocal

    try:
        # Create async engine with security configurations
        engine = create_async_engine(
            config.database.database_url.replace(
                "postgresql://", "postgresql+asyncpg://"
            ),
            echo=config.platform.debug_mode,
            pool_size=config.database.db_pool_size,
            max_overflow=config.database.db_max_overflow,
            pool_pre_ping=True,  # Validate connections before use
            pool_recycle=3600,  # Recycle connections every hour
            poolclass=NullPool if config.platform.environment == "test" else None,
            # Security: Disable SQL statement logging in production
            echo_pool=config.platform.environment == "development",
        )

        # Create session maker
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Test connection
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

        logger.info("✅ Database connection established successfully")

    except Exception as e:
        logger.error(f"❌ Failed to connect to database: {e}")
        raise


async def init_redis():
    """Initialize Redis connection with security measures."""
    global redis_pool

    try:
        # Create Redis connection pool
        redis_pool = redis.ConnectionPool.from_url(
            config.database.redis_url,
            max_connections=config.database.redis_pool_size,
            retry_on_timeout=True,
            health_check_interval=30,
        )

        # Test connection
        redis_client = redis.Redis(connection_pool=redis_pool)
        await redis_client.ping()
        await redis_client.close()

        logger.info("✅ Redis connection established successfully")

    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        raise


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session with proper error handling."""
    if not AsyncSessionLocal:
        raise RuntimeError("Database not initialized. Call init_database() first.")

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_redis() -> redis.Redis:
    """Get Redis client with proper error handling."""
    if not redis_pool:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")

    return redis.Redis(connection_pool=redis_pool)


async def close_database_connections():
    """Close all database connections."""
    global engine, redis_pool

    if engine:
        await engine.dispose()
        logger.info("📤 Database connections closed")

    if redis_pool:
        await redis_pool.disconnect()
        logger.info("📤 Redis connections closed")
