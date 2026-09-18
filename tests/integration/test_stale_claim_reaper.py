"""PostgreSQL evidence that an abandoned claim is failed, not left running."""

from __future__ import annotations

import asyncpg
import pytest
import pytest_asyncio

from src.queue.setup import mark_stale_jobs_failed

BASE_ID = 9_720_000


async def _claimed_job(conn: asyncpg.Connection, operation_id: int, *, age_hours: float) -> None:
    """An in_progress row whose last heartbeat is `age_hours` old."""
    await conn.execute(
        """
        INSERT INTO pgqueuer_jobs (
            id, entrypoint, payload, status, started_at, heartbeat_at, claim_generation
        )
        VALUES ($1, 'ingestion.execute', '{}'::jsonb, 'in_progress',
                NOW() - ($2 || ' hours')::interval, NOW() - ($2 || ' hours')::interval, 0)
        """,
        operation_id,
        str(age_hours),
    )


@pytest_asyncio.fixture
async def pg_conn(test_engine):
    conn = await asyncpg.connect(test_engine.url.render_as_string(hide_password=False))
    transaction = conn.transaction()
    await transaction.start()
    try:
        yield conn
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_an_abandoned_claim_fails_and_a_live_one_keeps_running(pg_conn) -> None:
    """The threshold is the whole contract: reap the dead, never the living.

    A worker killed mid-job leaves its row in_progress, and claims only take
    queued rows, so nothing recovers it. A worker that is merely slow is still
    heartbeating, and failing its job would abandon work in flight.
    """
    abandoned, live = BASE_ID, BASE_ID + 1
    await _claimed_job(pg_conn, abandoned, age_hours=3)
    await _claimed_job(pg_conn, live, age_hours=0)

    failed = await mark_stale_jobs_failed(1, conn=pg_conn)

    assert failed == 1
    reaped = await pg_conn.fetchrow(
        "SELECT status, error, completed_at FROM pgqueuer_jobs WHERE id = $1", abandoned
    )
    assert reaped["status"] == "failed"
    assert reaped["error"] == "stale_timeout"
    assert reaped["completed_at"] is not None
    assert (
        await pg_conn.fetchval("SELECT status FROM pgqueuer_jobs WHERE id = $1", live)
        == "in_progress"
    )


@pytest.mark.asyncio
async def test_reaping_emits_the_terminal_event_that_makes_it_alertable(pg_conn) -> None:
    """Silence is the failure mode here: an operation that dies unnoticed is
    the reason one sat claimed for hours. The status change fires the terminal
    event trigger, so the reaped operation reaches the alert pipeline."""
    operation_id = BASE_ID + 2
    await _claimed_job(pg_conn, operation_id, age_hours=5)

    await mark_stale_jobs_failed(1, conn=pg_conn)

    event = await pg_conn.fetchrow(
        """
        SELECT source_kind, terminal_status, claim_generation
        FROM workflow_terminal_events WHERE operation_id = $1
        """,
        operation_id,
    )
    assert event is not None, "a reaped claim must not vanish quietly"
    assert event["source_kind"] == "operation"
    assert event["terminal_status"] == "failed"


@pytest.mark.asyncio
async def test_a_returning_worker_cannot_overwrite_the_recorded_failure(pg_conn) -> None:
    """Terminal status is the fence. `_complete_job` requires the row to still
    be in_progress, so a process that wakes up holding a reaped claim writes
    nothing instead of resurrecting a job nobody is running."""
    from src.queue.worker import _complete_job

    operation_id = BASE_ID + 3
    await _claimed_job(pg_conn, operation_id, age_hours=4)
    await mark_stale_jobs_failed(1, conn=pg_conn)

    assert await _complete_job(pg_conn, operation_id, 0) is False
    assert (
        await pg_conn.fetchval("SELECT status FROM pgqueuer_jobs WHERE id = $1", operation_id)
        == "failed"
    )
