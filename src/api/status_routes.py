"""Status routes — system health and connection status.

Migrated from /api/v1/settings/connections to /api/v1/status/connections.
The old endpoint returns a 307 redirect (see connection_status_routes.py).
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.dependencies import verify_admin_key
from src.services.connection_checker import check_all_connections

router = APIRouter(prefix="/api/v1/status", tags=["status"])


class ServiceStatusInfo(BaseModel):
    name: str
    status: str  # "ok" | "unavailable" | "not_configured" | "error"
    details: str = ""
    latency_ms: float | None = None


class ConnectionStatusResponse(BaseModel):
    services: list[ServiceStatusInfo]
    all_ok: bool


@router.get(
    "/connections",
    response_model=ConnectionStatusResponse,
    dependencies=[Depends(verify_admin_key)],
)
async def get_connection_status() -> ConnectionStatusResponse:
    """Get health status for all backend services."""
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
