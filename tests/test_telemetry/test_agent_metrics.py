"""Tests for agent-specific OTel metrics and tracing.

Verifies that agent metrics instruments are created correctly,
record functions are safe no-ops when disabled, and tracing
context managers work in both enabled and disabled modes.

Covers OpenSpec task 8.3.
"""

from unittest.mock import MagicMock, patch

from src.telemetry.agent_metrics import (
    _NoopSpan,
    record_agent_task,
    record_approval_check,
    record_memory_operation,
    record_specialist_invocation,
    reset_agent_metrics,
    trace_agent_task,
    trace_approval_check,
    trace_memory_operation,
    trace_specialist,
)


class TestAgentMetricsDisabled:
    """When OTel is disabled, all record functions are safe no-ops."""

    def setup_method(self):
        reset_agent_metrics()

    def teardown_method(self):
        reset_agent_metrics()

    def test_record_agent_task_noop_when_disabled(self):
        with patch("src.telemetry.agent_metrics._ensure_meter", return_value=False):
            # Should not raise
            record_agent_task(
                task_type="research",
                status="completed",
                persona="default",
                source="user",
                duration_ms=1500.0,
                tokens=100,
                cost=0.01,
            )

    def test_record_specialist_invocation_noop_when_disabled(self):
        with patch("src.telemetry.agent_metrics._ensure_meter", return_value=False):
            record_specialist_invocation(
                specialist="research",
                success=True,
                duration_ms=500.0,
                retries=0,
            )

    def test_record_memory_operation_noop_when_disabled(self):
        with patch("src.telemetry.agent_metrics._ensure_meter", return_value=False):
            record_memory_operation(operation="recall", strategy="vector", success=True)

    def test_record_approval_check_noop_when_disabled(self):
        with patch("src.telemetry.agent_metrics._ensure_meter", return_value=False):
            record_approval_check(action="delegate.research", risk_level="low", approved=True)


class TestAgentMetricsEnabled:
    """When OTel is enabled, metrics are recorded correctly."""

    def setup_method(self):
        reset_agent_metrics()

    def teardown_method(self):
        reset_agent_metrics()

    def test_record_agent_task_creates_metrics(self):
        """Verify task counter, duration histogram, token and cost counters are called."""
        import src.telemetry.agent_metrics as mod

        mock_counter = MagicMock()
        mock_histogram = MagicMock()
        mock_token_counter = MagicMock()
        mock_cost_counter = MagicMock()

        mod._meter = MagicMock()  # Mark as initialized
        mod._agent_task_counter = mock_counter
        mod._agent_task_duration = mock_histogram
        mod._agent_token_counter = mock_token_counter
        mod._agent_cost_counter = mock_cost_counter

        record_agent_task(
            task_type="research",
            status="completed",
            persona="default",
            source="user",
            duration_ms=1500.0,
            tokens=200,
            cost=0.05,
        )

        mock_counter.add.assert_called_once()
        mock_histogram.record.assert_called_once()
        mock_token_counter.add.assert_called_once()
        mock_cost_counter.add.assert_called_once()

        # Verify attributes
        call_attrs = mock_counter.add.call_args[0][1]
        assert call_attrs["task_type"] == "research"
        assert call_attrs["status"] == "completed"
        assert call_attrs["persona"] == "default"

    def test_record_specialist_invocation_creates_metrics(self):
        import src.telemetry.agent_metrics as mod

        mock_counter = MagicMock()
        mock_histogram = MagicMock()

        mod._meter = MagicMock()
        mod._specialist_invocation_counter = mock_counter
        mod._specialist_duration = mock_histogram

        record_specialist_invocation(
            specialist="analysis",
            success=True,
            duration_ms=800.0,
            retries=1,
        )

        mock_counter.add.assert_called_once()
        attrs = mock_counter.add.call_args[0][1]
        assert attrs["specialist"] == "analysis"
        assert attrs["retries"] == "1"

    def test_record_memory_operation_creates_metrics(self):
        import src.telemetry.agent_metrics as mod

        mock_counter = MagicMock()
        mod._meter = MagicMock()
        mod._memory_operation_counter = mock_counter

        record_memory_operation(operation="recall", strategy="vector", success=True)

        mock_counter.add.assert_called_once()
        attrs = mock_counter.add.call_args[0][1]
        assert attrs["operation"] == "recall"
        assert attrs["strategy"] == "vector"

    def test_record_approval_check_creates_metrics(self):
        import src.telemetry.agent_metrics as mod

        mock_counter = MagicMock()
        mod._meter = MagicMock()
        mod._approval_check_counter = mock_counter

        record_approval_check(
            action="delegate.ingestion",
            risk_level="high",
            approved=False,
        )

        mock_counter.add.assert_called_once()
        attrs = mock_counter.add.call_args[0][1]
        assert attrs["action"] == "delegate.ingestion"
        assert attrs["approved"] == "False"

    def test_zero_tokens_and_cost_not_recorded(self):
        """When tokens=0 and cost=0, those counters are not called."""
        import src.telemetry.agent_metrics as mod

        mock_token = MagicMock()
        mock_cost = MagicMock()

        mod._meter = MagicMock()
        mod._agent_task_counter = MagicMock()
        mod._agent_task_duration = MagicMock()
        mod._agent_token_counter = mock_token
        mod._agent_cost_counter = mock_cost

        record_agent_task(
            task_type="research",
            status="completed",
            persona="default",
            source="user",
            duration_ms=100.0,
            tokens=0,
            cost=0.0,
        )

        mock_token.add.assert_not_called()
        mock_cost.add.assert_not_called()


class TestAgentTracing:
    """Test tracing context managers."""

    def setup_method(self):
        reset_agent_metrics()

    def teardown_method(self):
        reset_agent_metrics()

    def test_trace_agent_task_noop_when_disabled(self):
        with patch("src.telemetry.agent_metrics._ensure_tracer", return_value=False):
            with trace_agent_task("t1", "research", "default", "user") as span:
                assert isinstance(span, _NoopSpan)
                # Should be callable without error
                span.set_attribute("key", "value")

    def test_trace_specialist_noop_when_disabled(self):
        with patch("src.telemetry.agent_metrics._ensure_tracer", return_value=False):
            with trace_specialist("research", "t1") as span:
                assert isinstance(span, _NoopSpan)

    def test_trace_memory_operation_noop_when_disabled(self):
        with patch("src.telemetry.agent_metrics._ensure_tracer", return_value=False):
            with trace_memory_operation("recall") as span:
                assert isinstance(span, _NoopSpan)

    def test_trace_approval_check_noop_when_disabled(self):
        with patch("src.telemetry.agent_metrics._ensure_tracer", return_value=False):
            with trace_approval_check("delegate.research") as span:
                assert isinstance(span, _NoopSpan)

    def test_noop_span_methods_safe(self):
        span = _NoopSpan()
        span.set_attribute("key", "value")
        span.set_status("OK")
        span.record_exception(ValueError("test"))


class TestResetAgentMetrics:
    """Verify reset clears all module-level state."""

    def test_reset_clears_meter_and_tracer(self):
        import src.telemetry.agent_metrics as mod

        mod._meter = MagicMock()
        mod._tracer = MagicMock()
        mod._agent_task_counter = MagicMock()

        reset_agent_metrics()

        assert mod._meter is None
        assert mod._tracer is None
        assert mod._agent_task_counter is None
