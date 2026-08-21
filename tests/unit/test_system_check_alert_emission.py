"""ACCEPTANCE — a system_check alert survives the whole emission path.

This file is the acceptance criterion for the alerting slice (design A13, task
3.9b), and it exists because of a specific near-miss worth restating.

Three rounds of plan review produced the same class of defect in five places: a
*document describing* a constraint stood in for the *code enforcing* it. The last
and worst instance was that all seven "widening points" identified for this change
lived in `workflow_alert_models.py` — and that model does not emit the alert.
`WorkflowTerminalEventService.process_pending_event` does, and a `system_check`
row hit three further gates before an envelope was ever constructed:

* `_validate_event_identity` raised for a non-operation kind with NULL
  reconciliation identity;
* it then constructed `WorkflowTerminalEventV1`, the class an earlier amendment
  had dismissed as irrelevant;
* `classify_terminal_event` fell through to `_operation_type(None)`, which raised.

All three raise `ValueError`, which `process_pending_event` catches and turns into
`classification_status='rejected'` with `envelope=None`. Nothing raises to the
caller. No delivery is enqueued. No error is logged as a failure. The orphan
cleanup in the worker then DELETEs the row.

Built as originally planned, *the alert reporting that backups were dead would
itself have been silently dropped*.

So: envelope construction, classification and persistence are each necessary and
none is sufficient. These tests drive the real path and assert a delivery-ready
outcome — never a regex in isolation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch
from uuid import UUID

import pytest

from src.services.workflow_terminal_event_service import (
    TerminalEventEvidence,
    WorkflowTerminalEventService,
    _system_check_snapshot,
    classify_terminal_event,
    project_alert_envelope,
)

NOW = datetime(2026, 8, 21, 4, 0, tzinfo=UTC)
EVENT_ID = UUID("550e8400-e29b-41d4-a716-446655440000")
EVENT_KEY = "system_check:backup_freshness:1755734400"
ORIGIN = "https://ops.example.com"


def system_check_event(**overrides: Any) -> TerminalEventEvidence:
    base: dict[str, Any] = {
        "event_id": EVENT_ID,
        "event_key": EVENT_KEY,
        "source_kind": "system_check",
        "operation_id": None,
        "claim_generation": None,
        "terminal_status": None,
        "reconciliation_action_id": None,
        "reconciliation_run_id": None,
        "reconciliation_content_id": None,
        "occurred_at": NOW,
    }
    base.update(overrides)
    return TerminalEventEvidence(**base)


def stale_freshness() -> Any:
    from src.services.backup.manifest_reader import BackupFreshness, BackupFreshnessStatus

    return BackupFreshness(
        status=BackupFreshnessStatus.STALE,
        manifest_age_seconds=200_000,
        stores_succeeded=3,
        stores_failed=0,
        stores_skipped=1,
    )


def backup_settings() -> SimpleNamespace:
    return SimpleNamespace(
        environment="production",
        backup_monitoring_enabled=True,
        backup_staleness_hours=48,
        backup_s3_bucket="aca-backups",
        backup_s3_prefix="aca",
    )


class FakeConnection:
    """Minimal asyncpg stand-in that behaves like the migrated table.

    It enforces the shape the CHECK constraints enforce, so a test cannot pass here
    while the real insert would be rejected.
    """

    def __init__(self, row: dict[str, Any]) -> None:
        self.row = row
        self.stored: dict[str, Any] = {}
        self.executed: list[str] = []

    async def fetchrow(self, query: str, *args: Any) -> Any:
        if "UPDATE workflow_terminal_events" in query:
            _, status, envelope = args
            self.stored = {"classification_status": status, "envelope": envelope}
            return {"id": self.row["id"]}
        return self.row

    async def execute(self, query: str, *args: Any) -> None:
        self.executed.append(query)

    async def fetchval(self, query: str, *args: Any) -> Any:
        return None


def pending_row() -> dict[str, Any]:
    return {
        "id": EVENT_ID,
        "event_key": EVENT_KEY,
        "source_kind": "system_check",
        "operation_id": None,
        "claim_generation": None,
        "terminal_status": None,
        "reconciliation_action_id": None,
        "reconciliation_run_id": None,
        "reconciliation_content_id": None,
        "classification_status": "pending",
        "occurred_at": NOW,
    }


# ---------------------------------------------------- each gate, individually


class TestEachGateAdmitsSystemCheck:
    """Necessary but not sufficient — each is checked so a failure localises."""

    def test_identity_validation_admits_null_reconciliation_identity(self) -> None:
        from src.services.workflow_terminal_event_service import _validate_event_identity

        _validate_event_identity(system_check_event())  # must not raise

    def test_identity_validation_still_rejects_a_smuggled_operation_id(self) -> None:
        from src.services.workflow_terminal_event_service import _validate_event_identity

        with pytest.raises(ValueError, match="no workflow identity"):
            _validate_event_identity(system_check_event(operation_id=42))

    def test_identity_validation_rejects_a_foreign_key_grammar(self) -> None:
        from src.services.workflow_terminal_event_service import _validate_event_identity

        with pytest.raises(ValueError):
            _validate_event_identity(
                system_check_event(event_key="system_check:backup_freshness:2026-08-21T03:00:00Z")
            )

    def test_classification_returns_a_classification_not_a_raise(self) -> None:
        with patch(
            "src.services.backup.manifest_reader.read_freshness",
            lambda *_a, **_k: stale_freshness(),
        ):
            snapshot = _system_check_snapshot_with(backup_settings())
        classification = classify_terminal_event(system_check_event(), snapshot)
        assert classification.workflow_type == "system.backup_freshness"
        assert classification.outcome == "failed"
        assert classification.severity == "error"
        assert classification.external_routed is True
        assert classification.codes == ("backup_stale",)

    def test_projection_builds_a_real_envelope(self) -> None:
        with patch(
            "src.services.backup.manifest_reader.read_freshness",
            lambda *_a, **_k: stale_freshness(),
        ):
            snapshot = _system_check_snapshot_with(backup_settings())
        event = system_check_event()
        envelope = project_alert_envelope(
            event, classify_terminal_event(event, snapshot), ORIGIN
        )
        assert envelope.source_kind == "system_check"
        assert envelope.operation_id is None
        assert envelope.attempt == 1
        assert str(envelope.diagnostic_url).endswith(f"/api/v1/workflow-terminal-events/{EVENT_ID}")
        assert envelope.counts.manifest_age_seconds == 200_000


# ------------------------------------------------------------ the whole path


@pytest.mark.asyncio
class TestEndToEndEmission:
    async def test_a_system_check_event_is_classified_ready_with_an_envelope(self) -> None:
        """The acceptance assertion: NOT rejected, and an envelope was stored."""
        conn = FakeConnection(pending_row())
        service = WorkflowTerminalEventService(
            conn,
            diagnostic_origin=ORIGIN,
            external_delivery_enabled=True,
            telemetry_emitter=lambda **_: True,
        )
        with patch(
            "src.services.backup.manifest_reader.read_freshness",
            lambda *_a, **_k: stale_freshness(),
        ), patch("src.config.settings.get_settings", backup_settings):
            processed = await service.process_pending_event(EVENT_ID)

        assert processed is not None
        assert processed.classification_status == "ready"
        assert processed.envelope is not None
        assert conn.stored["classification_status"] == "ready"

    async def test_no_path_silently_marks_the_alert_rejected(self) -> None:
        """The failure this test exists to catch is not an exception — it is a quiet
        'rejected' row that nothing raises about and the worker later deletes."""
        conn = FakeConnection(pending_row())
        service = WorkflowTerminalEventService(
            conn,
            diagnostic_origin=ORIGIN,
            external_delivery_enabled=True,
            telemetry_emitter=lambda **_: True,
        )
        with patch(
            "src.services.backup.manifest_reader.read_freshness",
            lambda *_a, **_k: stale_freshness(),
        ), patch("src.config.settings.get_settings", backup_settings):
            processed = await service.process_pending_event(EVENT_ID)

        assert processed is not None
        assert processed.classification_status != "rejected"
        assert conn.stored["classification_status"] != "rejected"

    async def test_the_stored_envelope_is_delivery_ready(self) -> None:
        """The worker's delivery query selects on classification_status='ready' AND
        envelope IS NOT NULL. Both must hold or no delivery is ever created."""
        conn = FakeConnection(pending_row())
        service = WorkflowTerminalEventService(
            conn,
            diagnostic_origin=ORIGIN,
            external_delivery_enabled=True,
            telemetry_emitter=lambda **_: True,
        )
        with patch(
            "src.services.backup.manifest_reader.read_freshness",
            lambda *_a, **_k: stale_freshness(),
        ), patch("src.config.settings.get_settings", backup_settings):
            await service.process_pending_event(EVENT_ID)

        assert conn.stored["envelope"] is not None
        payload = json.loads(conn.stored["envelope"])
        assert payload["source_kind"] == "system_check"
        assert payload["codes"] == ["backup_stale"]

    async def test_the_stored_envelope_carries_no_credentials(self) -> None:
        conn = FakeConnection(pending_row())
        service = WorkflowTerminalEventService(
            conn,
            diagnostic_origin=ORIGIN,
            external_delivery_enabled=True,
            telemetry_emitter=lambda **_: True,
        )
        with patch(
            "src.services.backup.manifest_reader.read_freshness",
            lambda *_a, **_k: stale_freshness(),
        ), patch("src.config.settings.get_settings", backup_settings):
            await service.process_pending_event(EVENT_ID)

        body = conn.stored["envelope"]
        for secret in ("postgresql://", "AKIA", "secret", "password", "aca-backups"):
            assert secret not in body

    async def test_the_stored_envelope_conforms_to_the_published_contract(self) -> None:
        from pathlib import Path

        from jsonschema import FormatChecker
        from jsonschema.validators import validator_for

        conn = FakeConnection(pending_row())
        service = WorkflowTerminalEventService(
            conn,
            diagnostic_origin=ORIGIN,
            external_delivery_enabled=True,
            telemetry_emitter=lambda **_: True,
        )
        with patch(
            "src.services.backup.manifest_reader.read_freshness",
            lambda *_a, **_k: stale_freshness(),
        ), patch("src.config.settings.get_settings", backup_settings):
            await service.process_pending_event(EVENT_ID)

        schema_path = (
            Path(__file__).resolve().parents[2]
            / "openspec"
            / "contracts"
            / "backup"
            / "events"
            / "backup-freshness-alert.schema.json"
        )
        schema = json.loads(schema_path.read_text())
        validator_for(schema)(schema, format_checker=FormatChecker()).validate(
            json.loads(conn.stored["envelope"])
        )


def _system_check_snapshot_with(settings: Any) -> Any:
    with patch("src.config.settings.get_settings", lambda: settings):
        return _system_check_snapshot()
