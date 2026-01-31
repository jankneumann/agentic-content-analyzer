"""Tests for OTel metrics instrumentation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.telemetry.metrics import (
    record_ingestion,
    record_llm_request,
    reset_metrics,
)


class TestMetricsDisabled:
    """Tests when OTel is disabled."""

    def setup_method(self):
        reset_metrics()

    def test_record_llm_request_noop_when_disabled(self):
        """record_llm_request should be a no-op when OTel is disabled."""
        with patch("src.telemetry.metrics.settings", create=True) as mock_settings:
            mock_settings.otel_enabled = False
            # Should not raise
            record_llm_request(
                model="test-model",
                provider="anthropic",
                input_tokens=100,
                output_tokens=50,
                duration_ms=500.0,
            )

    def test_record_ingestion_noop_when_disabled(self):
        """record_ingestion should be a no-op when OTel is disabled."""
        with patch("src.telemetry.metrics.settings", create=True) as mock_settings:
            mock_settings.otel_enabled = False
            record_ingestion(source_type="gmail", count=5)


class TestMetricsEnabled:
    """Tests when OTel is enabled (mocked)."""

    def setup_method(self):
        reset_metrics()

    def test_record_llm_request_creates_metrics(self):
        """record_llm_request should record counter and histogram."""
        mock_meter = MagicMock()
        mock_counter = MagicMock()
        mock_histogram = MagicMock()
        mock_meter.create_counter.return_value = mock_counter
        mock_meter.create_histogram.return_value = mock_histogram

        mock_metrics = MagicMock()
        mock_metrics.get_meter.return_value = mock_meter

        with (
            patch("src.telemetry.metrics.settings", create=True) as mock_settings,
            patch.dict(
                "sys.modules",
                {"opentelemetry": MagicMock(), "opentelemetry.metrics": mock_metrics},
            ),
            patch("src.telemetry.metrics.metrics", mock_metrics, create=True),
        ):
            mock_settings.otel_enabled = True
            # Need to patch the import inside _ensure_meter
            import src.telemetry.metrics as metrics_mod

            # Reset and force re-init
            reset_metrics()

            # Manually init to avoid import issues in test
            metrics_mod._meter = mock_meter
            metrics_mod._llm_request_counter = mock_counter
            metrics_mod._llm_token_counter = mock_counter
            metrics_mod._llm_duration_histogram = mock_histogram
            metrics_mod._ingestion_counter = mock_counter

            record_llm_request(
                model="claude-sonnet",
                provider="anthropic",
                input_tokens=100,
                output_tokens=50,
                duration_ms=500.0,
            )

            # Should have called add on counters
            assert mock_counter.add.call_count >= 1
            assert mock_histogram.record.call_count == 1

    def test_record_ingestion_increments_counter(self):
        """record_ingestion should increment the ingestion counter."""
        mock_counter = MagicMock()

        import src.telemetry.metrics as metrics_mod

        reset_metrics()
        metrics_mod._meter = MagicMock()  # Non-None to skip init
        metrics_mod._ingestion_counter = mock_counter

        record_ingestion(source_type="gmail", count=3)

        mock_counter.add.assert_called_once_with(3, {"source_type": "gmail"})


class TestMetricsReset:
    """Tests for reset_metrics."""

    def test_reset_clears_all_state(self):
        """reset_metrics should clear all module-level state."""
        import src.telemetry.metrics as metrics_mod

        metrics_mod._meter = MagicMock()
        metrics_mod._llm_request_counter = MagicMock()

        reset_metrics()

        assert metrics_mod._meter is None
        assert metrics_mod._llm_request_counter is None
        assert metrics_mod._llm_token_counter is None
        assert metrics_mod._llm_duration_histogram is None
        assert metrics_mod._ingestion_counter is None
