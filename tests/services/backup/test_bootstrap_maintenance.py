from __future__ import annotations

import inspect
import json
import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.clients import operational_observability
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


class _Transaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: Any) -> None:
        del args


class _ImportConnection:
    def __init__(self) -> None:
        self.hashes: set[str] = set()
        self.inserted_hashes: list[str] = []

    def transaction(self) -> _Transaction:
        return _Transaction()

    async def fetchval(self, query: str, *args: Any) -> Any:
        if "pg_advisory_xact_lock" in query:
            return True
        if "SELECT id FROM pgqueuer_jobs" in query:
            return 900 if str(args[1]) in self.hashes else None
        if "INSERT INTO pgqueuer_jobs" in query:
            record_hash = str(args[4])
            self.hashes.add(record_hash)
            self.inserted_hashes.append(record_hash)
            return 900 + len(self.inserted_hashes)
        raise AssertionError(query)

    async def execute(self, query: str, *args: Any) -> str:
        del query, args
        return "INSERT 0 1"


class _ConnectionFactory:
    def __init__(self, connection: _ImportConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> _ImportConnection:
        return self.connection

    async def __aexit__(self, *args: Any) -> None:
        del args


def _production_settings() -> SimpleNamespace:
    return SimpleNamespace(
        environment="production",
        observability_provider="noop",
        observability_required=False,
        telemetry_buffer_capacity=100,
        telemetry_buffer_capacity_bytes=1024,
    )


@pytest.mark.asyncio
async def test_crash_after_database_commit_restarts_without_duplicate_record_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    spool = BootstrapAuditSpool(tmp_path)
    record = spool.append(entrypoint="bootstrap.seed", outcome="succeeded")
    connection = _ImportConnection()
    health: list[tuple[str, str | None]] = []

    async def heartbeat(lifecycle: Any, conn: Any) -> None:
        del conn
        health.append((lifecycle.status, lifecycle.last_error_code))

    monkeypatch.setenv("ACA_BOOTSTRAP_AUDIT_DIR", str(tmp_path))
    monkeypatch.setattr("src.queue.setup._queue_connection", lambda: _ConnectionFactory(connection))
    monkeypatch.setattr(operational_observability.TelemetryLifecycle, "heartbeat", heartbeat)
    original_mark_imported = BootstrapAuditSpool.mark_imported
    crashed = False

    def crash_once(self: BootstrapAuditSpool, record_hash: str) -> None:
        nonlocal crashed
        if not crashed:
            crashed = True
            raise RuntimeError("simulated crash after commit")
        original_mark_imported(self, record_hash)

    monkeypatch.setattr(BootstrapAuditSpool, "mark_imported", crash_once)
    with pytest.raises(RuntimeError, match="simulated crash"):
        await operational_observability.reconcile_bootstrap_audit(
            _production_settings(), maintenance_connection=connection
        )

    restarted = await operational_observability.reconcile_bootstrap_audit(
        _production_settings(), maintenance_connection=connection
    )
    assert connection.inserted_hashes == [record["record_hash"]]
    assert restarted.imported_count == 0
    assert BootstrapAuditSpool(tmp_path).pending_records(required=True) == []
    assert health == [("healthy", None), ("healthy", None)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("corrupt", "expected_code"),
    [(False, "bootstrap.spool_missing"), (True, "bootstrap.spool_corrupt")],
)
async def test_missing_or_corrupt_production_spool_persists_degraded_process_health(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    corrupt: bool,
    expected_code: str,
) -> None:
    if corrupt:
        spool = BootstrapAuditSpool(tmp_path)
        spool.append(entrypoint="bootstrap.seed", outcome="succeeded")
        payload = json.loads(spool.path.read_text(encoding="utf-8"))
        payload["entrypoint"] = "tampered"
        spool.path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        spool.path.chmod(0o600)
    connection = _ImportConnection()
    health: list[tuple[str, str | None]] = []

    async def heartbeat(lifecycle: Any, conn: Any) -> None:
        del conn
        health.append((lifecycle.status, lifecycle.last_error_code))

    monkeypatch.setenv("ACA_BOOTSTRAP_AUDIT_DIR", str(tmp_path))
    monkeypatch.setattr("src.queue.setup._queue_connection", lambda: _ConnectionFactory(connection))
    monkeypatch.setattr(operational_observability.TelemetryLifecycle, "heartbeat", heartbeat)

    result = await operational_observability.reconcile_bootstrap_audit(
        _production_settings(), maintenance_connection=connection
    )
    assert result.readiness.ready is False
    assert result.readiness.diagnostic_code == expected_code
    assert health == [("degraded", expected_code)]
