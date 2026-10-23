"""Unit contracts for durable operation-observation projections."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.queue import setup as queue_setup
from src.repositories.operation_observation_attempts import (
    AttemptCompletion,
    AttemptStart,
    complete_attempt,
    find_attempts_by_trace,
    list_attempts,
    record_stale_claim_diagnostic,
    start_attempt,
)
from src.repositories.telemetry_process_health import (
    ProcessHealthHeartbeat,
    cleanup_expired_process_health,
    list_process_health,
    upsert_process_health,
)

NOW = datetime(2026, 8, 29, tzinfo=UTC)
TRACE_ID = "1" * 32
SPAN_ID = "2" * 16


def _attempt_start(*, generation: int = 0) -> AttemptStart:
    return AttemptStart(
        operation_id=41,
        claim_generation=generation,
        trace_id=TRACE_ID,
        root_span_id=SPAN_ID,
        langfuse_observation_id="obs-41",
        service_name="aca-worker",
        service_instance_id="worker-1",
        environment="test",
        release_revision="abc123",
        started_at=NOW,
    )


@pytest.mark.asyncio
async def test_attempt_start_is_fenced_by_canonical_claim_generation() -> None:
    conn = AsyncMock()
    conn.fetchval.return_value = 41
    assert await start_attempt(conn, _attempt_start(generation=7))
    query = conn.fetchval.await_args.args[0]
    assert "INSERT INTO operation_observation_attempts" in query
    assert "pgqueuer_jobs" in query
    assert "claim_generation" in query
    assert "status = 'in_progress'" in query
    assert conn.fetchval.await_args.args[2] == 7


@pytest.mark.asyncio
async def test_attempt_completion_is_fenced_and_never_upserts() -> None:
    conn = AsyncMock()
    conn.fetchval.return_value = 41
    completion = AttemptCompletion(
        completed_at=NOW,
        terminal_stage="persist",
        outcome="succeeded",
        retryable=False,
        telemetry_delivery_state="delivered",
        diagnostic_codes=("telemetry.export_recovered",),
        diagnostics_omitted=0,
    )
    assert await complete_attempt(conn, 41, 7, completion)
    query = conn.fetchval.await_args.args[0]
    assert "UPDATE operation_observation_attempts" in query
    assert "pgqueuer_jobs" in query
    assert "claim_generation" in query
    assert "INSERT" not in query


@pytest.mark.asyncio
async def test_stale_attempt_start_and_completion_report_false() -> None:
    conn = AsyncMock()
    conn.fetchval.return_value = None
    completion = AttemptCompletion(
        completed_at=NOW,
        terminal_stage="cleanup",
        outcome="retryable_failure",
        retryable=True,
        telemetry_delivery_state="degraded",
        diagnostic_codes=("queue.stale_claim",),
        diagnostics_omitted=2,
    )
    assert not await start_attempt(conn, _attempt_start(generation=6))
    assert not await complete_attempt(conn, 41, 6, completion)


@pytest.mark.asyncio
async def test_stale_claim_diagnostic_is_bounded_to_its_own_attempt() -> None:
    conn = AsyncMock()
    conn.fetchval.return_value = 41

    assert await record_stale_claim_diagnostic(conn, 41, 6)

    query = conn.fetchval.await_args.args[0]
    assert "UPDATE operation_observation_attempts AS attempt" in query
    assert "attempt.claim_generation = $2" in query
    assert "job.claim_generation > $2" in query
    assert "queue.stale_claim" in query
    assert "cardinality(attempt.diagnostic_codes) < 20" in query
    assert "diagnostics_omitted" in query
    assert "UPDATE pgqueuer_jobs" not in query


@pytest.mark.asyncio
async def test_attempt_queries_are_exact_and_deterministically_ordered() -> None:
    conn = AsyncMock()
    conn.fetch.return_value = []
    assert await list_attempts(conn, 41, after_claim_generation=3, limit=20) == []
    operation_query = conn.fetch.await_args.args[0]
    assert "operation_id = $1" in operation_query
    assert "claim_generation > $2" in operation_query
    assert "ORDER BY claim_generation ASC" in operation_query
    assert await find_attempts_by_trace(conn, TRACE_ID, limit=20) == []
    trace_query = conn.fetch.await_args.args[0]
    assert "trace_id = $1" in trace_query
    assert "ORDER BY operation_id, claim_generation" in trace_query
    assert "LIKE" not in trace_query


@pytest.mark.asyncio
async def test_process_health_writer_derives_exact_expiry_classes() -> None:
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "environment": "test",
        "service_name": "aca-worker",
        "service_instance_id": "worker-1",
        "release_revision": "abc123",
        "lifecycle_kind": "long_running",
        "expires_at": NOW,
        "required_observability": True,
        "initialized": True,
        "status": "healthy",
        "export_target": "local_langfuse",
        "last_heartbeat_at": NOW,
        "last_success_at": NOW,
        "last_error_at": None,
        "last_error_code": None,
        "buffered_count": 0,
        "buffer_capacity": 100,
        "dropped_count": 0,
        "last_flush_at": None,
        "last_flush_succeeded": None,
    }
    heartbeat = ProcessHealthHeartbeat(
        environment="test",
        service_name="aca-worker",
        service_instance_id="worker-1",
        release_revision="abc123",
        lifecycle_kind="long_running",
        required_observability=True,
        initialized=True,
        status="healthy",
        export_target="local_langfuse",
        last_heartbeat_at=NOW,
        last_success_at=NOW,
        last_error_at=None,
        last_error_code=None,
        buffered_count=0,
        buffer_capacity=100,
        dropped_count=0,
        last_flush_at=None,
        last_flush_succeeded=None,
    )
    await upsert_process_health(conn, heartbeat)
    query = conn.fetchrow.await_args.args[0]
    assert "INTERVAL '24 hours'" in query
    assert "INTERVAL '7 days'" in query
    assert "ON CONFLICT (environment, service_name, service_instance_id)" in query


@pytest.mark.asyncio
async def test_process_health_cleanup_is_failure_biased_and_listing_is_bounded() -> None:
    conn = AsyncMock()
    conn.fetchval.return_value = 4
    conn.fetch.return_value = []
    assert await cleanup_expired_process_health(conn, now=NOW) == 4
    cleanup_query = conn.fetchval.await_args.args[0]
    assert "expires_at <= $1" in cleanup_query
    assert "status" not in cleanup_query.lower().split("where", 1)[1]
    rows, omitted = await list_process_health(conn, "test", now=NOW, limit=1000)
    assert rows == [] and omitted == 0
    list_query = conn.fetch.await_args.args[0]
    assert "expires_at > $2" in list_query
    assert "ORDER BY last_heartbeat_at DESC, service_name, service_instance_id" in list_query
    assert "LIMIT $3" in list_query


@pytest.mark.asyncio
async def test_queue_schema_compatibility_requires_observability_objects(monkeypatch) -> None:
    rows = [
        {"table_name": name}
        for name in queue_setup.REQUIRED_QUEUE_TABLES
        if name != "operation_observation_attempts"
    ]
    conn = AsyncMock()
    conn.fetch.side_effect = [rows]

    class AsyncContext:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *_args):
            return None

    context = AsyncContext()
    monkeypatch.setattr(queue_setup, "_queue_connection", lambda: context)
    with pytest.raises(RuntimeError, match="operation_observation_attempts"):
        await queue_setup.ensure_queue_schema_compatible()


def test_migration_contains_additive_and_reversible_observability_schema() -> None:
    migrations = list(Path("alembic/versions").glob("*_add_operation_observability.py"))
    assert len(migrations) == 1
    source = migrations[0].read_text()
    for required in (
        "root_job_id",
        "submission_context",
        "operation_observation_attempts",
        "telemetry_process_health",
        "environment_ownership",
        "trace_id",
        "request_span_id",
        "submitted_operation_id",
        "def upgrade()",
        "def downgrade()",
    ):
        assert required in source
