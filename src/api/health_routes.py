"""Health and readiness endpoints for Kubernetes/Docker probes."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness probe -- returns 200 if the process is alive."""
    return {"status": "healthy", "service": "newsletter-aggregator"}


@router.get("/ready")
async def readiness_check() -> JSONResponse:
    """Readiness probe -- checks database connectivity.

    Returns 200 if all dependencies are reachable, 503 otherwise.
    """
    checks: dict[str, str] = {}
    all_ok = True

    # Database check (synchronous function, run in executor)
    try:
        from src.storage.database import health_check as db_health_check

        loop = asyncio.get_event_loop()
        db_ok = await asyncio.wait_for(
            loop.run_in_executor(None, db_health_check),
            timeout=settings.health_check_timeout_seconds,
        )
        checks["database"] = "ok" if db_ok else "degraded"
        if not db_ok:
            all_ok = False
    except Exception as exc:
        logger.warning("Database health check failed: %s", exc)
        checks["database"] = "unavailable"
        all_ok = False

    # Queue check (PGQueuer uses PostgreSQL, so this is optional)
    try:
        from src.queue.setup import _connection as queue_conn

        if queue_conn is not None:
            checks["queue"] = "ok"
        else:
            checks["queue"] = "not_connected"
    except ImportError:
        checks["queue"] = "not_configured"
    except Exception as exc:
        logger.warning("Queue health check failed: %s", exc)
        checks["queue"] = "unavailable"

    status_code = 200 if all_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ok else "not_ready",
            "checks": checks,
        },
    )
