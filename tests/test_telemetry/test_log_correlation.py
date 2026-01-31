"""Tests for trace-log correlation and console formatters."""

from __future__ import annotations

import json
import logging

from src.utils.logging import JsonFormatter, TraceContextFormatter


class TestJsonFormatter:
    """Tests for the JSON console formatter."""

    def test_produces_valid_json(self):
        """JsonFormatter output should be valid JSON."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Hello %s",
            args=("world",),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "Hello world"
        assert "timestamp" in parsed

    def test_includes_trace_context_when_present(self):
        """Should include trace_id and span_id when set on record."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="traced event",
            args=(),
            exc_info=None,
        )
        record.otelTraceID = "abcdef1234567890abcdef1234567890"
        record.otelSpanID = "1234567890abcdef"

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["trace_id"] == "abcdef1234567890abcdef1234567890"
        assert parsed["span_id"] == "1234567890abcdef"

    def test_excludes_zero_trace_context(self):
        """Should not include trace_id/span_id when they are '0' (no active span)."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="no span",
            args=(),
            exc_info=None,
        )
        record.otelTraceID = "0"
        record.otelSpanID = "0"

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "trace_id" not in parsed
        assert "span_id" not in parsed

    def test_includes_extra_attributes(self):
        """Extra attributes passed via extra={} should appear in JSON output."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="with extras",
            args=(),
            exc_info=None,
        )
        record.source = "gmail"
        record.item_count = 42

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["source"] == "gmail"
        assert parsed["item_count"] == 42

    def test_includes_exception_info(self):
        """Should include exception details when exc_info is set."""
        formatter = JsonFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="failed",
                args=(),
                exc_info=sys.exc_info(),
            )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "exception" in parsed
        assert "ValueError: test error" in parsed["exception"]


class TestTraceContextFormatter:
    """Tests for the text formatter with trace context."""

    def test_standard_format_without_trace(self):
        """Should produce standard text format when no trace context."""
        formatter = TraceContextFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        assert "test.logger" in output
        assert "INFO" in output
        assert "hello" in output
        assert "trace_id" not in output

    def test_appends_trace_context_when_present(self):
        """Should append [trace_id=... span_id=...] when trace is active."""
        formatter = TraceContextFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="traced",
            args=(),
            exc_info=None,
        )
        record.otelTraceID = "abcdef1234567890abcdef1234567890"
        record.otelSpanID = "1234567890abcdef"

        output = formatter.format(record)

        assert "[trace_id=abcdef1234567890abcdef1234567890 span_id=1234567890abcdef]" in output

    def test_no_trace_suffix_for_zero_ids(self):
        """Should not append trace suffix when IDs are '0'."""
        formatter = TraceContextFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="no span",
            args=(),
            exc_info=None,
        )
        record.otelTraceID = "0"
        record.otelSpanID = "0"

        output = formatter.format(record)

        assert "trace_id" not in output


class TestTraceLogCorrelation:
    """Tests for automatic trace-log correlation via LoggingInstrumentor."""

    def test_log_within_active_span_has_trace_context(self):
        """Log records emitted within an active span should have otelTraceID/otelSpanID."""
        from opentelemetry import trace
        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        from opentelemetry.sdk.trace import TracerProvider

        # Set up a real TracerProvider
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        tracer = trace.get_tracer("test")

        # Instrument logging
        instrumentor = LoggingInstrumentor()
        instrumentor.instrument(set_logging_format=False)

        try:
            # Capture log records via a handler
            captured_records: list[logging.LogRecord] = []

            class CaptureHandler(logging.Handler):
                def emit(self, record: logging.LogRecord) -> None:
                    captured_records.append(record)

            test_logger = logging.getLogger("test.correlation")
            handler = CaptureHandler()
            test_logger.addHandler(handler)
            test_logger.setLevel(logging.DEBUG)

            with tracer.start_as_current_span("test-span") as span:
                test_logger.info("inside span")
                expected_trace_id = format(span.get_span_context().trace_id, "032x")
                expected_span_id = format(span.get_span_context().span_id, "016x")

            assert len(captured_records) == 1
            record = captured_records[0]
            assert getattr(record, "otelTraceID", None) == expected_trace_id
            assert getattr(record, "otelSpanID", None) == expected_span_id

            test_logger.removeHandler(handler)
        finally:
            instrumentor.uninstrument()
            trace.set_tracer_provider(TracerProvider())

    def test_log_outside_span_has_zero_trace_context(self):
        """Log records emitted outside a span should have zero/empty trace context."""
        from opentelemetry.instrumentation.logging import LoggingInstrumentor

        instrumentor = LoggingInstrumentor()
        instrumentor.instrument(set_logging_format=False)

        try:
            captured_records: list[logging.LogRecord] = []

            class CaptureHandler(logging.Handler):
                def emit(self, record: logging.LogRecord) -> None:
                    captured_records.append(record)

            test_logger = logging.getLogger("test.no_span")
            handler = CaptureHandler()
            test_logger.addHandler(handler)
            test_logger.setLevel(logging.DEBUG)

            test_logger.info("outside span")

            assert len(captured_records) == 1
            record = captured_records[0]
            # Outside a span, otelTraceID should be "0" or all zeros
            trace_id = getattr(record, "otelTraceID", "0")
            assert trace_id == "0" or trace_id == "00000000000000000000000000000000"

            test_logger.removeHandler(handler)
        finally:
            instrumentor.uninstrument()
