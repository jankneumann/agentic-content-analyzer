"""Emit backup-freshness alerts onto the durable out-of-band path.

Two decisions are load-bearing here.

**Emission belongs to worker maintenance, not to /ready.** The readiness endpoint
is polled by a load balancer many times a minute; emitting from there would
produce one alert per probe. Worker maintenance runs on a schedule and holds a
leader lock, so it is the only place a once-per-condition emission can live.

**The event key is a pure function of the check window** (design A10). The suffix
is the evaluation time truncated to a multiple of the window length — NOT a
wall-clock read at emission time. Every evaluation inside one window therefore
derives the identical key, and the unique index on `event_key` turns that into
per-window deduplication.

The consequence, stated here so it is not discovered in production: during a
sustained outage exactly one alert is emitted per staleness period. Not one per
worker tick, and not only one ever. Re-alerting is what distinguishes an ongoing
outage from a transient blip.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import wraps
from typing import Any

from src.clients.operational_observability import (
    operational_entrypoint,
    reconcile_bootstrap_audit,
)
from src.services.backup.manifest_reader import BackupFreshness, read_freshness
from src.utils.logging import get_logger

logger = get_logger(__name__)

#: Floor on the window length. A misconfigured `backup_staleness_hours` of 0 would
#: otherwise make every evaluation its own window and turn the alert channel into
#: a firehose — the fastest way to train operators to ignore it.
MIN_WINDOW_SECONDS = 3600


def check_window_start(moment: datetime, *, window_seconds: int) -> int:
    """Truncate `moment` to the start of its fixed-length window, as epoch seconds.

    Pure: same window, same answer, regardless of when within it this is called.
    That property is the entire idempotency mechanism, so it is tested directly
    rather than inferred from the absence of duplicate alerts.
    """
    window = max(int(window_seconds), MIN_WINDOW_SECONDS)
    epoch = int(moment.astimezone(UTC).timestamp())
    return epoch - (epoch % window)


def window_seconds_for(settings: Any) -> int:
    """The window length equals the configured staleness threshold.

    Note the absence of `or 48`: zero is falsy, so that idiom would silently turn a
    misconfigured `backup_staleness_hours=0` into 48 hours and defeat the floor
    below. An explicit None check is the difference between clamping a bad value
    and quietly substituting a different one.
    """
    hours = getattr(settings, "backup_staleness_hours", None)
    seconds = int(hours) * 3600 if hours is not None else 48 * 3600
    return max(seconds, MIN_WINDOW_SECONDS)


def event_key_for(settings: Any, moment: datetime) -> str:
    """The A2 grammar: lowercase throughout, so `WorkflowEventKey` accepts it.

    Both grammars proposed before this one embedded an ISO-8601 stamp, whose
    uppercase `T` and `Z` fail that pattern — every alert would have been rejected
    at construction.
    """
    start = check_window_start(moment, window_seconds=window_seconds_for(settings))
    return f"system_check:backup_freshness:{start}"


async def _emit_backup_freshness_alert_impl(
    conn: Any,
    *,
    settings: Any,
    now: datetime | None = None,
) -> str | None:
    """Enqueue one durable terminal event if the backup is not healthy.

    Returns the event key when a row was inserted, otherwise ``None`` — including
    when this window's alert already exists, which is the normal steady state
    during an ongoing outage.
    """
    if callable(getattr(conn, "transaction", None)):
        await reconcile_bootstrap_audit(settings, maintenance_connection=conn)

    if not getattr(settings, "backup_monitoring_enabled", True):
        return None

    moment = now or datetime.now(UTC)
    freshness: BackupFreshness = read_freshness(settings, now=moment)
    if not freshness.alertable:
        return None

    event_key = event_key_for(settings, moment)
    inserted = await conn.fetchval(
        """
        INSERT INTO workflow_terminal_events (event_key, source_kind, occurred_at)
        VALUES ($1, 'system_check', $2)
        ON CONFLICT (event_key) DO NOTHING
        RETURNING id
        """,
        event_key,
        moment,
    )
    if inserted is None:
        # Already alerted for this window. Not an error, and deliberately not
        # logged at warning: a sustained outage would otherwise emit a log line per
        # tick describing the absence of an alert.
        logger.debug("backup freshness alert already recorded for window %s", event_key)
        return None

    logger.warning(
        "backup freshness alert raised: %s (code=%s)",
        freshness.status,
        freshness.diagnostic_code,
    )
    return event_key


@operational_entrypoint("alert.backup_freshness", stage="alert", service_name="aca-maintenance")
async def _instrumented_backup_freshness_alert(
    conn: Any,
    *,
    settings: Any,
    now: datetime | None = None,
) -> str | None:
    return await _emit_backup_freshness_alert_impl(conn, settings=settings, now=now)


@wraps(_emit_backup_freshness_alert_impl)
async def emit_backup_freshness_alert(
    conn: Any,
    *,
    settings: Any,
    now: datetime | None = None,
) -> str | None:
    """Use durable instrumentation for real transactional maintenance calls."""
    if callable(getattr(conn, "transaction", None)):
        return await _instrumented_backup_freshness_alert(conn, settings=settings, now=now)
    return await _emit_backup_freshness_alert_impl(conn, settings=settings, now=now)
