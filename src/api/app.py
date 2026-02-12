"""
FastAPI Application Entry Point

Main application setup for the Newsletter Aggregator API.
Includes all routers, middleware, and configuration.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.audio_digest_routes import router as audio_digest_router
from src.api.chat_routes import router as chat_router
from src.api.content_routes import router as content_router
from src.api.digest_routes import router as digest_router
from src.api.files_routes import router as files_router
from src.api.health_routes import router as health_router
from src.api.job_routes import router as job_router
from src.api.middleware.error_handler import register_error_handlers
from src.api.middleware.telemetry import TraceIdMiddleware
from src.api.otel_proxy_routes import router as otel_proxy_router
from src.api.podcast_routes import router as podcast_router
from src.api.save_routes import router as save_router
from src.api.script_routes import router as script_router
from src.api.search_routes import router as search_router
from src.api.settings_routes import router as settings_router
from src.api.source_routes import router as source_router
from src.api.summary_routes import router as summary_router
from src.api.theme_routes import router as theme_router
from src.api.upload_routes import router as upload_router
from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup: Initialize telemetry (observability provider + OTel infrastructure)
    from src.telemetry import setup_telemetry

    setup_telemetry(app=app)

    yield

    # Shutdown: Flush and close telemetry
    from src.telemetry import shutdown_telemetry

    shutdown_telemetry()

    # Close queue connection if it was opened
    try:
        from src.queue.setup import close_queue

        await close_queue()
    except ImportError:
        pass  # Queue module not available


app = FastAPI(
    title="Newsletter Aggregator API",
    description="API for the AI Newsletter Aggregator - ingestion, summarization, and digest generation",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration - configurable via ALLOWED_ORIGINS env var
# Use "*" for iOS Shortcuts and other mobile clients
allowed_origins = settings.get_allowed_origins_list()
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Telemetry middleware — adds X-Trace-Id header to responses
app.add_middleware(TraceIdMiddleware)

# Structured error handling — includes trace_id in error responses
register_error_handlers(app)

# Include routers
app.include_router(audio_digest_router)
app.include_router(content_router)
app.include_router(summary_router)
app.include_router(script_router)
app.include_router(digest_router)
app.include_router(podcast_router)
app.include_router(theme_router)
app.include_router(chat_router)
app.include_router(settings_router)
app.include_router(upload_router)
app.include_router(files_router)
app.include_router(save_router)  # Mobile content capture
app.include_router(source_router)
app.include_router(health_router)  # Health and readiness probes
app.include_router(job_router)  # Job queue management
app.include_router(search_router)  # Hybrid document search
app.include_router(otel_proxy_router)  # Frontend OTLP trace proxy


@app.get("/api/v1/system/config", tags=["system"])
async def get_system_config():
    """Get system configuration for frontend."""
    return {
        "version": "0.1.0",
        "features": {
            "sse_enabled": True,
            "chat_enabled": True,
            "themes_enabled": True,
        },
    }
