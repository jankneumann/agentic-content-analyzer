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
        "release_revision": "a" * 40,
        "release_revision_source": "railway_commit_sha",
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
        "revision": "a" * 40,
        "revision_source": "railway_commit_sha",
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
    ("revision", "source"),
    [
        ("development", "railway_commit_sha"),
        ("a" * 40, "local_development"),
        ("a" * 40, "unavailable"),
    ],
)
def test_workflow_alert_envelope_rejects_mismatched_release_provenance(
    revision: str,
    source: str,
) -> None:
    instance = {
        **_valid_envelope(),
        "release_revision": revision,
        "release_revision_source": source,
    }

    with pytest.raises(JsonSchemaValidationError):
        _validate(_load_schema("workflow-alert-envelope.schema.json"), instance)
    with pytest.raises(ValidationError, match="release"):
        WorkflowAlertEnvelopeV1.model_validate(instance)


def test_workflow_alert_envelope_accepts_legacy_absent_release_provenance() -> None:
    instance = _valid_envelope()
    instance.pop("release_revision")
    instance.pop("release_revision_source")

    _validate(_load_schema("workflow-alert-envelope.schema.json"), instance)
    envelope = WorkflowAlertEnvelopeV1.model_validate(instance)

    assert envelope.release_revision is None
    assert envelope.release_revision_source is None


@pytest.mark.parametrize("missing", ["release_revision", "release_revision_source"])
def test_workflow_alert_envelope_rejects_one_sided_release_provenance(missing: str) -> None:
    instance = _valid_envelope()
    instance.pop(missing)

    with pytest.raises(JsonSchemaValidationError):
        _validate(_load_schema("workflow-alert-envelope.schema.json"), instance)
    with pytest.raises(ValidationError, match="present together"):
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
        release_revision="a" * 40,
        release_revision_source="railway_commit_sha",
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
        revision="a" * 40,
        revision_source="railway_commit_sha",
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


# ---------------------------------------------------------------------------
# system_check widening (design A9/A11/A12/A14)
#
# The schema for backup-freshness alerts is a NARROWED variant of
# WorkflowAlertEnvelopeV1 — constants where the model has enums, subsets where it
# has full literals. So the assertion is narrowing-compatibility, not field
# equality: every schema constraint at least as strict as the model's, no schema
# field absent from the model, and no model field absent from the schema.
#
# This check is mechanical and belongs in CI rather than in a reviewer's
# attention. The diagnostic-code set drifted three times during planning while it
# was enumerated in three places; it is now decided in the schema alone.
# ---------------------------------------------------------------------------

BACKUP_ALERT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "openspec"
    / "contracts"
    / "backup"
    / "events"
    / "backup-freshness-alert.schema.json"
)


def _backup_alert_schema() -> dict[str, object]:
    return json.loads(BACKUP_ALERT_SCHEMA_PATH.read_text())


def _valid_system_check_envelope() -> dict[str, object]:
    event_id = "550e8400-e29b-41d4-a716-446655440000"
    return {
        "schema_version": 1,
        "event_id": event_id,
        "event_key": "system_check:backup_freshness:1755734400",
        "occurred_at": "2026-08-21T03:00:00Z",
        "severity": "error",
        "outcome": "failed",
        "source_kind": "system_check",
        "workflow_type": "system.backup_freshness",
        "release_revision": "development",
        "release_revision_source": "local_development",
        "operation_id": None,
        "attempt": 1,
        "diagnostic_url": (f"https://ops.example.com/api/v1/workflow-terminal-events/{event_id}"),
        "resource_refs": [],
        "source_keys": [],
        "counts": {"manifest_age_seconds": 187200, "stores_succeeded": 3},
        "codes": ["backup_stale"],
    }


def test_backup_alert_schema_declares_no_field_the_model_lacks() -> None:
    schema_fields = set(_backup_alert_schema()["properties"])
    model_fields = set(WorkflowAlertEnvelopeV1.model_fields)

    assert schema_fields - model_fields == set(), (
        "the schema invents fields the model rejects under extra='forbid'"
    )


def test_backup_alert_schema_omits_no_model_field() -> None:
    schema_fields = set(_backup_alert_schema()["properties"])
    model_fields = set(WorkflowAlertEnvelopeV1.model_fields)

    assert model_fields - schema_fields == set(), (
        "the schema omits a model field, so a valid envelope could fail validation"
    )


def test_backup_alert_schema_requires_at_least_what_the_model_requires() -> None:
    schema_required = set(_backup_alert_schema()["required"])
    model_required = {
        name for name, field in WorkflowAlertEnvelopeV1.model_fields.items() if field.is_required()
    }

    assert model_required <= schema_required


def test_backup_alert_schema_instance_is_accepted_by_the_model() -> None:
    """Narrowing-compatibility, checked where it matters: an instance the schema
    accepts must construct as a real envelope, not merely resemble one."""
    _validate(_backup_alert_schema(), _valid_system_check_envelope())
    envelope = WorkflowAlertEnvelopeV1.model_validate(_valid_system_check_envelope())

    assert envelope.source_kind == "system_check"


def test_backup_alert_schema_examples_are_accepted_by_the_model() -> None:
    for example in _backup_alert_schema()["examples"]:
        _validate(_backup_alert_schema(), example)
        WorkflowAlertEnvelopeV1.model_validate(example)


def test_diagnostic_code_type_admits_exactly_the_schema_code_enum() -> None:
    """A11 — the schema is the single source of truth for the backup code set."""
    from pydantic import TypeAdapter

    from src.contracts.workflow_alert_models import WorkflowAlertDiagnosticCode

    adapter = TypeAdapter(WorkflowAlertDiagnosticCode)
    schema_codes = set(_backup_alert_schema()["properties"]["codes"]["items"]["enum"])

    for code in schema_codes:
        adapter.validate_python(code)

    model_backup_codes = {
        value
        for value in _literal_values(WorkflowAlertDiagnosticCode)
        if isinstance(value, str) and value.startswith("backup_")
    }
    assert model_backup_codes == schema_codes


def _literal_values(annotation: object) -> set[object]:
    from typing import get_args

    collected: set[object] = set()
    for arg in get_args(annotation):
        nested = get_args(arg)
        collected.update(nested if nested else ())
    return collected


@pytest.mark.parametrize(
    ("field", "value", "why"),
    [
        ("operation_id", "42", "system checks have no operation identity"),
        ("attempt", 2, "system checks are not retried claims"),
        ("workflow_type", "content.reconciliation", "wrong workflow type"),
        ("outcome", "reconciled", "reconciliation outcome on a system check"),
        (
            "event_key",
            "system_check:backup_freshness:2026-08-21T03:00:00Z",
            "uppercase T/Z fail WorkflowEventKey",
        ),
    ],
)
def test_model_rejects_malformed_system_check_envelopes(
    field: str, value: object, why: str
) -> None:
    """Asserted by constructing a REAL envelope, never by matching a regex in
    isolation — the closed model is authoritative, the table describing it is not."""
    payload = {**_valid_system_check_envelope(), field: value}

    with pytest.raises(ValidationError):
        WorkflowAlertEnvelopeV1.model_validate(payload)


def test_system_check_envelope_requires_the_event_scoped_diagnostic_route() -> None:
    payload = {
        **_valid_system_check_envelope(),
        "diagnostic_url": "https://ops.example.com/api/v1/operations/42",
    }

    with pytest.raises(ValidationError):
        WorkflowAlertEnvelopeV1.model_validate(payload)


def test_counts_model_accepts_the_backup_tallies() -> None:
    """WorkflowAlertCounts is a StrictModel with extra='forbid' — widening
    source_kind alone would have produced an alert that could never be built."""
    counts = WorkflowAlertCounts(
        manifest_age_seconds=1,
        stores_succeeded=2,
        stores_failed=3,
        stores_skipped=4,
    )

    assert counts.model_dump()["stores_failed"] == 3


def test_terminal_event_model_admits_the_system_check_key_grammar() -> None:
    """A13 point 9 retracts the earlier dismissal of this class as irrelevant: the
    emitting service instantiates it on the emission path."""
    event = WorkflowTerminalEventV1(
        event_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        event_key="system_check:backup_freshness:1755734400",
        source_kind="system_check",
        occurred_at=datetime(2026, 8, 21, 3, 0, tzinfo=UTC),
    )

    assert event.source_kind == "system_check"


def test_terminal_event_model_rejects_a_system_check_with_workflow_identity() -> None:
    with pytest.raises(ValidationError):
        WorkflowTerminalEventV1(
            event_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            event_key="system_check:backup_freshness:1755734400",
            source_kind="system_check",
            operation_id="42",
            occurred_at=datetime(2026, 8, 21, 3, 0, tzinfo=UTC),
        )
