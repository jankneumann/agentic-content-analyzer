"""Batch sweep workers: submit, poll/reconcile, and synchronous fallback.

These are dialect-agnostic async functions over a caller-supplied session so
they unit-test on SQLite (no Postgres, no network) and run in production behind
the queue entrypoints in :mod:`src.queue.worker`. All three are idempotent and
safe to run concurrently: row claims use ``FOR UPDATE SKIP LOCKED`` on
Postgres (silently skipped on SQLite, which is single-writer anyway).

Lifecycle of one ``batch_requests`` row::

    pending ──submit──▶ submitted ──poll SUCCEEDED──▶ succeeded
                                  └─poll FAILED/EXPIRED─▶ fallback ──sync rerun──▶ succeeded
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from src.config.models import ModelStep
from src.models.batch import BatchJob, BatchRequest as BatchRequestRow
from src.services.batch.handlers import ResultHandlerRegistry, result_handlers
from src.services.batch.types import BatchRequest, BatchState
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.services.llm_router import LLMRouter

logger = get_logger(__name__)

# Request lifecycle statuses (string column, kept local to avoid an enum migration).
STATUS_PENDING = "pending"
STATUS_SUBMITTED = "submitted"
STATUS_SUCCEEDED = "succeeded"
STATUS_FALLBACK = "fallback"
STATUS_FAILED = "failed"

# Non-terminal job states the poller revisits.
_OPEN_JOB_STATES = (BatchState.PENDING.value, BatchState.RUNNING.value)


@dataclass
class BatchSubmitSummary:
    jobs_created: int = 0
    requests_submitted: int = 0
    groups_held: int = 0  # under threshold, left for a later sweep


@dataclass
class BatchPollSummary:
    jobs_polled: int = 0
    requests_reconciled: int = 0
    requests_fallback: int = 0
    jobs_still_running: int = 0


@dataclass
class BatchFallbackSummary:
    requests_recovered: int = 0
    requests_failed: int = 0


def _utc(dt: datetime) -> datetime:
    """Normalize a possibly-naive timestamp to aware UTC (SQLite returns naive)."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _is_postgres(db: Session) -> bool:
    bind = db.get_bind()
    return bool(bind is not None and bind.dialect.name == "postgresql")


async def run_batch_submit(
    db: Session,
    router: LLMRouter,
    *,
    flush_max_requests: int,
    flush_max_wait_minutes: int,
    now: datetime | None = None,
) -> BatchSubmitSummary:
    """Group ``pending`` requests by (step, model) and flush ripe groups.

    A group flushes when it has ``>= flush_max_requests`` rows OR its oldest row
    is ``>= flush_max_wait_minutes`` old — so small trickles still go out on a
    timer instead of waiting forever. Each flush creates one ``batch_jobs`` row
    and moves its requests to ``submitted``.
    """
    now = now or datetime.now(UTC)
    summary = BatchSubmitSummary()

    query = db.query(BatchRequestRow).filter(BatchRequestRow.status == STATUS_PENDING)
    if _is_postgres(db):
        query = query.with_for_update(skip_locked=True)
    pending = query.order_by(
        BatchRequestRow.model_step,
        BatchRequestRow.model_id,
        BatchRequestRow.created_at,
    ).all()

    groups: dict[tuple[str, str], list[BatchRequestRow]] = defaultdict(list)
    for row in pending:
        groups[row.model_step, row.model_id].append(row)

    threshold = timedelta(minutes=flush_max_wait_minutes)
    for (model_step, model_id), rows in groups.items():
        oldest = min(_utc(r.created_at) for r in rows)
        ripe = len(rows) >= flush_max_requests or (now - oldest) >= threshold
        if not ripe:
            summary.groups_held += 1
            continue

        requests = [
            BatchRequest(
                key=r.request_key,
                contents=r.request_payload.get("contents"),
                config=r.request_payload.get("config") or {},
            )
            for r in rows
        ]
        provider_job_name = await router.submit_batch(model_id, requests)

        job = BatchJob(
            provider="google_ai",
            provider_job_name=provider_job_name,
            model_id=model_id,
            model_step=model_step,
            state=BatchState.RUNNING.value,
            request_count=len(rows),
            submitted_at=now,
        )
        db.add(job)
        db.flush()  # need job.id before linking requests
        for r in rows:
            r.batch_job_id = job.id
            r.status = STATUS_SUBMITTED
        summary.jobs_created += 1
        summary.requests_submitted += len(rows)

    db.commit()
    logger.info(
        "batch submit sweep",
        extra={
            "jobs_created": summary.jobs_created,
            "requests_submitted": summary.requests_submitted,
            "groups_held": summary.groups_held,
        },
    )
    return summary


async def run_batch_poll(
    db: Session,
    router: LLMRouter,
    *,
    registry: ResultHandlerRegistry | None = None,
    now: datetime | None = None,
) -> BatchPollSummary:
    """Poll every open job; reconcile successes, route failures to fallback.

    On ``SUCCEEDED``: each request whose key is in the result is applied via its
    step handler and marked ``succeeded``; any request missing from the result
    (partial success) is marked ``fallback``. On ``FAILED``/``EXPIRED``/
    ``CANCELLED``: all the job's requests are marked ``fallback`` so the sync
    pass can recover them. Still-running jobs are left untouched.
    """
    now = now or datetime.now(UTC)
    registry = registry or result_handlers
    summary = BatchPollSummary()

    query = db.query(BatchJob).filter(BatchJob.state.in_(_OPEN_JOB_STATES))
    if _is_postgres(db):
        query = query.with_for_update(skip_locked=True)
    jobs = query.all()

    for job in jobs:
        summary.jobs_polled += 1
        result = await router.poll_batch(job.provider_job_name)
        rows = db.query(BatchRequestRow).filter(BatchRequestRow.batch_job_id == job.id).all()

        if result.state == BatchState.SUCCEEDED:
            handler = registry.get(ModelStep(job.model_step))
            results = result.results_by_key or {}
            errors = result.errors_by_key or {}
            for row in rows:
                if row.request_key in results:
                    text = results[row.request_key]
                    if handler is not None:
                        handler.apply(db, row.target_id, text)
                    row.status = STATUS_SUCCEEDED
                    row.result_text = text
                    row.completed_at = now
                    summary.requests_reconciled += 1
                else:
                    row.status = STATUS_FALLBACK
                    row.error = errors.get(row.request_key, "missing from batch result")
                    summary.requests_fallback += 1
            job.state = BatchState.SUCCEEDED.value
            job.completed_at = now

        elif result.is_terminal:  # FAILED / EXPIRED / CANCELLED
            for row in rows:
                row.status = STATUS_FALLBACK
                row.error = result.error or result.state.value
                summary.requests_fallback += 1
            job.state = result.state.value
            job.error = result.error
            job.completed_at = now

        else:  # still PENDING / RUNNING
            summary.jobs_still_running += 1

    db.commit()
    logger.info(
        "batch poll sweep",
        extra={
            "jobs_polled": summary.jobs_polled,
            "requests_reconciled": summary.requests_reconciled,
            "requests_fallback": summary.requests_fallback,
        },
    )
    return summary


async def run_sync_fallback(
    db: Session,
    router: LLMRouter,
    *,
    registry: ResultHandlerRegistry | None = None,
    max_requests: int = 100,
    now: datetime | None = None,
) -> BatchFallbackSummary:
    """Re-run ``fallback`` requests synchronously so no item is permanently stuck.

    Reconstructs the original prompt from the stored payload (``config``'s
    ``system_instruction`` + string ``contents``), calls the normal
    ``router.generate`` path, applies the result via the step handler, and marks
    the row ``succeeded``. Requests whose contents aren't a plain string (e.g.
    native-video parts — a Phase 3 concern) are left ``failed`` for visibility
    rather than silently dropped.
    """
    now = now or datetime.now(UTC)
    registry = registry or result_handlers
    summary = BatchFallbackSummary()

    rows = (
        db.query(BatchRequestRow)
        .filter(BatchRequestRow.status == STATUS_FALLBACK)
        .order_by(BatchRequestRow.created_at)
        .limit(max_requests)
        .all()
    )

    for row in rows:
        payload: dict[str, Any] = row.request_payload or {}
        contents = payload.get("contents")
        if not isinstance(contents, str):
            row.status = STATUS_FAILED
            row.error = "sync fallback unsupported for non-text contents"
            summary.requests_failed += 1
            continue

        config = payload.get("config") or {}
        try:
            response = await router.generate(
                model=row.model_id,
                system_prompt=config.get("system_instruction", "") or "",
                user_prompt=contents,
                max_tokens=int(config.get("max_output_tokens", 4096)),
                temperature=float(config.get("temperature", 0.7)),
            )
        except Exception as exc:
            row.status = STATUS_FAILED
            row.error = f"sync fallback error: {exc}"
            summary.requests_failed += 1
            continue

        handler = registry.get(ModelStep(row.model_step))
        if handler is not None:
            handler.apply(db, row.target_id, response.text)
        row.status = STATUS_SUCCEEDED
        row.result_text = response.text
        row.completed_at = now
        summary.requests_recovered += 1

    db.commit()
    logger.info(
        "batch sync fallback",
        extra={
            "requests_recovered": summary.requests_recovered,
            "requests_failed": summary.requests_failed,
        },
    )
    return summary
