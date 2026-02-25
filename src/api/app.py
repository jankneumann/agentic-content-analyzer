"""
FastAPI Application Entry Point

Main application setup for the Newsletter Aggregator API.
Includes all routers, middleware, and configuration.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.audio_digest_routes import router as audio_digest_router
from src.api.auth_routes import router as auth_router
from src.api.chat_routes import router as chat_router
from src.api.connection_status_routes import router as connection_status_router
from src.api.content_routes import router as content_router
from src.api.digest_routes import router as digest_router
from src.api.files_routes import router as files_router
from src.api.health_routes import router as health_router
from src.api.image_generation_routes import router as image_generation_router
from src.api.job_routes import router as job_router
from src.api.middleware.auth import AuthMiddleware
from src.api.middleware.error_handler import register_error_handlers
from src.api.middleware.telemetry import TraceIdMiddleware
from src.api.model_settings_routes import router as model_settings_router
from src.api.notification_preferences_routes import router as notification_preferences_router
from src.api.notification_routes import router as notification_router
from src.api.otel_proxy_routes import router as otel_proxy_router
from src.api.podcast_routes import router as podcast_router
from src.api.save_routes import router as save_router
from src.api.script_routes import router as script_router
from src.api.search_routes import router as search_router
from src.api.settings_override_routes import router as settings_override_router
from src.api.settings_routes import router as settings_router
from src.api.share_routes import router as share_router
from src.api.shared_routes import router as shared_router
from src.api.source_routes import router as source_router
from src.api.summary_routes import router as summary_router
from src.api.theme_routes import router as theme_router
from src.api.upload_routes import router as upload_router
from src.api.voice_cleanup_routes import router as voice_cleanup_router
from src.api.voice_settings_routes import router as voice_settings_router
from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    import asyncio

    from src.utils.logging import get_logger

    logger = get_logger(__name__)

    # Startup: Initialize telemetry (observability provider + OTel infrastructure)
    from src.telemetry import setup_telemetry

    setup_telemetry(app=app)

    # Check embedding configuration matches database state (non-blocking)
    if settings.enable_search_indexing:
        try:
            from src.services.embedding_check import check_embedding_config_mismatch
            from src.storage.database import get_db_session

            db = get_db_session()
            try:
                check_embedding_config_mismatch(db)
            finally:
                db.close()
        except Exception:
            logger.debug("Embedding config check skipped", exc_info=True)

    # Auto-cleanup old notification events (>90 days)
    try:
        from src.services.notification_cleanup import auto_cleanup_notifications

        auto_cleanup_notifications()
    except Exception:
        logger.debug("Notification cleanup skipped", exc_info=True)

    # Start embedded queue worker if enabled
    worker_task: asyncio.Task | None = None
    if settings.worker_enabled:
        from src.queue.setup import ensure_queue_schema_compatible
        from src.queue.worker import register_all_handlers, run_worker

        await ensure_queue_schema_compatible()
        concurrency = min(max(settings.worker_concurrency, 1), 20)
        register_all_handlers()
        worker_task = asyncio.create_task(run_worker(concurrency=concurrency))

    yield

    # Shutdown: Stop embedded worker
    if worker_task is not None:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        logger.info("Embedded worker stopped")

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

# Auth middleware — enforces session cookie or X-Admin-Key on all non-exempt endpoints
# Added before telemetry so auth errors still get trace IDs
app.add_middleware(AuthMiddleware)

# Telemetry middleware — adds X-Trace-Id header to responses
app.add_middleware(TraceIdMiddleware)

# Structured error handling — includes trace_id in error responses
register_error_handlers(app)

# Include routers
app.include_router(auth_router)  # Auth endpoints (login, logout, session)
app.include_router(audio_digest_router)
app.include_router(content_router)
app.include_router(summary_router)
app.include_router(script_router)
app.include_router(digest_router)
app.include_router(podcast_router)
app.include_router(theme_router)
app.include_router(chat_router)
app.include_router(settings_router)
app.include_router(settings_override_router)
app.include_router(model_settings_router)
app.include_router(voice_settings_router)
app.include_router(voice_cleanup_router)
app.include_router(connection_status_router)
app.include_router(upload_router)
app.include_router(files_router)
app.include_router(save_router)  # Mobile content capture
app.include_router(source_router)
app.include_router(health_router)  # Health and readiness probes
app.include_router(job_router)  # Job queue management
app.include_router(search_router)  # Hybrid document search
app.include_router(image_generation_router)  # AI image generation
app.include_router(share_router)  # Share management (enable/disable/status)
app.include_router(shared_router)  # Public shared content (no auth)
app.include_router(notification_router)  # Notification events and SSE stream
app.include_router(notification_preferences_router)  # Notification preferences
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
