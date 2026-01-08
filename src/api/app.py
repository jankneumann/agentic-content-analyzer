"""
FastAPI Application Entry Point

Main application setup for the Newsletter Aggregator API.
Includes all routers, middleware, and configuration.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.chat_routes import router as chat_router
from src.api.digest_routes import router as digest_router
from src.api.newsletter_routes import router as newsletter_router
from src.api.podcast_routes import router as podcast_router
from src.api.script_routes import router as script_router
from src.api.settings_routes import router as settings_router
from src.api.summary_routes import router as summary_router
from src.api.theme_routes import router as theme_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="Newsletter Aggregator API",
    description="API for the AI Newsletter Aggregator - ingestion, summarization, and digest generation",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Production frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(newsletter_router)
app.include_router(summary_router)
app.include_router(script_router)
app.include_router(digest_router)
app.include_router(podcast_router)
app.include_router(theme_router)
app.include_router(chat_router)
app.include_router(settings_router)


@app.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "newsletter-aggregator"}


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
