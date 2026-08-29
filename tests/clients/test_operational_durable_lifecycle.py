from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
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
        assert service_name == "aca-test"
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
