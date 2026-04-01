"""
Connection Status API Routes

Read-only dashboard showing health status for all configured
backend services (PostgreSQL, Neo4j, LLM, TTS, embedding).
"""

from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/settings/connections", tags=["settings"])


# ============================================================================
# Response Models
# ============================================================================


class ServiceStatusInfo(BaseModel):
    """Health status for a single service."""

    name: str
    status: str  # "ok" | "unavailable" | "not_configured" | "error"
    details: str = ""
    latency_ms: float | None = None


class ConnectionStatusResponse(BaseModel):
    """Health status for all configured services."""

    services: list[ServiceStatusInfo]
    all_ok: bool


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "",
    response_class=RedirectResponse,
    status_code=307,
)
async def get_connection_status_redirect() -> RedirectResponse:
    """Redirect to new status endpoint at /api/v1/status/connections.

    Returns 307 Temporary Redirect to preserve request method and headers.
    This redirect will be removed after one release cycle.
    """
    return RedirectResponse(url="/api/v1/status/connections", status_code=307)
