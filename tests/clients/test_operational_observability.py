from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest

from src.contracts.operation_context import get_current_operation_context


class _Lifecycle:
    service_name = "aca-test"
    service_instance_id = "test-instance"
    release_revision = "test-release"
    initialized = False
    last_flush_succeeded: bool | None = None

    class _Settings:
        environment = "test"

    settings = _Settings()

    def initialize(self, *, app: Any = None) -> None:
        del app
        self.initialized = True


class _Provider:
    def __init__(self) -> None:
        self.spans: list[tuple[str, dict[str, Any]]] = []

    @contextmanager
    def start_span(self, name: str, attributes: dict[str, Any] | None = None):
        self.spans.append((name, attributes or {}))
        yield None


@pytest.fixture
def operational_runtime(monkeypatch: pytest.MonkeyPatch):
    from src.clients import operational_observability as module

    lifecycles: list[_Lifecycle] = []
    provider = _Provider()

    def create_lifecycle(*, service_name: str, lifecycle_kind: str) -> _Lifecycle:
        assert service_name == "aca-test"
        assert lifecycle_kind == "short_lived"
        lifecycle = _Lifecycle()
        lifecycles.append(lifecycle)
        return lifecycle

    async def shutdown(lifecycle: _Lifecycle) -> bool:
        lifecycle.last_flush_succeeded = True
        return True

    monkeypatch.setattr(module, "create_telemetry_lifecycle", create_lifecycle)
    monkeypatch.setattr(module, "shutdown_process_telemetry", shutdown)
    monkeypatch.setattr(module, "get_provider", lambda: provider)
    return module, lifecycles, provider


def test_sync_operational_entrypoint_binds_valid_root_and_flushes(operational_runtime) -> None:
    module, lifecycles, provider = operational_runtime
    observed = None

    @module.operational_entrypoint("backup.run", stage="backup", service_name="aca-test")
    def execute(secret: str) -> str:
        nonlocal observed
        observed = get_current_operation_context()
        return "ok"

    assert execute("token=do-not-export") == "ok"
    assert observed is not None
    assert observed.operation_id == observed.root_operation_id
    assert observed.parent_operation_id is None
    assert observed.attempt_number is None
    assert observed.stage == "backup"
    assert lifecycles[0].initialized is True
    assert lifecycles[0].last_flush_succeeded is True
    assert provider.spans[0][0] == "operation.backup.run"
    assert "do-not-export" not in repr(provider.spans)


@pytest.mark.asyncio
async def test_async_operational_entrypoint_preserves_failure_and_flushes(
    operational_runtime,
) -> None:
    module, lifecycles, provider = operational_runtime

    @module.operational_entrypoint("mcp.search", stage="fetch", service_name="aca-test")
    async def execute() -> None:
        assert get_current_operation_context() is not None
        raise RuntimeError("provider failed")

    with pytest.raises(RuntimeError, match="provider failed"):
        await execute()

    assert lifecycles[0].last_flush_succeeded is True
    assert provider.spans[0][0] == "operation.mcp.search"
