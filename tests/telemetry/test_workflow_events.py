from __future__ import annotations

from unittest.mock import Mock
from uuid import UUID

from src.telemetry import workflow_events

SAFE_DIMENSIONS = {
    "workflow.operation_type": "ingestion.execute",
    "workflow.outcome": "failed",
    "workflow.severity": "error",
    "workflow.source_kind": "operation",
}


def test_terminal_telemetry_uses_stable_names_and_low_cardinality_dimensions(
    monkeypatch,
) -> None:
    counter = Mock()
    span = Mock()
    logger = Mock()
    monkeypatch.setattr(workflow_events, "logger", logger)

    emitted = workflow_events.emit_workflow_terminal_telemetry(
        event_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        event_key="operation:42:claim:2:status:failed",
        operation_type="ingestion.execute",
        outcome="failed",
        severity="error",
        source_kind="operation",
        counter=counter,
        span=span,
    )

    assert emitted is True
    counter.add.assert_called_once_with(1, SAFE_DIMENSIONS)
    event_name, event_attributes = span.add_event.call_args.args
    assert event_name == "workflow.terminal"
    assert event_attributes == {
        **SAFE_DIMENSIONS,
        "workflow.event_id": "550e8400-e29b-41d4-a716-446655440000",
        "workflow.event_key": "operation:42:claim:2:status:failed",
    }
    log_fields = logger.error.call_args.kwargs["extra"]
    assert log_fields == {
        "event": "workflow.terminal",
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "event_key": "operation:42:claim:2:status:failed",
        "operation_type": "ingestion.execute",
        "outcome": "failed",
        "severity": "error",
        "source_kind": "operation",
    }
    assert all("id" not in key and "key" not in key for key in SAFE_DIMENSIONS)


def test_disabled_otel_keeps_safe_local_evidence(monkeypatch) -> None:
    logger = Mock()
    monkeypatch.setattr(workflow_events, "logger", logger)
    monkeypatch.setattr(workflow_events, "_get_otel_emitters", lambda: (None, None))

    emitted = workflow_events.emit_workflow_terminal_telemetry(
        event_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        event_key="operation:42:claim:0:status:cancelled",
        operation_type="ingestion.execute",
        outcome="cancelled",
        severity="info",
        source_kind="operation",
    )

    assert emitted is True
    logger.info.assert_called_once()


def test_exporter_failure_is_swallowed_after_safe_local_log(monkeypatch) -> None:
    counter = Mock()
    counter.add.side_effect = RuntimeError("secret exporter error")
    span = Mock()
    logger = Mock()
    monkeypatch.setattr(workflow_events, "logger", logger)

    emitted = workflow_events.emit_workflow_terminal_telemetry(
        event_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        event_key="operation:42:claim:2:status:failed",
        operation_type="ingestion.execute",
        outcome="failed",
        severity="error",
        source_kind="operation",
        counter=counter,
        span=span,
    )

    assert emitted is True
    logger.error.assert_called_once()
    assert "secret exporter error" not in str(logger.mock_calls)


def test_telemetry_rejects_arbitrary_dimensions_before_logging(monkeypatch) -> None:
    logger = Mock()
    monkeypatch.setattr(workflow_events, "logger", logger)

    try:
        workflow_events.emit_workflow_terminal_telemetry(
            event_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            event_key="operation:42:claim:2:status:failed",
            operation_type="https://attacker.example/path",  # type: ignore[arg-type]
            outcome="failed",
            severity="error",
            source_kind="operation",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("arbitrary telemetry dimension was accepted")

    logger.info.assert_not_called()
    logger.warning.assert_not_called()
    logger.error.assert_not_called()


def test_telemetry_rejects_arbitrary_correlation_key_before_logging(monkeypatch) -> None:
    logger = Mock()
    monkeypatch.setattr(workflow_events, "logger", logger)

    try:
        workflow_events.emit_workflow_terminal_telemetry(
            event_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            event_key="secret_token",
            operation_type="ingestion.execute",
            outcome="failed",
            severity="error",
            source_kind="operation",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("arbitrary correlation key was accepted")

    logger.info.assert_not_called()
    logger.warning.assert_not_called()
    logger.error.assert_not_called()
