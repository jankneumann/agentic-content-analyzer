from __future__ import annotations

from contextlib import contextmanager
from contextlib import asynccontextmanager
from dataclasses import dataclass
from time import monotonic
from typing import Any

import pytest

from src.contracts.operation_context import get_current_operation_context


class _Lifecycle:
    service_name = "aca-test"
    service_instance_id = "test-instance"
    release_revision = "test-release"
    initialized = False
    last_flush_succeeded: bool | None = None

    def __init__(self, *, flush_succeeds: bool = True) -> None:
        self.flush_succeeds = flush_succeeds
        self.settings = self._Settings()

    class _Settings:
        environment = "test"
        telemetry_flush_timeout_seconds = 0.2

    settings = _Settings()

    def initialize(self, *, app: Any = None) -> None:
        del app
        self.initialized = True


@dataclass
class _SpanContext:
    trace_id: int
    span_id: int
    trace_flags: int = 1
    is_valid: bool = True


class _Span:
    def __init__(self, span_id: int) -> None:
        self._context = _SpanContext(
            trace_id=int("1234567890abcdef1234567890abcdef", 16),
            span_id=span_id,
        )

    def get_span_context(self) -> _SpanContext:
        return self._context


class _Provider:
    def __init__(self) -> None:
        self.spans: list[tuple[str, dict[str, Any]]] = []

    @contextmanager
    def start_span(self, name: str, attributes: dict[str, Any] | None = None):
        self.spans.append((name, attributes or {}))
        yield _Span(len(self.spans))


class _DurableStore:
    def __init__(self) -> None:
        self.next_id = 700
        self.events: list[str] = []
        self.records: dict[int, dict[str, Any]] = {}

    async def reserve(self, *, entrypoint: str, parent_context: Any) -> int:
        operation_id = self.next_id
        self.next_id += 1
        self.events.append("reserve")
        self.records[operation_id] = {
            "entrypoint": entrypoint,
            "parent_operation_id": (
                parent_context.operation_id if parent_context is not None else None
            ),
            "status": "reserved",
        }
        return operation_id

    async def activate(self, context: Any) -> None:
        operation_id = int(context.operation_id)
        self.events.append("activate")
        self.records[operation_id].update(
            status="in_progress",
            trace_id=context.trace_id,
            span_id=context.span_id,
            root_operation_id=context.root_operation_id,
        )

    async def finish(
        self,
        context: Any,
        *,
        outcome: str,
        telemetry_delivery_state: str,
        diagnostic_codes: tuple[str, ...],
    ) -> None:
        operation_id = int(context.operation_id)
        self.events.append("finish")
        self.records[operation_id].update(
            status="completed" if outcome != "permanent_failure" else "failed",
            outcome=outcome,
            telemetry_delivery_state=telemetry_delivery_state,
            diagnostic_codes=diagnostic_codes,
        )

    async def lookup(self, operation_id: int) -> dict[str, Any]:
        return dict(self.records[operation_id])


@pytest.fixture
def durable_runtime(monkeypatch: pytest.MonkeyPatch):
    from src.clients import operational_observability as module

    lifecycles: list[_Lifecycle] = []
    provider = _Provider()
    store = _DurableStore()

    def create_lifecycle(*, service_name: str, lifecycle_kind: str) -> _Lifecycle:
        assert service_name in {"aca-test", "aca-cli", "aca-agent", "aca-script"}
        assert lifecycle_kind == "short_lived"
        lifecycle = _Lifecycle()
        lifecycles.append(lifecycle)
        return lifecycle

    async def shutdown(lifecycle: _Lifecycle) -> bool:
        lifecycle.last_flush_succeeded = lifecycle.flush_succeeds
        return lifecycle.flush_succeeds

    monkeypatch.setattr(module, "create_telemetry_lifecycle", create_lifecycle)
    monkeypatch.setattr(module, "shutdown_process_telemetry", shutdown)
    monkeypatch.setattr(module, "get_provider", lambda: provider)
    monkeypatch.setattr(module, "create_durable_operation_store", lambda: store)
    return module, lifecycles, provider, store


def test_root_is_durable_before_body_and_uses_actual_provider_identity(durable_runtime) -> None:
    module, lifecycles, _provider, store = durable_runtime
    observed = None

    @module.operational_entrypoint("backup.run", stage="backup", service_name="aca-test")
    def execute() -> None:
        nonlocal observed
        assert store.events == ["reserve", "activate"]
        observed = get_current_operation_context()

    execute()

    assert observed is not None
    assert observed.trace_id == "1234567890abcdef1234567890abcdef"
    assert observed.span_id == "0000000000000001"
    durable = module._run_awaitable_sync(store.lookup(int(observed.operation_id)))
    assert durable["status"] == "completed"
    assert durable["trace_id"] == observed.trace_id
    assert durable["span_id"] == observed.span_id
    assert durable["outcome"] == "succeeded"
    assert store.events == ["reserve", "activate", "finish"]
    assert len(lifecycles) == 1


def test_production_cli_adapter_reserves_durable_root_before_command_body(
    durable_runtime,
) -> None:
    module, lifecycles, _provider, store = durable_runtime

    class _CliContext:
        invoked_subcommand = "manage"

        def __init__(self) -> None:
            self.close_callback = None

        def call_on_close(self, callback: Any) -> None:
            self.close_callback = callback

    context = _CliContext()
    scope = module.install_cli_telemetry(context)

    assert scope.context is get_current_operation_context()
    assert store.events == ["reserve", "activate"]
    assert context.close_callback is not None
    context.close_callback()
    assert store.events == ["reserve", "activate", "finish"]
    assert len(lifecycles) == 1


@pytest.mark.parametrize(
    ("entrypoint", "stage", "service_name"),
    [
        ("agent.execute_task", "model", "aca-agent"),
        ("script.verify_workflow_alerting", "alert", "aca-script"),
    ],
)
def test_production_agent_and_script_roots_are_durable_before_body(
    durable_runtime,
    entrypoint: str,
    stage: str,
    service_name: str,
) -> None:
    module, lifecycles, _provider, store = durable_runtime

    @module.operational_entrypoint(entrypoint, stage=stage, service_name=service_name)
    def execute() -> None:
        assert store.events == ["reserve", "activate"]
        assert get_current_operation_context() is not None

    execute()

    assert store.events == ["reserve", "activate", "finish"]
    assert len(lifecycles) == 1


def test_nested_mcp_tool_is_child_operation_with_one_process_lifecycle(durable_runtime) -> None:
    module, lifecycles, _provider, store = durable_runtime
    observed: list[Any] = []

    @module.operational_entrypoint("mcp.search", stage="fetch", service_name="aca-test")
    def tool() -> None:
        observed.append(get_current_operation_context())

    @module.operational_entrypoint("mcp.server", stage="submit", service_name="aca-test")
    def server() -> None:
        observed.append(get_current_operation_context())
        tool()

    server()

    root, child = observed
    assert len(lifecycles) == 1
    assert child.operation_id != root.operation_id
    assert child.parent_operation_id == root.operation_id
    durable_root = module._run_awaitable_sync(store.lookup(int(root.operation_id)))
    durable_child = module._run_awaitable_sync(store.lookup(int(child.operation_id)))
    assert durable_root["status"] == "completed"
    assert durable_child["status"] == "completed"
    assert durable_root["outcome"] == "succeeded"
    assert durable_child["outcome"] == "succeeded"
    assert store.events == [
        "reserve",
        "activate",
        "reserve",
        "activate",
        "finish",
        "finish",
    ]


def test_failed_flush_persists_degraded_terminal_exit_evidence(durable_runtime) -> None:
    module, lifecycles, _provider, store = durable_runtime
    operation_id = 0

    @module.operational_entrypoint("backup.run", stage="backup", service_name="aca-test")
    def execute() -> None:
        nonlocal operation_id
        context = get_current_operation_context()
        assert context is not None
        operation_id = int(context.operation_id)
        lifecycles[0].flush_succeeds = False

    with pytest.raises(module.OperationalFlushError, match="telemetry flush failed"):
        execute()

    durable = module._run_awaitable_sync(store.lookup(operation_id))
    assert durable["status"] == "completed"
    assert durable["outcome"] == "succeeded"
    assert durable["telemetry_delivery_state"] == "degraded"
    assert durable["diagnostic_codes"] == ("telemetry.flush_failed",)


def test_domain_failure_is_preserved_and_secret_is_not_persisted(durable_runtime) -> None:
    module, _lifecycles, _provider, store = durable_runtime
    secret = "postgresql://admin:do-not-store@example.test/private"

    @module.operational_entrypoint("restore.run", stage="restore", service_name="aca-test")
    def execute() -> None:
        raise ValueError(secret)

    with pytest.raises(ValueError, match="do-not-store"):
        execute()

    durable = module._run_awaitable_sync(store.lookup(700))
    assert durable["status"] == "failed"
    assert durable["outcome"] == "permanent_failure"
    assert secret not in repr(durable)


def test_final_database_failure_uses_masked_mode_0600_fallback(
    durable_runtime, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    module, _lifecycles, _provider, store = durable_runtime
    secret = "postgresql://admin:do-not-store@example.test/private"

    async def unavailable_finish(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise ConnectionError(secret)

    monkeypatch.setattr(store, "finish", unavailable_finish)
    monkeypatch.setenv("ACA_BOOTSTRAP_AUDIT_DIR", str(tmp_path))

    @module.operational_entrypoint("backup.run", stage="backup", service_name="aca-test")
    def execute() -> None:
        return None

    with pytest.raises(module.OperationalFlushError, match="terminal evidence"):
        execute()

    fallback = module.BootstrapAuditSpool(tmp_path)
    records = fallback.verify(required=True)
    assert records[-1]["diagnostic_code"] == "telemetry.database_unavailable"
    assert records[-1]["outcome"] == "succeeded"
    assert secret not in fallback.path.read_text(encoding="utf-8")
    assert fallback.path.stat().st_mode & 0o077 == 0


@pytest.mark.asyncio
async def test_one_outer_deadline_covers_flush_and_final_evidence(
    durable_runtime, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    module, lifecycles, _provider, store = durable_runtime
    original_finish = store.finish

    async def slow_shutdown(lifecycle: _Lifecycle) -> bool:
        await module.asyncio.sleep(0.04)
        lifecycle.last_flush_succeeded = True
        return True

    async def slow_finish(*args: Any, **kwargs: Any) -> None:
        await module.asyncio.sleep(0.04)
        await original_finish(*args, **kwargs)

    monkeypatch.setattr(module, "shutdown_process_telemetry", slow_shutdown)
    monkeypatch.setattr(store, "finish", slow_finish)
    monkeypatch.setenv("ACA_BOOTSTRAP_AUDIT_DIR", str(tmp_path))

    @module.operational_entrypoint("backup.run", stage="backup", service_name="aca-test")
    async def execute() -> None:
        lifecycles[0].settings.telemetry_flush_timeout_seconds = 0.05

    started = monotonic()
    with pytest.raises(module.OperationalFlushError, match="deadline"):
        await execute()
    assert monotonic() - started < 0.075
    records = module.BootstrapAuditSpool(tmp_path).verify(required=True)
    assert records[-1]["diagnostic_code"] == "telemetry.exit_deadline_exceeded"


@pytest.mark.asyncio
async def test_shutdown_flushes_exporter_once_when_heartbeat_persistence_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.clients import operational_observability as module
    from src.queue import setup as queue_setup

    calls = {"shutdown": 0, "heartbeat": 0, "exporter": 0}

    class _FailingHeartbeatLifecycle:
        async def shutdown(self, connection: Any, *, flush: Any) -> bool:
            calls["shutdown"] += 1
            await flush()
            if connection is not None:
                await self.heartbeat(connection)
            return True

        async def heartbeat(self, _connection: Any) -> None:
            calls["heartbeat"] += 1
            raise ConnectionError("database unavailable")

        def record_export_failure(self, _code: str) -> None:
            pass

    @asynccontextmanager
    async def connection():
        yield object()

    async def exporter_bridge(_callback: Any) -> None:
        calls["exporter"] += 1

    monkeypatch.setattr(queue_setup, "_queue_connection", connection)
    monkeypatch.setattr(module, "_ASYNCIO_TO_THREAD", exporter_bridge)

    assert await module.shutdown_process_telemetry(_FailingHeartbeatLifecycle()) is True
    assert calls == {"shutdown": 1, "heartbeat": 1, "exporter": 1}
