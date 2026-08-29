"""Status routes — system health and connection status.

Migrated from /api/v1/settings/connections to /api/v1/status/connections.
The old endpoint returns a 307 redirect (see connection_status_routes.py).
"""

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.dependencies import verify_admin_key, verify_operator_key
from src.contracts.workflow_models import EnvironmentOwnershipStatus, Problem
from src.services.connection_checker import check_all_connections
from src.services.environment_ownership import (
    configured_ownership_identity,
    evaluate_environment_ownership,
)
from src.storage.database import get_db

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


def environment_ownership_status(
    dry_run_target: str | None = None,
) -> EnvironmentOwnershipStatus:
    """Read the bounded ownership status from the shared queue database."""

    with get_db() as session:
        return evaluate_environment_ownership(
            session,
            configured_ownership_identity(),
            dry_run_target=dry_run_target,
        )


@router.get(
    "/environment-ownership",
    response_model=EnvironmentOwnershipStatus,
    dependencies=[Depends(verify_operator_key)],
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Ownership dry-run conflicts with current authority",
            "content": {"application/problem+json": {"schema": Problem.model_json_schema()}},
        }
    },
)
async def get_environment_ownership_status(
    dry_run_target: str | None = Query(default=None, min_length=1, max_length=32),
) -> EnvironmentOwnershipStatus | JSONResponse:
    """Return passive/active state and a non-mutating cutover-order check."""

    ownership_status = environment_ownership_status(dry_run_target)
    if ownership_status.dry_run is not None and not ownership_status.dry_run.allowed:
        problem = Problem(
            type="urn:aca:problem:environment-ownership-conflict",
            title="Environment ownership conflict",
            status=status.HTTP_409_CONFLICT,
            detail="The requested ownership dry run failed its shared-authority fence",
            code="environment_ownership_conflict",
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=problem.model_dump(mode="json", exclude_none=True),
            media_type="application/problem+json",
        )
    return ownership_status
