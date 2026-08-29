"""Contract tests for operator-facing operation observability surfaces."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.api.app import app
from src.api.workflow_dependencies import get_operation_service
from src.contracts.workflow_models import OperationHandle
from src.models.jobs import OperationStatus, OperationType

TRACE_ID = "1" * 32
SPAN_ID = "2" * 16
OPERATOR_KEY = "operator-capability-for-observability-tests"


def _handle() -> OperationHandle:
    return OperationHandle(
        operation_id="42",
        operation_type=OperationType.INGESTION_EXECUTE,
        status=OperationStatus.COMPLETED,
        progress=100,
        message="Completed",
        cancellable=False,
        retry_count=1,
        status_url="/api/v1/operations/42",
        events_url="/api/v1/operations/42/events",
        created_at=datetime(2026, 8, 29, tzinfo=UTC),
        completed_at=datetime(2026, 8, 29, 0, 1, tzinfo=UTC),
    )


def _attempt(generation: int) -> SimpleNamespace:
    return SimpleNamespace(
        operation_id=42,
        claim_generation=generation,
        attempt_number=generation + 1,
        trace_id=TRACE_ID,
        root_span_id=SPAN_ID,
        langfuse_observation_id=f"obs-{generation}",
        service_name="aca-worker",
        service_instance_id="worker-1",
        environment="production",
        release_revision="a" * 40,
        started_at=datetime(2026, 8, 29, tzinfo=UTC) + timedelta(seconds=generation),
        completed_at=datetime(2026, 8, 29, tzinfo=UTC)
        + timedelta(seconds=generation + 1),
        terminal_stage="persist",
        outcome="succeeded",
        retryable=False,
        telemetry_delivery_state="delivered",
        diagnostic_codes=(),
        diagnostics_omitted=0,
    )


class _OperationService:
    async def get(self, operation_id: str):
        assert operation_id == "42"
        return _handle()

    async def wait(self, operation_id: str, *, timeout_seconds: int):
        assert timeout_seconds <= 30
        return await self.get(operation_id)


class _Connection:
    async def fetchrow(self, _query: str, operation_id: int):
        assert operation_id == 42
        return {"root_operation_id": 42, "trace_id": TRACE_ID}

    async def fetchval(self, _query: str, operation_id: int, *_args):
        assert operation_id == 42
        return 3


def _settings(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    monkeypatch.setenv("OPERATOR_API_KEY", OPERATOR_KEY)
    monkeypatch.setenv("LANGFUSE_PUBLIC_URL", "https://traces.example.test")
    from src.config.settings import get_settings

    get_settings.cache_clear()


def _wire(monkeypatch, attempts: list[SimpleNamespace] | None = None) -> None:
    attempts = attempts or [_attempt(0), _attempt(1), _attempt(2)]

    @asynccontextmanager
    async def connection(*_args, **_kwargs):
        yield _Connection()

    async def fake_list_attempts(
        _connection,
        _operation_id,
        *,
        after_claim_generation=None,
        limit=100,
    ):
        selected = [
            attempt
            for attempt in attempts
            if after_claim_generation is None
            or attempt.claim_generation > after_claim_generation
        ]
        return selected[:limit]

    monkeypatch.setattr("src.api.operation_routes.queue_setup._queue_connection", connection)
    monkeypatch.setattr("src.api.operation_routes.list_attempts", fake_list_attempts)
    app.dependency_overrides[get_operation_service] = lambda: _OperationService()


def test_exact_operation_preserves_legacy_auth_and_hides_privileged_link(monkeypatch) -> None:
    _settings(monkeypatch)
    _wire(monkeypatch)
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/operations/42", headers={"X-Admin-Key": "test-admin-key"}
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["observability"]["trace_id"] == TRACE_ID
    assert response.json()["observability"]["langfuse_url"] is None


def test_exact_operation_operator_receives_only_trusted_langfuse_url(monkeypatch) -> None:
    _settings(monkeypatch)
    _wire(monkeypatch)
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/operations/42",
            headers={"X-Admin-Key": "test-admin-key", "X-Operator-Key": OPERATOR_KEY},
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["observability"]["langfuse_url"] == (
        f"https://traces.example.test/trace/{TRACE_ID}"
    )
    assert "localhost" not in response.text
    assert "langfuse" not in response.text.lower()


def test_legacy_exact_operation_remains_readable_without_fabricated_trace(monkeypatch) -> None:
    _settings(monkeypatch)
    _wire(monkeypatch, attempts=[])

    class LegacyConnection(_Connection):
        async def fetchrow(self, _query: str, operation_id: int):
            assert operation_id == 42
            return {"root_operation_id": None, "trace_id": None}

        async def fetchval(self, _query: str, operation_id: int, *_args):
            return 0

    @asynccontextmanager
    async def legacy_connection(*_args, **_kwargs):
        yield LegacyConnection()

    monkeypatch.setattr(
        "src.api.operation_routes.queue_setup._queue_connection", legacy_connection
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/operations/42", headers={"X-Admin-Key": "test-admin-key"}
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["observability"] is None


def test_attempt_history_requires_distinct_operator_capability(monkeypatch) -> None:
    _settings(monkeypatch)
    _wire(monkeypatch)
    with TestClient(app) as client:
        normal = client.get(
            "/api/v1/operations/42/attempts",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        wrong = client.get(
            "/api/v1/operations/42/attempts",
            headers={"X-Admin-Key": "test-admin-key", "X-Operator-Key": "wrong"},
        )
    app.dependency_overrides.clear()
    assert normal.status_code == 401
    assert wrong.status_code == 403
    assert normal.headers["content-type"].startswith("application/problem+json")
    assert wrong.headers["content-type"].startswith("application/problem+json")


def test_attempt_history_is_ascending_and_cursor_paginated(monkeypatch) -> None:
    _settings(monkeypatch)
    _wire(monkeypatch)
    headers = {"X-Admin-Key": "test-admin-key", "X-Operator-Key": OPERATOR_KEY}
    with TestClient(app) as client:
        first = client.get("/api/v1/operations/42/attempts?limit=2", headers=headers)
        second = client.get(
            "/api/v1/operations/42/attempts?limit=2&after_claim_generation=1",
            headers=headers,
        )
    app.dependency_overrides.clear()
    assert first.status_code == 200
    assert [item["claim_generation"] for item in first.json()["attempts"]] == ["0", "1"]
    assert first.json()["next_after_claim_generation"] == "1"
    assert first.json()["attempts_omitted"] == 1
    assert [item["claim_generation"] for item in second.json()["attempts"]] == ["2"]
    assert second.json()["next_after_claim_generation"] is None


def test_operation_lists_remain_summary_only(monkeypatch) -> None:
    _settings(monkeypatch)

    class ListingService(_OperationService):
        async def list(self, **_kwargs):
            summary = _handle().model_dump(
                exclude={"resource", "result", "problem", "observability"}
            )
            return {"data": [summary], "next_cursor": None}

    app.dependency_overrides[get_operation_service] = lambda: ListingService()
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/operations", headers={"X-Admin-Key": "test-admin-key"}
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    item = response.json()["data"][0]
    assert "attempts" not in item
    assert "langfuse_url" not in item


def test_deployment_observability_health_is_operator_only_and_aggregated(monkeypatch) -> None:
    _settings(monkeypatch)
    now = datetime.now(UTC)
    common = dict(
        environment="production",
        release_revision="a" * 40,
        lifecycle_kind="long_running",
        expires_at=now + timedelta(hours=23),
        required_observability=True,
        export_target="local_langfuse",
        last_heartbeat_at=now,
        buffer_capacity=10_000,
        last_flush_at=None,
        last_flush_succeeded=None,
    )
    rows = [
        SimpleNamespace(
            **common,
            service_name="aca-api",
            service_instance_id="api-1",
            initialized=True,
            status="healthy",
            last_success_at=now,
            last_error_at=None,
            last_error_code=None,
            buffered_count=0,
            dropped_count=0,
        ),
        SimpleNamespace(
            **common,
            service_name="aca-worker",
            service_instance_id="worker-1",
            initialized=False,
            status="degraded",
            last_success_at=None,
            last_error_at=now,
            last_error_code="export.unavailable",
            buffered_count=10,
            dropped_count=1,
        ),
    ]

    @asynccontextmanager
    async def connection(*_args, **_kwargs):
        yield object()

    async def fake_list_health(_connection, environment, *, now, limit):
        assert environment == "production"
        assert limit == 1000
        return rows, 7

    monkeypatch.setattr("src.api.operation_routes.queue_setup._queue_connection", connection)
    monkeypatch.setattr("src.api.operation_routes.list_process_health", fake_list_health)
    headers = {"X-Admin-Key": "test-admin-key", "X-Operator-Key": OPERATOR_KEY}
    with TestClient(app) as client:
        normal = client.get(
            "/api/v1/status/observability",
            headers={"X-Admin-Key": "test-admin-key"},
        )
        operator = client.get("/api/v1/status/observability", headers=headers)
    assert normal.status_code == 401
    assert operator.status_code == 503
    assert operator.json()["status"] == "degraded"
    assert operator.json()["processes_omitted"] == 7
    assert {row["service_name"] for row in operator.json()["processes"]} == {
        "aca-api",
        "aca-worker",
    }


def test_synthetic_mobile_response_always_has_lossless_trace_header(monkeypatch) -> None:
    _settings(monkeypatch)
    _wire(monkeypatch)
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/operations/42", headers={"X-Admin-Key": "test-admin-key"}
        )
    app.dependency_overrides.clear()
    trace_id = response.headers["X-Trace-Id"]
    assert len(trace_id) == 32
    assert trace_id != "0" * 32
    int(trace_id, 16)
