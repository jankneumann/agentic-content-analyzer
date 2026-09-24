"""ACCEPTANCE — a dead browser session survives the whole alert emission path.

A credential-gated source (Substack ``substack.sid``, X ``auth_token``/``ct0``)
fails closed: the ingestion handler attaches a durable result carrying
``session_expired`` or ``credentials_missing`` and then fails the operation. Three
closed points stood between that result and an alert that says what to run:

* ``WorkflowAlertDiagnosticCode`` did not admit either code, so
  ``_ingestion_codes`` silently dropped them;
* ``classify_terminal_event`` read only the lifecycle of a FAILED operation and
  reported a bare ``operation_failed``, never looking at the attached result;
* ``_apply_pipeline_routing`` suppressed the child in favour of the pipeline
  root's aggregate alert, which carries no codes at all.

Like ``test_system_check_alert_emission.py``, these tests drive the REAL
telemetry emitter: a stubbed ``telemetry_emitter`` hid a closed point there for
three review rounds.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from jsonschema import FormatChecker
from jsonschema.validators import validator_for

from src.contracts.workflow_models import IngestionResultV2
from src.ingestion.credential_failures import (
    CredentialsMissingError,
    SessionExpiredError,
)
from src.ingestion.result_sanitizer import sanitize_ingestion_metadata
from src.ingestion.substack import SUBSTACK_REFRESH_COMMAND
from src.services.workflow_terminal_event_service import (
    PersistedTerminalSnapshot,
    TerminalClassificationDeferredError,
    TerminalEventEvidence,
    WorkflowTerminalEventService,
    classify_terminal_event,
    project_alert_envelope,
)
from src.telemetry.workflow_events import emit_workflow_terminal_telemetry

NOW = datetime(2026, 9, 24, 6, 0, tzinfo=UTC)
EVENT_ID = UUID("6f1c2a4e-8b3d-4c5e-9f60-718293a4b5c6")
OPERATION_ID = 4242
EVENT_KEY = f"operation:{OPERATION_ID}:claim:0:status:failed"
ORIGIN = "https://ops.example.com"
#: A recognisable cookie value that must never reach any alert surface.
COOKIE_SENTINEL = "sid-live-sentinel-93af"

ENVELOPE_SCHEMA = (
    Path(__file__).resolve().parents[2]
    / "openspec"
    / "changes"
    / "production-telemetry-and-out-of-band-alerting"
    / "contracts"
    / "workflow-alert-envelope.schema.json"
)


def ingestion_result(
    *,
    command_key: str = "substack",
    errors: tuple[Any, ...] = (),
    warnings: tuple[Any, ...] = (),
    status: str = "error",
    outcome: str = "failed",
) -> dict[str, Any]:
    """Project a result exactly as ``WorkflowHandlers.ingestion`` does."""

    metadata = sanitize_ingestion_metadata(
        errors=[error.model_dump() for error in errors],
        warnings=[warning.model_dump() for warning in warnings],
    )
    return IngestionResultV2(
        command_key=command_key,
        resolved_route=command_key,
        emitted_sources=[command_key],
        status=status,
        outcome=outcome,
        items_ingested=0,
        items_skipped=0,
        items_failed=0,
        content_ids=[],
        **metadata,
    ).model_dump(mode="json", exclude_none=True)


def session_expired(source: str = "substack", command: str | None = None) -> Any:
    return SessionExpiredError(
        source=source,
        credential_label="substack.sid" if source == "substack" else "auth_token/ct0",
        refresh_command=command or SUBSTACK_REFRESH_COMMAND,
    ).to_ingestion_error()


def credentials_missing() -> Any:
    return CredentialsMissingError(
        source="substack",
        credential_label="substack.sid",
        refresh_command=SUBSTACK_REFRESH_COMMAND,
    ).to_ingestion_error()


def operation_event(
    *, terminal_status: str = "failed", operation_id: int = OPERATION_ID
) -> TerminalEventEvidence:
    return TerminalEventEvidence(
        event_id=EVENT_ID,
        event_key=f"operation:{operation_id}:claim:0:status:{terminal_status}",
        source_kind="operation",
        operation_id=operation_id,
        claim_generation=0,
        terminal_status=terminal_status,
        reconciliation_action_id=None,
        reconciliation_run_id=None,
        reconciliation_content_id=None,
        occurred_at=NOW,
    )


def failed_snapshot(result: object, **overrides: Any) -> PersistedTerminalSnapshot:
    values: dict[str, Any] = {
        "operation_type": "ingestion.execute",
        "operation_status": "failed",
        "result": result,
    }
    values.update(overrides)
    return PersistedTerminalSnapshot(**values)


class FakeConnection:
    """asyncpg stand-in: one pending operation event over one terminal job row."""

    def __init__(self, result: object, *, operation_type: str = "ingestion.execute") -> None:
        self.status = "pending"
        self.result = result
        self.operation_type = operation_type
        self.stored: dict[str, Any] = {}
        self.executed: list[str] = []

    async def fetchrow(self, query: str, *args: Any) -> Any:
        if "UPDATE workflow_terminal_events" in query:
            if self.status != "pending":
                return None
            _, self.status, envelope = args
            self.stored = {"classification_status": self.status, "envelope": envelope}
            return {"id": EVENT_ID}
        if "FROM pgqueuer_jobs AS job" in query:
            return {
                "operation_type": self.operation_type,
                "operation_status": "failed",
                "result": json.dumps(self.result),
                "pipeline_root_id": None,
                "pipeline_root_status": None,
                "pipeline_root_result": None,
            }
        return {
            "id": EVENT_ID,
            "event_key": EVENT_KEY,
            "source_kind": "operation",
            "operation_id": OPERATION_ID,
            "claim_generation": 0,
            "terminal_status": "failed",
            "reconciliation_action_id": None,
            "reconciliation_run_id": None,
            "reconciliation_content_id": None,
            "classification_status": self.status,
            "occurred_at": NOW,
        }

    async def execute(self, query: str, *args: Any) -> None:
        self.executed.append(query)


def real_service(connection: FakeConnection) -> WorkflowTerminalEventService:
    return WorkflowTerminalEventService(
        connection,
        diagnostic_origin=ORIGIN,
        external_delivery_enabled=True,
        telemetry_emitter=emit_workflow_terminal_telemetry,
        release_identity=lambda: ("development", "local_development"),
    )


@contextmanager
def captured_logs() -> Iterator[list[logging.LogRecord]]:
    records: list[logging.LogRecord] = []

    class _Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Handler(level=logging.DEBUG)
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        yield records
    finally:
        root.removeHandler(handler)


# ---------------------------------------------------------------- classification


class TestAFailedCredentialGatedIngestionNamesItsCause:
    @pytest.mark.parametrize(
        ("error", "code"),
        [(session_expired(), "session_expired"), (credentials_missing(), "credentials_missing")],
    )
    def test_the_failure_classifies_as_an_error_with_its_code_and_command(
        self, error: Any, code: str
    ) -> None:
        classification = classify_terminal_event(
            operation_event(), failed_snapshot(ingestion_result(errors=(error,)))
        )

        assert classification.outcome == "failed"
        assert classification.severity == "error"
        assert classification.external_routed is True
        assert classification.codes == ("operation_failed", code)
        assert classification.remediation_command == "aca auth session substack"

    def test_an_x_session_names_the_x_command(self) -> None:
        result = ingestion_result(
            command_key="x_bookmarks",
            errors=(session_expired("x_bookmarks", "aca auth session x"),),
        )

        classification = classify_terminal_event(operation_event(), failed_snapshot(result))

        assert classification.codes == ("operation_failed", "session_expired")
        assert classification.remediation_command == "aca auth session x"

    def test_a_source_with_no_browser_session_gets_the_code_but_no_command(self) -> None:
        result = ingestion_result(command_key="rss", errors=(session_expired("rss"),))

        classification = classify_terminal_event(operation_event(), failed_snapshot(result))

        assert "session_expired" in classification.codes
        assert classification.remediation_command is None

    def test_an_ordinary_failed_ingestion_gains_its_codes_but_no_command(self) -> None:
        from src.ingestion.result import IngestionError

        result = ingestion_result(errors=(IngestionError(code="fetch_error", message="x"),))

        classification = classify_terminal_event(operation_event(), failed_snapshot(result))

        assert classification.codes == ("operation_failed", "fetch_error")
        assert classification.remediation_command is None

    @pytest.mark.parametrize("result", [None, {"schema_version": 2}, "not-json"])
    def test_a_failed_ingestion_without_a_valid_result_keeps_the_historical_code(
        self, result: object
    ) -> None:
        classification = classify_terminal_event(operation_event(), failed_snapshot(result))

        assert classification.codes == ("operation_failed",)
        assert classification.remediation_command is None

    def test_a_failed_non_ingestion_operation_is_unchanged(self) -> None:
        classification = classify_terminal_event(
            operation_event(),
            failed_snapshot(
                ingestion_result(errors=(session_expired(),)), operation_type="digest.create"
            ),
        )

        assert classification.codes == ("operation_failed",)
        assert classification.remediation_command is None

    def test_a_completed_run_warning_of_a_missing_credential_is_a_warning(self) -> None:
        result = ingestion_result(
            warnings=(credentials_missing(),), status="ok", outcome="zero_items"
        )

        classification = classify_terminal_event(
            operation_event(terminal_status="completed"),
            failed_snapshot(result, operation_status="completed"),
        )

        assert classification.outcome == "zero_items"
        assert classification.severity == "warning"
        assert classification.codes == ("credentials_missing",)
        assert classification.remediation_command == "aca auth session substack"


class TestAPipelineDoesNotSwallowTheCommand:
    """The scheduled daily pipeline is where a yearly expiry actually happens."""

    @pytest.mark.parametrize("root_status", ["queued", "in_progress", "failed", "completed"])
    def test_a_credential_child_routes_whatever_its_root_is_doing(self, root_status: str) -> None:
        snapshot = failed_snapshot(
            ingestion_result(errors=(session_expired(),)),
            pipeline_root_id=1,
            pipeline_root_status=root_status,
            pipeline_root_result=None,
        )

        classification = classify_terminal_event(operation_event(), snapshot)

        assert classification.external_routed is True
        assert classification.suppression_reason is None
        assert classification.remediation_command == "aca auth session substack"

    def test_an_ordinary_child_still_defers_to_its_root(self) -> None:
        from src.ingestion.result import IngestionError

        snapshot = failed_snapshot(
            ingestion_result(errors=(IngestionError(code="fetch_error", message="x"),)),
            pipeline_root_id=1,
            pipeline_root_status="in_progress",
        )

        with pytest.raises(TerminalClassificationDeferredError):
            classify_terminal_event(operation_event(), snapshot)


# ------------------------------------------------------------------ projection


class TestTheEnvelope:
    def test_the_envelope_carries_the_code_and_the_command(self) -> None:
        event = operation_event()
        classification = classify_terminal_event(
            event, failed_snapshot(ingestion_result(errors=(session_expired(),)))
        )

        envelope = project_alert_envelope(event, classification, ORIGIN)
        body = envelope.model_dump(mode="json")

        assert body["severity"] == "error"
        assert body["codes"] == ["operation_failed", "session_expired"]
        assert body["remediation_command"] == "aca auth session substack"
        assert body["diagnostic_url"] == f"{ORIGIN}/api/v1/operations/{OPERATION_ID}"

    def test_an_alert_without_a_credential_code_serializes_as_before(self) -> None:
        event = operation_event()
        envelope = project_alert_envelope(
            event, classify_terminal_event(event, failed_snapshot(None)), ORIGIN
        )

        assert "remediation_command" not in envelope.model_dump(mode="json")
        assert "remediation_command" not in envelope.model_fields_set


# --------------------------------------------------------------- the whole path


@pytest.mark.asyncio
class TestEndToEndWithTheRealEmitter:
    async def test_the_event_is_ready_with_a_delivery_ready_envelope(self) -> None:
        connection = FakeConnection(ingestion_result(errors=(session_expired(),)))

        processed = await real_service(connection).process_pending_event(EVENT_ID)

        assert processed is not None
        assert processed.classification_status == "ready"
        assert connection.stored["classification_status"] == "ready"
        payload = json.loads(connection.stored["envelope"])
        assert payload["codes"] == ["operation_failed", "session_expired"]
        assert payload["remediation_command"] == "aca auth session substack"

    async def test_the_real_emitter_checkpoints_telemetry(self) -> None:
        """`emitted=False` is silent at the call site; the checkpoint proves it."""
        connection = FakeConnection(ingestion_result(errors=(session_expired(),)))

        await real_service(connection).process_pending_event(EVENT_ID)

        assert any("telemetry_emitted_at" in query for query in connection.executed)

    async def test_classification_happens_once(self) -> None:
        connection = FakeConnection(ingestion_result(errors=(session_expired(),)))
        service = real_service(connection)

        first = await service.process_pending_event(EVENT_ID)
        second = await service.process_pending_event(EVENT_ID)

        assert first is not None
        assert second is None
        assert len([q for q in connection.executed if "telemetry_emitted_at" in q]) == 1

    async def test_the_envelope_conforms_to_the_published_contract(self) -> None:
        connection = FakeConnection(ingestion_result(errors=(credentials_missing(),)))

        await real_service(connection).process_pending_event(EVENT_ID)

        schema = json.loads(ENVELOPE_SCHEMA.read_text())
        validator_for(schema)(schema, format_checker=FormatChecker()).validate(
            json.loads(connection.stored["envelope"])
        )

    async def test_no_cookie_value_reaches_the_envelope_or_the_logs(self, monkeypatch) -> None:
        monkeypatch.setenv("SUBSTACK_SESSION_COOKIE", COOKIE_SENTINEL)
        connection = FakeConnection(ingestion_result(errors=(session_expired(),)))

        with captured_logs() as records:
            await real_service(connection).process_pending_event(EVENT_ID)

        logged = "\n".join(f"{record.getMessage()} {record.__dict__}" for record in records)
        assert COOKIE_SENTINEL not in connection.stored["envelope"]
        assert COOKIE_SENTINEL not in logged
        assert "substack.sid" not in connection.stored["envelope"]

    async def test_the_diagnostic_projection_resolves_for_the_event(self) -> None:
        class DiagnosticConnection:
            async def fetchrow(self, _query: str, *_args: Any) -> Any:
                return {
                    "id": EVENT_ID,
                    "event_key": EVENT_KEY,
                    "source_kind": "operation",
                    "operation_id": OPERATION_ID,
                    "claim_generation": 0,
                    "terminal_status": "failed",
                    "classification_status": "ready",
                    "release_revision": "development",
                    "release_revision_source": "local_development",
                    "occurred_at": NOW,
                    "telemetry_emitted_at": NOW,
                    "deliveries_pending": 0,
                    "deliveries_leased": 0,
                    "deliveries_delivered": 1,
                    "deliveries_permanent_failure": 0,
                    "deliveries_exhausted": 0,
                }

        diagnostic = await WorkflowTerminalEventService(DiagnosticConnection()).get_diagnostic(
            EVENT_ID
        )

        assert diagnostic is not None
        assert diagnostic.operation_id == str(OPERATION_ID)
        assert diagnostic.delivery_counts.delivered == 1
