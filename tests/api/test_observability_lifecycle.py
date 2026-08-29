"""Unified process telemetry lifecycle tests (CORR-013/014, OBS-003)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.queue import worker


def _settings(**overrides: Any) -> SimpleNamespace:
    values = {
        "environment": "test",
        "otel_service_name": "aca-worker",
        "observability_required": False,
        "otel_enabled": True,
        "otel_exporter_otlp_endpoint": "http://otel:4318",
        "observability_provider": "otel",
        "telemetry_buffer_capacity": 2,
        "telemetry_buffer_capacity_bytes": 4,
        "telemetry_flush_timeout_seconds": 0.05,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_frozen_buffer_defaults_are_ten_thousand_items_and_256_mib() -> None:
    from src.config.settings import Settings

    assert Settings.model_fields["telemetry_buffer_capacity"].default == 10_000
    assert Settings.model_fields["telemetry_buffer_capacity_bytes"].default == 268_435_456


def test_required_observability_rejects_missing_export_target() -> None:
    lifecycle = worker.TelemetryLifecycle(
        settings=_settings(observability_required=True, otel_exporter_otlp_endpoint=None),
        service_name="aca-api",
        lifecycle_kind="long_running",
    )
    with pytest.raises(RuntimeError, match="required observability"):
        lifecycle.initialize()


def test_buffer_overflow_is_visible_and_export_recovery_clears_degradation() -> None:
    lifecycle = worker.TelemetryLifecycle(
        settings=_settings(), service_name="aca-worker", lifecycle_kind="long_running"
    )
    lifecycle.initialize(setup=lambda _app: None)
    lifecycle.record_buffered(2, buffered_bytes=5)
    assert lifecycle.buffered_count == 2
    assert lifecycle.buffered_bytes == 4
    assert lifecycle.dropped_count == 1
    assert lifecycle.last_error_code == "telemetry.buffer_overflow"
    lifecycle.record_export_success(buffered_count=0, buffered_bytes=0)
    lifecycle.record_buffered(3)
    assert lifecycle.buffered_count == 2
    assert lifecycle.dropped_count == 2
    assert lifecycle.status == "degraded"
    lifecycle.record_export_success(buffered_count=0)
    assert lifecycle.buffered_count == 0
    assert lifecycle.status == "healthy"
    assert lifecycle.last_success_at is not None
    assert lifecycle.buffered_bytes == 0


@pytest.mark.asyncio
async def test_outage_recovery_changes_persisted_heartbeat_fields(monkeypatch) -> None:
    rows: list[Any] = []

    async def upsert(_conn: object, heartbeat: Any) -> Any:
        rows.append(heartbeat)
        return heartbeat

    monkeypatch.setattr("src.repositories.telemetry_process_health.upsert_process_health", upsert)
    lifecycle = worker.TelemetryLifecycle(
        settings=_settings(), service_name="aca-worker", lifecycle_kind="long_running"
    )
    lifecycle.initialize(setup=lambda _app: None)
    lifecycle.record_export_failure("telemetry.export_failed")
    await lifecycle.heartbeat(object())
    lifecycle.record_export_success(buffered_count=0, buffered_bytes=0)
    await lifecycle.heartbeat(object())
    assert rows[0].status == "degraded"
    assert rows[0].last_error_code == "telemetry.export_failed"
    assert rows[1].status == "healthy"
    assert rows[1].last_error_code is None
    assert rows[1].last_success_at is not None


@pytest.mark.asyncio
async def test_heartbeat_persists_restart_distinct_instances_and_fresh_state(monkeypatch) -> None:
    rows: list[Any] = []

    async def upsert(_conn: object, heartbeat: Any) -> Any:
        rows.append(heartbeat)
        return heartbeat

    monkeypatch.setattr("src.repositories.telemetry_process_health.upsert_process_health", upsert)
    first = worker.TelemetryLifecycle(
        settings=_settings(),
        service_name="aca-worker",
        lifecycle_kind="long_running",
        service_instance_id="worker-old",
    )
    second = worker.TelemetryLifecycle(
        settings=_settings(),
        service_name="aca-worker",
        lifecycle_kind="long_running",
        service_instance_id="worker-new",
    )
    first.initialize(setup=lambda _app: None)
    second.initialize(setup=lambda _app: None)
    await first.heartbeat(object())
    await second.heartbeat(object())
    assert [row.service_instance_id for row in rows] == ["worker-old", "worker-new"]
    assert all(row.last_heartbeat_at.tzinfo is UTC for row in rows)
    assert all(row.lifecycle_kind == "long_running" for row in rows)


@pytest.mark.asyncio
async def test_short_lived_shutdown_flush_is_bounded_and_persisted(monkeypatch) -> None:
    rows: list[Any] = []

    async def upsert(_conn: object, heartbeat: Any) -> Any:
        rows.append(heartbeat)
        return heartbeat

    monkeypatch.setattr("src.repositories.telemetry_process_health.upsert_process_health", upsert)
    lifecycle = worker.TelemetryLifecycle(
        settings=_settings(), service_name="aca-cli-worker", lifecycle_kind="short_lived"
    )
    lifecycle.initialize(setup=lambda _app: None)

    async def never_finishes() -> None:
        await asyncio.sleep(60)

    succeeded = await lifecycle.shutdown(object(), flush=never_finishes)
    assert succeeded is False
    assert lifecycle.last_flush_succeeded is False
    assert lifecycle.status == "degraded"
    assert rows[-1].lifecycle_kind == "short_lived"
    assert rows[-1].last_flush_at <= datetime.now(UTC)


def test_api_deployment_worker_and_cli_worker_use_one_lifecycle_factory() -> None:
    from pathlib import Path

    surfaces = [Path("src/api/app.py"), Path("src/worker.py"), Path("src/cli/worker_commands.py")]
    for surface in surfaces:
        assert "create_telemetry_lifecycle" in surface.read_text()


@pytest.mark.asyncio
async def test_deployment_worker_uses_configured_role_service_name(monkeypatch) -> None:
    import src.worker as deployment_worker

    configured = _settings(otel_service_name="aca-worker-pool")
    lifecycle = SimpleNamespace(initialize=lambda *, app: None)
    captured: dict[str, str] = {}

    def create_lifecycle(*, service_name: str, lifecycle_kind: str) -> object:
        captured.update(service_name=service_name, lifecycle_kind=lifecycle_kind)
        return lifecycle

    async def wait_for_cancellation(_lifecycle: object) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(deployment_worker, "get_settings", lambda: configured, raising=False)
    monkeypatch.setattr(deployment_worker, "create_telemetry_lifecycle", create_lifecycle)
    monkeypatch.setattr(deployment_worker, "run_telemetry_heartbeat", wait_for_cancellation)
    monkeypatch.setattr(deployment_worker, "register_all_handlers", lambda: None)
    monkeypatch.setattr(deployment_worker, "run_worker", AsyncMock())
    monkeypatch.setattr(deployment_worker, "shutdown_process_telemetry", AsyncMock())
    monkeypatch.setattr("src.queue.setup.ensure_queue_schema_compatible", AsyncMock())

    await deployment_worker.main()

    assert captured == {
        "service_name": "aca-worker-pool",
        "lifecycle_kind": "long_running",
    }
