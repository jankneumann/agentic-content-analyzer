"""Redaction, controlled-detail, and metric-cardinality canaries."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.telemetry.operation_spans import (
    generation_metadata,
    operation_span,
)

from src.contracts.operation_context import parse_operation_context
from src.telemetry.providers.langfuse import LangfuseProvider
from src.telemetry.safety import (
    REDACTED,
    MaskingSpanExporter,
    TelemetryMasker,
    masked_exception_stack,
    safe_log_fields,
    safe_metric_attributes,
    select_trace_input,
    select_trace_output,
)

SECRET_CANARY = "gx10-secret-canary-7c836c"
PII_CANARY = "operator.canary@example.invalid"


def context_payload() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "operation_id": "42",
        "root_operation_id": "42",
        "parent_operation_id": None,
        "traceparent": "00-11111111111111111111111111111111-2222222222222222-01",
        "tracestate": None,
        "trace_id": "11111111111111111111111111111111",
        "span_id": "2222222222222222",
        "claim_generation": "2",
        "attempt_number": "3",
        "entrypoint": "worker.claim",
        "service_name": "worker",
        "service_instance_id": "worker-1",
        "environment": "test",
        "release_revision": "abc123",
        "stage": "fetch",
        "resource_kind": "content",
        "resource_key": "opaque-7",
    }


def test_trace_input_output_must_be_explicitly_selected_and_bounded() -> None:
    provider = LangfuseProvider(log_prompts=True)
    provider._client = MagicMock()
    provider._client.start_as_current_observation.return_value.__enter__ = MagicMock()
    provider._client.start_as_current_observation.return_value.__exit__ = MagicMock(
        return_value=False
    )

    provider.trace_llm_call(
        model="test-model",
        provider="test-provider",
        system_prompt=f"unselected {SECRET_CANARY}",
        user_prompt=f"unselected {SECRET_CANARY}",
        response_text=f"unselected {PII_CANARY}",
        input_tokens=3,
        output_tokens=4,
        duration_ms=5.0,
    )
    automatic = provider._client.start_as_current_observation.call_args.kwargs
    assert "input" not in automatic
    assert "output" not in automatic

    provider.trace_llm_call(
        model="test-model",
        provider="test-provider",
        system_prompt="never exported",
        user_prompt="never exported",
        response_text="never exported",
        input_tokens=3,
        output_tokens=4,
        duration_ms=5.0,
        trace_input=select_trace_input("😀" * 10 + SECRET_CANARY, max_code_points=12),
        trace_output=select_trace_output(PII_CANARY, max_code_points=100),
    )
    selected = provider._client.start_as_current_observation.call_args.kwargs
    assert len(selected["input"]) <= 12
    assert SECRET_CANARY not in selected["input"]
    assert PII_CANARY not in selected["output"]


def test_export_time_masker_recurses_without_destroying_useful_metadata() -> None:
    masker = TelemetryMasker(canaries=(SECRET_CANARY, PII_CANARY))
    payload = {
        "operation_id": "42",
        "stage": "fetch",
        "authorization": f"Bearer {SECRET_CANARY}",
        "nested": [
            {"message": f"failed for {PII_CANARY}"},
            f"token={SECRET_CANARY}",
        ],
    }

    masked = masker.mask(payload)

    assert masked["operation_id"] == "42"
    assert masked["stage"] == "fetch"
    assert masked["authorization"] == REDACTED
    assert SECRET_CANARY not in str(masked)
    assert PII_CANARY not in str(masked)


def test_exception_stack_keeps_diagnostic_shape_but_masks_canaries() -> None:
    masker = TelemetryMasker(canaries=(SECRET_CANARY, PII_CANARY))

    try:
        raise RuntimeError(f"provider failed for {PII_CANARY}: {SECRET_CANARY}")
    except RuntimeError as error:
        evidence = masked_exception_stack(error, masker=masker)

    assert "RuntimeError" in evidence
    assert "test_exception_stack_keeps_diagnostic_shape" in evidence
    assert SECRET_CANARY not in evidence
    assert PII_CANARY not in evidence


@dataclass(frozen=True)
class FakeEvent:
    name: str
    attributes: dict[str, Any]


@dataclass(frozen=True)
class FakeSpan:
    name: str
    attributes: dict[str, Any]
    events: tuple[FakeEvent, ...]


class CapturingExporter:
    def __init__(self) -> None:
        self.spans: tuple[Any, ...] = ()

    def export(self, spans: Any) -> str:
        self.spans = tuple(spans)
        return "success"

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True


def test_third_party_span_attributes_and_events_are_masked_at_export() -> None:
    delegate = CapturingExporter()
    exporter = MaskingSpanExporter(
        delegate,
        masker=TelemetryMasker(canaries=(SECRET_CANARY, PII_CANARY)),
    )
    span = FakeSpan(
        name="third.party.http",
        attributes={
            "http.request.header.authorization": f"Bearer {SECRET_CANARY}",
            "server.address": "provider.example",
        },
        events=(
            FakeEvent(
                name="exception",
                attributes={"exception.stacktrace": f"stack {PII_CANARY} {SECRET_CANARY}"},
            ),
        ),
    )

    assert exporter.export((span,)) == "success"
    exported = delegate.spans[0]
    assert exported.attributes["server.address"] == "provider.example"
    assert SECRET_CANARY not in str(exported.attributes)
    assert PII_CANARY not in str(exported.events[0].attributes)


def test_high_cardinality_identifiers_never_become_metric_labels() -> None:
    attributes = safe_metric_attributes(
        stage="fetch",
        outcome="retryable_failure",
        provider="youtube",
        operation_id="42",
        root_operation_id="42",
        trace_id="1" * 32,
        span_id="2" * 16,
        resource_key="opaque-7",
        event_key="operation:42:claim:2:status:failed",
        exception_message=f"failure {SECRET_CANARY}",
    )

    assert attributes == {
        "stage": "fetch",
        "outcome": "retryable_failure",
        "provider": "youtube",
    }


def test_log_enrichment_keeps_correlation_but_masks_selected_fields() -> None:
    context = parse_operation_context(context_payload())
    fields = safe_log_fields(
        context,
        extra={
            "diagnostic_code": "provider.timeout",
            "message": f"failed with {SECRET_CANARY}",
            "authorization": f"Bearer {SECRET_CANARY}",
        },
        masker=TelemetryMasker(canaries=(SECRET_CANARY,)),
    )

    assert fields["operation_id"] == "42"
    assert fields["claim_generation"] == "2"
    assert fields["stage"] == "fetch"
    assert fields["diagnostic_code"] == "provider.timeout"
    assert SECRET_CANARY not in str(fields)


def test_langfuse_setup_installs_native_export_mask_callback() -> None:
    provider = LangfuseProvider(mask_canaries=(SECRET_CANARY, PII_CANARY))
    client_class = MagicMock()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(provider, "_setup_anthropic_instrumentor", MagicMock())
        monkeypatch.setitem(
            __import__("sys").modules,
            "langfuse",
            SimpleNamespace(Langfuse=client_class),
        )
        provider.setup()

    mask = client_class.call_args.kwargs["mask"]
    masked = mask({"secret": SECRET_CANARY, "email": PII_CANARY, "stage": "model"})
    assert masked == {"secret": REDACTED, "email": REDACTED, "stage": "model"}


class FakeSpanProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def start_span(self, name: str, attributes: dict[str, Any] | None = None) -> Any:
        owner = self

        class SpanManager:
            def __enter__(self) -> object:
                owner.calls.append((name, attributes or {}))
                return object()

            def __exit__(self, *_args: object) -> None:
                return None

        return SpanManager()


def test_operation_span_adds_attempt_generation_and_bounded_metadata() -> None:
    context = parse_operation_context(context_payload())
    provider = FakeSpanProvider()

    with operation_span(
        provider,
        "operation.fetch",
        context=context,
        stage="fetch",
        attributes={"retry.reason": "timeout", "authorization": f"Bearer {SECRET_CANARY}"},
        masker=TelemetryMasker(canaries=(SECRET_CANARY,)),
    ):
        pass

    name, attributes = provider.calls[0]
    assert name == "operation.fetch"
    assert attributes["operation.id"] == "42"
    assert attributes["operation.claim_generation"] == "2"
    assert attributes["operation.attempt_number"] == "3"
    assert attributes["operation.stage"] == "fetch"
    assert attributes["retry.reason"] == "timeout"
    assert SECRET_CANARY not in str(attributes)


def test_generation_metadata_retains_useful_low_volume_fields() -> None:
    metadata = generation_metadata(
        model="claude-sonnet-4-5",
        provider="anthropic",
        input_tokens=120,
        output_tokens=30,
        duration_ms=42.5,
        cost_usd=0.0123,
        max_tokens=1_024,
        extra={"fallback": True, "prompt": SECRET_CANARY},
        masker=TelemetryMasker(canaries=(SECRET_CANARY,)),
    )

    assert metadata == {
        "model": "claude-sonnet-4-5",
        "provider": "anthropic",
        "input_tokens": 120,
        "output_tokens": 30,
        "duration_ms": 42.5,
        "cost_usd": 0.0123,
        "max_tokens": 1_024,
        "fallback": True,
        "prompt": REDACTED,
    }
