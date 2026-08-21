"""Contract tests for the durable backup schemas.

Two schemas are pinned here:

* ``backup-manifest.schema.json`` — the bucket-side run manifest that the freshness
  check reads. Its conditional requirements are the thing that makes an empty upload
  distinguishable from a good one, so they are tested directly rather than assumed.
* ``backup-freshness-alert.schema.json`` — the ``system_check`` narrowing of
  ``WorkflowAlertEnvelopeV1``.

The alert assertions are deliberately **narrowing-compatibility** assertions, not
field-equality assertions (design A14). The schema is correctly a narrowed variant in
several places — constants where the model has enums, subsets where the model has full
literals. What must hold is that the two describe the same shape: identical field sets,
identical required sets, and every instance the schema accepts is also accepted by the
model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from jsonschema.validators import validator_for

pytestmark = pytest.mark.contract

CONTRACT_DIR = Path(__file__).resolve().parents[2] / "openspec" / "contracts" / "backup"


def _load(relative: str) -> dict[str, Any]:
    return json.loads((CONTRACT_DIR / relative).read_text())


def _validate(schema: dict[str, Any], instance: dict[str, Any]) -> None:
    validator_type = validator_for(schema)
    validator_type.check_schema(schema)
    validator_type(schema, format_checker=FormatChecker()).validate(instance)


@pytest.fixture(scope="module")
def manifest_schema() -> dict[str, Any]:
    return _load("schemas/backup-manifest.schema.json")


@pytest.fixture(scope="module")
def alert_schema() -> dict[str, Any]:
    return _load("events/backup-freshness-alert.schema.json")


def _valid_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "environment": "production",
        "started_at": "2026-08-21T03:00:00Z",
        "completed_at": "2026-08-21T03:04:12Z",
        "overall_outcome": "succeeded",
        "retention_tier": "daily",
        "prefix": "aca",
        "stores": [
            {
                "store": "postgres",
                "outcome": "succeeded",
                "required": True,
                "artifact_key": "aca/daily/2026-08-21T030000Z/postgres.dump.age",
                "bytes": 52428800,
                "checksum_sha256": "0" * 64,
            }
        ],
    }


def _valid_alert() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
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
        "diagnostic_url": (
            "https://ops.example.com/api/v1/workflow-terminal-events/"
            "550e8400-e29b-41d4-a716-446655440000"
        ),
        "resource_refs": [],
        "source_keys": [],
        "counts": {"manifest_age_seconds": 187200, "stores_succeeded": 3},
        "codes": ["backup_stale"],
    }


# --------------------------------------------------------------------------- manifest


class TestBackupManifestSchema:
    def test_schema_is_valid_and_examples_conform(self, manifest_schema: dict[str, Any]) -> None:
        for example in manifest_schema["examples"]:
            _validate(manifest_schema, example)

    def test_valid_manifest_accepted(self, manifest_schema: dict[str, Any]) -> None:
        _validate(manifest_schema, _valid_manifest())

    @pytest.mark.parametrize(
        "missing",
        [
            "schema_version",
            "environment",
            "started_at",
            "completed_at",
            "overall_outcome",
            "retention_tier",
            "stores",
        ],
    )
    def test_required_fields_enforced(
        self, manifest_schema: dict[str, Any], missing: str
    ) -> None:
        instance = _valid_manifest()
        del instance[missing]
        with pytest.raises(JsonSchemaValidationError):
            _validate(manifest_schema, instance)

    def test_environment_is_closed(self, manifest_schema: dict[str, Any]) -> None:
        instance = _valid_manifest()
        instance["environment"] = "prod"
        with pytest.raises(JsonSchemaValidationError):
            _validate(manifest_schema, instance)

    def test_retention_tier_is_closed(self, manifest_schema: dict[str, Any]) -> None:
        instance = _valid_manifest()
        instance["retention_tier"] = "hourly"
        with pytest.raises(JsonSchemaValidationError):
            _validate(manifest_schema, instance)

    def test_unknown_top_level_field_rejected(self, manifest_schema: dict[str, Any]) -> None:
        instance = _valid_manifest()
        instance["backup_s3_secret_access_key"] = "AKIA-not-here"
        with pytest.raises(JsonSchemaValidationError):
            _validate(manifest_schema, instance)

    def test_unknown_store_field_rejected(self, manifest_schema: dict[str, Any]) -> None:
        instance = _valid_manifest()
        instance["stores"][0]["endpoint_url"] = "https://key:secret@example.com"
        with pytest.raises(JsonSchemaValidationError):
            _validate(manifest_schema, instance)

    @pytest.mark.parametrize("dropped", ["artifact_key", "bytes", "checksum_sha256"])
    def test_succeeded_store_requires_evidence(
        self, manifest_schema: dict[str, Any], dropped: str
    ) -> None:
        """A7 — without this, an empty upload validates as a good one."""
        instance = _valid_manifest()
        del instance["stores"][0][dropped]
        with pytest.raises(JsonSchemaValidationError):
            _validate(manifest_schema, instance)

    def test_skipped_store_requires_reason(self, manifest_schema: dict[str, Any]) -> None:
        instance = _valid_manifest()
        instance["stores"] = [{"store": "openbao", "outcome": "skipped", "required": False}]
        with pytest.raises(JsonSchemaValidationError):
            _validate(manifest_schema, instance)

    def test_skipped_store_may_not_claim_an_artifact(
        self, manifest_schema: dict[str, Any]
    ) -> None:
        instance = _valid_manifest()
        instance["stores"] = [
            {
                "store": "openbao",
                "outcome": "skipped",
                "required": False,
                "reason": "not_configured",
                "artifact_key": "aca/daily/x/openbao.snap.age",
            }
        ]
        with pytest.raises(JsonSchemaValidationError):
            _validate(manifest_schema, instance)

    def test_failed_store_requires_reason(self, manifest_schema: dict[str, Any]) -> None:
        instance = _valid_manifest()
        instance["stores"] = [{"store": "postgres", "outcome": "failed", "required": True}]
        with pytest.raises(JsonSchemaValidationError):
            _validate(manifest_schema, instance)

    def test_reason_is_a_closed_token_not_free_text(
        self, manifest_schema: dict[str, Any]
    ) -> None:
        """stderr bodies can echo a connection string; reasons are closed tokens."""
        instance = _valid_manifest()
        instance["stores"] = [
            {
                "store": "postgres",
                "outcome": "failed",
                "required": True,
                "reason": "pg_dump: error: connection to postgres://u:p@host failed",
            }
        ]
        with pytest.raises(JsonSchemaValidationError):
            _validate(manifest_schema, instance)

    def test_checksum_must_be_lowercase_sha256(self, manifest_schema: dict[str, Any]) -> None:
        instance = _valid_manifest()
        instance["stores"][0]["checksum_sha256"] = "A" * 64
        with pytest.raises(JsonSchemaValidationError):
            _validate(manifest_schema, instance)

    def test_failed_run_outcome_is_not_expressible(
        self, manifest_schema: dict[str, Any]
    ) -> None:
        """A manifest is never written for a failed run, so 'failed' is not an outcome."""
        instance = _valid_manifest()
        instance["overall_outcome"] = "failed"
        with pytest.raises(JsonSchemaValidationError):
            _validate(manifest_schema, instance)


# ------------------------------------------------------------------------------ alert


class TestBackupFreshnessAlertSchema:
    def test_schema_is_valid_and_examples_conform(self, alert_schema: dict[str, Any]) -> None:
        for example in alert_schema["examples"]:
            _validate(alert_schema, example)

    def test_valid_alert_accepted(self, alert_schema: dict[str, Any]) -> None:
        _validate(alert_schema, _valid_alert())

    def test_source_kind_is_pinned_to_system_check(self, alert_schema: dict[str, Any]) -> None:
        instance = _valid_alert()
        instance["source_kind"] = "operation"
        with pytest.raises(JsonSchemaValidationError):
            _validate(alert_schema, instance)

    def test_operation_identity_must_be_absent(self, alert_schema: dict[str, Any]) -> None:
        instance = _valid_alert()
        instance["operation_id"] = "42"
        with pytest.raises(JsonSchemaValidationError):
            _validate(alert_schema, instance)

    def test_attempt_is_immutable_one(self, alert_schema: dict[str, Any]) -> None:
        instance = _valid_alert()
        instance["attempt"] = 2
        with pytest.raises(JsonSchemaValidationError):
            _validate(alert_schema, instance)

    def test_event_key_grammar_is_lowercase_and_epoch_suffixed(
        self, alert_schema: dict[str, Any]
    ) -> None:
        """A2 — an ISO-8601 stamp carries uppercase T/Z and fails WorkflowEventKey."""
        instance = _valid_alert()
        instance["event_key"] = "system_check:backup_freshness:2026-08-21T03:00:00Z"
        with pytest.raises(JsonSchemaValidationError):
            _validate(alert_schema, instance)

    def test_diagnostic_url_must_be_https(self, alert_schema: dict[str, Any]) -> None:
        instance = _valid_alert()
        instance["diagnostic_url"] = instance["diagnostic_url"].replace("https://", "http://")
        with pytest.raises(JsonSchemaValidationError):
            _validate(alert_schema, instance)

    def test_diagnostic_url_must_be_the_allowlisted_route(
        self, alert_schema: dict[str, Any]
    ) -> None:
        """A3 — /api/v1/health/backup does not exist and is not allowlisted."""
        instance = _valid_alert()
        instance["diagnostic_url"] = "https://ops.example.com/api/v1/health/backup"
        with pytest.raises(JsonSchemaValidationError):
            _validate(alert_schema, instance)

    def test_alert_carries_no_resource_or_source_identity(
        self, alert_schema: dict[str, Any]
    ) -> None:
        for field, value in (
            ("resource_refs", [{"type": "content", "id": "42"}]),
            ("source_keys", ["src_0123456789abcdef0123"]),
        ):
            instance = _valid_alert()
            instance[field] = value
            with pytest.raises(JsonSchemaValidationError):
                _validate(alert_schema, instance)

    def test_unknown_field_rejected(self, alert_schema: dict[str, Any]) -> None:
        instance = _valid_alert()
        instance["backup_s3_endpoint"] = "https://key:secret@r2.example.com"
        with pytest.raises(JsonSchemaValidationError):
            _validate(alert_schema, instance)

    def test_counts_are_closed_to_the_backup_tallies(self, alert_schema: dict[str, Any]) -> None:
        instance = _valid_alert()
        instance["counts"] = {"items_ingested": 3}
        with pytest.raises(JsonSchemaValidationError):
            _validate(alert_schema, instance)

    def test_release_revision_and_source_travel_together(
        self, alert_schema: dict[str, Any]
    ) -> None:
        instance = _valid_alert()
        del instance["release_revision_source"]
        with pytest.raises(JsonSchemaValidationError):
            _validate(alert_schema, instance)

    def test_codes_are_the_authoritative_backup_set(self, alert_schema: dict[str, Any]) -> None:
        instance = _valid_alert()
        instance["codes"] = ["operation_failed"]
        with pytest.raises(JsonSchemaValidationError):
            _validate(alert_schema, instance)

    def test_code_enum_is_stated_once_here(self, alert_schema: dict[str, Any]) -> None:
        """A11 — this file is the single source of truth for the code set."""
        assert set(alert_schema["properties"]["codes"]["items"]["enum"]) == {
            "backup_stale",
            "backup_no_history",
            "backup_partial",
            "backup_target_unreachable",
            "backup_environment_mismatch",
        }
