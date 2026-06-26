"""Tests for batch sweep workers (submit / poll-reconcile / sync fallback).

Hermetic: in-memory SQLite (batch tables only) + a fake router that records
calls and returns canned batch results. No network, no Postgres.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

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
    """ResultHandler that records (target_id, text) applications."""

    def __init__(self) -> None:
        self.applied: list[tuple[str, str]] = []

    def apply(self, db, target_id, result_text):
        self.applied.append((target_id, result_text))


def _seed_request(db, key, *, created_at=None, status="pending", contents="classify", config=None):
    row = BatchRequestRow(
        request_key=key,
        model_step=STEP,
        model_id=MODEL,
        target_table="contents",
        target_id=key.split(":")[-1],
        request_payload={"contents": contents, "config": config or {}},
        status=status,
    )
    if created_at is not None:
        row.created_at = created_at
    db.add(row)
    db.commit()
    return row


class FakeRouter:
    def __init__(self, *, poll_result=None, generate_text="sync-result"):
        self.submitted: list[tuple[str, list]] = []
        self._poll_result = poll_result
        self._generate_text = generate_text
        self.generate_calls: list[dict] = []

    async def submit_batch(self, model, requests, provider=None):
        self.submitted.append((model, requests))
        return f"batches/job-{len(self.submitted)}"

    async def poll_batch(self, provider_job_name):
        return self._poll_result

    async def generate(
        self, *, model, system_prompt, user_prompt, max_tokens=4096, temperature=0.7
    ):
        self.generate_calls.append({"model": model, "system": system_prompt, "user": user_prompt})
        return SimpleNamespace(text=self._generate_text)


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
        assert job.state == BatchState.RUNNING.value
        assert job.request_count == 3
        assert db.query(BatchRequestRow).filter_by(status="submitted").count() == 3
        assert all(r.batch_job_id == job.id for r in db.query(BatchRequestRow).all())

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
        assert sorted(handler.applied) == [("1", "label-1"), ("2", "label-2")]
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


class TestSyncFallback:
    @pytest.mark.asyncio
    async def test_recovers_text_request_via_generate(self, db):
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
        router = FakeRouter(generate_text="recovered-label")

        summary = await run_sync_fallback(db, router, registry=registry)

        assert summary.requests_recovered == 1
        assert handler.applied == [("1", "recovered-label")]
        assert router.generate_calls[0]["system"] == "You label."
        assert router.generate_calls[0]["user"] == "classify this"
        db.refresh(row)
        assert row.status == "succeeded"
        assert row.result_text == "recovered-label"

    @pytest.mark.asyncio
    async def test_non_text_contents_marked_failed(self, db):
        row = _seed_request(
            db, f"{STEP}:contents:9", status="fallback", contents=["video-part", "prompt"]
        )
        router = FakeRouter()

        summary = await run_sync_fallback(db, router)

        assert summary.requests_failed == 1
        assert router.generate_calls == []  # never attempted
        db.refresh(row)
        assert row.status == "failed"

    @pytest.mark.asyncio
    async def test_only_fallback_status_rows_processed(self, db):
        _seed_request(db, f"{STEP}:contents:1", status="pending")
        _seed_request(db, f"{STEP}:contents:2", status="succeeded")
        router = FakeRouter()

        summary = await run_sync_fallback(db, router)

        assert summary.requests_recovered == 0
        assert router.generate_calls == []


class TestEntrypointRegistration:
    def test_batch_entrypoints_registered(self):
        from src.queue import worker

        worker.register_all_handlers()
        assert "batch_submit" in worker._handlers
        assert "batch_poll" in worker._handlers
