"""PostgreSQL evidence that a directly executed operation survives the stale sweep.

The gx-10 off-site upload runs 40-115 minutes outside any worker. Its queue row
was written once at start, so the worker's one-hour stale sweep failed it, and the
upload's own terminal write then reported "terminal evidence database unavailable".
"""

from __future__ import annotations

import asyncio

import asyncpg
import pytest
import pytest_asyncio

from src.clients import operational_observability as module
from src.contracts.operation_context import OperationStage
from src.queue import setup
from src.queue.setup import mark_stale_jobs_failed
from tests.clients.operational_runtime import _Lifecycle


@pytest_asyncio.fixture
async def pg_conn(test_engine, monkeypatch: pytest.MonkeyPatch):
    """One rolled-back transaction that the durable store reuses as its queue connection."""
    conn = await asyncpg.connect(test_engine.url.render_as_string(hide_password=False))
    transaction = conn.transaction()
    await transaction.start()
    monkeypatch.setattr(setup, "_connection", conn)
    monkeypatch.setattr(setup, "_connection_loop", asyncio.get_running_loop())
    try:
        yield conn
    finally:
        await transaction.rollback()
        await conn.close()


async def _running_root(conn: asyncpg.Connection, *, started_hours_ago: float) -> object:
    """Reserve and activate a root through the real store, then age its row."""
    store = module.PostgresDurableOperationStore()
    operation_id = await store.reserve(entrypoint="gx10.backup.offsite", parent_context=None)
    context = module._context_for(
        operation_id=operation_id,
        entrypoint="gx10.backup.offsite",
        stage=OperationStage("backup"),
        lifecycle=_Lifecycle("aca-test"),  # type: ignore[arg-type]
        parent_context=None,
    )
    await store.activate(context)
    await conn.execute(
        """
        UPDATE pgqueuer_jobs
        SET started_at = NOW() - make_interval(secs => $2),
            heartbeat_at = NOW() - make_interval(secs => $2)
        WHERE id = $1
        """,
        operation_id,
        started_hours_ago * 3600,
    )
    return context


@pytest.mark.asyncio
async def test_a_heartbeating_root_outlives_the_stale_sweep(pg_conn) -> None:
    store = module.PostgresDurableOperationStore()
    context = await _running_root(pg_conn, started_hours_ago=2)

    assert await store.heartbeat(int(context.operation_id)) is True
    await mark_stale_jobs_failed(1, conn=pg_conn)

    status = await pg_conn.fetchval(
        "SELECT status FROM pgqueuer_jobs WHERE id = $1", int(context.operation_id)
    )
    assert status == "in_progress"
    await store.finish(
        context, outcome="succeeded", telemetry_delivery_state="delivered", diagnostic_codes=()
    )
    status = await pg_conn.fetchval(
        "SELECT status FROM pgqueuer_jobs WHERE id = $1", int(context.operation_id)
    )
    assert status == "completed"


@pytest.mark.asyncio
async def test_a_reaped_root_stops_heartbeating_and_finish_names_the_reaping(pg_conn) -> None:
    store = module.PostgresDurableOperationStore()
    context = await _running_root(pg_conn, started_hours_ago=2)
    await mark_stale_jobs_failed(1, conn=pg_conn)

    assert await store.heartbeat(int(context.operation_id)) is False
    with pytest.raises(module.OperationNoLongerActiveError) as raised:
        await store.finish(
            context,
            outcome="succeeded",
            telemetry_delivery_state="delivered",
            diagnostic_codes=(),
        )

    assert (raised.value.status, raised.value.error) == ("failed", "stale_timeout")
    # The attempt still records what the command did; only the job row was taken.
    outcome = await pg_conn.fetchval(
        "SELECT outcome FROM operation_observation_attempts WHERE operation_id = $1",
        int(context.operation_id),
    )
    assert outcome == "succeeded"
