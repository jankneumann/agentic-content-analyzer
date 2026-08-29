"""In-memory topology proof for persisted W3C queue propagation."""

from __future__ import annotations

from typing import Any

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

from src.queue import worker


class _Capture(SpanExporter):
    def __init__(self) -> None:
        self.spans: list[Any] = []

    def export(self, spans: Any) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


def test_attempt_span_continues_stored_trace_and_submission_parent() -> None:
    trace_id = "11111111111111111111111111111111"
    parent_span_id = "2222222222222222"
    stored = {
        "schema_version": 1,
        "operation_id": "41",
        "root_operation_id": "41",
        "parent_operation_id": None,
        "traceparent": f"00-{trace_id}-{parent_span_id}-01",
        "tracestate": None,
        "trace_id": trace_id,
        "span_id": parent_span_id,
        "claim_generation": "0",
        "attempt_number": None,
        "entrypoint": "pipeline.run",
        "service_name": "aca-api",
        "service_instance_id": "api-1",
        "environment": "test",
        "release_revision": "test",
        "stage": "submit",
        "resource_kind": None,
        "resource_key": None,
    }
    capture = _Capture()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(capture))
    tracer = provider.get_tracer(__name__)
    with worker._bind_submission_parent({"submission_context": stored}):
        with tracer.start_as_current_span("operation.pipeline.run.attempt") as span:
            actual = worker._actual_attempt_context(
                worker._attempt_context_from_job(
                    {
                        "id": 41,
                        "entrypoint": "pipeline.run",
                        "claim_generation": 0,
                        "claim_protocol_version": 2,
                        "submission_context": stored,
                        "submission_traceparent": stored["traceparent"],
                        "submission_tracestate": None,
                        "trace_id": trace_id,
                        "root_operation_id": 41,
                    }
                ),
                span,
            )
    assert actual.trace_id == trace_id
    assert actual.span_id != parent_span_id
    assert capture.spans[0].context.trace_id == int(trace_id, 16)
    assert capture.spans[0].parent.span_id == int(parent_span_id, 16)
    assert actual.span_id == format(capture.spans[0].context.span_id, "016x")
