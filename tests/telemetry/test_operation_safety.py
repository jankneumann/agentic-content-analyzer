"""Redaction, controlled-detail, and metric-cardinality canaries."""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

import src.telemetry.safety as telemetry_safety
from src.contracts.operation_context import parse_operation_context
from src.telemetry.operation_spans import (
    generation_metadata,
    operation_span,
)
from src.telemetry.providers.langfuse import LangfuseProvider
from src.telemetry.safety import (
    REDACTED,
    MaskingSpanExporter,
    TelemetryMasker,
    export_selected_trace_value,
    masked_exception_stack,
    safe_log_fields,
    safe_metric_attributes,
    safe_span_attributes,
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
    assert "operation.parent_id" not in attributes
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


def test_explicit_excerpt_never_exceeds_four_kibibytes_utf8() -> None:
    selected = select_trace_input("😀" * 2_000, max_code_points=10_000)

    assert len(selected.value.encode("utf-8")) <= 4 * 1024
    assert selected.value.endswith("…")


def test_masked_exception_stack_never_exceeds_sixty_four_kibibytes_utf8() -> None:
    masker = TelemetryMasker(canaries=(SECRET_CANARY,))

    try:
        raise RuntimeError(f"{SECRET_CANARY} " + "😀" * 70_000)
    except RuntimeError as error:
        evidence = masked_exception_stack(error, masker=masker)

    assert len(evidence.encode("utf-8")) <= 64 * 1024
    assert evidence.endswith("…")
    assert SECRET_CANARY not in evidence


def test_span_attribute_payload_never_exceeds_one_hundred_twenty_eight_kibibytes() -> None:
    attributes = {f"field.{index}": "😀" * 2_048 for index in range(128)}

    safe = safe_span_attributes(attributes, masker=TelemetryMasker())
    serialized = json.dumps(
        safe,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")

    assert len(safe) <= 128
    assert len(serialized) <= 128 * 1024
    assert safe["field.0"].startswith("😀")


def test_attempt_budget_reserves_terminal_capacity_and_omits_success_detail_first() -> None:
    budget = telemetry_safety.AttemptObservationBudget(
        max_observations=4,
        max_bytes=100,
        reserved_observations=1,
        reserved_bytes=20,
    )

    detail_dropped = budget.record_success(
        topology_bytes=60,
        metadata_bytes=15,
        excerpt_bytes=10,
    )
    metadata_dropped = budget.record_success(
        topology_bytes=5,
        metadata_bytes=1,
        excerpt_bytes=1,
    )

    assert detail_dropped.accepted is True
    assert detail_dropped.include_metadata is True
    assert detail_dropped.include_excerpt is False
    assert metadata_dropped.accepted is True
    assert metadata_dropped.include_metadata is False
    assert metadata_dropped.include_excerpt is False
    assert budget.record_reserved(payload_bytes=20, kind="failure") is True
    assert budget.observations_used == 3
    assert budget.bytes_used == 100
    assert budget.omitted_counters == {
        "observations": 0,
        "bytes": 12,
        "successful_excerpts": 2,
        "successful_metadata": 1,
        "reserved_evidence": 0,
    }


def test_attempt_budget_default_envelope_is_256_observations_and_sixteen_mibibytes() -> None:
    budget = telemetry_safety.AttemptObservationBudget()

    assert budget.max_observations == 256
    assert budget.max_bytes == 16 * 1024 * 1024
    assert budget.reserved_observations == 64
    assert budget.reserved_bytes == 4 * 1024 * 1024
    assert budget.success_observation_limit == 192
    assert budget.success_byte_limit == 12 * 1024 * 1024

    for _ in range(budget.success_observation_limit):
        assert budget.record_success(topology_bytes=1).accepted is True
    rejected = budget.record_success(
        topology_bytes=1,
        metadata_bytes=1,
        excerpt_bytes=1,
    )
    assert rejected.accepted is False

    for _ in range(budget.reserved_observations):
        assert budget.record_reserved(payload_bytes=1, kind="telemetry_health") is True
    assert budget.record_reserved(payload_bytes=1, kind="terminal") is False
    assert budget.observations_used == 256
    assert budget.omitted_counters["observations"] == 2
    assert budget.omitted_counters["reserved_evidence"] == 1


def test_exported_excerpt_remains_four_kibibytes_after_mask_expansion() -> None:
    selected = select_trace_input("x" * 1_000, max_code_points=1_000)

    exported = export_selected_trace_value(
        selected,
        expected_kind="input",
        masker=TelemetryMasker(canaries=("x",)),
    )

    assert exported is not None
    assert len(exported.encode("utf-8")) <= 4 * 1024
    assert exported.endswith("…")


def test_attempt_budget_enforces_total_byte_limit_when_reserved_evidence_arrives_first() -> None:
    budget = telemetry_safety.AttemptObservationBudget(
        max_observations=4,
        max_bytes=100,
        reserved_observations=1,
        reserved_bytes=20,
    )
    assert budget.record_reserved(payload_bytes=90, kind="security") is True

    rejected = budget.record_success(topology_bytes=11)

    assert rejected.accepted is False
    assert budget.bytes_used == 90


def test_attempt_budget_enforces_total_count_when_reserved_evidence_arrives_first() -> None:
    budget = telemetry_safety.AttemptObservationBudget(
        max_observations=2,
        max_bytes=100,
        reserved_observations=1,
        reserved_bytes=20,
    )
    assert budget.record_reserved(payload_bytes=1, kind="failure") is True
    assert budget.record_reserved(payload_bytes=1, kind="terminal") is True

    rejected = budget.record_success(topology_bytes=1)

    assert rejected.accepted is False
    assert budget.observations_used == 2
