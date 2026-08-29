"""Typed bounded PostgreSQL projection for telemetry process health."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import asyncpg

LifecycleKind = Literal["long_running", "short_lived"]
HealthStatus = Literal["healthy", "degraded", "disabled", "stale"]
ExportTarget = Literal["local_langfuse", "remote_langfuse", "other_otlp", "none"]


@dataclass(frozen=True, slots=True)
class ProcessHealthHeartbeat:
    environment: str
    service_name: str
    service_instance_id: str
    release_revision: str
    lifecycle_kind: LifecycleKind
    required_observability: bool
    initialized: bool
    status: HealthStatus
    export_target: ExportTarget
    last_heartbeat_at: datetime
    last_success_at: datetime | None
    last_error_at: datetime | None
    last_error_code: str | None
    buffered_count: int
    buffer_capacity: int
    dropped_count: int
    last_flush_at: datetime | None
    last_flush_succeeded: bool | None


@dataclass(frozen=True, slots=True)
class TelemetryProcessHealth(ProcessHealthHeartbeat):
    expires_at: datetime


def _row_to_health(row: Any) -> TelemetryProcessHealth:
    return TelemetryProcessHealth(
        environment=str(row["environment"]),
        service_name=str(row["service_name"]),
        service_instance_id=str(row["service_instance_id"]),
        release_revision=str(row["release_revision"]),
        lifecycle_kind=row["lifecycle_kind"],
        expires_at=row["expires_at"],
        required_observability=bool(row["required_observability"]),
        initialized=bool(row["initialized"]),
        status=row["status"],
        export_target=row["export_target"],
        last_heartbeat_at=row["last_heartbeat_at"],
        last_success_at=row["last_success_at"],
        last_error_at=row["last_error_at"],
        last_error_code=row["last_error_code"],
        buffered_count=int(row["buffered_count"]),
        buffer_capacity=int(row["buffer_capacity"]),
        dropped_count=int(row["dropped_count"]),
        last_flush_at=row["last_flush_at"],
        last_flush_succeeded=row["last_flush_succeeded"],
    )


async def upsert_process_health(
    conn: asyncpg.Connection,
    heartbeat: ProcessHealthHeartbeat,
) -> TelemetryProcessHealth:
    row = await conn.fetchrow(
        """
        INSERT INTO telemetry_process_health (
            environment, service_name, service_instance_id, release_revision,
            lifecycle_kind, expires_at, required_observability, initialized, status,
            export_target, last_heartbeat_at, last_success_at, last_error_at,
            last_error_code, buffered_count, buffer_capacity, dropped_count,
            last_flush_at, last_flush_succeeded
        ) VALUES (
            $1,$2,$3,$4,$5,
            CASE WHEN $5::varchar = 'long_running' THEN $10::timestamptz + INTERVAL '24 hours'
                 ELSE $10::timestamptz + INTERVAL '7 days' END,
            $6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18
        )
        ON CONFLICT (environment, service_name, service_instance_id) DO UPDATE SET
            release_revision = EXCLUDED.release_revision,
            lifecycle_kind = EXCLUDED.lifecycle_kind,
            expires_at = EXCLUDED.expires_at,
            required_observability = EXCLUDED.required_observability,
            initialized = EXCLUDED.initialized,
            status = EXCLUDED.status,
            export_target = EXCLUDED.export_target,
            last_heartbeat_at = EXCLUDED.last_heartbeat_at,
            last_success_at = EXCLUDED.last_success_at,
            last_error_at = EXCLUDED.last_error_at,
            last_error_code = EXCLUDED.last_error_code,
            buffered_count = EXCLUDED.buffered_count,
            buffer_capacity = EXCLUDED.buffer_capacity,
            dropped_count = EXCLUDED.dropped_count,
            last_flush_at = EXCLUDED.last_flush_at,
            last_flush_succeeded = EXCLUDED.last_flush_succeeded
        RETURNING *
        """,
        heartbeat.environment,
        heartbeat.service_name,
        heartbeat.service_instance_id,
        heartbeat.release_revision,
        heartbeat.lifecycle_kind,
        heartbeat.required_observability,
        heartbeat.initialized,
        heartbeat.status,
        heartbeat.export_target,
        heartbeat.last_heartbeat_at,
        heartbeat.last_success_at,
        heartbeat.last_error_at,
        heartbeat.last_error_code,
        heartbeat.buffered_count,
        heartbeat.buffer_capacity,
        heartbeat.dropped_count,
        heartbeat.last_flush_at,
        heartbeat.last_flush_succeeded,
    )
    if row is None:
        raise RuntimeError("process-health upsert returned no row")
    return _row_to_health(row)


async def cleanup_expired_process_health(
    conn: asyncpg.Connection,
    *,
    now: datetime,
) -> int:
    """Remove only expired evidence; never delete fresh rows to meet a response cap."""
    count = await conn.fetchval(
        """
        WITH deleted AS (
            DELETE FROM telemetry_process_health
            WHERE expires_at <= $1
            RETURNING 1
        )
        SELECT COUNT(*) FROM deleted
        """,
        now,
    )
    return int(count or 0)


async def list_process_health(
    conn: asyncpg.Connection,
    environment: str,
    *,
    now: datetime,
    limit: int = 1000,
) -> tuple[list[TelemetryProcessHealth], int]:
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    rows = await conn.fetch(
        """
        SELECT health.*, COUNT(*) OVER () AS total_count
        FROM telemetry_process_health AS health
        WHERE environment = $1
          AND expires_at > $2
        ORDER BY last_heartbeat_at DESC, service_name, service_instance_id
        LIMIT $3
        """,
        environment,
        now,
        limit,
    )
    total = int(rows[0]["total_count"]) if rows else 0
    return [_row_to_health(row) for row in rows], max(0, total - len(rows))
