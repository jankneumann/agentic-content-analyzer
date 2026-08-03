"""RI-09 terminal-event diagnostic API contract and boundary tests."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import yaml
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.dependencies import verify_admin_key
from src.api.operation_routes import router as operation_router
from src.contracts.workflow_models import (
    WorkflowAlertVerificationContext,
    WorkflowTerminalDeliveryCounts,
    WorkflowTerminalEventDiagnostic,
)

EVENT_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
REVISION = "a" * 40


def test_workflow_alert_verification_context_is_authenticated_positive_staging_proof(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "src.api.operation_routes.get_settings",
        lambda: type("Settings", (), {"environment": "staging"})(),
    )
    monkeypatch.setattr(
        "src.api.operation_routes.release_identity",
        lambda: (REVISION, "railway_commit_sha"),
    )

    response = client.get("/api/v1/workflow-alert-verification-context")

    assert response.status_code == 200
    assert response.json() == WorkflowAlertVerificationContext(
        environment_class="staging",
        revision=REVISION,
        revision_source="railway_commit_sha",
    ).model_dump(mode="json")
    # Introspect the router rather than `app.routes`: starlette >=1.0 no longer
    # flattens included routers into `app.routes`, though the routes still
    # resolve — which is why the request above succeeds. CI resolves the newest
    # allowed starlette, so reading `app.routes` passes locally and fails there.
    route = next(
        route
        for route in operation_router.routes
        if getattr(route, "path", None) == "/api/v1/workflow-alert-verification-context"
    )
    assert verify_admin_key in [dependency.call for dependency in route.dependant.dependencies]


def test_workflow_alert_verification_context_fails_closed_outside_verified_staging(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "src.api.operation_routes.get_settings",
        lambda: type("Settings", (), {"environment": "production"})(),
    )
    monkeypatch.setattr(
        "src.api.operation_routes.release_identity",
        lambda: (REVISION, "railway_commit_sha"),
    )

    response = client.get("/api/v1/workflow-alert-verification-context")

    assert response.status_code == 503
    assert "production" not in response.text


def test_workflow_alert_verification_context_rejects_untrusted_revision_provenance(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "src.api.operation_routes.get_settings",
        lambda: type("Settings", (), {"environment": "staging"})(),
    )
    monkeypatch.setattr(
        "src.api.operation_routes.release_identity",
        lambda: ("secret-revision-marker", "unavailable"),
    )

    response = client.get("/api/v1/workflow-alert-verification-context")

    assert response.status_code == 503
    assert "secret-revision-marker" not in response.text


def _diagnostic() -> WorkflowTerminalEventDiagnostic:
    return WorkflowTerminalEventDiagnostic(
        event_id=EVENT_ID,
        event_key="operation:42:claim:2:status:failed",
        source_kind="operation",
        operation_id="42",
        claim_generation=2,
        terminal_status="failed",
        classification_status="ready",
        release_revision=REVISION,
        release_revision_source="railway_commit_sha",
        occurred_at=datetime(2026, 8, 1, 12, tzinfo=UTC),
        telemetry_emitted_at=datetime(2026, 8, 1, 12, 0, 1, tzinfo=UTC),
        delivery_counts=WorkflowTerminalDeliveryCounts(
            pending=0,
            leased=0,
            delivered=1,
            permanent_failure=0,
            exhausted=0,
        ),
    )


def test_terminal_event_diagnostic_is_authenticated_and_allowlist_first(
    client,
    monkeypatch,
) -> None:
    connection = object()

    @asynccontextmanager
    async def queue_connection(*_args, **_kwargs):
        yield connection

    get_diagnostic = AsyncMock(return_value=_diagnostic())
    monkeypatch.setattr(
        "src.api.operation_routes.queue_setup._queue_connection",
        queue_connection,
    )
    monkeypatch.setattr(
        "src.api.operation_routes.WorkflowTerminalEventService.get_diagnostic",
        get_diagnostic,
    )

    response = client.get(f"/api/v1/workflow-terminal-events/{EVENT_ID}")

    assert response.status_code == 200
    assert response.json() == _diagnostic().model_dump(mode="json")
    assert set(response.json()) == {
        "schema_version",
        "event_id",
        "event_key",
        "source_kind",
        "operation_id",
        "claim_generation",
        "terminal_status",
        "classification_status",
        "release_revision",
        "release_revision_source",
        "occurred_at",
        "telemetry_emitted_at",
        "delivery_counts",
    }
    get_diagnostic.assert_awaited_once_with(EVENT_ID)

    # See above: read the router, not `app.routes`, so this holds on starlette >=1.0.
    route = next(
        route
        for route in operation_router.routes
        if getattr(route, "path", None) == "/api/v1/workflow-terminal-events/{event_id}"
    )
    assert verify_admin_key in [dependency.call for dependency in route.dependant.dependencies]


def test_terminal_event_diagnostic_returns_bounded_not_found(client, monkeypatch) -> None:
    @asynccontextmanager
    async def queue_connection(*_args, **_kwargs):
        yield object()

    monkeypatch.setattr(
        "src.api.operation_routes.queue_setup._queue_connection",
        queue_connection,
    )
    monkeypatch.setattr(
        "src.api.operation_routes.WorkflowTerminalEventService.get_diagnostic",
        AsyncMock(return_value=None),
    )

    response = client.get(f"/api/v1/workflow-terminal-events/{EVENT_ID}")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json() == {
        "type": "https://aca.rotkohl.ai/problems/not-found",
        "title": "Not Found",
        "status": 404,
        "detail": "Not found",
    }


def test_terminal_event_diagnostic_auth_errors_match_problem_contract(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    from src.config.settings import get_settings

    get_settings.cache_clear()
    with TestClient(app) as production_client:
        unauthorized = production_client.get(f"/api/v1/workflow-terminal-events/{EVENT_ID}")
        forbidden = production_client.get(
            f"/api/v1/workflow-terminal-events/{EVENT_ID}",
            headers={"X-Admin-Key": "wrong-key"},
        )

    for response, status_code in ((unauthorized, 401), (forbidden, 403)):
        assert response.status_code == status_code
        assert response.headers["content-type"].startswith("application/problem+json")
        body = response.json()
        assert body["status"] == status_code
        assert set(body) >= {"type", "title", "status", "detail"}


def test_terminal_event_diagnostic_malformed_uuid_matches_validation_problem_contract(
    client,
) -> None:
    response = client.get("/api/v1/workflow-terminal-events/not-a-uuid")

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["type"] == "https://aca.rotkohl.ai/problems/validation_error"
    assert body["title"] == "Unprocessable Entity"
    assert body["status"] == 422
    assert body["detail"] == "Request validation failed"
    assert body["code"] == "validation_error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["path"] == ["path", "event_id"]
    assert body["errors"][0]["code"] == "uuid_parsing"
    assert len(body["errors"][0]["message"]) <= 200
    assert "not-a-uuid" not in response.text
    assert len(response.content) < 1024


def test_canonical_openapi_owns_terminal_event_diagnostic_contract() -> None:
    with open("openspec/contracts/content-workflows/openapi/v1.yaml") as contract:
        openapi = yaml.safe_load(contract)

    operation = openapi["paths"]["/api/v1/workflow-terminal-events/{event_id}"]["get"]
    assert operation["operationId"] == "getWorkflowTerminalEvent"
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/WorkflowTerminalEventDiagnostic"
    }
    assert operation["responses"]["422"] == {"$ref": "#/components/responses/ValidationProblem"}
    schema = openapi["components"]["schemas"]["WorkflowTerminalEventDiagnostic"]
    assert schema["additionalProperties"] is False
    assert "error" not in schema["properties"]
    assert "envelope" not in schema["properties"]


def test_canonical_openapi_owns_alert_verification_context_contract() -> None:
    with open("openspec/contracts/content-workflows/openapi/v1.yaml") as contract:
        openapi = yaml.safe_load(contract)

    operation = openapi["paths"]["/api/v1/workflow-alert-verification-context"]["get"]
    assert operation["operationId"] == "getWorkflowAlertVerificationContext"
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/WorkflowAlertVerificationContext"
    }
    schema = openapi["components"]["schemas"]["WorkflowAlertVerificationContext"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["environment_class"] == {"type": "string", "const": "staging"}
    assert schema["properties"]["revision_source"] == {
        "type": "string",
        "const": "railway_commit_sha",
    }
    ingestion_response = openapi["components"]["responses"]["AcceptedIngestionOperation"]
    assert set(ingestion_response["headers"]) == {
        "X-Release-Revision",
        "X-Release-Revision-Source",
    }
