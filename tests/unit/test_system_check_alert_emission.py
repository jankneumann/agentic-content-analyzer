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
from pathlib import Path
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


# ------------------------------------------- the two closed points found later


class TestTheRealTelemetryEmitterAcceptsSystemCheck:
    """A twelfth closed point, and the quietest one yet.

    Every test above stubs `telemetry_emitter`, so none of them could see that
    `src/telemetry/workflow_events._validate_event_key` keys a pattern map by
    `source_kind` and had no `system_check` entry — `pattern is None` raises, and
    `process_pending_event` swallows that into `emitted = False`. The alert is still
    delivered, but it emits no log line, no OTel counter, and never checkpoints
    `telemetry_emitted_at`: the backup monitor would be invisible in the channel
    operators actually watch, for exactly the events that matter most.

    These tests drive the REAL emitter, which is the only way the gap was visible.
    """

    def test_the_real_emitter_accepts_a_system_check_event_key(self) -> None:
        from src.telemetry.workflow_events import emit_workflow_terminal_telemetry

        assert (
            emit_workflow_terminal_telemetry(
                event_id=EVENT_ID,
                event_key=EVENT_KEY,
                operation_type="system.backup_freshness",
                outcome="failed",
                severity="error",
                source_kind="system_check",
            )
            is True
        )

    def test_the_real_emitter_still_rejects_a_foreign_key_grammar(self) -> None:
        """Widening must not become permissiveness."""
        from src.telemetry.workflow_events import emit_workflow_terminal_telemetry

        with pytest.raises(ValueError, match="correlation key"):
            emit_workflow_terminal_telemetry(
                event_id=EVENT_ID,
                event_key="reconciliation-action:1",
                operation_type="system.backup_freshness",
                outcome="failed",
                severity="error",
                source_kind="system_check",
            )

    def test_the_emitter_grammar_is_the_envelope_grammar(self) -> None:
        """Restating the pattern is how it drifted three times before."""
        from src.contracts.workflow_alert_models import SYSTEM_CHECK_EVENT_KEY_PATTERN
        from src.telemetry import workflow_events

        source = Path(workflow_events.__file__).read_text()
        assert "SYSTEM_CHECK_EVENT_KEY_PATTERN" in source
        assert SYSTEM_CHECK_EVENT_KEY_PATTERN.startswith("system_check:backup_freshness:")

    @pytest.mark.asyncio
    async def test_telemetry_is_checkpointed_on_the_real_path(self) -> None:
        """`emitted=False` is indistinguishable from success at the call site, so
        the checkpoint UPDATE is what proves the emitter did not quietly fail."""
        from src.telemetry.workflow_events import emit_workflow_terminal_telemetry

        conn = FakeConnection(pending_row())
        service = WorkflowTerminalEventService(
            conn,
            diagnostic_origin=ORIGIN,
            external_delivery_enabled=True,
            telemetry_emitter=emit_workflow_terminal_telemetry,
        )
        with patch(
            "src.services.backup.manifest_reader.read_freshness",
            lambda *_a, **_k: stale_freshness(),
        ), patch("src.config.settings.get_settings", backup_settings):
            await service.process_pending_event(EVENT_ID)

        assert any("telemetry_emitted_at" in query for query in conn.executed)


class TestTheDiagnosticRouteAdmitsSystemCheck:
    """A thirteenth closed point: the alert's OWN follow-up link.

    Every system_check envelope carries
    `/api/v1/workflow-terminal-events/{event_id}` as its `diagnostic_url` — the
    validator in `WorkflowAlertEnvelopeV1` requires exactly that path. The response
    model behind that route closed `source_kind` over three kinds, so the one route
    an operator reaches from a backup alert raised a ValidationError for precisely
    the events it exists to explain.
    """

    def test_the_response_model_admits_system_check(self) -> None:
        from src.contracts.workflow_models import WorkflowTerminalEventDiagnostic

        diagnostic = WorkflowTerminalEventDiagnostic(
            event_id=EVENT_ID,
            event_key=EVENT_KEY,
            source_kind="system_check",
            operation_id=None,
            claim_generation=None,
            terminal_status=None,
            classification_status="ready",
            release_revision="development",
            release_revision_source="local_development",
            occurred_at=NOW,
            telemetry_emitted_at=None,
            delivery_counts={
                "pending": 1,
                "leased": 0,
                "delivered": 0,
                "permanent_failure": 0,
                "exhausted": 0,
            },
        )
        assert diagnostic.source_kind == "system_check"

    def test_the_published_openapi_admits_it_too(self) -> None:
        """A response the server can return and the contract forbids is a lie the
        generated clients inherit."""
        import yaml

        contract = (
            Path(__file__).resolve().parents[2]
            / "openspec"
            / "contracts"
            / "content-workflows"
            / "openapi"
            / "v1.yaml"
        )
        openapi = yaml.safe_load(contract.read_text())
        schema = openapi["components"]["schemas"]["WorkflowTerminalEventDiagnostic"]
        assert "system_check" in schema["properties"]["source_kind"]["enum"]

    @pytest.mark.asyncio
    async def test_get_diagnostic_projects_a_system_check_row(self) -> None:
        class DiagnosticConnection:
            async def fetchrow(self, _query: str, *_args: Any) -> Any:
                return {
                    "id": EVENT_ID,
                    "event_key": EVENT_KEY,
                    "source_kind": "system_check",
                    "operation_id": None,
                    "claim_generation": None,
                    "terminal_status": None,
                    "classification_status": "ready",
                    "release_revision": None,
                    "release_revision_source": None,
                    "occurred_at": NOW,
                    "telemetry_emitted_at": None,
                    "deliveries_pending": 1,
                    "deliveries_leased": 0,
                    "deliveries_delivered": 0,
                    "deliveries_permanent_failure": 0,
                    "deliveries_exhausted": 0,
                }

        diagnostic = await WorkflowTerminalEventService(
            DiagnosticConnection()
        ).get_diagnostic(EVENT_ID)
        assert diagnostic is not None
        assert diagnostic.source_kind == "system_check"


class TestARecoveredBackupDoesNotRaiseAnAlert:
    """Classification reads the CURRENT manifest, so the condition can resolve
    between emission and classification — a backup lands in the gap.

    Mapping that to `unknown` gave severity `warning`, which IS externally routed,
    with an EMPTY `codes` list: an alert asserting a problem it cannot name, about a
    backup that is fine. `success` classifies to `info`, which is not routed, so the
    event is stored `telemetry_only` and no delivery is created.
    """

    @staticmethod
    def _freshness(status_name: str) -> Any:
        from src.services.backup.manifest_reader import BackupFreshness, BackupFreshnessStatus

        return BackupFreshness(
            status=getattr(BackupFreshnessStatus, status_name),
            manifest_age_seconds=60,
            stores_succeeded=4,
        )

    @pytest.mark.parametrize("status_name", ["OK", "NOT_CONFIGURED"])
    def test_a_healthy_reading_classifies_as_info(self, status_name: str) -> None:
        event = system_check_event()
        with patch(
            "src.services.backup.manifest_reader.read_freshness",
            lambda *_a, **_k: self._freshness(status_name),
        ), patch("src.config.settings.get_settings", backup_settings):
            snapshot = _system_check_snapshot()
        classification = classify_terminal_event(event, snapshot)
        assert classification.outcome == "success"
        assert classification.severity == "info"
        assert classification.external_routed is False

    @pytest.mark.parametrize("status_name", ["OK", "NOT_CONFIGURED"])
    def test_no_codeless_warning_is_ever_projected(self, status_name: str) -> None:
        event = system_check_event()
        with patch(
            "src.services.backup.manifest_reader.read_freshness",
            lambda *_a, **_k: self._freshness(status_name),
        ), patch("src.config.settings.get_settings", backup_settings):
            snapshot = _system_check_snapshot()
        with pytest.raises(ValueError, match="not externally routable"):
            project_alert_envelope(event, classify_terminal_event(event, snapshot), ORIGIN)

    @pytest.mark.asyncio
    async def test_a_recovered_backup_stores_telemetry_only_and_no_envelope(self) -> None:
        conn = FakeConnection(pending_row())
        service = WorkflowTerminalEventService(
            conn,
            diagnostic_origin=ORIGIN,
            external_delivery_enabled=True,
            telemetry_emitter=lambda **_: True,
        )
        with patch(
            "src.services.backup.manifest_reader.read_freshness",
            lambda *_a, **_k: self._freshness("OK"),
        ), patch("src.config.settings.get_settings", backup_settings):
            processed = await service.process_pending_event(EVENT_ID)

        assert processed is not None
        assert processed.classification_status == "telemetry_only"
        assert conn.stored["envelope"] is None

    @pytest.mark.parametrize(
        ("status_name", "expected_outcome"),
        [
            ("STALE", "failed"),
            ("PARTIAL", "partial"),
            ("NO_HISTORY", "unknown"),
            ("UNKNOWN", "unknown"),
            ("ENVIRONMENT_MISMATCH", "unknown"),
        ],
    )
    def test_every_alertable_status_still_routes(
        self, status_name: str, expected_outcome: str
    ) -> None:
        """The recovery branch must not swallow a real problem on its way past."""
        event = system_check_event()
        with patch(
            "src.services.backup.manifest_reader.read_freshness",
            lambda *_a, **_k: self._freshness(status_name),
        ), patch("src.config.settings.get_settings", backup_settings):
            snapshot = _system_check_snapshot()
        classification = classify_terminal_event(event, snapshot)
        assert classification.outcome == expected_outcome
        assert classification.external_routed is True
        assert classification.codes  # every alertable status names its code
