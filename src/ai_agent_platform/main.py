"""
AI Agent Platform - Main FastAPI Application
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer

from .config import config
from .logging_config import setup_logging

# Security
security = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logging.info("🚀 AI Agent Platform starting up...")
    logging.info(f"Environment: {config.platform.environment}")
    logging.info(f"Version: {config.platform.platform_version}")

    # Validate configuration
    try:
        config._validate_security()
        logging.info("✅ Security configuration validated")
    except ValueError as e:
        logging.error(f"❌ Security validation failed: {e}")
        raise

    yield

    # Shutdown
    logging.info("🛑 AI Agent Platform shutting down...")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    # Setup logging first
    setup_logging(config.platform.log_level, config.platform.log_format)

    # Create FastAPI app with secure defaults
    app = FastAPI(
        title=config.platform.platform_name,
        version=config.platform.platform_version,
        description="Universal AI Agent Platform - Factory for creating specialized AI agents",
        docs_url="/docs" if config.platform.environment != "production" else None,
        redoc_url="/redoc" if config.platform.environment != "production" else None,
        openapi_url=(
            "/openapi.json" if config.platform.environment != "production" else None
        ),
        lifespan=lifespan,
    )

    # Security Middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=(
            ["*"]
            if config.platform.environment == "development"
            else ["localhost", "127.0.0.1"]
        ),
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.security.cors_origins,
        allow_credentials=config.security.cors_allow_credentials,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    # Custom Security Headers Middleware
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        if config.platform.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response

    # Request Logging Middleware
    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        start_time = time.time()

        # Log request
        logging.info(f"🔄 {request.method} {request.url.path}")

        try:
            response = await call_next(request)
            process_time = time.time() - start_time

            # Log response
            logging.info(
                f"✅ {request.method} {request.url.path} "
                f"Status: {response.status_code} "
                f"Time: {process_time:.3f}s"
            )

            response.headers["X-Process-Time"] = str(process_time)
            return response

        except Exception as e:
            process_time = time.time() - start_time
            logging.error(
                f"❌ {request.method} {request.url.path} "
                f"Error: {e!s} "
                f"Time: {process_time:.3f}s"
            )
            raise

    # Global Exception Handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logging.error(f"Unhandled exception: {exc}", exc_info=True)

        if config.platform.environment == "production":
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error", "request_id": id(request)},
            )
        else:
            return JSONResponse(
                status_code=500, content={"error": str(exc), "type": type(exc).__name__}
            )

    # Health Check Endpoints
    @app.get("/health")
    async def health_check() -> Dict[str, Any]:
        """Basic health check endpoint."""
        return {
            "status": "healthy",
            "platform": config.platform.platform_name,
            "version": config.platform.platform_version,
            "environment": config.platform.environment,
            "timestamp": time.time(),
        }

    @app.get("/health/detailed")
    async def detailed_health_check() -> Dict[str, Any]:
        """Detailed health check with system information."""
        # TODO: Add database, Redis, vector DB health checks
        return {
            "status": "healthy",
            "platform": {
                "name": config.platform.platform_name,
                "version": config.platform.platform_version,
                "environment": config.platform.environment,
            },
            "services": {
                "database": "pending",  # Will implement with DB connection
                "redis": "pending",  # Will implement with Redis connection
                "vector_db": "pending",  # Will implement with vector DB
            },
            "configuration": {
                "max_concurrent_agents": config.platform.max_concurrent_agents,
                "agent_timeout": config.platform.agent_timeout_seconds,
            },
            "timestamp": time.time(),
        }

    # Root endpoint
    @app.get("/")
    async def root() -> Dict[str, str]:
        """Root endpoint with platform information."""
        return {
            "message": "AI Agent Platform API",
            "version": config.platform.platform_version,
            "docs": (
                "/docs" if config.platform.environment != "production" else "disabled"
            ),
        }

    return app


# Create application instance
app = create_app()


# Development server runner
def run_dev_server():
    """Run development server with auto-reload."""
    uvicorn.run(
        "ai_agent_platform.main:app",
        host=config.platform.api_host,
        port=config.platform.api_port,
        reload=config.platform.debug_mode,
        log_level=config.platform.log_level.lower(),
    )


if __name__ == "__main__":
    run_dev_server()
