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
from .api.agents import router as agents_router
from .api.rag import router as rag_router
from .api.tools import router as tools_router
from .llm.providers import get_llm_manager
from .database.connection import get_db_engine
from .rag.vector_store import get_rag_system

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
        services_status = {}
        
        # Check LLM service
        try:
            llm_manager = get_llm_manager()
            llm_health = await llm_manager.health_check()
            services_status["llm"] = llm_health
        except Exception as e:
            services_status["llm"] = {"status": "unhealthy", "error": str(e)}
        
        # Check database
        try:
            from sqlalchemy import text
            engine = get_db_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            services_status["database"] = {"status": "healthy"}
        except Exception as e:
            services_status["database"] = {"status": "unhealthy", "error": str(e)}
        
        # Check RAG system
        try:
            rag_system = get_rag_system()
            rag_health = await rag_system.health_check()
            services_status["rag"] = rag_health
        except Exception as e:
            services_status["rag"] = {"status": "unhealthy", "error": str(e)}
        
        # Overall status
        overall_status = "healthy" if all(
            service.get("status") == "healthy" for service in services_status.values()
        ) else "degraded"
        
        return {
            "status": overall_status,
            "platform": {
                "name": config.platform.platform_name,
                "version": config.platform.platform_version,
                "environment": config.platform.environment,
            },
            "services": services_status,
            "configuration": {
                "max_concurrent_agents": config.platform.max_concurrent_agents,
                "agent_timeout": config.platform.agent_timeout_seconds,
                "llm_provider": config.llm.llm_provider,
                "llm_model": config.llm.llm_model_name,
            },
            "timestamp": time.time(),
        }

    # Include API routers
    app.include_router(agents_router, prefix="/api")
    app.include_router(rag_router, prefix="/api")
    app.include_router(tools_router, prefix="/api")

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
