"""
Connection Status API Routes

Read-only dashboard showing health status for all configured
backend services (PostgreSQL, Neo4j, LLM, TTS, embedding).
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.dependencies import verify_admin_key
from src.services.connection_checker import check_all_connections

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
    response_model=ConnectionStatusResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def get_connection_status() -> ConnectionStatusResponse:
    """Get health status for all configured backend services.

    Runs all checks concurrently with per-service timeout.
    Statuses: ok, unavailable, not_configured, error.
    """
    result = await check_all_connections()
    return ConnectionStatusResponse(
        services=[
            ServiceStatusInfo(
                name=s.name,
                status=s.status,
                details=s.details,
                latency_ms=s.latency_ms,
            )
            for s in result.services
        ],
        all_ok=result.all_ok,
    )
