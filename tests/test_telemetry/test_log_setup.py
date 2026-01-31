"""Tests for OTel log bridge setup and lifecycle."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch


class TestSetupOtelLogBridge:
    """Tests for setup_otel_log_bridge function."""

    @patch("src.telemetry.log_setup.settings")
    def test_returns_none_when_otel_disabled(self, mock_settings):
        """Bridge should return None when otel_enabled=False."""
        mock_settings.otel_enabled = False

        from src.telemetry.log_setup import setup_otel_log_bridge

        result = setup_otel_log_bridge(resource=MagicMock())
        assert result is None

    @patch("src.telemetry.log_setup.settings")
    def test_returns_none_when_logs_disabled(self, mock_settings):
        """Bridge should return None when otel_logs_enabled=False."""
        mock_settings.otel_enabled = True
        mock_settings.otel_logs_enabled = False

        from src.telemetry.log_setup import setup_otel_log_bridge

        result = setup_otel_log_bridge(resource=MagicMock())
        assert result is None

    @patch("src.telemetry.log_setup.settings")
    def test_returns_none_when_no_endpoint(self, mock_settings):
        """Bridge should return None when no OTLP endpoint is configured."""
        mock_settings.otel_enabled = True
        mock_settings.otel_logs_enabled = True
        mock_settings.otel_exporter_otlp_endpoint = None

        from src.telemetry.log_setup import setup_otel_log_bridge

        result = setup_otel_log_bridge(resource=MagicMock())
        assert result is None

    @patch("src.telemetry.log_setup.settings")
    def test_creates_logger_provider_when_enabled(self, mock_settings):
        """LoggerProvider should be created with correct Resource when enabled."""
        mock_settings.otel_enabled = True
        mock_settings.otel_logs_enabled = True
        mock_settings.otel_exporter_otlp_endpoint = "http://localhost:4318"
        mock_settings.otel_exporter_otlp_headers = None
        mock_settings.otel_logs_export_level = "WARNING"

        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": "test-service"})

        from src.telemetry.log_setup import setup_otel_log_bridge

        result = setup_otel_log_bridge(resource=resource)

        try:
            assert result is not None
            # Verify it's a LoggerProvider
            from opentelemetry.sdk._logs import LoggerProvider

            assert isinstance(result, LoggerProvider)
        finally:
            # Clean up: shut down and remove the OTel handler from root logger
            from src.telemetry.log_setup import shutdown_otel_log_bridge

            shutdown_otel_log_bridge()
            _remove_otel_handlers()

    @patch("src.telemetry.log_setup.settings")
    def test_logging_handler_attached_to_root(self, mock_settings):
        """A LoggingHandler should be added to the root logger."""
        mock_settings.otel_enabled = True
        mock_settings.otel_logs_enabled = True
        mock_settings.otel_exporter_otlp_endpoint = "http://localhost:4318"
        mock_settings.otel_exporter_otlp_headers = None
        mock_settings.otel_logs_export_level = "WARNING"

        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": "test-service"})

        root_handlers_before = len(logging.getLogger().handlers)

        from src.telemetry.log_setup import setup_otel_log_bridge

        setup_otel_log_bridge(resource=resource)

        try:
            root_handlers_after = len(logging.getLogger().handlers)
            assert root_handlers_after == root_handlers_before + 1

            # Verify the new handler is a LoggingHandler
            from opentelemetry.sdk._logs import LoggingHandler

            new_handler = logging.getLogger().handlers[-1]
            assert isinstance(new_handler, LoggingHandler)
        finally:
            from src.telemetry.log_setup import shutdown_otel_log_bridge

            shutdown_otel_log_bridge()
            _remove_otel_handlers()

    @patch("src.telemetry.log_setup.settings")
    def test_export_level_respected(self, mock_settings):
        """LoggingHandler should use the configured export level."""
        mock_settings.otel_enabled = True
        mock_settings.otel_logs_enabled = True
        mock_settings.otel_exporter_otlp_endpoint = "http://localhost:4318"
        mock_settings.otel_exporter_otlp_headers = None
        mock_settings.otel_logs_export_level = "ERROR"

        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": "test-service"})

        from src.telemetry.log_setup import setup_otel_log_bridge

        setup_otel_log_bridge(resource=resource)

        try:
            from opentelemetry.sdk._logs import LoggingHandler

            otel_handlers = [
                h for h in logging.getLogger().handlers if isinstance(h, LoggingHandler)
            ]
            assert len(otel_handlers) >= 1
            assert otel_handlers[-1].level == logging.ERROR
        finally:
            from src.telemetry.log_setup import shutdown_otel_log_bridge

            shutdown_otel_log_bridge()
            _remove_otel_handlers()


class TestShutdownOtelLogBridge:
    """Tests for shutdown_otel_log_bridge function."""

    @patch("src.telemetry.log_setup.settings")
    def test_shutdown_cleans_up_provider(self, mock_settings):
        """Shutdown should set _logger_provider to None."""
        mock_settings.otel_enabled = True
        mock_settings.otel_logs_enabled = True
        mock_settings.otel_exporter_otlp_endpoint = "http://localhost:4318"
        mock_settings.otel_exporter_otlp_headers = None
        mock_settings.otel_logs_export_level = "WARNING"

        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": "test-service"})

        import src.telemetry.log_setup as log_setup_module
        from src.telemetry.log_setup import setup_otel_log_bridge

        setup_otel_log_bridge(resource=resource)
        assert log_setup_module._logger_provider is not None

        from src.telemetry.log_setup import shutdown_otel_log_bridge

        shutdown_otel_log_bridge()
        assert log_setup_module._logger_provider is None
        _remove_otel_handlers()

    def test_shutdown_is_idempotent(self):
        """Shutdown should not raise when called without setup."""
        from src.telemetry.log_setup import shutdown_otel_log_bridge

        # Should not raise
        shutdown_otel_log_bridge()
        shutdown_otel_log_bridge()


def _remove_otel_handlers() -> None:
    """Remove any OTel LoggingHandlers from the root logger (test cleanup)."""
    root = logging.getLogger()
    try:
        from opentelemetry.sdk._logs import LoggingHandler

        root.handlers = [h for h in root.handlers if not isinstance(h, LoggingHandler)]
    except ImportError:
        pass
