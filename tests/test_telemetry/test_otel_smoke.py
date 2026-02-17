"""Smoke tests for the OTel trace pipeline.

These tests wire real OpenTelemetry SDK components (TracerProvider,
SimpleSpanProcessor) with an in-memory exporter to verify that our
providers produce correct spans with gen_ai.* semantic conventions —
without requiring any external infrastructure.

Why this matters:
  Unit tests mock the OTel SDK.  These smoke tests run the REAL SDK
  pipeline: Provider → Tracer → Span → Processor → Exporter.  If OTel
  changes an API or we misconfigure a provider, these tests catch it.
"""

from __future__ import annotations

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)


# ---------------------------------------------------------------------------
# In-memory exporter (InMemorySpanExporter was removed in newer OTel SDK)
# ---------------------------------------------------------------------------
class MemoryExporter(SpanExporter):
    """Captures exported spans in a list for test assertions."""

    def __init__(self) -> None:
        self.spans: list = []

    def export(self, spans):
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def otel_harness():
    """Provide a fresh TracerProvider + MemoryExporter for each test.

    Yields (tracer_provider, exporter) and shuts down after.
    """
    exporter = MemoryExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    yield provider, exporter

    provider.shutdown()


# ---------------------------------------------------------------------------
# OpikProvider smoke tests
# ---------------------------------------------------------------------------
class TestOpikProviderSmoke:
    """Verify OpikProvider emits correct OTel spans with gen_ai.* attrs."""

    def test_trace_llm_call_produces_span_with_gen_ai_attributes(self, otel_harness):
        """A single trace_llm_call should produce one span with all gen_ai attrs."""
        tracer_provider, exporter = otel_harness

        from src.telemetry.providers.opik import OpikProvider

        provider = OpikProvider(log_prompts=True)
        # Inject our test TracerProvider instead of the real one
        provider._tracer_provider = tracer_provider
        provider._tracer = tracer_provider.get_tracer(__name__)
        provider._setup_complete = True

        provider.trace_llm_call(
            model="claude-sonnet-4-5",
            provider="anthropic",
            system_prompt="You are a helpful assistant.",
            user_prompt="Summarize this article about AI.",
            response_text="AI is transforming many industries...",
            input_tokens=150,
            output_tokens=80,
            duration_ms=1234.5,
            max_tokens=4096,
            metadata={"pipeline_step": "summarization"},
        )

        spans = exporter.spans
        assert len(spans) == 1

        span = spans[0]
        attrs = dict(span.attributes)

        # Span name
        assert span.name == "llm.completion"

        # gen_ai.* semantic conventions
        assert attrs["gen_ai.system"] == "anthropic"
        assert attrs["gen_ai.request.model"] == "claude-sonnet-4-5"
        assert attrs["gen_ai.usage.input_tokens"] == 150
        assert attrs["gen_ai.usage.output_tokens"] == 80
        assert attrs["gen_ai.request.max_tokens"] == 4096

        # Prompt logging (enabled via log_prompts=True)
        assert "Summarize this article" in attrs["gen_ai.prompt"]
        assert "AI is transforming" in attrs["gen_ai.completion"]

        # Custom metadata
        assert attrs["custom.pipeline_step"] == "summarization"

    def test_trace_llm_call_respects_prompt_privacy(self, otel_harness):
        """With log_prompts=False, no prompt/completion text should appear."""
        tracer_provider, exporter = otel_harness

        from src.telemetry.providers.opik import OpikProvider

        provider = OpikProvider(log_prompts=False)
        provider._tracer_provider = tracer_provider
        provider._tracer = tracer_provider.get_tracer(__name__)
        provider._setup_complete = True

        provider.trace_llm_call(
            model="claude-haiku-4-5",
            provider="anthropic",
            system_prompt="secret system prompt",
            user_prompt="secret user prompt",
            response_text="secret response",
            input_tokens=50,
            output_tokens=30,
            duration_ms=200.0,
        )

        attrs = dict(exporter.spans[0].attributes)
        assert "gen_ai.prompt" not in attrs
        assert "gen_ai.completion" not in attrs
        # Token counts should still be present
        assert attrs["gen_ai.usage.input_tokens"] == 50

    def test_start_span_creates_named_span_with_attributes(self, otel_harness):
        """start_span should create a span with the given name and attributes."""
        tracer_provider, exporter = otel_harness

        from src.telemetry.providers.opik import OpikProvider

        provider = OpikProvider()
        provider._tracer_provider = tracer_provider
        provider._tracer = tracer_provider.get_tracer(__name__)
        provider._setup_complete = True

        with provider.start_span(
            "ingestion.gmail",
            attributes={"source": "newsletter", "count": "42"},
        ) as span:
            assert span is not None

        spans = exporter.spans
        assert len(spans) == 1
        assert spans[0].name == "ingestion.gmail"
        attrs = dict(spans[0].attributes)
        assert attrs["source"] == "newsletter"
        assert attrs["count"] == "42"

    def test_multiple_calls_produce_separate_spans(self, otel_harness):
        """Each trace_llm_call should produce its own independent span."""
        tracer_provider, exporter = otel_harness

        from src.telemetry.providers.opik import OpikProvider

        provider = OpikProvider()
        provider._tracer_provider = tracer_provider
        provider._tracer = tracer_provider.get_tracer(__name__)
        provider._setup_complete = True

        for model in ["claude-haiku-4-5", "claude-sonnet-4-5", "gpt-4o"]:
            provider.trace_llm_call(
                model=model,
                provider="test",
                system_prompt="sys",
                user_prompt="usr",
                response_text="resp",
                input_tokens=10,
                output_tokens=5,
                duration_ms=100.0,
            )

        assert len(exporter.spans) == 3
        models = [dict(s.attributes)["gen_ai.request.model"] for s in exporter.spans]
        assert models == ["claude-haiku-4-5", "claude-sonnet-4-5", "gpt-4o"]


# ---------------------------------------------------------------------------
# OTelProvider smoke tests
# ---------------------------------------------------------------------------
class TestOTelProviderSmoke:
    """Verify OTelProvider emits correct spans (same gen_ai.* contract)."""

    def test_trace_llm_call_produces_span(self, otel_harness):
        """OTelProvider should produce spans with the same gen_ai attrs as Opik."""
        tracer_provider, exporter = otel_harness

        from src.telemetry.providers.otel_provider import OTelProvider

        provider = OTelProvider(log_prompts=True)
        provider._tracer_provider = tracer_provider
        provider._tracer = tracer_provider.get_tracer(__name__)
        provider._setup_complete = True

        provider.trace_llm_call(
            model="gpt-4o",
            provider="openai",
            system_prompt="You are helpful.",
            user_prompt="What is RAG?",
            response_text="RAG stands for Retrieval-Augmented Generation...",
            input_tokens=200,
            output_tokens=150,
            duration_ms=800.0,
            max_tokens=8192,
        )

        spans = exporter.spans
        assert len(spans) == 1

        attrs = dict(spans[0].attributes)
        assert attrs["gen_ai.system"] == "openai"
        assert attrs["gen_ai.request.model"] == "gpt-4o"
        assert attrs["gen_ai.usage.input_tokens"] == 200
        assert attrs["gen_ai.usage.output_tokens"] == 150
        assert attrs["gen_ai.request.max_tokens"] == 8192
        assert "RAG" in attrs["gen_ai.prompt"]
        assert "Retrieval-Augmented" in attrs["gen_ai.completion"]

    def test_start_span_creates_named_span(self, otel_harness):
        """OTelProvider.start_span should work identically to OpikProvider."""
        tracer_provider, exporter = otel_harness

        from src.telemetry.providers.otel_provider import OTelProvider

        provider = OTelProvider()
        provider._tracer_provider = tracer_provider
        provider._tracer = tracer_provider.get_tracer(__name__)
        provider._setup_complete = True

        with provider.start_span("digest.creation", attributes={"type": "weekly"}):
            pass

        assert len(exporter.spans) == 1
        assert exporter.spans[0].name == "digest.creation"
        assert dict(exporter.spans[0].attributes)["type"] == "weekly"


# ---------------------------------------------------------------------------
# Provider contract parity
# ---------------------------------------------------------------------------
class TestProviderContractParity:
    """Ensure Opik and OTel providers emit identical span shapes.

    Both providers should produce the exact same gen_ai.* attribute set
    for the same input, since downstream tools (dashboards, alerts) rely
    on consistent schema.
    """

    def test_same_input_produces_same_attributes(self, otel_harness):
        """Given identical inputs, Opik and OTel providers should emit matching attrs."""
        tracer_provider, exporter = otel_harness

        from src.telemetry.providers.opik import OpikProvider
        from src.telemetry.providers.otel_provider import OTelProvider

        call_kwargs = {
            "model": "claude-sonnet-4-5",
            "provider": "anthropic",
            "system_prompt": "sys",
            "user_prompt": "What is observability?",
            "response_text": "Observability is the ability to...",
            "input_tokens": 100,
            "output_tokens": 75,
            "duration_ms": 500.0,
            "max_tokens": 2048,
            "metadata": {"step": "test"},
        }

        # Opik provider
        opik = OpikProvider(log_prompts=True)
        opik._tracer_provider = tracer_provider
        opik._tracer = tracer_provider.get_tracer("opik-test")
        opik._setup_complete = True
        opik.trace_llm_call(**call_kwargs)

        # OTel provider (shares same TracerProvider)
        otel = OTelProvider(log_prompts=True)
        otel._tracer_provider = tracer_provider
        otel._tracer = tracer_provider.get_tracer("otel-test")
        otel._setup_complete = True
        otel.trace_llm_call(**call_kwargs)

        assert len(exporter.spans) == 2
        opik_attrs = dict(exporter.spans[0].attributes)
        otel_attrs = dict(exporter.spans[1].attributes)

        # Same attribute keys
        assert set(opik_attrs.keys()) == set(otel_attrs.keys())

        # Same attribute values
        for key in opik_attrs:
            assert opik_attrs[key] == otel_attrs[key], (
                f"Mismatch on {key}: opik={opik_attrs[key]!r} vs otel={otel_attrs[key]!r}"
            )
