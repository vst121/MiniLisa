"""
FastAPI Main Application Entrypoint.
Initializes lifespan events, CORS middleware, OpenTelemetry, and API v1 routers.
"""

from contextlib import asynccontextmanager
import logging
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from src.api.deps import get_workflow_engine
from src.api.v1.router import api_v1_router
from src.config.settings import settings
from src.infrastructure.database import Base, engine

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI Application Lifespan: Startup & Shutdown events."""
    logger.info(f"🚀 Starting {settings.APP_NAME} in '{settings.ENV}' mode...")
    
    # Create upload directory
    settings.create_upload_dir()

    # Initialize DB tables (for dev/testing)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Register workflow subscribers to event bus
    workflow_engine = get_workflow_engine()
    await workflow_engine.register_subscribers()
    logger.info("✅ Event Bus Workflow Subscribers registered.")

    yield

    logger.info("👋 Shutting down Procurement AI Assistant...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Production-Grade Enterprise AI Procurement Assistant API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    started_at = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started_at) * 1000
    response.headers["X-Correlation-ID"] = correlation_id
    logger.info(
        "HTTP %s %s -> %s (%.2fms, correlation_id=%s)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        correlation_id,
    )
    return response

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Include API v1 Router
app.include_router(api_v1_router, prefix=settings.API_V1_STR)
