"""Leader-election tests for the embedded worker's internal batch tick."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


class FakeLockConnection:
    def __init__(self, acquired: bool) -> None:
        self.acquired = acquired
        self.fetchval = AsyncMock(return_value=acquired)
        self.execute = AsyncMock()


def _config(*, enabled: bool):
    return SimpleNamespace(
        batch_config={
            "enabled": enabled,
            "flush_max_requests": 50,
            "flush_max_wait_minutes": 60,
            "fallback_max_attempts": 2,
        }
    )


def _fake_get_db(db):
    @contextmanager
    def get_db():
        yield db

    return get_db


@pytest.mark.asyncio
async def test_disabled_batch_tick_does_not_try_advisory_lock(monkeypatch):
    from src.queue import worker

    conn = FakeLockConnection(acquired=True)
    monkeypatch.setattr("src.config.models.get_model_config", lambda: _config(enabled=False))

    ran = await worker._run_batch_maintenance_tick(conn)

    assert ran is False
    conn.fetchval.assert_not_awaited()


@pytest.mark.asyncio
async def test_losing_batch_tick_advisory_lock_skips_maintenance(monkeypatch):
    from src.queue import worker

    conn = FakeLockConnection(acquired=False)
    maintenance = AsyncMock()
    monkeypatch.setattr("src.config.models.get_model_config", lambda: _config(enabled=True))
    monkeypatch.setattr("src.services.batch.workers.run_batch_maintenance", maintenance)

    ran = await worker._run_batch_maintenance_tick(conn)

    assert ran is False
    maintenance.assert_not_awaited()
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_lock_winner_runs_maintenance_and_always_unlocks(monkeypatch):
    from src.queue import worker

    conn = FakeLockConnection(acquired=True)
    db = MagicMock()
    maintenance = AsyncMock()
    monkeypatch.setattr("src.config.models.get_model_config", lambda: _config(enabled=True))
    monkeypatch.setattr("src.storage.database.get_db", _fake_get_db(db))
    monkeypatch.setattr("src.services.batch.workers.run_batch_maintenance", maintenance)
    monkeypatch.setattr("src.services.llm_router.LLMRouter", lambda config: "router")

    ran = await worker._run_batch_maintenance_tick(conn)

    assert ran is True
    maintenance.assert_awaited_once_with(
        db,
        "router",
        flush_max_requests=50,
        flush_max_wait_minutes=60,
        fallback_max_attempts=2,
    )
    conn.execute.assert_awaited_once()
