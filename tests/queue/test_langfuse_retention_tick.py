"""The pruner has to be scheduled, leader-elected, and unable to kill the worker.

The stale-claim reaper sat in this repo for months with no caller, which is how
a claimed ingest survived a full stack restart. A retention routine nothing
invokes is the same defect with a slower symptom: the disk fills instead.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock

import pytest

from src.queue.worker import (
    _LANGFUSE_RETENTION_ADVISORY_LOCK,
    _run_langfuse_retention_tick,
    run_worker,
)


class _Settings:
    langfuse_trace_retention_enabled = True
    langfuse_trace_retention_days = 30
    langfuse_trace_retention_batch_size = 50
    langfuse_trace_retention_max_deletes_per_run = 1000
    langfuse_public_key = "pk-lf-test"
    langfuse_secret_key = "sk-lf-test"
    langfuse_base_url = "http://langfuse-web:3000"


def _connection(*, lock_acquired: bool) -> AsyncMock:
    connection = AsyncMock()
    connection.fetchval = AsyncMock(return_value=lock_acquired)
    connection.execute = AsyncMock(return_value="SELECT 1")
    return connection


@pytest.mark.asyncio
async def test_only_one_process_prunes_at_a_time() -> None:
    """Every role runs the worker loop; without the lock they all page the API."""
    connection = _connection(lock_acquired=False)

    deleted = await _run_langfuse_retention_tick(connection, retention_settings=_Settings())

    assert deleted == 0
    assert connection.fetchval.await_args.args[1] == _LANGFUSE_RETENTION_ADVISORY_LOCK


@pytest.mark.asyncio
async def test_the_advisory_lock_is_distinct_from_the_other_maintenance_ticks() -> None:
    """A shared lock id would silently starve one of the two ticks."""
    from src.queue.worker import (
        _BATCH_MAINTENANCE_ADVISORY_LOCK,
        _RETENTION_MAINTENANCE_ADVISORY_LOCK,
        _STALE_CLAIM_ADVISORY_LOCK,
        _WORKFLOW_ALERT_MAINTENANCE_ADVISORY_LOCK,
    )

    locks = [
        _BATCH_MAINTENANCE_ADVISORY_LOCK,
        _RETENTION_MAINTENANCE_ADVISORY_LOCK,
        _WORKFLOW_ALERT_MAINTENANCE_ADVISORY_LOCK,
        _STALE_CLAIM_ADVISORY_LOCK,
        _LANGFUSE_RETENTION_ADVISORY_LOCK,
    ]
    assert len(set(locks)) == len(locks)


@pytest.mark.asyncio
async def test_a_disabled_pruner_holds_the_lock_for_nothing_and_releases_it() -> None:
    connection = _connection(lock_acquired=True)

    class _Off(_Settings):
        langfuse_trace_retention_enabled = False

    deleted = await _run_langfuse_retention_tick(connection, retention_settings=_Off())

    assert deleted == 0
    assert "pg_advisory_unlock" in connection.execute.await_args_list[-1].args[0]


@pytest.mark.asyncio
async def test_an_api_failure_never_takes_down_the_worker(monkeypatch) -> None:
    """Housekeeping the trace store must not stop the queue carrying real work."""
    connection = _connection(lock_acquired=True)

    async def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("langfuse unreachable")

    monkeypatch.setattr("src.services.langfuse_retention.prune_expired_traces", _boom)

    deleted = await _run_langfuse_retention_tick(connection, retention_settings=_Settings())

    assert deleted == 0
    assert "pg_advisory_unlock" in connection.execute.await_args_list[-1].args[0]


@pytest.mark.asyncio
async def test_the_failure_reason_lands_in_the_message_not_in_extra(caplog) -> None:
    """The host log formatter drops `extra`, so a reason put there is invisible."""
    connection = _connection(lock_acquired=True)

    async def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("langfuse unreachable")

    import src.services.langfuse_retention as retention_module

    original = retention_module.prune_expired_traces
    retention_module.prune_expired_traces = _boom
    try:
        with caplog.at_level("WARNING"):
            await _run_langfuse_retention_tick(connection, retention_settings=_Settings())
    finally:
        retention_module.prune_expired_traces = original

    assert any("langfuse unreachable" in record.getMessage() for record in caplog.records)


def test_the_worker_loop_actually_schedules_the_prune() -> None:
    source = inspect.getsource(run_worker)
    assert "_run_langfuse_retention_tick(" in source
    assert "langfuse_trace_retention_interval_seconds" in source
    assert "langfuse_retention_conn.close()" in source
