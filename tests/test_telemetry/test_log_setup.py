"""Tests for OTel log bridge setup and lifecycle."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def otel_log_bridge_cleanup():
    """Ensure OTel log bridge is torn down and handlers removed after test."""
    yield
    from src.telemetry.log_setup import shutdown_otel_log_bridge

    shutdown_otel_log_bridge()

    # Belt-and-suspenders: remove any lingering OTel handlers
    root = logging.getLogger()
    try:
        from opentelemetry.sdk._logs import LoggingHandler

        root.handlers = [h for h in root.handlers if not isinstance(h, LoggingHandler)]
    except ImportError:
        pass


@pytest.fixture()
def _enabled_settings(mock_settings):
    """Configure mock_settings for an enabled log bridge."""
    mock_settings.otel_enabled = True
    mock_settings.otel_logs_enabled = True
    mock_settings.otel_exporter_otlp_endpoint = "http://localhost:4318"
    mock_settings.otel_exporter_otlp_headers = None
    mock_settings.otel_logs_export_level = "WARNING"
    return mock_settings


@pytest.fixture()
def mock_settings():
    """Patch settings in the log_setup module."""
    with patch("src.telemetry.log_setup.settings") as ms:
        yield ms


@pytest.fixture()
def test_resource():
    """Create a real OTel Resource for tests."""
    from opentelemetry.sdk.resources import Resource

    return Resource.create({"service.name": "test-service"})


class TestSetupOtelLogBridge:
    """Tests for setup_otel_log_bridge function."""

    def test_returns_none_when_otel_disabled(self, mock_settings):
        """Bridge should return None when otel_enabled=False."""
        mock_settings.otel_enabled = False

        from src.telemetry.log_setup import setup_otel_log_bridge

        result = setup_otel_log_bridge(resource=MagicMock())
        assert result is None

    def test_returns_none_when_logs_disabled(self, mock_settings):
        """Bridge should return None when otel_logs_enabled=False."""
        mock_settings.otel_enabled = True
        mock_settings.otel_logs_enabled = False

        from src.telemetry.log_setup import setup_otel_log_bridge

        result = setup_otel_log_bridge(resource=MagicMock())
        assert result is None

    def test_returns_none_when_no_endpoint(self, mock_settings):
        """Bridge should return None when no OTLP endpoint is configured."""
        mock_settings.otel_enabled = True
        mock_settings.otel_logs_enabled = True
        mock_settings.otel_exporter_otlp_endpoint = None

        from src.telemetry.log_setup import setup_otel_log_bridge

        result = setup_otel_log_bridge(resource=MagicMock())
        assert result is None

    @pytest.mark.usefixtures("otel_log_bridge_cleanup")
    def test_creates_logger_provider_when_enabled(self, _enabled_settings, test_resource):
        """LoggerProvider should be created with correct Resource when enabled."""
        from opentelemetry.sdk._logs import LoggerProvider

        from src.telemetry.log_setup import setup_otel_log_bridge

        result = setup_otel_log_bridge(resource=test_resource)

        assert result is not None
        assert isinstance(result, LoggerProvider)

    @pytest.mark.usefixtures("otel_log_bridge_cleanup")
    def test_logging_handler_attached_to_root(self, _enabled_settings, test_resource):
        """A LoggingHandler should be added to the root logger."""
        root_handlers_before = len(logging.getLogger().handlers)

        import src.telemetry.log_setup as log_setup_module
        from src.telemetry.log_setup import setup_otel_log_bridge

        setup_otel_log_bridge(resource=test_resource)

        root_handlers_after = len(logging.getLogger().handlers)
        assert root_handlers_after == root_handlers_before + 1

        from opentelemetry.sdk._logs import LoggingHandler

        new_handler = logging.getLogger().handlers[-1]
        assert isinstance(new_handler, LoggingHandler)

        # Verify module-level handler reference is set
        assert log_setup_module._otel_handler is new_handler

    @pytest.mark.usefixtures("otel_log_bridge_cleanup")
    def test_export_level_respected(self, mock_settings, test_resource):
        """LoggingHandler should use the configured export level."""
        mock_settings.otel_enabled = True
        mock_settings.otel_logs_enabled = True
        mock_settings.otel_exporter_otlp_endpoint = "http://localhost:4318"
        mock_settings.otel_exporter_otlp_headers = None
        mock_settings.otel_logs_export_level = "ERROR"

        from src.telemetry.log_setup import setup_otel_log_bridge

        setup_otel_log_bridge(resource=test_resource)

        from opentelemetry.sdk._logs import LoggingHandler

        otel_handlers = [h for h in logging.getLogger().handlers if isinstance(h, LoggingHandler)]
        assert len(otel_handlers) >= 1
        assert otel_handlers[-1].level == logging.ERROR

    @pytest.mark.usefixtures("otel_log_bridge_cleanup")
    def test_double_init_returns_existing_provider(self, _enabled_settings, test_resource):
        """Calling setup twice should return same provider without adding handlers."""
        from src.telemetry.log_setup import setup_otel_log_bridge

        first = setup_otel_log_bridge(resource=test_resource)
        handler_count_after_first = len(logging.getLogger().handlers)

        second = setup_otel_log_bridge(resource=test_resource)
        handler_count_after_second = len(logging.getLogger().handlers)

        assert first is second
        assert handler_count_after_first == handler_count_after_second


class TestShutdownOtelLogBridge:
    """Tests for shutdown_otel_log_bridge function."""

    @pytest.mark.usefixtures("otel_log_bridge_cleanup")
    def test_shutdown_cleans_up_provider_and_handler(self, _enabled_settings, test_resource):
        """Shutdown should set both _logger_provider and _otel_handler to None."""
        import src.telemetry.log_setup as log_setup_module
        from src.telemetry.log_setup import setup_otel_log_bridge, shutdown_otel_log_bridge

        setup_otel_log_bridge(resource=test_resource)
        assert log_setup_module._logger_provider is not None
        assert log_setup_module._otel_handler is not None

        shutdown_otel_log_bridge()
        assert log_setup_module._logger_provider is None
        assert log_setup_module._otel_handler is None

    @pytest.mark.usefixtures("otel_log_bridge_cleanup")
    def test_reset_telemetry_cleans_up_log_bridge(self, _enabled_settings, test_resource):
        """reset_telemetry() should also shut down the OTel log bridge."""
        import src.telemetry.log_setup as log_setup_module
        from src.telemetry import reset_telemetry
        from src.telemetry.log_setup import setup_otel_log_bridge

        setup_otel_log_bridge(resource=test_resource)
        assert log_setup_module._logger_provider is not None
        assert log_setup_module._otel_handler is not None

        reset_telemetry()
        assert log_setup_module._logger_provider is None
        assert log_setup_module._otel_handler is None

    def test_shutdown_is_idempotent(self):
        """Shutdown should not raise when called without setup."""
        from src.telemetry.log_setup import shutdown_otel_log_bridge

        # Should not raise
        shutdown_otel_log_bridge()
        shutdown_otel_log_bridge()

    @pytest.mark.usefixtures("otel_log_bridge_cleanup")
    def test_shutdown_removes_handler_from_root(self, _enabled_settings, test_resource):
        """Shutdown should remove the LoggingHandler from root logger."""
        from opentelemetry.sdk._logs import LoggingHandler

        from src.telemetry.log_setup import setup_otel_log_bridge, shutdown_otel_log_bridge

        handlers_before = len(logging.getLogger().handlers)

        setup_otel_log_bridge(resource=test_resource)
        assert any(isinstance(h, LoggingHandler) for h in logging.getLogger().handlers)

        shutdown_otel_log_bridge()
        assert not any(isinstance(h, LoggingHandler) for h in logging.getLogger().handlers)
        assert len(logging.getLogger().handlers) == handlers_before
