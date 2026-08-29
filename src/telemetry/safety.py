"""Central privacy, size, and cardinality controls for telemetry export."""

from __future__ import annotations

import os
import re
import traceback
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

from opentelemetry.sdk._logs.export import LogRecordExporter
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter

from src.contracts.operation_context import OperationContext

REDACTED = "[REDACTED]"
DEFAULT_EXCERPT_CODE_POINTS = 1_000
MAX_ATTRIBUTE_COUNT = 128
MAX_SERIALIZED_PAYLOAD_BYTES = 128 * 1024

_SENSITIVE_KEY = re.compile(
    r"(?:authorization|cookie|password|passwd|secret|token|api[_-]?key|credential|"
    r"prompt|transcript|article[_-]?body|request[_-]?body|response[_-]?body|url)$",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*\b")
_BASIC = re.compile(r"(?i)\bBasic\s+[A-Za-z0-9+/]+=*\b")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])")
_ASSIGNMENT_SECRET = re.compile(
    r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[=:]\s*[^\s,;]+"
)

_METRIC_ATTRIBUTE_BOUNDS: dict[str, int] = {
    "direction": 16,
    "environment": 32,
    "error_class": 64,
    "model": 160,
    "operation_type": 64,
    "outcome": 64,
    "provider": 64,
    "severity": 16,
    "source_kind": 64,
    "source_type": 64,
    "stage": 64,
    "telemetry_delivery_state": 32,
}


@dataclass(frozen=True, slots=True)
class SelectedTraceValue:
    """An explicitly selected, already bounded input or output excerpt."""

    kind: Literal["input", "output"]
    value: str


def bounded_excerpt(value: Any, *, max_code_points: int = DEFAULT_EXCERPT_CODE_POINTS) -> str:
    """Convert an explicitly selected value to a Unicode-code-point-bounded excerpt."""
    if max_code_points < 1:
        raise ValueError("max_code_points must be positive")
    text = str(value)
    if len(text) <= max_code_points:
        return text
    if max_code_points == 1:
        return "…"
    return f"{text[: max_code_points - 1]}…"


def select_trace_input(
    value: Any,
    *,
    max_code_points: int = DEFAULT_EXCERPT_CODE_POINTS,
) -> SelectedTraceValue:
    """Explicitly opt a bounded input excerpt into detailed trace export."""
    return SelectedTraceValue("input", bounded_excerpt(value, max_code_points=max_code_points))


def select_trace_output(
    value: Any,
    *,
    max_code_points: int = DEFAULT_EXCERPT_CODE_POINTS,
) -> SelectedTraceValue:
    """Explicitly opt a bounded output excerpt into detailed trace export."""
    return SelectedTraceValue("output", bounded_excerpt(value, max_code_points=max_code_points))


class TelemetryMasker:
    """Recursively redact configured canaries and common credential/PII forms."""

    def __init__(self, *, canaries: Sequence[str] = ()) -> None:
        self._canaries = tuple(canary for canary in canaries if canary)

    @classmethod
    def from_environment(cls) -> TelemetryMasker:
        """Load comma-separated test/secret canaries without ever logging their values."""
        configured = (
            os.environ.get("TELEMETRY_REDACTION_CANARIES", ""),
            os.environ.get("TELEMETRY_PII_CANARIES", ""),
        )
        return cls(canaries=tuple(item for group in configured for item in group.split(",")))

    def mask(self, value: Any) -> Any:
        """Return an export-safe copy of a nested telemetry value."""
        if isinstance(value, Mapping):
            result: dict[Any, Any] = {}
            for key, item in value.items():
                if _SENSITIVE_KEY.search(str(key)):
                    result[key] = REDACTED
                else:
                    result[key] = self.mask(item)
            return result
        if isinstance(value, tuple):
            return tuple(self.mask(item) for item in value)
        if isinstance(value, list):
            return [self.mask(item) for item in value]
        if isinstance(value, set):
            return {self.mask(item) for item in value}
        if isinstance(value, str):
            return self._mask_text(value)
        return value

    def _mask_text(self, value: str) -> str:
        masked = value
        for canary in self._canaries:
            masked = masked.replace(canary, REDACTED)
        masked = _BEARER.sub(REDACTED, masked)
        masked = _BASIC.sub(REDACTED, masked)
        masked = _EMAIL.sub(REDACTED, masked)
        return _ASSIGNMENT_SECRET.sub(REDACTED, masked)


def export_selected_trace_value(
    selected: SelectedTraceValue | None,
    *,
    expected_kind: Literal["input", "output"],
    masker: TelemetryMasker,
) -> str | None:
    """Mask an explicit selection at the final native-provider export boundary."""
    if selected is None:
        return None
    if not isinstance(selected, SelectedTraceValue) or selected.kind != expected_kind:
        raise TypeError(f"trace {expected_kind} must use select_trace_{expected_kind}()")
    masked = masker.mask(selected.value)
    return str(masked)


def masked_exception_stack(
    error: BaseException,
    *,
    masker: TelemetryMasker | None = None,
) -> str:
    """Preserve full stack shape while masking its serialized text at export."""
    rendered = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    return str((masker or TelemetryMasker.from_environment()).mask(rendered))


def safe_metric_attributes(
    attributes: Mapping[str, Any] | None = None,
    /,
    **values: Any,
) -> dict[str, str | bool | int | float]:
    """Allow only low-cardinality metric dimensions; correlation IDs are never labels."""
    candidates = {**(attributes or {}), **values}
    result: dict[str, str | bool | int | float] = {}
    for key, value in candidates.items():
        bound = _METRIC_ATTRIBUTE_BOUNDS.get(key)
        if bound is None or value is None:
            continue
        if isinstance(value, bool | int | float):
            result[key] = value
            continue
        text = str(value)
        if 0 < len(text) <= bound and "\n" not in text and "\r" not in text:
            result[key] = text
    return result


def safe_span_attributes(
    attributes: Mapping[str, Any] | None,
    *,
    masker: TelemetryMasker,
) -> dict[str, Any]:
    """Bound and mask explicitly supplied span attributes before provider enqueueing."""
    if not attributes:
        return {}
    bounded = dict(list(attributes.items())[:MAX_ATTRIBUTE_COUNT])
    masked = masker.mask(bounded)
    return {
        str(key)[:128]: _bound_attribute_value(value)
        for key, value in masked.items()
        if value is not None
    }


def safe_log_fields(
    context: OperationContext,
    *,
    extra: Mapping[str, Any] | None = None,
    masker: TelemetryMasker | None = None,
) -> dict[str, Any]:
    """Create bounded, masked structured-log enrichment from validated context."""
    fields: dict[str, Any] = {
        "operation_id": context.operation_id,
        "root_operation_id": context.root_operation_id,
        "parent_operation_id": context.parent_operation_id,
        "trace_id": context.trace_id,
        "span_id": context.span_id,
        "claim_generation": context.claim_generation,
        "attempt_number": context.attempt_number,
        "service_name": context.service_name,
        "service_instance_id": context.service_instance_id,
        "environment": context.environment,
        "release_revision": context.release_revision,
        "stage": context.stage,
        "resource_kind": context.resource_kind,
        "resource_key": context.resource_key,
    }
    if extra:
        fields.update(dict(list(extra.items())[: MAX_ATTRIBUTE_COUNT - len(fields)]))
    return safe_span_attributes(fields, masker=masker or TelemetryMasker.from_environment())


class MaskingSpanExporter(SpanExporter):
    """OpenTelemetry exporter decorator masking native and third-party spans."""

    def __init__(self, delegate: SpanExporter, *, masker: TelemetryMasker | None = None) -> None:
        self._delegate = delegate
        self._masker = masker or TelemetryMasker.from_environment()

    def export(self, spans: Sequence[Any]) -> Any:
        masked = tuple(_MaskedSpan(span, self._masker) for span in spans)
        return self._delegate.export(cast(Sequence[ReadableSpan], masked))

    def shutdown(self) -> Any:
        return self._delegate.shutdown()

    def force_flush(self, timeout_millis: int = 30_000) -> Any:
        force_flush = getattr(self._delegate, "force_flush", None)
        if force_flush is None:
            return True
        return force_flush(timeout_millis=timeout_millis)


class MaskingLogExporter(LogRecordExporter):
    """OpenTelemetry log exporter decorator masking bodies and attributes."""

    def __init__(self, delegate: Any, *, masker: TelemetryMasker | None = None) -> None:
        self._delegate = delegate
        self._masker = masker or TelemetryMasker.from_environment()

    def export(self, batch: Sequence[Any]) -> Any:
        return self._delegate.export(
            tuple(_MaskedReadableLogRecord(record, self._masker) for record in batch)
        )

    def shutdown(self) -> Any:
        return self._delegate.shutdown()


class _MaskedReadableLogRecord:
    def __init__(self, target: Any, masker: TelemetryMasker) -> None:
        self._target = target
        self._masker = masker

    @property
    def log_record(self) -> Any:
        return _MaskedLogRecord(self._target.log_record, self._masker)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)


class _MaskedLogRecord:
    def __init__(self, target: Any, masker: TelemetryMasker) -> None:
        self._target = target
        self._masker = masker

    @property
    def body(self) -> Any:
        return self._masker.mask(self._target.body)

    @property
    def attributes(self) -> Any:
        return self._masker.mask(self._target.attributes)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)


class _MaskedSpan:
    def __init__(self, target: Any, masker: TelemetryMasker) -> None:
        self._target = target
        self._masker = masker

    @property
    def attributes(self) -> Any:
        return self._masker.mask(getattr(self._target, "attributes", None))

    @property
    def events(self) -> tuple[Any, ...]:
        return tuple(
            _MaskedEvent(event, self._masker) for event in getattr(self._target, "events", ())
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)


class _MaskedEvent:
    def __init__(self, target: Any, masker: TelemetryMasker) -> None:
        self._target = target
        self._masker = masker

    @property
    def attributes(self) -> Any:
        return self._masker.mask(getattr(self._target, "attributes", None))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._target, name)


def _bound_attribute_value(value: Any) -> Any:
    if isinstance(value, str):
        return bounded_excerpt(value, max_code_points=2_048)
    if isinstance(value, list | tuple):
        return type(value)(_bound_attribute_value(item) for item in value[:128])
    return value


__all__ = [
    "DEFAULT_EXCERPT_CODE_POINTS",
    "MAX_ATTRIBUTE_COUNT",
    "MAX_SERIALIZED_PAYLOAD_BYTES",
    "REDACTED",
    "MaskingLogExporter",
    "MaskingSpanExporter",
    "SelectedTraceValue",
    "TelemetryMasker",
    "bounded_excerpt",
    "export_selected_trace_value",
    "masked_exception_stack",
    "safe_log_fields",
    "safe_metric_attributes",
    "safe_span_attributes",
    "select_trace_input",
    "select_trace_output",
]
