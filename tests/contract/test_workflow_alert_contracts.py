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
        "attempt": 4,
        "diagnostic_url": "https://ops.example.com/api/v1/operations/42",
        "resource_refs": [{"type": "content", "id": "42"}],
        "source_keys": ["src_0123456789abcdef0123"],
        "counts": {"items_failed": 1, "sources_total": 1},
        "codes": ["operation_failed"],
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
        (("attempt",), 2_147_483_649),
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
        ("workflow_type", "secret-token"),
        ("resource_refs", [{"type": "credential", "id": "42"}]),
        ("resource_refs", [{"type": "content", "id": "TOPSECRET123"}]),
        ("codes", ["sk-live-secret"]),
    ],
)
def test_workflow_alert_envelope_rejects_pattern_shaped_untrusted_values(
    field: str,
    value: object,
) -> None:
    instance = {**_valid_envelope(), field: value}

    with pytest.raises(JsonSchemaValidationError):
        _validate(_load_schema("workflow-alert-envelope.schema.json"), instance)
    with pytest.raises(ValidationError):
        WorkflowAlertEnvelopeV1.model_validate(instance)


@pytest.mark.parametrize(
    "changes",
    [
        {"diagnostic_url": "https://ops.example.com/api/v1/operations/99"},
        {
            "diagnostic_url": (
                "https://ops.example.com/api/v1/workflow-terminal-events/"
                "550e8400-e29b-41d4-a716-446655440000"
            )
        },
        {"event_key": "operation:99:claim:3:status:failed"},
        {"attempt": 3},
        {"event_key": "operation:42:claim:3:status:completed"},
        {"severity": "warning"},
        {"source_kind": "reconciliation_action", "outcome": "reconciled"},
    ],
)
def test_operation_alert_envelope_rejects_inconsistent_identity_and_classification(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        WorkflowAlertEnvelopeV1.model_validate({**_valid_envelope(), **changes})


@pytest.mark.parametrize(
    "changes",
    [
        {"operation_id": "42"},
        {"severity": "error"},
        {"outcome": "failed"},
        {"attempt": 2},
        {"workflow_type": "ingestion.execute"},
        {"event_key": "reconciliation-action:0"},
        {"diagnostic_url": "https://ops.example.com/api/v1/operations/42"},
        {
            "diagnostic_url": (
                "https://ops.example.com/api/v1/workflow-terminal-events/"
                "16fd2706-8baf-433b-82eb-8c7fada847da"
            )
        },
    ],
)
def test_reconciliation_alert_envelope_rejects_inconsistent_identity_and_classification(
    changes: dict[str, object],
) -> None:
    instance = {
        **_valid_envelope(),
        "event_key": "reconciliation-action:7",
        "severity": "warning",
        "outcome": "reconciled",
        "source_kind": "reconciliation_action",
        "workflow_type": "content.reconciliation",
        "operation_id": None,
        "attempt": 1,
        "diagnostic_url": (
            "https://ops.example.com/api/v1/workflow-terminal-events/"
            "550e8400-e29b-41d4-a716-446655440000"
        ),
        "codes": ["summary_exists"],
        **changes,
    }

    with pytest.raises(ValidationError):
        WorkflowAlertEnvelopeV1.model_validate(instance)


def test_reconciliation_alert_envelope_matches_checked_in_schema() -> None:
    instance = {
        **_valid_envelope(),
        "event_key": "reconciliation-action:7",
        "severity": "warning",
        "outcome": "reconciled",
        "source_kind": "reconciliation_action",
        "workflow_type": "content.reconciliation",
        "operation_id": None,
        "attempt": 1,
        "diagnostic_url": (
            "https://ops.example.com/api/v1/workflow-terminal-events/"
            "550e8400-e29b-41d4-a716-446655440000"
        ),
        "codes": ["summary_exists"],
    }

    envelope = WorkflowAlertEnvelopeV1.model_validate(instance)
    _validate(
        _load_schema("workflow-alert-envelope.schema.json"),
        envelope.model_dump(mode="json"),
    )


def test_reconciliation_failure_envelope_matches_checked_in_schema() -> None:
    instance = {
        **_valid_envelope(),
        "event_key": (
            "reconciliation-failure:550e8400-e29b-41d4-a716-446655440000:"
            "content:42:reason:apply_failed"
        ),
        "source_kind": "reconciliation_failure",
        "workflow_type": "content.reconciliation",
        "operation_id": None,
        "attempt": 1,
        "diagnostic_url": (
            "https://ops.example.com/api/v1/workflow-terminal-events/"
            "550e8400-e29b-41d4-a716-446655440000"
        ),
        "codes": ["apply_failed"],
    }

    envelope = WorkflowAlertEnvelopeV1.model_validate(instance)
    _validate(
        _load_schema("workflow-alert-envelope.schema.json"),
        envelope.model_dump(mode="json"),
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"severity": "warning"},
        {"event_key": "operation:42:claim:3:status:completed"},
        {
            "diagnostic_url": (
                "https://ops.example.com/api/v1/workflow-terminal-events/"
                "550e8400-e29b-41d4-a716-446655440000"
            )
        },
        {
            "source_kind": "reconciliation_action",
            "outcome": "reconciled",
            "event_key": "reconciliation-action:7",
        },
    ],
)
def test_workflow_alert_schema_rejects_cross_field_classification_mismatches(
    changes: dict[str, object],
) -> None:
    with pytest.raises(JsonSchemaValidationError):
        _validate(
            _load_schema("workflow-alert-envelope.schema.json"),
            {**_valid_envelope(), **changes},
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("operation_id", "12345678901234567890"),
        ("attempt", 2_147_483_649),
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


@pytest.mark.parametrize(
    ("outcome", "severity"),
    [("failed", "warning"), ("partial", "error"), ("reconciled", "error")],
)
def test_staging_evidence_rejects_inconsistent_outcome_severity(
    outcome: str,
    severity: str,
) -> None:
    instance = {**_valid_staging_evidence(), "outcome": outcome, "severity": severity}

    with pytest.raises(JsonSchemaValidationError):
        _validate(_load_schema("staging-evidence.schema.json"), instance)
    with pytest.raises(ValidationError):
        WorkflowAlertStagingEvidenceV1.model_validate(instance)


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
        attempt=4,
        diagnostic_url="https://ops.example.com/api/v1/operations/42",
        resource_refs=[WorkflowAlertResourceReference(type="content", id="42")],
        source_keys=["src_0123456789abcdef0123"],
        counts=WorkflowAlertCounts(items_failed=1, sources_total=1),
        codes=["operation_failed"],
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


@pytest.mark.parametrize(
    "changes",
    [
        {"event_key": "operation:42:claim:1:status:cancelled"},
        {"operation_id": None},
        {"claim_generation": None},
        {"terminal_status": None},
    ],
)
def test_terminal_operation_event_requires_exact_claim_identity(
    changes: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "event_id": UUID("550e8400-e29b-41d4-a716-446655440000"),
        "event_key": "operation:42:claim:0:status:cancelled",
        "source_kind": "operation",
        "operation_id": "42",
        "claim_generation": 0,
        "terminal_status": "cancelled",
        "occurred_at": datetime(2026, 8, 1, 23, 30, tzinfo=UTC),
        **changes,
    }

    with pytest.raises(ValidationError):
        WorkflowTerminalEventV1.model_validate(values)


@pytest.mark.parametrize(
    ("source_kind", "event_key"),
    [
        ("reconciliation_action", "reconciliation-action:7"),
        (
            "reconciliation_failure",
            (
                "reconciliation-failure:550e8400-e29b-41d4-a716-446655440000:"
                "content:42:reason:apply_failed"
            ),
        ),
    ],
)
def test_terminal_reconciliation_event_uses_closed_identity_without_operation_fields(
    source_kind: str,
    event_key: str,
) -> None:
    event = WorkflowTerminalEventV1(
        event_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        event_key=event_key,
        source_kind=source_kind,
        occurred_at=datetime(2026, 8, 1, 23, 30, tzinfo=UTC),
    )

    assert event.operation_id is None
    assert event.claim_generation is None
    assert event.terminal_status is None


@pytest.mark.parametrize(
    ("status", "attempt_count", "lease_expires_at", "delivered_at", "error_code"),
    [
        ("pending", 0, datetime(2026, 8, 1, 23, 31, tzinfo=UTC), None, None),
        ("leased", 1, None, None, None),
        ("leased", 0, datetime(2026, 8, 1, 23, 31, tzinfo=UTC), None, None),
        ("delivered", 1, None, None, None),
        ("delivered", 1, None, datetime(2026, 8, 1, 23, 31, tzinfo=UTC), "timeout"),
        ("permanent_failure", 1, None, None, None),
        ("exhausted", 0, None, None, "retry_exhausted"),
    ],
)
def test_delivery_state_rejects_inconsistent_timestamps_and_error_codes(
    status: str,
    attempt_count: int,
    lease_expires_at: datetime | None,
    delivered_at: datetime | None,
    error_code: str | None,
) -> None:
    with pytest.raises(ValidationError):
        WorkflowAlertDeliveryV1(
            delivery_id=UUID("16fd2706-8baf-433b-82eb-8c7fada847da"),
            event_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            sink_name="webhook",
            status=status,
            attempt_count=attempt_count,
            next_attempt_at=datetime(2026, 8, 1, 23, 30, tzinfo=UTC),
            lease_expires_at=lease_expires_at,
            delivered_at=delivered_at,
            last_error_code=error_code,
        )


@pytest.mark.parametrize(
    ("status", "attempt_count", "lease_expires_at", "delivered_at", "error_code"),
    [
        ("pending", 0, None, None, None),
        ("pending", 1, None, None, "timeout"),
        ("leased", 1, datetime(2026, 8, 1, 23, 31, tzinfo=UTC), None, "timeout"),
        ("delivered", 1, None, datetime(2026, 8, 1, 23, 31, tzinfo=UTC), None),
        ("permanent_failure", 1, None, None, "http_4xx"),
        ("exhausted", 5, None, None, "retry_exhausted"),
    ],
)
def test_delivery_state_accepts_each_consistent_lifecycle_state(
    status: str,
    attempt_count: int,
    lease_expires_at: datetime | None,
    delivered_at: datetime | None,
    error_code: str | None,
) -> None:
    delivery = WorkflowAlertDeliveryV1(
        delivery_id=UUID("16fd2706-8baf-433b-82eb-8c7fada847da"),
        event_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        sink_name="webhook",
        status=status,
        attempt_count=attempt_count,
        next_attempt_at=datetime(2026, 8, 1, 23, 30, tzinfo=UTC),
        lease_expires_at=lease_expires_at,
        delivered_at=delivered_at,
        last_error_code=error_code,
    )

    assert delivery.status == status


def test_staging_evidence_python_model_matches_checked_in_schema() -> None:
    evidence = WorkflowAlertStagingEvidenceV1(
        operation_id="42",
        attempt=4,
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
