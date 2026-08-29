from __future__ import annotations

import inspect
import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.clients.operational_observability import BootstrapAuditSpool
from src.services import backup_freshness_alert


def test_concurrent_bootstrap_writers_hold_a_mode_0600_file_lock(tmp_path: Path) -> None:
    spool = BootstrapAuditSpool(tmp_path / "bootstrap-audit")

    def append(index: int) -> None:
        spool.append(entrypoint=f"bootstrap.command_{index}", outcome="succeeded")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(append, range(24)))

    records = spool.verify(required=True)
    assert len(records) == 24
    assert len({record["record_hash"] for record in records}) == 24
    assert all(
        record["previous_hash"] == (records[index - 1]["record_hash"] if index else None)
        for index, record in enumerate(records)
    )
    assert stat.S_IMODE(spool.lock_path.stat().st_mode) == 0o600


class _TransactionalConnection:
    def transaction(self) -> None:
        return None


@pytest.mark.asyncio
async def test_real_backup_maintenance_invokes_bootstrap_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Any] = []

    async def reconcile(settings: Any, *, maintenance_connection: Any) -> None:
        calls.append((settings, maintenance_connection))

    async def no_alert(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        return None

    connection = _TransactionalConnection()
    settings = SimpleNamespace(environment="production", backup_monitoring_enabled=False)
    monkeypatch.setattr(backup_freshness_alert, "reconcile_bootstrap_audit", reconcile)
    monkeypatch.setattr(backup_freshness_alert, "read_freshness", no_alert)

    assert (
        await inspect.unwrap(backup_freshness_alert.emit_backup_freshness_alert)(
            connection, settings=settings
        )
        is None
    )
    assert calls == [(settings, connection)]


def test_maintenance_module_uses_production_bootstrap_helper() -> None:
    source = inspect.getsource(backup_freshness_alert)
    assert "reconcile_bootstrap_audit" in source
    assert "maintenance_connection=conn" in source
