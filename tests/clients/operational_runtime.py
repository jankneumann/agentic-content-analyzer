"""In-memory adapters for external operational-observability boundaries."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any


class _Settings:
    environment = "test"
    telemetry_flush_timeout_seconds = 0.2


class _Lifecycle:
    service_instance_id = "test-instance"
    release_revision = "test-release"
    settings = _Settings()

    def __init__(self, service_name: str) -> None:
        self.service_name = service_name

    def initialize(self, *, app: Any = None) -> None:
        del app


@dataclass
class _SpanContext:
    trace_id: int = int("1234567890abcdef1234567890abcdef", 16)
    span_id: int = 0x42
    trace_flags: int = 1
    is_valid: bool = True


class _Span:
    def get_span_context(self) -> _SpanContext:
        return _SpanContext()


class _Provider:
    @contextmanager
    def start_span(self, _name: str, attributes: dict[str, Any] | None = None):
        del attributes
        yield _Span()


class _Store:
    def __init__(self, runtime: OperationalRuntime) -> None:
        self.runtime = runtime

    async def reserve(self, *, entrypoint: str, parent_context: Any) -> int:
        self.runtime.events.append("reserve")
        self.runtime.entrypoints.append(entrypoint)
        self.runtime.parents.append(
            parent_context.operation_id if parent_context is not None else None
        )
        operation_id = self.runtime.next_id
        self.runtime.next_id += 1
        return operation_id

    async def activate(self, _context: Any) -> None:
        self.runtime.events.append("activate")

    async def finish(self, _context: Any, **_kwargs: Any) -> None:
        self.runtime.events.append("finish")


@dataclass
class OperationalRuntime:
    events: list[str]
    entrypoints: list[str]
    parents: list[str | None]
    next_id: int = 8000


def install_operational_runtime(monkeypatch: Any) -> OperationalRuntime:
    """Replace only provider, persistence, lifecycle, and exporter boundaries."""
    from src.clients import operational_observability as module

    runtime = OperationalRuntime(events=[], entrypoints=[], parents=[])
    store = _Store(runtime)

    def create_lifecycle(*, service_name: str, lifecycle_kind: str) -> _Lifecycle:
        assert lifecycle_kind == "short_lived"
        return _Lifecycle(service_name)

    async def shutdown(_lifecycle: _Lifecycle) -> bool:
        return True

    monkeypatch.setattr(module, "create_telemetry_lifecycle", create_lifecycle)
    monkeypatch.setattr(module, "create_durable_operation_store", lambda: store)
    monkeypatch.setattr(module, "get_provider", _Provider)
    monkeypatch.setattr(module, "shutdown_process_telemetry", shutdown)
    return runtime
