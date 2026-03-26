"""Health and readiness endpoints for Kubernetes/Docker probes."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["system"])


def _check_backup_recency() -> str:
    """Check if the most recent pg_cron backup completed within expected window.

    Queries the cron.job_run_details table for the 'railway-backup' job
    and compares its last successful run against 2x the schedule interval.

    Returns:
        "ok" if backup ran recently, "stale" if overdue,
        "no_history" if no runs found, "not_configured" if pg_cron unavailable
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    from src.storage.database import get_engine

    try:
        engine = get_engine()
    except Exception:
        return "not_configured"

    try:
        with engine.connect() as conn:
            # Check if cron schema exists (pg_cron installed)
            result = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'cron' AND table_name = 'job_run_details'"
                )
            )
            if result.fetchone() is None:
                return "not_configured"

            # Get last successful run of the backup job
            result = conn.execute(
                text(
                    "SELECT end_time FROM cron.job_run_details "
                    "WHERE jobname = 'railway-backup' AND status = 'succeeded' "
                    "ORDER BY end_time DESC LIMIT 1"
                )
            )
            row = result.fetchone()

            if row is None:
                return "no_history"

            last_run = row[0]
            if last_run.tzinfo is None:
                last_run = last_run.replace(tzinfo=UTC)

            # Stale if last backup exceeds configured threshold
            threshold = timedelta(hours=settings.railway_backup_staleness_hours)
            if datetime.now(UTC) - last_run > threshold:
                return "stale"

            return "ok"
    except Exception:
        return "not_configured"


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
        from src.queue.setup import get_queue_health_snapshot

        queue_snapshot = await asyncio.wait_for(
            get_queue_health_snapshot(),
            timeout=settings.health_check_timeout_seconds,
        )
        checks["queue"] = "ok"
        checks["queue_queued"] = str(queue_snapshot["queued"])
        checks["queue_in_progress"] = str(queue_snapshot["in_progress"])
        checks["queue_active_workers"] = str(queue_snapshot["active_workers"])
    except ImportError:
        checks["queue"] = "not_configured"
    except Exception as exc:
        logger.warning("Queue health check failed: %s", exc)
        checks["queue"] = "unavailable"

    # Crawl4AI remote server check (only if configured)
    if settings.crawl4ai_enabled and settings.crawl4ai_server_url:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{settings.crawl4ai_server_url}/health")
                checks["crawl4ai"] = "ok" if resp.status_code == 200 else "degraded"
        except Exception as exc:
            logger.warning("Crawl4AI health check failed: %s", exc)
            checks["crawl4ai"] = "unavailable"

    # Backup recency check (Railway provider with pg_cron only)
    if settings.database_provider == "railway" and settings.railway_backup_enabled:
        try:
            backup_status = await asyncio.wait_for(
                loop.run_in_executor(None, _check_backup_recency),
                timeout=settings.health_check_timeout_seconds,
            )
            checks["backup"] = backup_status
            if backup_status == "stale":
                logger.warning("Backup is stale — last successful run exceeds 2x schedule interval")
        except Exception as exc:
            logger.warning("Backup health check failed: %s", exc)
            checks["backup"] = "unknown"

    status_code = 200 if all_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ok else "not_ready",
            "checks": checks,
        },
    )
