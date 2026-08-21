"""Safe local and OpenTelemetry emission for workflow terminal evidence."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, TypeAdapter

from src.contracts.workflow_alert_models import (
    SYSTEM_CHECK_EVENT_KEY_PATTERN,
    WorkflowAlertSeverity,
    WorkflowTerminalOutcome,
    WorkflowTerminalSourceKind,
    WorkflowTypeName,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)

_meter: Any = None
_terminal_counter: Any = None
_UUID_ADAPTER = TypeAdapter(UUID)


class _TelemetryDimensions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_type: WorkflowTypeName
    outcome: WorkflowTerminalOutcome
    severity: WorkflowAlertSeverity
    source_kind: WorkflowTerminalSourceKind


def emit_workflow_terminal_telemetry(
    *,
    event_id: UUID,
    event_key: str,
    operation_type: WorkflowTypeName,
    outcome: WorkflowTerminalOutcome,
    severity: WorkflowAlertSeverity,
    source_kind: WorkflowTerminalSourceKind,
    counter: Any = None,
    span: Any = None,
) -> bool:
    """Emit bounded evidence; OTel failures never escape this boundary."""

    validated_event_id = _UUID_ADAPTER.validate_python(event_id)
    _validate_event_key(event_key, source_kind)
    dimensions = _TelemetryDimensions(
        operation_type=operation_type,
        outcome=outcome,
        severity=severity,
        source_kind=source_kind,
    )
    metric_attributes = {
        "workflow.operation_type": dimensions.operation_type,
        "workflow.outcome": dimensions.outcome,
        "workflow.severity": dimensions.severity,
        "workflow.source_kind": dimensions.source_kind,
    }
    log_attributes = {
        "event": "workflow.terminal",
        "event_id": str(validated_event_id),
        "event_key": event_key,
        "operation_type": dimensions.operation_type,
        "outcome": dimensions.outcome,
        "severity": dimensions.severity,
        "source_kind": dimensions.source_kind,
    }
    log_method = _log_method(dimensions.severity)
    log_method("workflow terminal event", extra=log_attributes)

    if counter is None and span is None:
        counter, span = _get_otel_emitters()
    try:
        if counter is not None:
            counter.add(1, metric_attributes)
        if span is not None:
            span.add_event(
                "workflow.terminal",
                {
                    **metric_attributes,
                    "workflow.event_id": str(validated_event_id),
                    "workflow.event_key": event_key,
                },
            )
    except Exception:
        # Exporter errors can contain credentials or endpoints. Do not log them.
        pass
    return True


def _validate_event_key(event_key: str, source_kind: WorkflowTerminalSourceKind) -> None:
    if not isinstance(event_key, str) or len(event_key) > 160:
        raise ValueError("invalid workflow terminal correlation key")
    patterns = {
        "operation": r"operation:[1-9][0-9]*:claim:(?:0|[1-9][0-9]*):status:(?:completed|failed|cancelled)",
        "reconciliation_action": r"reconciliation-action:[1-9][0-9]*",
        "reconciliation_failure": (
            r"reconciliation-failure:[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-"
            r"[89ab][a-f0-9]{3}-[a-f0-9]{12}:content:[1-9][0-9]*:reason:apply_failed"
        ),
        # Yet another closed set on the emission path, and one of the quietest: a
        # missing entry here makes `pattern is None` raise, and
        # `process_pending_event` catches that into `emitted = False`. The alert is
        # still delivered, but it produces no log line, no OTel counter, and never
        # checkpoints `telemetry_emitted_at` — the backup monitor would be invisible
        # in the one channel operators actually watch. The grammar is imported
        # rather than restated so it cannot drift from the envelope's copy.
        "system_check": SYSTEM_CHECK_EVENT_KEY_PATTERN,
    }
    pattern = patterns.get(source_kind)
    if pattern is None or re.fullmatch(pattern, event_key) is None:
        raise ValueError("invalid workflow terminal correlation key")


def _log_method(
    severity: WorkflowAlertSeverity,
) -> Any:
    if severity == "error":
        return logger.error
    if severity == "warning":
        return logger.warning
    return logger.info


def _get_otel_emitters() -> tuple[Any, Any]:
    global _meter, _terminal_counter
    try:
        from src.config import settings

        if not settings.otel_enabled:
            return None, None
        from opentelemetry import metrics, trace

        if _meter is None:
            _meter = metrics.get_meter("newsletter-aggregator")
        if _terminal_counter is None:
            _terminal_counter = _meter.create_counter(
                name="workflow.terminal.events",
                description="Committed workflow terminal events",
                unit="1",
            )
        return _terminal_counter, trace.get_current_span()
    except Exception:
        return None, None


def reset_workflow_event_telemetry() -> None:
    """Reset lazily initialized instruments for isolated tests."""

    global _meter, _terminal_counter
    _meter = None
    _terminal_counter = None
