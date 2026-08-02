from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from jsonschema import FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from jsonschema.validators import validator_for
from pydantic import ValidationError

from src.contracts.workflow_alert_models import (
    WorkflowAlertCounts,
    WorkflowAlertDeliveryV1,
    WorkflowAlertEnvelopeV1,
    WorkflowAlertResourceReference,
    WorkflowAlertStagingEvidenceV1,
    WorkflowAlertStagingRedactionAssertions,
    WorkflowTerminalEventV1,
)

CHANGE_DIR = (
    Path(__file__).resolve().parents[2]
    / "openspec"
    / "changes"
    / "production-telemetry-and-out-of-band-alerting"
)


def _load_schema(name: str) -> dict[str, object]:
    return json.loads((CHANGE_DIR / "contracts" / name).read_text())


def _validate(schema: dict[str, object], instance: dict[str, object]) -> None:
    validator_type = validator_for(schema)
    validator_type.check_schema(schema)
    validator_type(schema, format_checker=FormatChecker()).validate(instance)


def _valid_envelope() -> dict[str, object]:
    return {
        "schema_version": 1,
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "event_key": "operation:42:claim:3:status:failed",
        "occurred_at": "2026-08-01T23:30:00Z",
        "severity": "error",
        "outcome": "failed",
        "source_kind": "operation",
        "workflow_type": "ingestion.execute",
        "operation_id": "42",
        "attempt": 3,
        "diagnostic_url": "https://ops.example.com/api/v1/operations/42",
        "resource_refs": [{"type": "content", "id": "opaque_42"}],
        "source_keys": ["src_0123456789abcdef0123"],
        "counts": {"items_failed": 1, "sources_total": 1},
        "codes": ["source_timeout"],
    }


def _valid_staging_evidence() -> dict[str, object]:
    return {
        "schema_version": 1,
        "environment_class": "staging",
        "operation_id": "42",
        "attempt": 3,
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "outcome": "failed",
        "severity": "error",
        "terminal_at": "2026-08-01T23:30:00Z",
        "received_at": "2026-08-01T23:30:01Z",
        "receipt_sha256": "a" * 64,
        "delivery_count": 1,
        "redaction_assertions": {
            "no_secrets": True,
            "no_pii": True,
            "no_user_content": True,
            "no_raw_urls": True,
            "schema_valid": True,
        },
    }


@pytest.mark.parametrize(
    ("schema_name", "factory"),
    [
        ("workflow-alert-envelope.schema.json", _valid_envelope),
        ("staging-evidence.schema.json", _valid_staging_evidence),
    ],
)
def test_workflow_alert_schemas_accept_the_closed_valid_contract(
    schema_name: str,
    factory,
) -> None:
    _validate(_load_schema(schema_name), factory())


@pytest.mark.parametrize(
    ("schema_name", "factory"),
    [
        ("workflow-alert-envelope.schema.json", _valid_envelope),
        ("staging-evidence.schema.json", _valid_staging_evidence),
    ],
)
def test_workflow_alert_schemas_reject_unknown_extension_fields(
    schema_name: str,
    factory,
) -> None:
    instance = factory()
    instance["raw_error"] = "do-not-export"

    with pytest.raises(JsonSchemaValidationError):
        _validate(_load_schema(schema_name), instance)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("event_id",), "x" * 37),
        (("event_key",), "x" * 161),
        (("occurred_at",), "2026-08-01T23:30:00.12345678901234567890Z"),
        (("attempt",), 2_147_483_648),
        (("diagnostic_url",), "https://example.com/" + "x" * 2048),
        (("resource_refs",), [{"type": "content", "id": "x"}] * 21),
        (("resource_refs", 0, "id"), "x" * 81),
        (("source_keys",), [f"src_{index:020x}" for index in range(101)]),
        (("counts", "items_failed"), 9_223_372_036_854_775_808),
        (("codes",), [f"code_{index}" for index in range(21)]),
    ],
)
def test_workflow_alert_envelope_schema_enforces_every_declared_bound(
    path: tuple[str | int, ...],
    value: object,
) -> None:
    instance = _valid_envelope()
    target: object = instance
    for component in path[:-1]:
        target = target[component]  # type: ignore[index]
    target[path[-1]] = value  # type: ignore[index]

    with pytest.raises(JsonSchemaValidationError):
        _validate(_load_schema("workflow-alert-envelope.schema.json"), instance)


@pytest.mark.parametrize(
    "diagnostic_url",
    [
        "https://user:password@ops.example.com/api/v1/operations/42",
        "https://ops.example.com/api/v1/operations/42?token=secret",
        "https://ops.example.com/api/v1/operations/42#secret",
        "https://ops.example.com/api/v1/operations/0",
        "https://ops.example.com/arbitrary/path",
    ],
)
def test_workflow_alert_envelope_rejects_untrusted_diagnostic_urls(
    diagnostic_url: str,
) -> None:
    instance = {**_valid_envelope(), "diagnostic_url": diagnostic_url}

    with pytest.raises(JsonSchemaValidationError):
        _validate(_load_schema("workflow-alert-envelope.schema.json"), instance)
    with pytest.raises(ValidationError, match="diagnostic_url"):
        WorkflowAlertEnvelopeV1.model_validate(instance)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("operation_id", "12345678901234567890"),
        ("attempt", 2_147_483_648),
        ("event_id", "x" * 37),
        ("terminal_at", "2026-08-01T23:30:00.12345678901234567890Z"),
        ("received_at", "2026-08-01T23:30:00.12345678901234567890Z"),
    ],
)
def test_staging_evidence_schema_enforces_every_declared_bound(
    field: str,
    value: object,
) -> None:
    instance = _valid_staging_evidence()
    instance[field] = value

    with pytest.raises(JsonSchemaValidationError):
        _validate(_load_schema("staging-evidence.schema.json"), instance)


def test_workflow_alert_python_models_are_strict_and_json_safe() -> None:
    occurred_at = datetime(2026, 8, 1, 23, 30, tzinfo=UTC)
    event_id = UUID("550e8400-e29b-41d4-a716-446655440000")
    event = WorkflowTerminalEventV1(
        event_id=event_id,
        event_key="operation:42:claim:3:status:failed",
        source_kind="operation",
        operation_id="42",
        claim_generation=3,
        terminal_status="failed",
        occurred_at=occurred_at,
    )
    envelope = WorkflowAlertEnvelopeV1(
        event_id=event_id,
        event_key=event.event_key,
        occurred_at=occurred_at,
        severity="error",
        outcome="failed",
        source_kind="operation",
        workflow_type="ingestion.execute",
        operation_id="42",
        attempt=3,
        diagnostic_url="https://ops.example.com/api/v1/operations/42",
        resource_refs=[WorkflowAlertResourceReference(type="content", id="opaque_42")],
        source_keys=["src_0123456789abcdef0123"],
        counts=WorkflowAlertCounts(items_failed=1, sources_total=1),
        codes=["source_timeout"],
    )
    delivery = WorkflowAlertDeliveryV1(
        delivery_id=UUID("16fd2706-8baf-433b-82eb-8c7fada847da"),
        event_id=event_id,
        sink_name="webhook",
        status="pending",
        attempt_count=0,
        next_attempt_at=occurred_at,
    )

    _validate(
        _load_schema("workflow-alert-envelope.schema.json"),
        envelope.model_dump(mode="json"),
    )
    assert delivery.model_dump(mode="json")["status"] == "pending"

    with pytest.raises(ValidationError, match="extra_forbidden"):
        WorkflowAlertEnvelopeV1.model_validate({**_valid_envelope(), "payload": {"x": 1}})

    with pytest.raises(ValidationError, match="must be omitted rather than null"):
        WorkflowAlertCounts(items_failed=None)

    with pytest.raises(ValidationError, match="source_keys must be unique"):
        WorkflowAlertEnvelopeV1.model_validate(
            {**_valid_envelope(), "source_keys": ["src_0123456789abcdef0123"] * 2}
        )

    with pytest.raises(ValidationError, match="timezone"):
        WorkflowAlertEnvelopeV1.model_validate(
            {**_valid_envelope(), "occurred_at": "2026-08-01T23:30:00"}
        )


def test_terminal_event_preserves_unclaimed_queued_cancellation_generation() -> None:
    event = WorkflowTerminalEventV1(
        event_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        event_key="operation:42:claim:0:status:cancelled",
        source_kind="operation",
        operation_id="42",
        claim_generation=0,
        terminal_status="cancelled",
        occurred_at=datetime(2026, 8, 1, 23, 30, tzinfo=UTC),
    )

    assert event.claim_generation == 0


def test_staging_evidence_python_model_matches_checked_in_schema() -> None:
    evidence = WorkflowAlertStagingEvidenceV1(
        operation_id="42",
        attempt=3,
        event_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        outcome="failed",
        severity="error",
        terminal_at=datetime(2026, 8, 1, 23, 30, tzinfo=UTC),
        received_at=datetime(2026, 8, 1, 23, 30, 1, tzinfo=UTC),
        receipt_sha256="a" * 64,
        delivery_count=1,
        redaction_assertions=WorkflowAlertStagingRedactionAssertions(
            no_secrets=True,
            no_pii=True,
            no_user_content=True,
            no_raw_urls=True,
            schema_valid=True,
        ),
    )

    _validate(
        _load_schema("staging-evidence.schema.json"),
        evidence.model_dump(mode="json"),
    )

    with pytest.raises(ValidationError, match="literal_error"):
        WorkflowAlertStagingEvidenceV1.model_validate(
            {**_valid_staging_evidence(), "delivery_count": 2}
        )


def test_workflow_alert_secret_is_absent_from_settings_api_contract() -> None:
    from src.api.app import app

    openapi = json.dumps(app.openapi(), sort_keys=True)

    assert "workflow_alert_webhook_secret" not in openapi
    assert "WORKFLOW_ALERT_WEBHOOK_SECRET" not in openapi
