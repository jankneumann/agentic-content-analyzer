"""A claim whose worker died must not hold an operation open forever.

Kill a worker mid-job and its row keeps ``status='in_progress'``. Claims only
ever take ``queued`` rows, so no restart recovers it: on GX-10 an ingest sat
claimed across a full stack restart while its submitter polled a status that
would never change. ``mark_stale_jobs_failed`` was written for exactly this and
nothing ever called it.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from src.queue.worker import _STALE_CLAIM_ADVISORY_LOCK, _run_stale_claim_tick, run_worker


def _connection(*, lock_acquired: bool, updated: str = "UPDATE 0") -> AsyncMock:
    connection = AsyncMock()
    connection.fetchval = AsyncMock(return_value=lock_acquired)
    connection.execute = AsyncMock(return_value=updated)
    return connection


@pytest.mark.asyncio
async def test_the_leader_fails_claims_older_than_the_threshold() -> None:
    connection = _connection(lock_acquired=True, updated="UPDATE 3")

    failed = await _run_stale_claim_tick(connection, stale_threshold_hours=2)

    assert failed == 3
    statements = [call.args[0] for call in connection.execute.await_args_list]
    sweep = next(sql for sql in statements if "UPDATE pgqueuer_jobs" in sql)
    assert "status = 'failed'" in sweep
    assert "error = 'stale_timeout'" in sweep
    assert "WHERE status = 'in_progress'" in sweep
    assert "COALESCE(heartbeat_at, started_at)" in sweep

    cutoff = next(
        call.args[1]
        for call in connection.execute.await_args_list
        if "UPDATE pgqueuer_jobs" in call.args[0]
    )
    expected = datetime.now(UTC) - timedelta(hours=2)
    assert abs((cutoff - expected).total_seconds()) < 60


@pytest.mark.asyncio
async def test_only_one_process_sweeps_at_a_time() -> None:
    """Every role runs the worker loop, so the sweep is leader-elected."""
    connection = _connection(lock_acquired=False)

    failed = await _run_stale_claim_tick(connection, stale_threshold_hours=1)

    assert failed == 0
    connection.fetchval.assert_awaited_once()
    assert connection.fetchval.await_args.args[1] == _STALE_CLAIM_ADVISORY_LOCK
    assert not connection.execute.await_args_list, "it must not sweep without the lock"


@pytest.mark.asyncio
async def test_the_lock_is_released_even_when_the_sweep_raises() -> None:
    """A lock held by a crashed tick would stop every later sweep."""
    connection = _connection(lock_acquired=True)
    connection.execute = AsyncMock(side_effect=[RuntimeError("sweep failed"), "UNLOCK"])

    with pytest.raises(RuntimeError):
        await _run_stale_claim_tick(connection, stale_threshold_hours=1)

    assert "pg_advisory_unlock" in connection.execute.await_args_list[-1].args[0]


def test_the_worker_loop_actually_schedules_the_sweep() -> None:
    """The reaper existed for months without a caller; that is the defect."""
    source = inspect.getsource(run_worker)
    assert "_run_stale_claim_tick(" in source
    assert "job_stale_claim_interval_seconds" in source
    assert "job_stale_claim_hours" in source
    assert "stale_claim_conn.close()" in source
