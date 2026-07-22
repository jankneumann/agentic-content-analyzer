"""Durable submit, poll/reconcile, and bounded-fallback maintenance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import func

from src.config.models import ModelStep
from src.models.batch import (
    BatchJob,
    BatchJobState,
    BatchRequest as BatchRequestRow,
    BatchRequestStatus,
)
from src.services.batch.handlers import ResultHandlerRegistry, result_handlers
from src.services.batch.types import BatchRequest, BatchState
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.services.llm_router import LLMRouter

logger = get_logger(__name__)

_OPEN_JOB_STATES = (BatchJobState.PENDING.value, BatchJobState.RUNNING.value)
_INTERRUPTED_SUBMISSION_GRACE = timedelta(minutes=15)


@dataclass
class BatchSubmitSummary:
    jobs_created: int = 0
    jobs_failed: int = 0
    interrupted_jobs_recovered: int = 0
    requests_submitted: int = 0
    requests_fallback: int = 0
    groups_held: int = 0


@dataclass
class BatchPollSummary:
    jobs_polled: int = 0
    jobs_poll_failed: int = 0
    requests_reconciled: int = 0
    requests_fallback: int = 0
    jobs_still_running: int = 0


@dataclass
class BatchFallbackSummary:
    requests_recovered: int = 0
    requests_failed: int = 0
    requests_retrying: int = 0


@dataclass
class BatchMaintenanceSummary:
    submit: BatchSubmitSummary
    poll: BatchPollSummary
    fallback: BatchFallbackSummary


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _is_postgres(db: Session) -> bool:
    bind = db.get_bind()
    return bool(bind is not None and bind.dialect.name == "postgresql")


def _provider_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"[:2000]


def _is_permanent_submission_error(exc: Exception) -> bool:
    """Report whether a failed ``submit_batch`` call can never succeed as-is.

    ``LLMRouter.submit_batch`` documents ``ValueError`` as its deterministic
    rejection: an empty or duplicate request key, a model that does not resolve
    to ``google_ai``, or an inline payload over the cap. Re-submitting the same
    rows reproduces it exactly, so those requests must leave the pending queue.

    A missing credential (``RuntimeError``) is deliberately treated as
    retryable: the operator can export the key and the next sweep drains the
    backlog without losing work.
    """
    return isinstance(exc, ValueError)


def _recover_interrupted_submissions(db: Session, now: datetime) -> int:
    """Release claims left by a maintainer that died during provider submission.

    A provider handle cannot be recovered after a create call was accepted but
    before it was persisted. The failed local job preserves that documented
    orphan window while returning its requests to a recoverable pending state.
    """
    jobs = (
        db.query(BatchJob)
        .filter(
            BatchJob.state == BatchJobState.SUBMITTING.value,
            BatchJob.provider_job_name.is_(None),
            BatchJob.updated_at <= now - _INTERRUPTED_SUBMISSION_GRACE,
        )
        .all()
    )
    for job in jobs:
        rows = (
            db.query(BatchRequestRow)
            .filter(
                BatchRequestRow.batch_job_id == job.id,
                BatchRequestRow.status == BatchRequestStatus.CLAIMED.value,
            )
            .all()
        )
        for row in rows:
            row.status = BatchRequestStatus.PENDING.value
            row.batch_job_id = None
            row.error = "recovered interrupted provider submission"
        job.state = BatchJobState.FAILED.value
        job.error = "provider submission interrupted before handle was persisted"
        job.completed_at = now
    if jobs:
        db.commit()
    return len(jobs)


async def run_batch_submit(
    db: Session,
    router: LLMRouter,
    *,
    flush_max_requests: int,
    flush_max_wait_minutes: int,
    now: datetime | None = None,
) -> BatchSubmitSummary:
    """Claim ripe groups durably before making the non-idempotent provider call."""
    now = now or datetime.now(UTC)
    max_requests = max(1, int(flush_max_requests))
    threshold = timedelta(minutes=max(0, int(flush_max_wait_minutes)))
    summary = BatchSubmitSummary()
    summary.interrupted_jobs_recovered = _recover_interrupted_submissions(db, now)

    pending_groups = (
        db.query(
            BatchRequestRow.model_step,
            BatchRequestRow.model_id,
            func.count(BatchRequestRow.id),
            func.min(BatchRequestRow.created_at),
        )
        .filter(BatchRequestRow.status == BatchRequestStatus.PENDING.value)
        .group_by(BatchRequestRow.model_step, BatchRequestRow.model_id)
        .order_by(
            BatchRequestRow.model_step,
            BatchRequestRow.model_id,
        )
        .all()
    )

    for model_step, model_id, request_count, oldest_created_at in pending_groups:
        oldest = _utc(oldest_created_at)
        if request_count < max_requests and now - oldest < threshold:
            summary.groups_held += 1
            continue

        claim_query = (
            db.query(BatchRequestRow)
            .filter(
                BatchRequestRow.model_step == model_step,
                BatchRequestRow.model_id == model_id,
                BatchRequestRow.status == BatchRequestStatus.PENDING.value,
            )
            .order_by(
                BatchRequestRow.created_at,
                BatchRequestRow.id,
            )
            .limit(max_requests)
        )
        if _is_postgres(db):
            claim_query = claim_query.with_for_update(skip_locked=True)
        claimed = claim_query.all()
        if not claimed:
            db.rollback()
            continue

        job = BatchJob(
            provider="google_ai",
            model_id=model_id,
            model_step=model_step,
            state=BatchJobState.SUBMITTING.value,
            request_count=len(claimed),
        )
        db.add(job)
        db.flush()
        requests: list[BatchRequest] = []
        for row in claimed:
            payload = cast(dict[str, Any], row.request_payload or {})
            requests.append(
                BatchRequest(
                    key=row.request_key,
                    contents=payload.get("contents"),
                    config=payload.get("config") or {},
                )
            )
        claimed_ids = [row.id for row in claimed]
        for row in claimed:
            row.status = BatchRequestStatus.CLAIMED.value
            row.batch_job_id = job.id
            row.error = None
        job_id = job.id
        db.commit()

        try:
            provider_job_name = await router.submit_batch(model_id, requests)
        except Exception as exc:
            error = _provider_error(exc)
            permanent = _is_permanent_submission_error(exc)
            failed_job = db.get(BatchJob, job_id)
            if failed_job is not None:
                failed_job.state = BatchJobState.FAILED.value
                failed_job.error = error
                failed_job.completed_at = now
            rows = db.query(BatchRequestRow).filter(BatchRequestRow.id.in_(claimed_ids)).all()
            for row in rows:
                if row.status != BatchRequestStatus.CLAIMED.value:
                    continue
                if permanent:
                    # Retrying is futile: the next sweep would reclaim the same
                    # rows and fail identically, spawning a failed job per tick
                    # forever. Route to the bounded sync fallback instead so the
                    # queue drains and the work still completes.
                    row.status = BatchRequestStatus.FALLBACK.value
                    row.error = error
                    summary.requests_fallback += 1
                else:
                    row.status = BatchRequestStatus.PENDING.value
                    row.batch_job_id = None
                    row.error = error
            db.commit()
            summary.jobs_failed += 1
            logger.warning(
                "batch provider submission failed",
                extra={"job_id": job_id, "permanent": permanent},
            )
            continue

        submitted_job = db.get(BatchJob, job_id)
        if submitted_job is None:
            raise RuntimeError(f"claimed batch job {job_id} disappeared")
        submitted_job.provider_job_name = provider_job_name
        submitted_job.state = BatchJobState.PENDING.value
        submitted_job.submitted_at = now
        rows = db.query(BatchRequestRow).filter(BatchRequestRow.id.in_(claimed_ids)).all()
        for row in rows:
            if row.status == BatchRequestStatus.CLAIMED.value:
                row.status = BatchRequestStatus.SUBMITTED.value
                row.error = None
        db.commit()
        summary.jobs_created += 1
        summary.requests_submitted += len(rows)

    logger.info("batch submit sweep", extra=summary.__dict__)
    return summary


async def run_batch_poll(
    db: Session,
    router: LLMRouter,
    *,
    registry: ResultHandlerRegistry | None = None,
    now: datetime | None = None,
) -> BatchPollSummary:
    """Poll provider jobs and reconcile only requests that are still submitted."""
    now = now or datetime.now(UTC)
    registry = registry or result_handlers
    summary = BatchPollSummary()
    jobs = db.query(BatchJob).filter(BatchJob.state.in_(_OPEN_JOB_STATES)).all()

    for job in jobs:
        if not job.provider_job_name:
            continue
        rows = (
            db.query(BatchRequestRow)
            .filter(
                BatchRequestRow.batch_job_id == job.id,
                BatchRequestRow.status == BatchRequestStatus.SUBMITTED.value,
            )
            .all()
        )
        expected_keys = {row.request_key for row in rows}
        summary.jobs_polled += 1
        try:
            result = await router.poll_batch(
                job.provider_job_name, expected_request_keys=expected_keys
            )
        except Exception as exc:
            job.error = _provider_error(exc)
            db.commit()
            summary.jobs_poll_failed += 1
            continue

        if result.state == BatchState.SUCCEEDED:
            handler = registry.get(ModelStep(job.model_step))
            results = result.results_by_key or {}
            errors = result.errors_by_key or {}
            for row in rows:
                text = results.get(row.request_key)
                if text is not None and handler is not None:
                    try:
                        # Domain writes and request reconciliation are atomic:
                        # a caught handler failure must not leak partial ORM
                        # mutations or poison the outer job transaction.
                        with db.begin_nested():
                            handler.apply(db, row, text)
                    except Exception as exc:
                        row.status = BatchRequestStatus.FALLBACK.value
                        row.error = f"result handler failed: {_provider_error(exc)}"
                        summary.requests_fallback += 1
                    else:
                        row.status = BatchRequestStatus.SUCCEEDED.value
                        row.result_text = text
                        row.error = None
                        row.completed_at = now
                        summary.requests_reconciled += 1
                else:
                    row.status = BatchRequestStatus.FALLBACK.value
                    row.error = (
                        errors.get(row.request_key)
                        or ("no result handler registered" if handler is None else None)
                        or "missing from batch result"
                    )
                    summary.requests_fallback += 1
            job.state = BatchJobState.SUCCEEDED.value
            job.error = result.error
            job.completed_at = now
        elif result.is_terminal:
            for row in rows:
                row.status = BatchRequestStatus.FALLBACK.value
                row.error = result.error or result.state.value
                summary.requests_fallback += 1
            job.state = result.state.value
            job.error = result.error
            job.completed_at = now
        else:
            job.state = result.state.value
            job.error = result.error
            summary.jobs_still_running += 1
        db.commit()

    logger.info("batch poll sweep", extra=summary.__dict__)
    return summary


async def run_sync_fallback(
    db: Session,
    *,
    registry: ResultHandlerRegistry | None = None,
    fallback_max_attempts: int,
    max_requests: int = 100,
    now: datetime | None = None,
) -> BatchFallbackSummary:
    """Execute registered domain fallbacks with a persisted attempt bound."""
    now = now or datetime.now(UTC)
    registry = registry or result_handlers
    attempt_limit = max(1, int(fallback_max_attempts))
    summary = BatchFallbackSummary()
    query = (
        db.query(BatchRequestRow)
        .filter(BatchRequestRow.status == BatchRequestStatus.FALLBACK.value)
        .order_by(BatchRequestRow.created_at)
        .limit(max(1, int(max_requests)))
    )
    if _is_postgres(db):
        query = query.with_for_update(skip_locked=True)
    rows = query.all()

    for selected_row in rows:
        row_id = selected_row.id
        current_attempts = int(selected_row.fallback_attempts or 0)
        if current_attempts >= attempt_limit:
            selected_row.status = BatchRequestStatus.FAILED.value
            selected_row.error = "sync fallback attempt limit exhausted"
            selected_row.completed_at = now
            db.commit()
            summary.requests_failed += 1
            continue

        # Persist the chargeable external-attempt claim before invoking the
        # domain fallback. A crash/cancellation can consume an attempt, but it
        # cannot roll the counter back and retry without bound.
        selected_row.fallback_attempts = current_attempts + 1
        db.commit()
        row = db.get(BatchRequestRow, row_id)
        if row is None:
            continue

        step = ModelStep(row.model_step)
        result_handler = registry.get(step)
        fallback_handler = registry.get_fallback(step)
        try:
            with db.begin_nested():
                if fallback_handler is None:
                    raise RuntimeError("no fallback handler registered")
                if result_handler is None:
                    raise RuntimeError("no result handler registered")
                result_text = await fallback_handler.fallback(db, row)
                if not isinstance(result_text, str) or not result_text:
                    raise RuntimeError("fallback handler returned no result")
                result_handler.apply(db, row, result_text)
        except Exception as exc:
            row.error = f"sync fallback error: {_provider_error(exc)}"
            if row.fallback_attempts >= attempt_limit:
                row.status = BatchRequestStatus.FAILED.value
                row.completed_at = now
                summary.requests_failed += 1
            else:
                summary.requests_retrying += 1
            db.commit()
            continue

        row.status = BatchRequestStatus.SUCCEEDED.value
        row.result_text = result_text
        row.error = None
        row.completed_at = now
        summary.requests_recovered += 1
        db.commit()

    logger.info("batch sync fallback", extra=summary.__dict__)
    return summary


async def run_batch_maintenance(
    db: Session,
    router: LLMRouter,
    *,
    flush_max_requests: int,
    flush_max_wait_minutes: int,
    fallback_max_attempts: int,
    registry: ResultHandlerRegistry | None = None,
) -> BatchMaintenanceSummary:
    """Run one leader-elected submit/poll/fallback maintenance cycle."""
    submit = await run_batch_submit(
        db,
        router,
        flush_max_requests=flush_max_requests,
        flush_max_wait_minutes=flush_max_wait_minutes,
    )
    poll = await run_batch_poll(db, router, registry=registry)
    fallback = await run_sync_fallback(
        db,
        registry=registry,
        fallback_max_attempts=fallback_max_attempts,
    )
    return BatchMaintenanceSummary(submit=submit, poll=poll, fallback=fallback)
