"""Durable operation projection and controls over ``pgqueuer_jobs``."""

# ruff: noqa: S608 -- history query fragments are selected from internal static SQL

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any, cast

import asyncpg

from src.contracts.workflow_models import (
    ConfiguredSourceHistoryOutcome,
    IngestionHistoryItem,
    IngestionHistoryPage,
    IngestionOutcome,
    IngestionStatus,
    OperationPage,
    OperationSummary,
    PipelineIngestionSummary,
    PipelineResultV2,
)
from src.ingestion.result_sanitizer import (
    SAFE_INGESTION_DIAGNOSTIC_CODES,
    sanitize_ingestion_diagnostic_code,
)
from src.models.jobs import (
    LEGACY_OPERATION_TYPES,
    JobRecord,
    JobStatus,
    OperationEvent,
    OperationHandle,
    OperationPayloadV2,
    OperationProblem,
    OperationStatus,
    OperationType,
    ResourceReference,
    normalize_operation_payload,
)
from src.queue import setup as queue_setup

_SUMMARY_MESSAGES: dict[JobStatus, str] = {
    JobStatus.QUEUED: "Queued",
    JobStatus.IN_PROGRESS: "In progress",
    JobStatus.COMPLETED: "Completed",
    JobStatus.FAILED: "Failed",
    JobStatus.CANCELLED: "Cancelled",
}
_HISTORY_CURSOR_VERSION = 1
_MAX_HISTORY_CURSOR_LENGTH = 2048
_MAX_HISTORY_CURSOR_BYTES = 1024
_MAX_BIGINT = 9_223_372_036_854_775_807
_SOURCE_KEY_RE = re.compile(r"^src_[a-f0-9]{20}$")
_SAFE_COMMAND_RE = re.compile(r"^[a-z][a-z0-9_]{0,99}$")
_HISTORY_OUTCOMES = frozenset(
    {"success", "zero_items", "partial", "failed", "cancelled", "unknown"}
)
_TERMINAL_STATUSES = frozenset(
    {OperationStatus.COMPLETED, OperationStatus.FAILED, OperationStatus.CANCELLED}
)
_LEGACY_INGESTION_ENTRYPOINTS = ("ingest_content", "extract_url_content")
_LEGACY_COMMAND_BY_ENTRYPOINT = {"extract_url_content": "url"}
_HISTORY_PROBLEM_CODES = SAFE_INGESTION_DIAGNOSTIC_CODES | {
    "operation_failed",
    "source_partial",
}


@dataclass(frozen=True)
class _CompactSourceResult:
    source_key: str
    status: IngestionStatus
    items_ingested: int
    items_failed: int
    error_codes: tuple[str, ...]
    warning_codes: tuple[str, ...]


@dataclass(frozen=True)
class _CompactIngestionResult:
    command_key: str
    outcome: IngestionOutcome
    items_ingested: int
    items_skipped: int
    items_failed: int
    source_outcomes: tuple[_CompactSourceResult, ...]


class OperationError(RuntimeError):
    """Base class for errors exposed by operation adapters."""


class OperationNotFoundError(OperationError):
    """Raised when an operation ID does not exist."""


class OperationConflictError(OperationError):
    """Raised when a control is invalid for the durable operation state."""


class OperationService:
    """Application boundary for submission, observation, and safe controls."""

    def __init__(
        self,
        *,
        connection: asyncpg.Connection | None = None,
        poll_interval: float = queue_setup.DEFAULT_STATUS_POLL_SECONDS,
        max_wait_seconds: float = 30,
        cursor_signing_key: str | None = None,
    ) -> None:
        if poll_interval < 0:
            raise ValueError("poll_interval must be non-negative")
        if max_wait_seconds < 0:
            raise ValueError("max_wait_seconds must be non-negative")
        self._connection = connection
        self._poll_interval = poll_interval
        self._max_wait_seconds = max_wait_seconds
        self._cursor_signing_key = cursor_signing_key

    @staticmethod
    def project(job: JobRecord) -> OperationHandle:
        """Project a queue record into the shared OpenAPI operation shape."""

        payload = normalize_operation_payload(job.entrypoint, job.payload)
        problem = payload.problem
        if job.status is JobStatus.FAILED and problem is None:
            detail = job.error or "Operation failed"
            problem = OperationProblem(
                title="Operation failed",
                status=500,
                detail=detail,
                instance=f"/api/v1/operations/{job.id}",
                code="operation_failed",
            )

        active = job.status in {JobStatus.QUEUED, JobStatus.IN_PROGRESS}
        cancellable = active and payload.cancellable and not payload.cancel_requested
        result = OperationService._project_result(
            payload.operation_type,
            job.status,
            payload.result,
        )
        return OperationHandle(
            operation_id=str(job.id),
            operation_type=payload.operation_type,
            status=OperationStatus(job.status.value),
            progress=payload.progress,
            message=payload.message,
            cancellable=cancellable,
            retry_count=job.retry_count,
            status_url=f"/api/v1/operations/{job.id}",
            events_url=f"/api/v1/operations/{job.id}/events",
            resource=payload.resource,
            result=result,
            problem=problem,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )

    @staticmethod
    def project_summary(job: JobRecord) -> OperationSummary:
        """Project only bounded, non-sensitive fields for collection reads."""

        handle = OperationService.project(job)
        return OperationSummary(
            operation_id=handle.operation_id,
            operation_type=handle.operation_type.value,
            status=handle.status.value,
            progress=handle.progress,
            message=_SUMMARY_MESSAGES[job.status],
            cancellable=handle.cancellable,
            retry_count=handle.retry_count,
            status_url=handle.status_url,
            events_url=handle.events_url,
            created_at=handle.created_at,
            started_at=handle.started_at,
            completed_at=handle.completed_at,
        )

    @staticmethod
    def _project_result(
        operation_type: OperationType,
        status: JobStatus,
        result: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Reconcile pipeline aggregate outcomes with the authoritative lifecycle."""

        if operation_type is not OperationType.PIPELINE_RUN or status not in {
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        }:
            return result

        outcome = status.value
        projected = dict(result or {})
        raw_summary = projected.get("ingestion_summary")
        if isinstance(raw_summary, dict):
            try:
                summary = PipelineIngestionSummary.model_validate(raw_summary).model_copy(
                    update={"outcome": outcome}
                )
            except ValueError:
                summary = PipelineIngestionSummary(
                    outcome=outcome,
                    sources=[],
                    sources_omitted=0,
                )
        else:
            summary = PipelineIngestionSummary(
                outcome=outcome,
                sources=[],
                sources_omitted=0,
            )
        projected["schema_version"] = 2
        projected["ingestion_summary"] = summary.model_dump(mode="json")
        return PipelineResultV2.model_validate(projected).model_dump(mode="json")

    @staticmethod
    def event(
        handle: OperationHandle,
        *,
        sequence: int = 0,
        occurred_at: datetime | None = None,
    ) -> OperationEvent:
        """Encode the latest operation snapshot as a progress event."""

        if sequence < 0:
            raise ValueError("sequence must be non-negative")
        return OperationEvent(
            event_id=f"{handle.operation_id}:{sequence}",
            operation_id=handle.operation_id,
            operation_type=handle.operation_type,
            status=handle.status,
            progress=handle.progress,
            message=handle.message,
            resource=handle.resource,
            problem=handle.problem,
            occurred_at=occurred_at or datetime.now(UTC),
        )

    async def submit(
        self,
        operation_type: OperationType,
        normalized_input: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        priority: int = 0,
        parent_job_id: int | None = None,
        cancellable: bool = True,
    ) -> OperationHandle:
        """Submit a schema-v2 operation or return its active duplicate."""

        payload_model = OperationPayloadV2(
            operation_type=operation_type,
            input=normalized_input,
            cancellable=cancellable,
        )
        payload = payload_model.model_dump(mode="json")
        key = idempotency_key or self._derive_idempotency_key(
            operation_type,
            payload["input"],
        )
        job_id, _created = await queue_setup.enqueue_queue_job(
            operation_type.value,
            payload,
            priority=priority,
            parent_job_id=parent_job_id,
            conn=self._connection,
            idempotency_key=key,
        )
        return await self.get(str(job_id))

    async def submit_child(
        self,
        parent_operation_id: str | int,
        operation_type: OperationType,
        normalized_input: dict[str, Any],
        *,
        idempotency_key: str,
        priority: int = 0,
        cancellable: bool = True,
    ) -> OperationHandle:
        """Submit or recover one parent-scoped child, including terminal children."""

        parent_job_id = self._parse_operation_id(parent_operation_id)
        effective_key = f"parent:{parent_job_id}:{idempotency_key}"
        existing = await queue_setup.get_child_job_by_idempotency_key(
            parent_job_id,
            operation_type.value,
            effective_key,
            conn=self._connection,
        )
        if existing is not None:
            return self.project(existing)

        payload = OperationPayloadV2(
            operation_type=operation_type,
            input=normalized_input,
            cancellable=cancellable,
        ).model_dump(mode="json")
        job_id, _created = await queue_setup.enqueue_queue_job(
            operation_type.value,
            payload,
            priority=priority,
            parent_job_id=parent_job_id,
            conn=self._connection,
            idempotency_key=effective_key,
        )
        return await self.get(job_id)

    async def get(self, operation_id: str | int) -> OperationHandle:
        job_id = self._parse_operation_id(operation_id)
        return self.project(await self._get_job(job_id))

    async def wait(
        self,
        operation_id: str | int,
        *,
        timeout_seconds: float,
    ) -> OperationHandle:
        """Wait up to the configured bound, returning the latest state on timeout."""

        timeout = min(max(timeout_seconds, 0), self._max_wait_seconds)
        deadline = monotonic() + timeout
        latest = await self.get(operation_id)
        while not latest.is_terminal and monotonic() < deadline:
            remaining = deadline - monotonic()
            await asyncio.sleep(min(self._poll_interval, max(remaining, 0)))
            latest = await self.get(operation_id)
        return latest

    async def list(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        status: OperationStatus | None = None,
    ) -> OperationPage:
        """List canonical operations with a stable, opaque keyset cursor."""

        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        before_created_at, before_id = self._decode_cursor(cursor)
        async with queue_setup._queue_connection(self._connection) as conn:
            rows = await conn.fetch(
                """
                SELECT id, entrypoint, status, payload, priority, error,
                       retry_count, parent_job_id, heartbeat_at, created_at,
                       started_at, completed_at
                FROM pgqueuer_jobs
                WHERE (
                    ($1::timestamptz IS NULL)
                    OR (created_at, id) < ($1::timestamptz, $2::bigint)
                )
                  AND (
                    payload->>'schema_version' = '2'
                    OR entrypoint = ANY($3::text[])
                  )
                  AND ($4::text IS NULL OR status = $4::text)
                ORDER BY created_at DESC, id DESC
                LIMIT $5
                """,
                before_created_at,
                before_id,
                list(LEGACY_OPERATION_TYPES),
                status.value if status is not None else None,
                limit + 1,
            )

        jobs = [self._job_from_row(row) for row in rows[:limit]]
        summaries = [self.project_summary(job) for job in jobs]
        next_cursor = None
        if len(rows) > limit and jobs:
            last = jobs[-1]
            next_cursor = self._encode_cursor(last.created_at, last.id)
        return OperationPage(data=summaries, next_cursor=next_cursor)

    async def list_ingestion_history(
        self,
        *,
        command_key: str | None = None,
        configured_source_key: str | None = None,
        outcome: str | None = None,
        status: OperationStatus | str | None = None,
        parent_operation_id: str | int | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> IngestionHistoryPage:
        """List compact terminal ingestion projections with fixed-filter pagination."""

        filters, normalized_values = self._normalize_history_filters(
            command_key=command_key,
            configured_source_key=configured_source_key,
            outcome=outcome,
            status=status,
            parent_operation_id=parent_operation_id,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
        )
        signing_key = self._history_cursor_signing_key()
        before_created_at, before_id = self._decode_history_cursor(
            cursor,
            filters=filters,
            signing_key=signing_key,
        )
        id_prefilters = []
        if normalized_values["configured_source_key"] is not None:
            id_prefilters.append(
                """
                    jsonb_typeof(payload->'result'->'source_outcomes') = 'array'
                    AND (
                        (
                            jsonb_typeof(payload->'schema_version') = 'number'
                            AND (payload->'schema_version')::text = '2'
                            AND payload->>'operation_type' = 'ingestion.execute'
                        )
                        OR (
                            NOT COALESCE(
                                jsonb_typeof(payload->'schema_version') = 'number'
                                AND (payload->'schema_version')::text = '2',
                                FALSE
                            )
                            AND entrypoint = ANY($10::text[])
                        )
                    )
                    AND payload->'result'->'source_outcomes' @>
                          jsonb_build_array(
                              jsonb_build_object('source_key', $4::text)
                          )
                """
            )
        if normalized_values["parent_operation_id"] is not None:
            id_prefilters.append(
                "parent_job_id = $7::bigint AND status IN ('completed', 'failed', 'cancelled')"
            )
        id_prefilter_cte = ""
        candidate_source = "pgqueuer_jobs"
        if id_prefilters:
            id_prefilter_cte = f"""
                prefiltered_ids AS MATERIALIZED (
                    SELECT id
                    FROM pgqueuer_jobs
                    WHERE {" AND ".join(f"({predicate})" for predicate in id_prefilters)}
                ),
                prefiltered_rows AS MATERIALIZED (
                    SELECT selected_job.*
                    FROM prefiltered_ids
                    CROSS JOIN LATERAL (
                        SELECT *
                        FROM pgqueuer_jobs AS selected_job
                        WHERE selected_job.id = prefiltered_ids.id
                        OFFSET 0
                    ) AS selected_job
                ),
            """
            candidate_source = "prefiltered_rows AS pgqueuer_jobs"
        async with queue_setup._queue_connection(self._connection) as conn:
            # Interpolated fragments above are selected from internal static SQL only.
            rows = await conn.fetch(
                rf"""
                WITH {id_prefilter_cte}
                candidates AS (
                    SELECT id, entrypoint, status, payload, priority, error,
                           retry_count, parent_job_id, heartbeat_at, created_at,
                           started_at, completed_at,
                           (
                               jsonb_typeof(payload->'result') = 'object'
                               AND jsonb_typeof(payload->'result'->'schema_version') = 'number'
                               AND (payload->'result'->'schema_version')::text = '2'
                               AND jsonb_typeof(payload->'result'->'command_key') = 'string'
                               AND payload->'result'->>'command_key'
                                   ~ '^[a-z][a-z0-9_]{{0,99}}$'
                               AND jsonb_typeof(payload->'result'->'outcome') = 'string'
                               AND payload->'result'->>'outcome' IN (
                                   'success', 'zero_items', 'partial',
                                   'failed', 'cancelled', 'unknown'
                               )
                               AND jsonb_typeof(payload->'result'->'items_ingested') = 'number'
                               AND (payload->'result'->'items_ingested')::text
                                   ~ '^(0|[1-9][0-9]*)$'
                               AND jsonb_typeof(payload->'result'->'items_skipped') = 'number'
                               AND (payload->'result'->'items_skipped')::text
                                   ~ '^(0|[1-9][0-9]*)$'
                               AND jsonb_typeof(payload->'result'->'items_failed') = 'number'
                               AND (payload->'result'->'items_failed')::text
                                   ~ '^(0|[1-9][0-9]*)$'
                               AND jsonb_typeof(payload->'result'->'source_outcomes') = 'array'
                           ) AS compact_result_eligible
                    FROM {candidate_source}
                    WHERE status IN ('completed', 'failed', 'cancelled')
                      AND (
                          (
                              jsonb_typeof(payload->'schema_version') = 'number'
                              AND (payload->'schema_version')::text = '2'
                              AND payload->>'operation_type' = 'ingestion.execute'
                          )
                          OR (
                              NOT COALESCE(
                                  jsonb_typeof(payload->'schema_version') = 'number'
                                  AND (payload->'schema_version')::text = '2',
                                  FALSE
                              )
                              AND entrypoint = ANY($10::text[])
                          )
                      )
                ),
                history AS (
                    SELECT id, entrypoint, status, payload, priority, error,
                           retry_count, parent_job_id, heartbeat_at, created_at,
                           started_at, completed_at, compact_result_eligible,
                           CASE
                               WHEN compact_result_eligible
                                   THEN payload->'result'->>'command_key'
                               WHEN jsonb_typeof(payload->'input'->'kind') = 'string'
                                AND payload->'input'->>'kind'
                                    ~ '^[a-z][a-z0-9_]{{0,99}}$'
                                   THEN payload->'input'->>'kind'
                               WHEN jsonb_typeof(payload->'source') = 'string'
                                AND payload->>'source' ~ '^[a-z][a-z0-9_]{{0,99}}$'
                                   THEN payload->>'source'
                               WHEN entrypoint = 'extract_url_content' THEN 'url'
                               ELSE 'unknown'
                           END AS history_command_key,
                           CASE
                               WHEN status = 'failed' THEN 'failed'
                               WHEN status = 'cancelled' THEN 'cancelled'
                               WHEN compact_result_eligible
                                   THEN payload->'result'->>'outcome'
                               ELSE 'unknown'
                           END AS history_outcome
                    FROM candidates
                )
                SELECT id, entrypoint, status, payload, priority, error,
                       retry_count, parent_job_id, heartbeat_at, created_at,
                       started_at, completed_at
                FROM history
                WHERE (
                    $1::timestamptz IS NULL
                    OR (created_at, id) < ($1::timestamptz, $2::bigint)
                )
                  AND ($3::text IS NULL OR history_command_key = $3::text)
                  AND (
                      $4::text IS NULL
                      OR (
                          compact_result_eligible
                          AND payload->'result'->'source_outcomes' @>
                              jsonb_build_array(
                                  jsonb_build_object('source_key', $4::text)
                              )
                          AND EXISTS (
                          SELECT 1
                          FROM jsonb_array_elements(
                              CASE
                                  WHEN jsonb_typeof(payload->'result'->'source_outcomes') = 'array'
                                      THEN payload->'result'->'source_outcomes'
                                  ELSE '[]'::jsonb
                              END
                          ) WITH ORDINALITY AS source_outcome(
                              source_value, source_ordinality
                          )
                          WHERE source_ordinality <= 100
                            AND jsonb_typeof(source_value) = 'object'
                            AND jsonb_typeof(source_value->'source_key') = 'string'
                            AND source_value->>'source_key'
                                ~ '^src_[a-f0-9]{{20}}$'
                            AND source_value->>'source_key' = $4::text
                            AND jsonb_typeof(source_value->'status') = 'string'
                            AND source_value->>'status' IN ('ok', 'partial', 'error')
                            AND jsonb_typeof(source_value->'items_ingested') = 'number'
                            AND (source_value->'items_ingested')::text
                                ~ '^(0|[1-9][0-9]*)$'
                            AND jsonb_typeof(source_value->'items_failed') = 'number'
                            AND (source_value->'items_failed')::text
                                ~ '^(0|[1-9][0-9]*)$'
                          )
                      )
                  )
                  AND ($5::text IS NULL OR history_outcome = $5::text)
                  AND ($6::text IS NULL OR status = $6::text)
                  AND ($7::bigint IS NULL OR parent_job_id = $7::bigint)
                  AND ($8::timestamptz IS NULL OR created_at >= $8::timestamptz)
                  AND ($9::timestamptz IS NULL OR created_at < $9::timestamptz)
                ORDER BY created_at DESC, id DESC
                LIMIT $11
                """,
                before_created_at,
                before_id,
                normalized_values["command_key"],
                normalized_values["configured_source_key"],
                normalized_values["outcome"],
                normalized_values["status"],
                normalized_values["parent_operation_id"],
                normalized_values["created_after"],
                normalized_values["created_before"],
                list(_LEGACY_INGESTION_ENTRYPOINTS),
                limit + 1,
            )

        jobs = [self._job_from_row(row) for row in rows[:limit]]
        items = [self._project_ingestion_history(job) for job in jobs]
        next_cursor = None
        if len(rows) > limit and jobs:
            last = jobs[-1]
            next_cursor = self._encode_history_cursor(
                last.created_at,
                last.id,
                filters=filters,
                signing_key=signing_key,
            )
        return IngestionHistoryPage(data=items, next_cursor=next_cursor)

    @staticmethod
    def _project_ingestion_history(job: JobRecord) -> IngestionHistoryItem:
        payload = job.payload if isinstance(job.payload, dict) else {}
        result = OperationService._compact_history_result(payload.get("result"))

        command_key = OperationService._history_command_key(job.entrypoint, payload, result)
        if job.status is JobStatus.FAILED:
            history_outcome = "failed"
        elif job.status is JobStatus.CANCELLED:
            history_outcome = "cancelled"
        elif result is not None:
            history_outcome = result.outcome
        else:
            history_outcome = "unknown"

        source_outcomes: list[ConfiguredSourceHistoryOutcome] = []
        if result is not None:
            for source in result.source_outcomes:
                if source.status == "error":
                    source_history_outcome = "failed"
                elif source.status == "partial":
                    source_history_outcome = "partial"
                elif source.items_ingested:
                    source_history_outcome = "success"
                else:
                    source_history_outcome = "zero_items"
                source_outcomes.append(
                    ConfiguredSourceHistoryOutcome(
                        source_key=source.source_key,
                        status=source.status,
                        outcome=source_history_outcome,
                        items_ingested=source.items_ingested,
                        items_failed=source.items_failed,
                        error_codes=list(source.error_codes) or None,
                        warning_codes=list(source.warning_codes) or None,
                    )
                )

        raw_problem = payload.get("problem")
        raw_problem_code = raw_problem.get("code") if isinstance(raw_problem, dict) else None
        problem_code = (
            raw_problem_code
            if isinstance(raw_problem_code, str) and raw_problem_code in _HISTORY_PROBLEM_CODES
            else ("operation_failed" if job.status is JobStatus.FAILED else None)
        )
        return IngestionHistoryItem(
            operation_id=str(job.id),
            parent_operation_id=str(job.parent_job_id) if job.parent_job_id is not None else None,
            command_key=command_key,
            operation_status=job.status.value,
            outcome=history_outcome,
            items_ingested=result.items_ingested if result is not None else None,
            items_skipped=result.items_skipped if result is not None else None,
            items_failed=result.items_failed if result is not None else None,
            source_outcomes=source_outcomes,
            retry_count=job.retry_count,
            problem_code=problem_code,
            status_url=f"/api/v1/operations/{job.id}",
            created_at=job.created_at,
            completed_at=job.completed_at,
        )

    @staticmethod
    def _compact_history_result(raw_result: object) -> _CompactIngestionResult | None:
        if not isinstance(raw_result, dict):
            return None
        if type(raw_result.get("schema_version")) is not int:
            return None
        if raw_result["schema_version"] != 2:
            return None

        command_key = raw_result.get("command_key")
        outcome = raw_result.get("outcome")
        if not isinstance(command_key, str) or not _SAFE_COMMAND_RE.fullmatch(command_key):
            return None
        if not isinstance(outcome, str) or outcome not in _HISTORY_OUTCOMES:
            return None

        counts: list[int] = []
        for field in ("items_ingested", "items_skipped", "items_failed"):
            value = raw_result.get(field)
            if type(value) is not int or value < 0:
                return None
            counts.append(value)

        raw_sources = raw_result.get("source_outcomes")
        if not isinstance(raw_sources, list):
            return None
        source_outcomes = tuple(
            parsed
            for raw_source in raw_sources[:100]
            if (parsed := OperationService._compact_history_source(raw_source)) is not None
        )
        return _CompactIngestionResult(
            command_key=command_key,
            outcome=cast(IngestionOutcome, outcome),
            items_ingested=counts[0],
            items_skipped=counts[1],
            items_failed=counts[2],
            source_outcomes=source_outcomes,
        )

    @staticmethod
    def _compact_history_source(raw_source: object) -> _CompactSourceResult | None:
        if not isinstance(raw_source, dict):
            return None
        source_key = raw_source.get("source_key")
        status = raw_source.get("status")
        items_ingested = raw_source.get("items_ingested")
        items_failed = raw_source.get("items_failed")
        if not isinstance(source_key, str) or not _SOURCE_KEY_RE.fullmatch(source_key):
            return None
        if not isinstance(status, str) or status not in {"ok", "partial", "error"}:
            return None
        if type(items_ingested) is not int or items_ingested < 0:
            return None
        if type(items_failed) is not int or items_failed < 0:
            return None
        return _CompactSourceResult(
            source_key=source_key,
            status=cast(IngestionStatus, status),
            items_ingested=items_ingested,
            items_failed=items_failed,
            error_codes=OperationService._history_machine_codes(raw_source.get("errors")),
            warning_codes=OperationService._history_machine_codes(raw_source.get("warnings")),
        )

    @staticmethod
    def _history_machine_codes(raw_diagnostics: object) -> tuple[str, ...]:
        if not isinstance(raw_diagnostics, list):
            return ()
        codes: list[str] = []
        seen: set[str] = set()
        for diagnostic in raw_diagnostics:
            raw_code = diagnostic.get("code") if isinstance(diagnostic, dict) else None
            code = sanitize_ingestion_diagnostic_code(raw_code)
            if code not in seen:
                seen.add(code)
                codes.append(code)
                if len(codes) == 20:
                    break
        return tuple(codes)

    @staticmethod
    def _history_command_key(
        entrypoint: str,
        payload: dict[str, Any],
        result: _CompactIngestionResult | None,
    ) -> str:
        candidates: list[object] = [result.command_key if result is not None else None]
        raw_input = payload.get("input")
        candidates.append(raw_input.get("kind") if isinstance(raw_input, dict) else None)
        candidates.append(payload.get("source"))
        candidates.append(_LEGACY_COMMAND_BY_ENTRYPOINT.get(entrypoint))
        for candidate in candidates:
            if isinstance(candidate, str) and _SAFE_COMMAND_RE.fullmatch(candidate):
                return candidate
        return "unknown"

    @staticmethod
    def _normalize_history_filters(
        *,
        command_key: str | None,
        configured_source_key: str | None,
        outcome: str | None,
        status: OperationStatus | str | None,
        parent_operation_id: str | int | None,
        created_after: datetime | None,
        created_before: datetime | None,
        limit: int,
    ) -> tuple[dict[str, str], dict[str, object | None]]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        if command_key is not None and not 1 <= len(command_key) <= 100:
            raise ValueError("command_key must be between 1 and 100 characters")
        if configured_source_key is not None and not _SOURCE_KEY_RE.fullmatch(
            configured_source_key
        ):
            raise ValueError("configured_source_key must be an opaque source key")
        if outcome is not None and outcome not in _HISTORY_OUTCOMES:
            raise ValueError("Invalid ingestion outcome")
        normalized_status = OperationStatus(status) if status is not None else None
        if normalized_status is not None and normalized_status not in _TERMINAL_STATUSES:
            raise ValueError("Ingestion history status must be terminal")

        normalized_parent: int | None = None
        if parent_operation_id is not None:
            try:
                normalized_parent = int(parent_operation_id)
            except (TypeError, ValueError) as exc:
                raise ValueError("parent_operation_id must be a positive bigint") from exc
            if normalized_parent < 1 or normalized_parent > _MAX_BIGINT:
                raise ValueError("parent_operation_id must be a positive bigint")

        normalized_after = OperationService._normalize_history_datetime(
            created_after, "created_after"
        )
        normalized_before = OperationService._normalize_history_datetime(
            created_before, "created_before"
        )
        if (
            normalized_after is not None
            and normalized_before is not None
            and normalized_after >= normalized_before
        ):
            raise ValueError("created_after must be earlier than created_before")

        values: dict[str, object | None] = {
            "command_key": command_key,
            "configured_source_key": configured_source_key,
            "outcome": outcome,
            "status": normalized_status.value if normalized_status is not None else None,
            "parent_operation_id": normalized_parent,
            "created_after": normalized_after,
            "created_before": normalized_before,
        }
        filters = {
            key: OperationService._history_filter_value(value)
            for key, value in values.items()
            if value is not None
        }
        return filters, values

    @staticmethod
    def _normalize_history_datetime(value: datetime | None, field: str) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field} must include a timezone")
        return value.astimezone(UTC)

    @staticmethod
    def _history_filter_value(value: object) -> str:
        if isinstance(value, datetime):
            return value.isoformat().replace("+00:00", "Z")
        return str(value)

    def _history_cursor_signing_key(self) -> bytes:
        key = self._cursor_signing_key
        if key is None:
            from src.config.settings import get_settings

            key = get_settings().get_operation_cursor_signing_key()
        if len(key.encode("utf-8")) < 32:
            raise RuntimeError("OPERATION_CURSOR_SIGNING_KEY must be at least 32 bytes")
        return key.encode("utf-8")

    @staticmethod
    def _encode_history_cursor(
        created_at: datetime,
        operation_id: int,
        *,
        filters: dict[str, str],
        signing_key: bytes,
    ) -> str:
        payload = {
            "v": _HISTORY_CURSOR_VERSION,
            "position": {
                "created_at": OperationService._history_filter_value(created_at.astimezone(UTC)),
                "id": str(operation_id),
            },
            "filters": filters,
        }
        encoded_payload = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        envelope = {
            "payload": payload,
            "signature": hmac.new(signing_key, encoded_payload, hashlib.sha256).hexdigest(),
        }
        raw = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
        if len(raw) > _MAX_HISTORY_CURSOR_BYTES:
            raise ValueError("Invalid ingestion history cursor")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_history_cursor(
        cursor: str | None,
        *,
        filters: dict[str, str],
        signing_key: bytes,
    ) -> tuple[datetime | None, int]:
        if cursor is None:
            return None, 0
        try:
            if len(cursor) > _MAX_HISTORY_CURSOR_LENGTH:
                raise ValueError("cursor is too long")
            padded = cursor + "=" * (-len(cursor) % 4)
            raw = base64.b64decode(padded, altchars=b"-_", validate=True)
            if len(raw) > _MAX_HISTORY_CURSOR_BYTES:
                raise ValueError("decoded cursor is too large")
            envelope = json.loads(raw.decode("utf-8"))
            if not isinstance(envelope, dict) or set(envelope) != {"payload", "signature"}:
                raise ValueError("invalid envelope")
            payload = envelope["payload"]
            signature = envelope["signature"]
            if not isinstance(payload, dict) or not isinstance(signature, str):
                raise ValueError("invalid envelope values")
            encoded_payload = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            expected = hmac.new(signing_key, encoded_payload, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError("invalid signature")
            if set(payload) != {"v", "position", "filters"}:
                raise ValueError("invalid payload")
            if payload["v"] != _HISTORY_CURSOR_VERSION or payload["filters"] != filters:
                raise ValueError("cursor query mismatch")
            position = payload["position"]
            if not isinstance(position, dict) or set(position) != {"created_at", "id"}:
                raise ValueError("invalid position")
            raw_id = position["id"]
            if not isinstance(raw_id, str) or not raw_id.isdigit() or len(raw_id) > 19:
                raise ValueError("invalid bigint")
            operation_id = int(raw_id)
            if operation_id < 1 or operation_id > _MAX_BIGINT:
                raise ValueError("invalid bigint")
            raw_created_at = position["created_at"]
            if not isinstance(raw_created_at, str) or len(raw_created_at) > 64:
                raise ValueError("invalid timestamp")
            created_at = datetime.fromisoformat(raw_created_at.replace("Z", "+00:00"))
            normalized_created_at = OperationService._normalize_history_datetime(
                created_at, "cursor created_at"
            )
            if (
                normalized_created_at is None
                or OperationService._history_filter_value(normalized_created_at) != raw_created_at
            ):
                raise ValueError("non-canonical timestamp")
        except (
            binascii.Error,
            json.JSONDecodeError,
            TypeError,
            UnicodeDecodeError,
            ValueError,
        ) as exc:
            raise ValueError("Invalid ingestion history cursor") from exc
        return normalized_created_at, operation_id

    async def update_progress(
        self,
        operation_id: str | int,
        progress: int,
        message: str,
    ) -> OperationHandle:
        if progress < 0 or progress > 100:
            raise ValueError("progress must be between 0 and 100")
        job_id = self._parse_operation_id(operation_id)
        row = await self._update_returning(
            """
            UPDATE pgqueuer_jobs
            SET payload = COALESCE(payload, '{}'::jsonb) || $1::jsonb,
                heartbeat_at = NOW()
            WHERE id = $2 AND status = 'in_progress'
            RETURNING id, entrypoint, status, payload, priority, error,
                      retry_count, parent_job_id, heartbeat_at, created_at,
                      started_at, completed_at
            """,
            json.dumps({"progress": progress, "message": message}),
            job_id,
        )
        return self._require_updated(row, operation_id, "cannot accept progress updates")

    async def defer(
        self,
        operation_id: str | int,
        *,
        checkpoint: dict[str, Any],
        progress: int,
        message: str,
    ) -> OperationHandle:
        """Atomically checkpoint and release running work back to the queue."""

        if progress < 0 or progress > 99:
            raise ValueError("deferred progress must be between 0 and 99")
        job_id = self._parse_operation_id(operation_id)
        patch = json.dumps({"result": checkpoint, "progress": progress, "message": message})
        row = await self._update_returning(
            """
            UPDATE pgqueuer_jobs
            SET status = 'queued',
                payload = COALESCE(payload, '{}'::jsonb) || $1::jsonb,
                priority = LEAST(priority, -1),
                execute_after = NOW() + INTERVAL '1 second',
                started_at = NULL,
                heartbeat_at = NOW()
            WHERE id = $2 AND status = 'in_progress'
            RETURNING id, entrypoint, status, payload, priority, error,
                      retry_count, parent_job_id, heartbeat_at, created_at,
                      started_at, completed_at
            """,
            patch,
            job_id,
        )
        return self._require_updated(row, operation_id, "cannot be deferred")

    async def attach_resource(
        self,
        operation_id: str | int,
        resource: ResourceReference,
    ) -> OperationHandle:
        return await self._attach_payload(
            operation_id,
            {"resource": resource.model_dump(mode="json")},
            action="cannot attach a resource",
        )

    async def attach_result(
        self,
        operation_id: str | int,
        result: dict[str, Any],
    ) -> OperationHandle:
        return await self._attach_payload(
            operation_id,
            {"result": result},
            action="cannot attach a result",
        )

    async def attach_completion(
        self,
        operation_id: str | int,
        *,
        result: dict[str, Any],
        resource: ResourceReference,
        message: str,
    ) -> OperationHandle:
        """Atomically project a workflow's final result, resource, and progress."""

        job_id = self._parse_operation_id(operation_id)
        patch = json.dumps(
            {
                "result": result,
                "resource": resource.model_dump(mode="json"),
                "progress": 100,
                "message": message,
            }
        )
        row = await self._update_returning(
            """
            UPDATE pgqueuer_jobs
            SET payload = COALESCE(payload, '{}'::jsonb) || $1::jsonb,
                heartbeat_at = NOW()
            WHERE id = $2 AND status = 'in_progress'
            RETURNING id, entrypoint, status, payload, priority, error,
                      retry_count, parent_job_id, heartbeat_at, created_at,
                      started_at, completed_at
            """,
            patch,
            job_id,
        )
        return self._require_updated(row, operation_id, "cannot attach completion")

    async def cancel(self, operation_id: str | int) -> OperationHandle:
        """Cancel queued work or request cancellation of running work atomically."""

        job_id = self._parse_operation_id(operation_id)
        row = await self._update_returning(
            """
            UPDATE pgqueuer_jobs
            SET status = CASE WHEN status = 'queued' THEN 'cancelled' ELSE status END,
                payload = COALESCE(payload, '{}'::jsonb) || jsonb_build_object(
                    'cancel_requested', TRUE,
                    'message', CASE
                        WHEN status = 'queued' THEN 'Cancelled'
                        ELSE 'Cancellation requested'
                    END
                ),
                completed_at = CASE WHEN status = 'queued' THEN NOW() ELSE completed_at END,
                heartbeat_at = NOW()
            WHERE id = $1
              AND status IN ('queued', 'in_progress')
              AND COALESCE((payload->>'cancellable')::boolean, TRUE)
              AND NOT COALESCE((payload->>'cancel_requested')::boolean, FALSE)
            RETURNING id, entrypoint, status, payload, priority, error,
                      retry_count, parent_job_id, heartbeat_at, created_at,
                      started_at, completed_at
            """,
            job_id,
        )
        if row is not None:
            return self.project(self._job_from_row(row))

        job = await self._get_job(job_id)
        current = self.project(job)
        payload = normalize_operation_payload(job.entrypoint, job.payload)
        if current.status is OperationStatus.CANCELLED or (
            current.status is OperationStatus.IN_PROGRESS and payload.cancel_requested
        ):
            return current
        raise OperationConflictError(
            f"Operation {operation_id} cannot be cancelled from state {current.status.value}"
        )

    async def retry(self, operation_id: str | int) -> OperationHandle:
        """Requeue failed work while retaining durable pipeline checkpoints."""

        job_id = self._parse_operation_id(operation_id)
        reset = {
            "progress": 0,
            "message": "Queued",
            "cancel_requested": False,
            "resource": None,
            "result": None,
            "problem": None,
        }
        try:
            row = await self._update_returning(
                """
                WITH retried_children AS (
                    UPDATE pgqueuer_jobs AS child
                    SET status = 'queued',
                        payload = COALESCE(child.payload, '{}'::jsonb) || $1::jsonb,
                        error = NULL,
                        retry_count = child.retry_count + 1,
                        started_at = NULL,
                        completed_at = NULL,
                        execute_after = NOW(),
                        heartbeat_at = NOW()
                    WHERE child.parent_job_id = $2
                      AND child.status IN ('failed', 'cancelled')
                      AND child.id = ANY (
                          SELECT jsonb_array_elements_text(
                              COALESCE(
                                  pipeline_parent.payload->'result'->'retry_child_operation_ids',
                                  '[]'::jsonb
                              )
                          )::bigint
                          FROM pgqueuer_jobs AS pipeline_parent
                          WHERE pipeline_parent.id = $2
                            AND pipeline_parent.entrypoint = 'pipeline.run'
                            AND pipeline_parent.status = 'failed'
                      )
                    RETURNING child.id
                )
                UPDATE pgqueuer_jobs AS parent
                SET status = 'queued',
                    payload = (COALESCE(parent.payload, '{}'::jsonb) || $1::jsonb) ||
                        CASE
                            WHEN parent.entrypoint = 'pipeline.run'
                                AND parent.payload->'result' IS NOT NULL
                            THEN jsonb_build_object('result', parent.payload->'result')
                            ELSE '{}'::jsonb
                        END,
                    error = NULL,
                    retry_count = retry_count + 1,
                    started_at = NULL,
                    completed_at = NULL,
                    execute_after = NOW(),
                    heartbeat_at = NOW()
                WHERE parent.id = $2 AND parent.status = 'failed'
                RETURNING id, entrypoint, status, payload, priority, error,
                          retry_count, parent_job_id, heartbeat_at, created_at,
                          started_at, completed_at
                """,
                json.dumps(reset),
                job_id,
            )
        except asyncpg.UniqueViolationError as exc:
            raise OperationConflictError(
                f"Operation {operation_id} cannot be retried while an equivalent operation is active"
            ) from exc
        if row is None:
            current = await self.get(operation_id)
            raise OperationConflictError(
                f"Operation {operation_id} cannot be retried from state {current.status.value}"
            )
        async with queue_setup._queue_connection(self._connection) as conn:
            await conn.execute("SELECT pg_notify('pgqueuer', $1)", "operation_retry")
        return self.project(self._job_from_row(row))

    async def checkpoint_cancellation(
        self,
        operation_id: str | int,
    ) -> OperationHandle | None:
        """Transition requested running work at a workflow-declared safe point."""

        job_id = self._parse_operation_id(operation_id)
        row = await self._update_returning(
            """
            UPDATE pgqueuer_jobs
            SET status = 'cancelled',
                payload = COALESCE(payload, '{}'::jsonb) ||
                          '{"message":"Cancelled"}'::jsonb,
                completed_at = NOW(),
                heartbeat_at = NOW()
            WHERE id = $1
              AND status = 'in_progress'
              AND COALESCE((payload->>'cancel_requested')::boolean, FALSE)
            RETURNING id, entrypoint, status, payload, priority, error,
                      retry_count, parent_job_id, heartbeat_at, created_at,
                      started_at, completed_at
            """,
            job_id,
        )
        return self.project(self._job_from_row(row)) if row is not None else None

    async def _attach_payload(
        self,
        operation_id: str | int,
        patch: dict[str, Any],
        *,
        action: str,
    ) -> OperationHandle:
        job_id = self._parse_operation_id(operation_id)
        row = await self._update_returning(
            """
            UPDATE pgqueuer_jobs
            SET payload = COALESCE(payload, '{}'::jsonb) || $1::jsonb,
                heartbeat_at = NOW()
            WHERE id = $2 AND status = 'in_progress'
            RETURNING id, entrypoint, status, payload, priority, error,
                      retry_count, parent_job_id, heartbeat_at, created_at,
                      started_at, completed_at
            """,
            json.dumps(patch),
            job_id,
        )
        return self._require_updated(row, operation_id, action)

    async def _update_returning(self, query: str, *args: Any) -> Any:
        async with queue_setup._queue_connection(self._connection) as conn:
            return await conn.fetchrow(query, *args)

    async def _get_job(self, job_id: int) -> JobRecord:
        job = await queue_setup.get_job_status(job_id, conn=self._connection)
        if job is None:
            raise OperationNotFoundError(f"Operation {job_id} was not found")
        return job

    def _require_updated(
        self,
        row: Any,
        operation_id: str | int,
        action: str,
    ) -> OperationHandle:
        if row is None:
            raise OperationConflictError(f"Operation {operation_id} {action}")
        return self.project(self._job_from_row(row))

    @staticmethod
    def _job_from_row(row: Any) -> JobRecord:
        payload = row["payload"] or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        return JobRecord(
            id=int(row["id"]),
            entrypoint=str(row["entrypoint"]),
            status=JobStatus(row["status"]),
            payload=payload,
            priority=int(row["priority"] or 0),
            error=row["error"],
            retry_count=int(row["retry_count"] or 0),
            parent_job_id=row["parent_job_id"],
            heartbeat_at=row["heartbeat_at"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )

    @staticmethod
    def _derive_idempotency_key(
        operation_type: OperationType,
        normalized_input: dict[str, Any],
    ) -> str:
        canonical = json.dumps(normalized_input, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"operation:{operation_type.value}:{digest}"

    @staticmethod
    def _parse_operation_id(operation_id: str | int) -> int:
        try:
            parsed = int(operation_id)
        except (TypeError, ValueError) as exc:
            raise OperationNotFoundError(f"Invalid operation ID: {operation_id}") from exc
        if parsed < 1:
            raise OperationNotFoundError(f"Invalid operation ID: {operation_id}")
        return parsed

    @staticmethod
    def _encode_cursor(created_at: datetime, job_id: int) -> str:
        payload = json.dumps(
            {"created_at": created_at.isoformat(), "id": job_id},
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str | None) -> tuple[datetime | None, int]:
        if cursor is None:
            return None, 0
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
            created_at = datetime.fromisoformat(payload["created_at"])
            if created_at.tzinfo is None:
                raise ValueError("cursor timestamp must include a timezone")
            job_id = int(payload["id"])
            if job_id < 1:
                raise ValueError("cursor job ID must be positive")
        except (
            binascii.Error,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            UnicodeDecodeError,
            ValueError,
        ) as exc:
            raise ValueError("Invalid operation cursor") from exc
        return created_at, job_id
