from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from pydantic import ValidationError

from src.services.workflow_terminal_event_service import (
    PersistedTerminalSnapshot,
    TerminalClassificationDeferredError,
    TerminalEventEvidence,
    WorkflowTerminalEventService,
    build_diagnostic_url,
    classify_terminal_event,
    project_alert_envelope,
)

NOW = datetime(2026, 8, 1, 23, 30, tzinfo=UTC)
EVENT_ID = UUID("550e8400-e29b-41d4-a716-446655440000")


def _operation_event(*, status: str = "completed", claim_generation: int = 2):
    return TerminalEventEvidence(
        event_id=EVENT_ID,
        event_key=f"operation:42:claim:{claim_generation}:status:{status}",
        source_kind="operation",
        operation_id=42,
        claim_generation=claim_generation,
        terminal_status=status,
        reconciliation_action_id=None,
        reconciliation_run_id=None,
        reconciliation_content_id=None,
        occurred_at=NOW,
    )


def _ingestion_result(outcome: str = "partial") -> dict[str, object]:
    return {
        "schema_version": 2,
        "command_key": "rss",
        "resolved_route": "rss",
        "emitted_sources": ["rss"],
        "status": "partial" if outcome == "partial" else "ok",
        "outcome": outcome,
        "items_ingested": 2,
        "items_skipped": 1,
        "items_failed": 1,
        "content_ids": [7, 8],
        "errors": [{"code": "feed_ingest_error", "message": "hostile error"}],
        "warnings": [],
        "errors_omitted": 0,
        "warnings_omitted": 0,
        "source_outcomes": [
            {
                "source_key": "src_0123456789abcdef0123",
                "status": "partial",
                "items_ingested": 2,
                "items_failed": 1,
                "errors": [],
                "warnings": [],
                "errors_omitted": 0,
                "warnings_omitted": 0,
            }
        ],
        "source_outcomes_omitted": 0,
        "details": {},
        "details_omitted": 0,
    }


@pytest.mark.parametrize(
    ("lifecycle", "result_outcome", "expected", "severity", "external"),
    [
        ("failed", "success", "failed", "error", True),
        ("cancelled", "success", "cancelled", "info", False),
        ("completed", "success", "success", "info", False),
        ("completed", "partial", "partial", "warning", True),
        ("completed", "zero_items", "zero_items", "warning", True),
        ("completed", "unknown", "unknown", "warning", True),
        ("completed", "failed", "unknown", "warning", True),
        ("completed", "cancelled", "unknown", "warning", True),
    ],
)
def test_ingestion_classification_uses_lifecycle_then_strict_v2_result(
    lifecycle: str,
    result_outcome: str,
    expected: str,
    severity: str,
    external: bool,
) -> None:
    event = _operation_event(status=lifecycle)
    snapshot = PersistedTerminalSnapshot(
        operation_type="ingestion.execute",
        operation_status=lifecycle,
        result=_ingestion_result(result_outcome),
    )

    classified = classify_terminal_event(event, snapshot)

    assert classified.outcome == expected
    assert classified.severity == severity
    assert classified.external_eligible is external


@pytest.mark.parametrize(
    "result",
    [
        None,
        {"schema_version": 1, "outcome": "partial"},
        {"schema_version": 2, "outcome": "partial", "raw_error": "ignored"},
        {**_ingestion_result(), "raw_error": "ignored"},
    ],
)
def test_completed_ingestion_does_not_infer_from_legacy_or_extended_result(
    result: object,
) -> None:
    classified = classify_terminal_event(
        _operation_event(),
        PersistedTerminalSnapshot(
            operation_type="ingestion.execute",
            operation_status="completed",
            result=result,
        ),
    )

    assert classified.outcome == "unknown"
    assert classified.counts.model_dump(exclude_none=True) == {}
    assert classified.source_keys == ()
    assert classified.resource_refs == ()


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        ("success", "success"),
        ("partial", "partial"),
        ("zero_items", "zero_items"),
        ("unknown", "unknown"),
        ("failed", "unknown"),
    ],
)
def test_pipeline_classification_uses_closed_aggregate(outcome: str, expected: str) -> None:
    result = {
        "schema_version": 2,
        "ingestion_summary": {
            "outcome": outcome,
            "sources": [
                {
                    "operation_id": "7",
                    "command_key": "rss",
                    "operation_status": "completed",
                    "outcome": outcome,
                    "items_ingested": 2,
                    "items_skipped": 1,
                    "items_failed": 0,
                }
            ],
            "sources_omitted": 0,
        },
    }
    classified = classify_terminal_event(
        _operation_event(),
        PersistedTerminalSnapshot(
            operation_type="pipeline.run",
            operation_status="completed",
            result=result,
        ),
    )

    assert classified.outcome == expected
    assert classified.counts.sources_total == 1
    assert classified.counts.items_ingested == 2


def test_pipeline_child_keeps_telemetry_but_suppresses_external_route() -> None:
    classified = classify_terminal_event(
        _operation_event(),
        PersistedTerminalSnapshot(
            operation_type="ingestion.execute",
            operation_status="completed",
            result=_ingestion_result(),
            pipeline_root_id=99,
            pipeline_root_status="completed",
            pipeline_root_result={
                "schema_version": 2,
                "ingestion_summary": {
                    "outcome": "partial",
                    "sources": [],
                    "sources_omitted": 0,
                },
            },
        ),
    )

    assert classified.outcome == "partial"
    assert classified.external_eligible is True
    assert classified.external_routed is False
    assert classified.suppression_reason == "pipeline_root_aggregates"


@pytest.mark.parametrize(
    ("root_id", "root_status", "root_outcome"),
    [
        (None, None, None),
        (99, "cancelled", None),
        (99, "completed", "success"),
    ],
)
def test_missing_cancelled_or_successful_root_does_not_suppress_child(
    root_id: int | None,
    root_status: str | None,
    root_outcome: str | None,
) -> None:
    root_result = (
        {
            "schema_version": 2,
            "ingestion_summary": {
                "outcome": root_outcome,
                "sources": [],
                "sources_omitted": 0,
            },
        }
        if root_outcome is not None
        else None
    )

    classified = classify_terminal_event(
        _operation_event(status="failed"),
        PersistedTerminalSnapshot(
            operation_type="ingestion.execute",
            operation_status="failed",
            pipeline_root_id=root_id,
            pipeline_root_status=root_status,
            pipeline_root_result=root_result,
        ),
    )

    assert classified.external_routed is True
    assert classified.suppression_reason is None


@pytest.mark.parametrize("root_status", ["queued", "in_progress"])
def test_nonterminal_or_stuck_pipeline_root_defers_child(root_status: str) -> None:
    with pytest.raises(TerminalClassificationDeferredError):
        classify_terminal_event(
            _operation_event(status="failed"),
            PersistedTerminalSnapshot(
                operation_type="ingestion.execute",
                operation_status="failed",
                pipeline_root_id=99,
                pipeline_root_status=root_status,
                pipeline_root_result=None,
            ),
        )


def test_retry_closure_turns_nonterminal_root_deferral_into_bounded_telemetry() -> None:
    classified = classify_terminal_event(
        _operation_event(status="failed"),
        PersistedTerminalSnapshot(
            operation_type="ingestion.execute",
            operation_status="failed",
            pipeline_root_id=99,
            pipeline_root_status="in_progress",
            pipeline_root_result=None,
        ),
        defer_nonterminal_root=False,
    )

    assert classified.external_eligible is True
    assert classified.external_routed is False
    assert classified.suppression_reason == "pipeline_root_aggregates"


@pytest.mark.parametrize(
    ("root_status", "root_outcome"),
    [
        ("failed", None),
        ("completed", "partial"),
        ("completed", "zero_items"),
        ("completed", "unknown"),
    ],
)
def test_alertable_terminal_pipeline_root_suppresses_child(
    root_status: str,
    root_outcome: str | None,
) -> None:
    root_result = (
        {
            "schema_version": 2,
            "ingestion_summary": {
                "outcome": root_outcome,
                "sources": [],
                "sources_omitted": 0,
            },
        }
        if root_outcome is not None
        else None
    )

    classified = classify_terminal_event(
        _operation_event(status="failed"),
        PersistedTerminalSnapshot(
            operation_type="ingestion.execute",
            operation_status="failed",
            pipeline_root_id=99,
            pipeline_root_status=root_status,
            pipeline_root_result=root_result,
        ),
    )

    assert classified.external_eligible is True
    assert classified.external_routed is False
    assert classified.suppression_reason == "pipeline_root_aggregates"


def test_non_ingestion_completed_operation_is_success_telemetry_only() -> None:
    classified = classify_terminal_event(
        _operation_event(),
        PersistedTerminalSnapshot(
            operation_type="digest.create",
            operation_status="completed",
            result={"raw": "never inspected"},
        ),
    )

    assert classified.outcome == "success"
    assert classified.severity == "info"
    assert classified.external_routed is False


def test_reconciliation_action_and_failure_are_closed() -> None:
    action = TerminalEventEvidence(
        event_id=EVENT_ID,
        event_key="reconciliation-action:7",
        source_kind="reconciliation_action",
        operation_id=None,
        claim_generation=None,
        terminal_status=None,
        reconciliation_action_id=7,
        reconciliation_run_id=UUID("16fd2706-8baf-433b-82eb-8c7fada847da"),
        reconciliation_content_id=42,
        occurred_at=NOW,
    )
    reconciled = classify_terminal_event(
        action,
        PersistedTerminalSnapshot(reconciliation_reason="summary_exists"),
    )
    assert (reconciled.outcome, reconciled.severity, reconciled.codes) == (
        "reconciled",
        "warning",
        ("summary_exists",),
    )

    failure = TerminalEventEvidence(
        **{
            **action.__dict__,
            "event_key": (
                "reconciliation-failure:16fd2706-8baf-433b-82eb-8c7fada847da:"
                "content:42:reason:apply_failed"
            ),
            "source_kind": "reconciliation_failure",
            "reconciliation_action_id": None,
        }
    )
    failed = classify_terminal_event(failure, PersistedTerminalSnapshot())
    assert (failed.outcome, failed.severity, failed.codes) == (
        "failed",
        "error",
        ("apply_failed",),
    )


@pytest.mark.parametrize(
    "origin",
    [
        "http://ops.example.com",
        "https://user:secret@ops.example.com",
        "https://ops.example.com/base",
        "https://ops.example.com?token=secret",
        "https://ops.example.com#secret",
        "https://ops.example.com/%2fetc",
    ],
)
def test_diagnostic_url_rejects_every_untrusted_component(origin: str) -> None:
    with pytest.raises(ValueError, match="trusted diagnostic origin"):
        build_diagnostic_url(origin, operation_id=42)


def test_diagnostic_url_and_envelope_correlate_exact_identity() -> None:
    event = _operation_event(status="failed", claim_generation=2)
    classified = classify_terminal_event(
        event,
        PersistedTerminalSnapshot(
            operation_type="ingestion.execute",
            operation_status="failed",
            result=_ingestion_result("success"),
        ),
    )

    envelope = project_alert_envelope(event, classified, "https://ops.example.com")

    assert envelope.operation_id == "42"
    assert envelope.event_key == "operation:42:claim:2:status:failed"
    assert envelope.attempt == 3
    assert str(envelope.diagnostic_url) == "https://ops.example.com/api/v1/operations/42"


def test_projection_fails_closed_when_event_identity_is_inconsistent() -> None:
    event = _operation_event(status="failed")
    object.__setattr__(event, "event_key", "operation:41:claim:2:status:failed")

    with pytest.raises((ValueError, ValidationError)):
        classify_terminal_event(
            event,
            PersistedTerminalSnapshot(
                operation_type="ingestion.execute",
                operation_status="failed",
            ),
        )


@pytest.mark.asyncio
async def test_processing_reads_fresh_closed_state_then_checkpoints_telemetry() -> None:
    event_row = {
        "id": EVENT_ID,
        "event_key": "operation:42:claim:0:status:failed",
        "source_kind": "operation",
        "operation_id": 42,
        "claim_generation": 0,
        "terminal_status": "failed",
        "reconciliation_action_id": None,
        "reconciliation_run_id": None,
        "reconciliation_content_id": None,
        "classification_status": "pending",
        "occurred_at": NOW,
    }
    operation_row = {
        "operation_type": "ingestion.execute",
        "operation_status": "failed",
        "result": _ingestion_result("success"),
        "pipeline_root_id": None,
    }
    connection = Mock()
    connection.fetchrow = AsyncMock(side_effect=[event_row, operation_row, {"id": EVENT_ID}])
    connection.execute = AsyncMock(return_value="UPDATE 1")
    emitter = Mock(return_value=True)
    service = WorkflowTerminalEventService(
        connection,
        diagnostic_origin="https://ops.example.com",
        external_delivery_enabled=True,
        telemetry_emitter=emitter,
    )

    processed = await service.process_pending_event(EVENT_ID)

    assert processed is not None
    assert processed.classification_status == "ready"
    assert processed.envelope is not None
    assert processed.envelope.event_key == "operation:42:claim:0:status:failed"
    assert processed.envelope.attempt == 1
    operation_sql = connection.fetchrow.await_args_list[1].args[0]
    assert "payload->'result'" in operation_sql
    assert "problem" not in operation_sql
    assert "error" not in operation_sql
    assert "input" not in operation_sql
    emitter.assert_called_once_with(
        event_id=EVENT_ID,
        event_key="operation:42:claim:0:status:failed",
        operation_type="ingestion.execute",
        outcome="failed",
        severity="error",
        source_kind="operation",
    )
    assert "telemetry_emitted_at = COALESCE" in connection.execute.await_args.args[0]


@pytest.mark.asyncio
async def test_pipeline_child_processing_is_telemetry_only() -> None:
    connection = Mock()
    connection.fetchrow = AsyncMock(
        side_effect=[
            {
                "id": EVENT_ID,
                "event_key": "operation:42:claim:2:status:completed",
                "source_kind": "operation",
                "operation_id": 42,
                "claim_generation": 2,
                "terminal_status": "completed",
                "reconciliation_action_id": None,
                "reconciliation_run_id": None,
                "reconciliation_content_id": None,
                "classification_status": "pending",
                "occurred_at": NOW,
            },
            {
                "operation_type": "ingestion.execute",
                "operation_status": "completed",
                "result": _ingestion_result(),
                "pipeline_root_id": 99,
                "pipeline_root_status": "completed",
                "pipeline_root_result": {
                    "schema_version": 2,
                    "ingestion_summary": {
                        "outcome": "partial",
                        "sources": [],
                        "sources_omitted": 0,
                    },
                },
            },
            {"id": EVENT_ID},
        ]
    )
    connection.execute = AsyncMock(return_value="UPDATE 1")
    service = WorkflowTerminalEventService(
        connection,
        diagnostic_origin="https://ops.example.com",
        external_delivery_enabled=True,
        telemetry_emitter=Mock(return_value=True),
    )

    processed = await service.process_pending_event(EVENT_ID)

    assert processed is not None
    assert processed.classification_status == "telemetry_only"
    assert processed.envelope is None
    assert processed.classification.suppression_reason == "pipeline_root_aggregates"


@pytest.mark.asyncio
async def test_nonterminal_pipeline_root_leaves_child_event_pending() -> None:
    connection = Mock()
    connection.fetchrow = AsyncMock(
        side_effect=[
            {
                "id": EVENT_ID,
                "event_key": "operation:42:claim:2:status:failed",
                "source_kind": "operation",
                "operation_id": 42,
                "claim_generation": 2,
                "terminal_status": "failed",
                "reconciliation_action_id": None,
                "reconciliation_run_id": None,
                "reconciliation_content_id": None,
                "classification_status": "pending",
                "occurred_at": NOW,
            },
            {
                "operation_type": "ingestion.execute",
                "operation_status": "failed",
                "result": None,
                "pipeline_root_id": 99,
                "pipeline_root_status": "in_progress",
                "pipeline_root_result": None,
            },
        ]
    )
    connection.execute = AsyncMock()
    service = WorkflowTerminalEventService(
        connection,
        diagnostic_origin="https://ops.example.com",
        external_delivery_enabled=True,
    )

    assert await service.process_pending_event(EVENT_ID) is None
    assert connection.fetchrow.await_count == 2
    connection.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_closure_processes_matching_pending_attempt_before_reset() -> None:
    connection = Mock()
    connection.fetch = AsyncMock(return_value=[{"id": EVENT_ID}])
    connection.fetchrow = AsyncMock(
        side_effect=[
            {
                "id": EVENT_ID,
                "event_key": "operation:42:claim:2:status:failed",
                "source_kind": "operation",
                "operation_id": 42,
                "claim_generation": 2,
                "terminal_status": "failed",
                "reconciliation_action_id": None,
                "reconciliation_run_id": None,
                "reconciliation_content_id": None,
                "classification_status": "pending",
                "occurred_at": NOW,
            },
            {
                "operation_type": "ingestion.execute",
                "operation_status": "failed",
                "result": None,
                "pipeline_root_id": 99,
                "pipeline_root_status": "in_progress",
                "pipeline_root_result": None,
            },
            {"id": EVENT_ID},
        ]
    )
    connection.execute = AsyncMock(return_value="UPDATE 1")
    service = WorkflowTerminalEventService(
        connection,
        diagnostic_origin="https://ops.example.com",
        external_delivery_enabled=True,
        telemetry_emitter=Mock(return_value=True),
    )

    processed = await service.process_pending_operation_events(
        [42],
        close_deferred_children=True,
    )

    assert [item.classification_status for item in processed] == ["telemetry_only"]
    query, operation_ids = connection.fetch.await_args.args
    assert "event.claim_generation = job.claim_generation" in query
    assert operation_ids == [42]


@pytest.mark.asyncio
async def test_export_failure_does_not_undo_classification_state() -> None:
    connection = Mock()
    connection.fetchrow = AsyncMock(
        side_effect=[
            {
                "id": EVENT_ID,
                "event_key": "operation:42:claim:2:status:cancelled",
                "source_kind": "operation",
                "operation_id": 42,
                "claim_generation": 2,
                "terminal_status": "cancelled",
                "reconciliation_action_id": None,
                "reconciliation_run_id": None,
                "reconciliation_content_id": None,
                "classification_status": "pending",
                "occurred_at": NOW,
            },
            {
                "operation_type": "ingestion.execute",
                "operation_status": "cancelled",
                "result": {"secret": "must-not-read"},
                "pipeline_root_id": None,
            },
            {"id": EVENT_ID},
        ]
    )
    connection.execute = AsyncMock(return_value="UPDATE 1")
    emitter = Mock(side_effect=RuntimeError("unsafe exporter detail"))
    service = WorkflowTerminalEventService(connection, telemetry_emitter=emitter)

    processed = await service.process_pending_event(EVENT_ID)

    assert processed is not None
    assert processed.classification_status == "telemetry_only"
    connection.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_already_processed_event_is_an_idempotent_noop() -> None:
    connection = Mock()
    connection.fetchrow = AsyncMock(
        return_value={
            "id": EVENT_ID,
            "event_key": "operation:42:claim:2:status:failed",
            "source_kind": "operation",
            "operation_id": 42,
            "claim_generation": 2,
            "terminal_status": "failed",
            "reconciliation_action_id": None,
            "reconciliation_run_id": None,
            "reconciliation_content_id": None,
            "classification_status": "ready",
            "occurred_at": NOW,
        }
    )
    connection.execute = AsyncMock()
    service = WorkflowTerminalEventService(connection)

    assert await service.process_pending_event(EVENT_ID) is None
    assert connection.fetchrow.await_count == 1
    connection.execute.assert_not_awaited()
