"""Tests for batch sweep workers (submit / poll-reconcile / sync fallback).

Hermetic: in-memory SQLite (batch tables only) + a fake router that records
calls and returns canned batch results. No network, no Postgres.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config.models import ModelStep
from src.models.batch import BatchJob, BatchRequest as BatchRequestRow
from src.services.batch.handlers import ResultHandlerRegistry
from src.services.batch.types import BatchPollResult, BatchState
from src.services.batch.workers import (
    run_batch_poll,
    run_batch_submit,
    run_sync_fallback,
)

STEP = ModelStep.CONTENT_FILTERING.value
MODEL = "gemini-2.5-flash-lite"


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    BatchJob.__table__.create(engine)
    BatchRequestRow.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


class RecordingHandler:
    """ResultHandler that records (content_id, text) applications."""

    def __init__(self) -> None:
        self.applied: list[tuple[int | None, str]] = []

    def apply(self, db, request, result_text):
        self.applied.append((request.content_id, result_text))


class RecordingFallback:
    def __init__(self, result: str = "sync-result") -> None:
        self.result = result
        self.requests: list[str] = []

    async def fallback(self, db, request):
        self.requests.append(request.request_key)
        return self.result


class FailingFallback:
    async def fallback(self, db, request):
        raise RuntimeError("temporary sync failure")


class PartialMutationHandler:
    def apply(self, db, request, result_text):
        request.result_text = "partial-write"
        raise RuntimeError("handler failed after mutation")


class FlushFailureHandler:
    def apply(self, db, request, result_text):
        db.add(
            BatchRequestRow(
                request_key=request.request_key,
                model_step=request.model_step,
                model_id=request.model_id,
                request_payload={},
                status="pending",
            )
        )
        db.flush()


def _seed_request(db, key, *, created_at=None, status="pending", contents="classify", config=None):
    row = BatchRequestRow(
        request_key=key,
        model_step=STEP,
        model_id=MODEL,
        content_id=int(key.split(":")[-1]),
        request_payload={"contents": contents, "config": config or {}},
        status=status,
    )
    if created_at is not None:
        row.created_at = created_at
    db.add(row)
    db.commit()
    return row


class FakeRouter:
    def __init__(self, *, poll_result=None, on_submit=None, submit_error=None):
        self.submitted: list[tuple[str, list]] = []
        self._poll_result = poll_result
        self._on_submit = on_submit
        self._submit_error = submit_error

    async def submit_batch(self, model, requests, provider=None):
        if self._on_submit is not None:
            self._on_submit()
        if self._submit_error is not None:
            raise self._submit_error
        self.submitted.append((model, requests))
        return f"batches/job-{len(self.submitted)}"

    async def poll_batch(self, provider_job_name, *, expected_request_keys=None):
        return self._poll_result


class TestSubmit:
    @pytest.mark.asyncio
    async def test_flushes_group_over_count_threshold(self, db):
        for i in range(3):
            _seed_request(db, f"{STEP}:contents:{i}")
        router = FakeRouter()

        summary = await run_batch_submit(
            db, router, flush_max_requests=3, flush_max_wait_minutes=60
        )

        assert summary.jobs_created == 1
        assert summary.requests_submitted == 3
        # one job row, all requests submitted + linked
        job = db.query(BatchJob).one()
        assert job.state == BatchState.PENDING.value
        assert job.request_count == 3
        assert db.query(BatchRequestRow).filter_by(status="submitted").count() == 3
        assert all(r.batch_job_id == job.id for r in db.query(BatchRequestRow).all())

    @pytest.mark.asyncio
    async def test_claims_are_committed_before_provider_submission(self, db):
        row = _seed_request(db, f"{STEP}:contents:1")

        def assert_claim_is_durable():
            db.expire_all()
            assert db.query(BatchJob).one().state == "submitting"
            assert db.get(BatchRequestRow, row.id).status == "claimed"

        await run_batch_submit(
            db,
            FakeRouter(on_submit=assert_claim_is_durable),
            flush_max_requests=1,
            flush_max_wait_minutes=60,
        )

    @pytest.mark.asyncio
    async def test_transport_failure_releases_claims_and_preserves_failed_job(self, db):
        row = _seed_request(db, f"{STEP}:contents:1")

        summary = await run_batch_submit(
            db,
            FakeRouter(submit_error=RuntimeError("provider unavailable")),
            flush_max_requests=1,
            flush_max_wait_minutes=60,
        )

        db.refresh(row)
        job = db.query(BatchJob).one()
        assert summary.jobs_failed == 1
        assert row.status == "pending"
        assert row.batch_job_id is None
        assert job.state == "failed"
        assert "provider unavailable" in job.error

    @pytest.mark.asyncio
    async def test_permanent_failure_routes_requests_to_fallback(self, db):
        """A deterministic rejection must leave the pending queue, not requeue."""
        row = _seed_request(db, f"{STEP}:contents:1")

        summary = await run_batch_submit(
            db,
            FakeRouter(submit_error=ValueError("inline payload exceeds cap")),
            flush_max_requests=1,
            flush_max_wait_minutes=60,
        )

        db.refresh(row)
        job = db.query(BatchJob).one()
        assert summary.jobs_failed == 1
        assert summary.requests_fallback == 1
        assert row.status == "fallback"
        assert "inline payload exceeds cap" in row.error
        assert job.state == "failed"

    @pytest.mark.asyncio
    async def test_permanent_failure_does_not_respawn_jobs_each_sweep(self, db):
        """Regression: permanent errors used to requeue and loop forever.

        Returning the rows to ``pending`` meant the next maintenance tick
        reclaimed the identical rows and created another failed job, without
        bound. Two sweeps must therefore produce exactly one failed job.
        """
        _seed_request(db, f"{STEP}:contents:1")
        router = FakeRouter(submit_error=ValueError("unsupported provider"))

        first = await run_batch_submit(db, router, flush_max_requests=1, flush_max_wait_minutes=60)
        second = await run_batch_submit(db, router, flush_max_requests=1, flush_max_wait_minutes=60)

        assert first.jobs_failed == 1
        assert second.jobs_failed == 0
        assert db.query(BatchJob).count() == 1
        assert db.query(BatchRequestRow).filter_by(status="pending").count() == 0

    @pytest.mark.asyncio
    async def test_fresh_submitting_job_is_not_recovered_as_interrupted(self, db):
        """A concurrent maintainer must not reclaim an in-flight provider call."""
        now = datetime.now(UTC)
        row = _seed_request(db, f"{STEP}:contents:1", status="claimed")
        job = BatchJob(
            provider="google_ai",
            model_id=MODEL,
            model_step=STEP,
            state="submitting",
            request_count=1,
            updated_at=now,
        )
        db.add(job)
        db.flush()
        row.batch_job_id = job.id
        db.commit()
        router = FakeRouter()

        summary = await run_batch_submit(
            db,
            router,
            flush_max_requests=1,
            flush_max_wait_minutes=60,
            now=now,
        )

        db.refresh(row)
        db.refresh(job)
        assert summary.interrupted_jobs_recovered == 0
        assert router.submitted == []
        assert row.status == "claimed"
        assert job.state == "submitting"

    @pytest.mark.asyncio
    async def test_stale_submitting_job_is_recovered_and_resubmitted(self, db):
        now = datetime.now(UTC)
        row = _seed_request(db, f"{STEP}:contents:1", status="claimed")
        job = BatchJob(
            provider="google_ai",
            model_id=MODEL,
            model_step=STEP,
            state="submitting",
            request_count=1,
            updated_at=now - timedelta(minutes=16),
        )
        db.add(job)
        db.flush()
        row.batch_job_id = job.id
        db.commit()
        router = FakeRouter()

        summary = await run_batch_submit(
            db,
            router,
            flush_max_requests=1,
            flush_max_wait_minutes=60,
            now=now,
        )

        db.refresh(job)
        assert summary.interrupted_jobs_recovered == 1
        assert summary.jobs_created == 1
        assert len(router.submitted) == 1
        assert job.state == "failed"

    @pytest.mark.asyncio
    async def test_holds_group_under_threshold(self, db):
        _seed_request(db, f"{STEP}:contents:1")  # only 1, fresh
        router = FakeRouter()

        summary = await run_batch_submit(
            db, router, flush_max_requests=50, flush_max_wait_minutes=60
        )

        assert summary.jobs_created == 0
        assert summary.groups_held == 1
        assert router.submitted == []
        assert db.query(BatchRequestRow).filter_by(status="pending").count() == 1

    @pytest.mark.asyncio
    async def test_flushes_old_group_on_age(self, db):
        old = datetime.now(UTC) - timedelta(minutes=120)
        _seed_request(db, f"{STEP}:contents:1", created_at=old)
        router = FakeRouter()

        summary = await run_batch_submit(
            db, router, flush_max_requests=50, flush_max_wait_minutes=60
        )

        assert summary.jobs_created == 1  # aged out despite count < threshold
        assert summary.requests_submitted == 1


class TestPollReconcile:
    @pytest.mark.asyncio
    async def test_success_reconciles_via_handler(self, db):
        r1 = _seed_request(db, f"{STEP}:contents:1", status="submitted")
        r2 = _seed_request(db, f"{STEP}:contents:2", status="submitted")
        job = BatchJob(
            provider="google_ai",
            provider_job_name="batches/j1",
            model_id=MODEL,
            model_step=STEP,
            state="running",
            request_count=2,
        )
        db.add(job)
        db.flush()
        r1.batch_job_id = job.id
        r2.batch_job_id = job.id
        db.commit()

        registry = ResultHandlerRegistry()
        handler = RecordingHandler()
        registry.register(ModelStep.CONTENT_FILTERING, handler)
        router = FakeRouter(
            poll_result=BatchPollResult(
                state=BatchState.SUCCEEDED,
                results_by_key={r1.request_key: "label-1", r2.request_key: "label-2"},
            )
        )

        summary = await run_batch_poll(db, router, registry=registry)

        assert summary.requests_reconciled == 2
        assert sorted(handler.applied) == [(1, "label-1"), (2, "label-2")]
        assert db.query(BatchRequestRow).filter_by(status="succeeded").count() == 2
        assert db.query(BatchJob).one().state == BatchState.SUCCEEDED.value

    @pytest.mark.asyncio
    async def test_partial_success_routes_missing_to_fallback(self, db):
        r1 = _seed_request(db, f"{STEP}:contents:1", status="submitted")
        r2 = _seed_request(db, f"{STEP}:contents:2", status="submitted")
        job = BatchJob(
            provider="google_ai",
            provider_job_name="batches/j1",
            model_id=MODEL,
            model_step=STEP,
            state="running",
            request_count=2,
        )
        db.add(job)
        db.flush()
        r1.batch_job_id = job.id
        r2.batch_job_id = job.id
        db.commit()

        registry = ResultHandlerRegistry()
        registry.register(ModelStep.CONTENT_FILTERING, RecordingHandler())
        router = FakeRouter(
            poll_result=BatchPollResult(
                state=BatchState.SUCCEEDED,
                results_by_key={r1.request_key: "ok"},
                errors_by_key={r2.request_key: "blocked"},
            )
        )

        summary = await run_batch_poll(db, router, registry=registry)

        assert summary.requests_reconciled == 1
        assert summary.requests_fallback == 1
        db.refresh(r2)
        assert r2.status == "fallback"
        assert r2.error == "blocked"

    @pytest.mark.asyncio
    async def test_failed_job_marks_all_fallback(self, db):
        r1 = _seed_request(db, f"{STEP}:contents:1", status="submitted")
        job = BatchJob(
            provider="google_ai",
            provider_job_name="batches/j1",
            model_id=MODEL,
            model_step=STEP,
            state="running",
            request_count=1,
        )
        db.add(job)
        db.flush()
        r1.batch_job_id = job.id
        db.commit()

        router = FakeRouter(
            poll_result=BatchPollResult(state=BatchState.EXPIRED, error="job expired")
        )

        summary = await run_batch_poll(db, router)

        assert summary.requests_fallback == 1
        db.refresh(r1)
        assert r1.status == "fallback"
        assert db.query(BatchJob).one().state == BatchState.EXPIRED.value

    @pytest.mark.asyncio
    async def test_running_job_left_untouched(self, db):
        r1 = _seed_request(db, f"{STEP}:contents:1", status="submitted")
        job = BatchJob(
            provider="google_ai",
            provider_job_name="batches/j1",
            model_id=MODEL,
            model_step=STEP,
            state="running",
            request_count=1,
        )
        db.add(job)
        db.flush()
        r1.batch_job_id = job.id
        db.commit()

        router = FakeRouter(poll_result=BatchPollResult(state=BatchState.RUNNING))
        summary = await run_batch_poll(db, router)

        assert summary.jobs_still_running == 1
        assert summary.requests_reconciled == 0
        db.refresh(r1)
        assert r1.status == "submitted"  # unchanged

    @pytest.mark.asyncio
    async def test_terminal_request_is_not_applied_twice(self, db):
        row = _seed_request(db, f"{STEP}:contents:1", status="succeeded")
        job = BatchJob(
            provider="google_ai",
            provider_job_name="batches/j1",
            model_id=MODEL,
            model_step=STEP,
            state="running",
            request_count=1,
        )
        db.add(job)
        db.flush()
        row.batch_job_id = job.id
        db.commit()
        handler = RecordingHandler()
        registry = ResultHandlerRegistry()
        registry.register(ModelStep.CONTENT_FILTERING, handler)

        await run_batch_poll(
            db,
            FakeRouter(
                poll_result=BatchPollResult(
                    state=BatchState.SUCCEEDED,
                    results_by_key={row.request_key: "duplicate"},
                )
            ),
            registry=registry,
        )

        assert handler.applied == []

    @pytest.mark.asyncio
    async def test_missing_result_handler_routes_request_to_fallback(self, db):
        row = _seed_request(db, f"{STEP}:contents:1", status="submitted")
        job = BatchJob(
            provider="google_ai",
            provider_job_name="batches/j1",
            model_id=MODEL,
            model_step=STEP,
            state="running",
            request_count=1,
        )
        db.add(job)
        db.flush()
        row.batch_job_id = job.id
        db.commit()

        await run_batch_poll(
            db,
            FakeRouter(
                poll_result=BatchPollResult(
                    state=BatchState.SUCCEEDED,
                    results_by_key={row.request_key: "unhandled"},
                )
            ),
            registry=ResultHandlerRegistry(),
        )

        db.refresh(row)
        assert row.status == "fallback"
        assert "handler" in row.error

    @pytest.mark.asyncio
    @pytest.mark.parametrize("handler", [PartialMutationHandler(), FlushFailureHandler()])
    async def test_handler_failure_rolls_back_partial_writes_and_keeps_session_usable(
        self, db, handler
    ):
        row = _seed_request(db, f"{STEP}:contents:1", status="submitted")
        job = BatchJob(
            provider="google_ai",
            provider_job_name="batches/j1",
            model_id=MODEL,
            model_step=STEP,
            state="running",
            request_count=1,
        )
        db.add(job)
        db.flush()
        row.batch_job_id = job.id
        db.commit()
        registry = ResultHandlerRegistry()
        registry.register(ModelStep.CONTENT_FILTERING, handler)

        summary = await run_batch_poll(
            db,
            FakeRouter(
                poll_result=BatchPollResult(
                    state=BatchState.SUCCEEDED,
                    results_by_key={row.request_key: "result"},
                )
            ),
            registry=registry,
        )

        db.refresh(row)
        assert summary.requests_fallback == 1
        assert row.status == "fallback"
        assert row.result_text is None
        assert db.query(BatchRequestRow).count() == 1


class TestSyncFallback:
    @pytest.mark.asyncio
    async def test_recovers_request_via_registered_fallback(self, db):
        row = _seed_request(
            db,
            f"{STEP}:contents:1",
            status="fallback",
            contents="classify this",
            config={"system_instruction": "You label.", "temperature": 0.0},
        )

        registry = ResultHandlerRegistry()
        handler = RecordingHandler()
        registry.register(ModelStep.CONTENT_FILTERING, handler)
        fallback = RecordingFallback("recovered-label")
        registry.register_fallback(ModelStep.CONTENT_FILTERING, fallback)

        summary = await run_sync_fallback(db, registry=registry, fallback_max_attempts=2)

        assert summary.requests_recovered == 1
        assert handler.applied == [(1, "recovered-label")]
        assert fallback.requests == [row.request_key]
        db.refresh(row)
        assert row.status == "succeeded"
        assert row.result_text == "recovered-label"

    @pytest.mark.asyncio
    async def test_fallback_attempts_are_bounded(self, db):
        row = _seed_request(db, f"{STEP}:contents:9", status="fallback")
        registry = ResultHandlerRegistry()
        registry.register(ModelStep.CONTENT_FILTERING, RecordingHandler())
        registry.register_fallback(ModelStep.CONTENT_FILTERING, FailingFallback())

        first = await run_sync_fallback(db, registry=registry, fallback_max_attempts=2)
        db.refresh(row)
        assert first.requests_failed == 0
        assert row.status == "fallback"
        assert row.fallback_attempts == 1

        second = await run_sync_fallback(db, registry=registry, fallback_max_attempts=2)
        db.refresh(row)
        assert second.requests_failed == 1
        assert row.status == "failed"
        assert row.fallback_attempts == 2

    @pytest.mark.asyncio
    async def test_only_fallback_status_rows_processed(self, db):
        _seed_request(db, f"{STEP}:contents:1", status="pending")
        _seed_request(db, f"{STEP}:contents:2", status="succeeded")
        summary = await run_sync_fallback(
            db, registry=ResultHandlerRegistry(), fallback_max_attempts=1
        )

        assert summary.requests_recovered == 0

    @pytest.mark.asyncio
    async def test_attempt_is_committed_before_external_fallback_and_bounds_cancellation(self, db):
        row = _seed_request(db, f"{STEP}:contents:10", status="fallback")
        observed_attempts: list[int] = []

        class CancellingFallback:
            async def fallback(self, callback_db, request):
                with Session(callback_db.get_bind()) as observer:
                    observed_attempts.append(
                        observer.get(BatchRequestRow, request.id).fallback_attempts
                    )
                raise asyncio.CancelledError

        registry = ResultHandlerRegistry()
        registry.register(ModelStep.CONTENT_FILTERING, RecordingHandler())
        registry.register_fallback(ModelStep.CONTENT_FILTERING, CancellingFallback())

        with pytest.raises(asyncio.CancelledError):
            await run_sync_fallback(db, registry=registry, fallback_max_attempts=1)

        db.expire_all()
        assert observed_attempts == [1]
        assert db.get(BatchRequestRow, row.id).fallback_attempts == 1

        summary = await run_sync_fallback(db, registry=registry, fallback_max_attempts=1)
        db.refresh(row)
        assert summary.requests_failed == 1
        assert row.status == "failed"
        assert observed_attempts == [1]


class TestEntrypointRegistration:
    def test_batch_maintenance_does_not_register_free_form_entrypoints(self):
        from src.queue import worker

        worker.register_all_handlers()
        assert "batch_submit" not in worker._handlers
        assert "batch_poll" not in worker._handlers
