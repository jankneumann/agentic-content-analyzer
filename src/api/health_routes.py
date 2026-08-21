"""Health and readiness endpoints for Kubernetes/Docker probes."""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import TYPE_CHECKING

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.config import settings
from src.config.release_identity import release_identity
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.storage.graph_provider import GraphDBProvider

logger = get_logger(__name__)

router = APIRouter(tags=["system"])

_release_identity = release_identity


@lru_cache(maxsize=1)
def _cached_graph_provider() -> GraphDBProvider:
    """Return a process-wide graph provider for readiness probes.

    Cached to avoid creating a fresh Neo4j driver (or FalkorDB client)
    on every /ready call. CLI callers still get fresh providers via
    get_graph_provider() directly — they manage their own lifecycle.
    """
    from src.storage.graph_provider import get_graph_provider

    return get_graph_provider()


def _check_backup_recency() -> str:
    """Report backup freshness for THIS environment, derived from the manifest.

    Rewritten from the pg_cron original, which was unfixable rather than merely
    wrong. It queried `cron.job_run_details` for a job that had never once
    succeeded, on a platform where the GUC mechanism that job depended on is
    restricted — so the honest answer to "when did the backup last run?" was never
    available from inside the database.

    Freshness now comes from the backup target's own manifest, which is written by
    the process that actually takes the backup. Reading the evidence where the work
    happens is the whole difference between a monitored backup and a scheduled one.

    The reader never raises: a slow or unreachable bucket becomes a status value.
    A readiness probe that 500s because a bucket is slow has converted a monitoring
    signal into an outage.
    """
    from src.services.backup.manifest_reader import read_freshness

    return str(read_freshness(settings).status)


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness probe -- returns 200 if the process is alive."""
    revision, revision_source = _release_identity()
    return {
        "status": "healthy",
        "service": "newsletter-aggregator",
        "revision": revision,
        "revision_source": revision_source,
    }


@router.get("/ready")
async def readiness_check() -> JSONResponse:
    """Readiness probe -- checks database connectivity.

    Returns 200 if all dependencies are reachable, 503 otherwise.
    """
    checks: dict[str, str] = {}
    all_ok = True

    # Bound OUTSIDE the database try block. It was previously bound at the top of
    # that block and used by the backup check far below, so an import failure in
    # the database layer left `loop` unbound — the backup check then raised
    # NameError, which its own except swallowed into "unknown". The backup monitor
    # went dark at exactly the moment something was already wrong (design D8).
    loop = asyncio.get_event_loop()

    # Database check (synchronous function, run in executor)
    try:
        from src.storage.database import health_check as db_health_check

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

    # Graph DB check (always — surfaces misconfiguration even when graph is non-critical)
    checks["graphdb_backend"] = f"{settings.graphdb_provider}/{settings.graphdb_mode}"
    try:
        provider = _cached_graph_provider()
        graph_ok = await asyncio.wait_for(
            provider.health_check(),
            timeout=settings.health_check_timeout_seconds,
        )
        checks["graphdb"] = "ok" if graph_ok else "degraded"
    except ValueError as exc:
        # Misconfigured settings (e.g., cloud mode without FALKORDB_CLOUD_HOST)
        logger.warning("Graph DB not configured: %s", exc)
        checks["graphdb"] = "not_configured"
    except Exception as exc:
        logger.warning("Graph DB health check failed: %s", exc)
        checks["graphdb"] = "unavailable"

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

    # Backup recency check.
    #
    # No longer gated on `database_provider == "railway"`. That gate meant the
    # check never ran anywhere except Railway — including on the self-hosted host
    # this project is migrating to, where there is no managed PITR to fall back on
    # and the check matters most. Backup freshness has nothing to do with which
    # database provider is configured.
    if settings.backup_monitoring_enabled:
        try:
            backup_status = await asyncio.wait_for(
                loop.run_in_executor(None, _check_backup_recency),
                timeout=settings.health_check_timeout_seconds,
            )
            checks["backup"] = backup_status
            if backup_status == "stale":
                # The old text claimed "2x schedule interval". The real threshold is
                # backup_staleness_hours, which is independent of any schedule — so
                # the message told operators to look at the wrong setting.
                logger.warning(
                    "Backup is stale — the last recorded run is older than the "
                    "configured backup_staleness_hours threshold (%s hours)",
                    settings.backup_staleness_hours,
                )
        except Exception as exc:
            logger.warning("Backup health check failed: %s", exc)
            checks["backup"] = "unknown"
        # `all_ok` is deliberately NOT touched. Backup staleness is a real problem,
        # but it is not a reason to pull this instance out of the load balancer:
        # doing so would turn a backup problem into a serving outage. The durable
        # alert emitted by worker maintenance is what makes it actionable.

    status_code = 200 if all_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ok else "not_ready",
            "checks": checks,
        },
    )
