"""Typed PostgreSQL projection for bounded operation-attempt evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import asyncpg

OperationStage = Literal[
    "submit",
    "queue_wait",
    "claim",
    "fetch",
    "discover",
    "metadata",
    "transcript",
    "extract",
    "parse",
    "filter",
    "deduplicate",
    "model",
    "fallback",
    "persist",
    "index",
    "graph",
    "deliver",
    "backup",
    "restore",
    "alert",
    "cleanup",
    "flush",
]
OperationOutcome = Literal[
    "succeeded",
    "partial",
    "skipped_policy",
    "skipped_duplicate",
    "filtered",
    "retryable_failure",
    "permanent_failure",
    "cancelled",
]
TelemetryDeliveryState = Literal["pending", "delivered", "degraded", "dropped", "disabled"]


@dataclass(frozen=True, slots=True)
class AttemptStart:
    operation_id: int
    claim_generation: int
    trace_id: str
    root_span_id: str | None
    langfuse_observation_id: str | None
    service_name: str
    service_instance_id: str
    environment: str
    release_revision: str
    started_at: datetime


@dataclass(frozen=True, slots=True)
class AttemptCompletion:
    completed_at: datetime
    terminal_stage: OperationStage | None
    outcome: OperationOutcome | None
    retryable: bool | None
    telemetry_delivery_state: TelemetryDeliveryState
    diagnostic_codes: tuple[str, ...]
    diagnostics_omitted: int


@dataclass(frozen=True, slots=True)
class OperationObservationAttempt:
    operation_id: int
    claim_generation: int
    attempt_number: int
    trace_id: str
    root_span_id: str | None
    langfuse_observation_id: str | None
    service_name: str
    service_instance_id: str
    environment: str
    release_revision: str
    started_at: datetime
    completed_at: datetime | None
    terminal_stage: str | None
    outcome: str | None
    retryable: bool | None
    telemetry_delivery_state: str
    diagnostic_codes: tuple[str, ...]
    diagnostics_omitted: int


def _row_to_attempt(row: Any) -> OperationObservationAttempt:
    return OperationObservationAttempt(
        operation_id=int(row["operation_id"]),
        claim_generation=int(row["claim_generation"]),
        attempt_number=int(row["attempt_number"]),
        trace_id=str(row["trace_id"]),
        root_span_id=row["root_span_id"],
        langfuse_observation_id=row["langfuse_observation_id"],
        service_name=str(row["service_name"]),
        service_instance_id=str(row["service_instance_id"]),
        environment=str(row["environment"]),
        release_revision=str(row["release_revision"]),
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        terminal_stage=row["terminal_stage"],
        outcome=row["outcome"],
        retryable=row["retryable"],
        telemetry_delivery_state=str(row["telemetry_delivery_state"]),
        diagnostic_codes=tuple(row["diagnostic_codes"]),
        diagnostics_omitted=int(row["diagnostics_omitted"]),
    )


async def start_attempt(conn: asyncpg.Connection, attempt: AttemptStart) -> bool:
    """Append attempt identity only when the canonical claim still owns the job."""

    operation_id = await conn.fetchval(
        """
        WITH canonical_claim AS (
            SELECT id, claim_generation, status
            FROM pgqueuer_jobs
            WHERE id = $1
              AND claim_generation = $2::bigint
              AND status = 'in_progress'
            FOR UPDATE
        )
        INSERT INTO operation_observation_attempts (
            operation_id, claim_generation, attempt_number, trace_id, root_span_id,
            langfuse_observation_id, service_name, service_instance_id, environment,
            release_revision, started_at
        )
        SELECT job.id, $2::bigint, $2::bigint + 1, $3, $4, $5, $6, $7, $8, $9, $10
        FROM canonical_claim AS job
        WHERE job.id = $1
          AND job.claim_generation = $2::bigint
          AND job.status = 'in_progress'
        ON CONFLICT (operation_id, claim_generation) DO NOTHING
        RETURNING operation_id
        """,
        attempt.operation_id,
        attempt.claim_generation,
        attempt.trace_id,
        attempt.root_span_id,
        attempt.langfuse_observation_id,
        attempt.service_name,
        attempt.service_instance_id,
        attempt.environment,
        attempt.release_revision,
        attempt.started_at,
    )
    return operation_id is not None


async def complete_attempt(
    conn: asyncpg.Connection,
    operation_id: int,
    claim_generation: int,
    completion: AttemptCompletion,
) -> bool:
    """Complete only the attempt still matching the canonical claim fence."""

    completed_id = await conn.fetchval(
        """
        WITH canonical_claim AS (
            SELECT id, claim_generation, status
            FROM pgqueuer_jobs
            WHERE id = $1
              AND claim_generation = $2::bigint
              AND status = 'in_progress'
            FOR UPDATE
        )
        UPDATE operation_observation_attempts AS attempt
        SET completed_at = $3,
            terminal_stage = $4,
            outcome = $5,
            retryable = $6,
            telemetry_delivery_state = $7,
            diagnostic_codes = $8::operation_diagnostic_code[],
            diagnostics_omitted = $9
        FROM canonical_claim AS job
        WHERE attempt.operation_id = $1
          AND attempt.claim_generation = $2
          AND job.id = attempt.operation_id
          AND job.claim_generation = $2
        RETURNING attempt.operation_id
        """,
        operation_id,
        claim_generation,
        completion.completed_at,
        completion.terminal_stage,
        completion.outcome,
        completion.retryable,
        completion.telemetry_delivery_state,
        list(completion.diagnostic_codes),
        completion.diagnostics_omitted,
    )
    return completed_id is not None


async def record_stale_claim_diagnostic(
    conn: asyncpg.Connection,
    operation_id: int,
    stale_claim_generation: int,
) -> bool:
    """Record only bounded evidence on an attempt superseded by a newer claim."""

    updated_id = await conn.fetchval(
        """
        WITH newer_claim AS (
            SELECT id
            FROM pgqueuer_jobs AS job
            WHERE job.id = $1
              AND job.claim_generation > $2::bigint
            FOR UPDATE
        )
        UPDATE operation_observation_attempts AS attempt
        SET diagnostic_codes = CASE
                WHEN 'queue.stale_claim'::operation_diagnostic_code =
                     ANY(attempt.diagnostic_codes)
                    THEN attempt.diagnostic_codes
                WHEN cardinality(attempt.diagnostic_codes) < 20
                 AND octet_length(array_to_string(
                         array_append(
                             attempt.diagnostic_codes,
                             'queue.stale_claim'::operation_diagnostic_code
                         ),
                         ','
                     )) <= 2048
                    THEN array_append(
                        attempt.diagnostic_codes,
                        'queue.stale_claim'::operation_diagnostic_code
                    )
                ELSE attempt.diagnostic_codes
            END,
            diagnostics_omitted = CASE
                WHEN 'queue.stale_claim'::operation_diagnostic_code =
                     ANY(attempt.diagnostic_codes)
                    THEN attempt.diagnostics_omitted
                WHEN cardinality(attempt.diagnostic_codes) < 20
                 AND octet_length(array_to_string(
                         array_append(
                             attempt.diagnostic_codes,
                             'queue.stale_claim'::operation_diagnostic_code
                         ),
                         ','
                     )) <= 2048
                    THEN attempt.diagnostics_omitted
                WHEN attempt.diagnostics_omitted < 2147483647
                    THEN attempt.diagnostics_omitted + 1
                ELSE attempt.diagnostics_omitted
            END
        FROM newer_claim AS job
        WHERE attempt.operation_id = $1
          AND attempt.claim_generation = $2::bigint
          AND job.id = attempt.operation_id
        RETURNING attempt.operation_id
        """,
        operation_id,
        stale_claim_generation,
    )
    return updated_id is not None


async def list_attempts(
    conn: asyncpg.Connection,
    operation_id: int,
    *,
    after_claim_generation: int | None = None,
    limit: int = 100,
) -> list[OperationObservationAttempt]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    after = -1 if after_claim_generation is None else after_claim_generation
    rows = await conn.fetch(
        """
        SELECT *
        FROM operation_observation_attempts
        WHERE operation_id = $1
          AND claim_generation > $2
        ORDER BY claim_generation ASC
        LIMIT $3
        """,
        operation_id,
        after,
        limit,
    )
    return [_row_to_attempt(row) for row in rows]


async def find_attempts_by_trace(
    conn: asyncpg.Connection,
    trace_id: str,
    *,
    limit: int = 100,
) -> list[OperationObservationAttempt]:
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    rows = await conn.fetch(
        """
        SELECT *
        FROM operation_observation_attempts
        WHERE trace_id = $1
        ORDER BY operation_id, claim_generation
        LIMIT $2
        """,
        trace_id,
        limit,
    )
    return [_row_to_attempt(row) for row in rows]
