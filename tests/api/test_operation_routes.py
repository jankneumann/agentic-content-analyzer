"""RI-09 terminal-event diagnostic API contract and boundary tests."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import yaml

from src.api.app import app
from src.api.dependencies import verify_admin_key
from src.contracts.workflow_models import (
    WorkflowTerminalDeliveryCounts,
    WorkflowTerminalEventDiagnostic,
)

EVENT_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def _diagnostic() -> WorkflowTerminalEventDiagnostic:
    return WorkflowTerminalEventDiagnostic(
        event_id=EVENT_ID,
        event_key="operation:42:claim:2:status:failed",
        source_kind="operation",
        operation_id="42",
        claim_generation=2,
        terminal_status="failed",
        classification_status="ready",
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
        "occurred_at",
        "telemetry_emitted_at",
        "delivery_counts",
    }
    get_diagnostic.assert_awaited_once_with(EVENT_ID)

    route = next(
        route
        for route in app.routes
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
    assert response.json()["detail"] == "Not found"


def test_canonical_openapi_owns_terminal_event_diagnostic_contract() -> None:
    with open("openspec/contracts/content-workflows/openapi/v1.yaml") as contract:
        openapi = yaml.safe_load(contract)

    operation = openapi["paths"]["/api/v1/workflow-terminal-events/{event_id}"]["get"]
    assert operation["operationId"] == "getWorkflowTerminalEvent"
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/WorkflowTerminalEventDiagnostic"
    }
    schema = openapi["components"]["schemas"]["WorkflowTerminalEventDiagnostic"]
    assert schema["additionalProperties"] is False
    assert "error" not in schema["properties"]
    assert "envelope" not in schema["properties"]
