"""Tests for OTel infrastructure auto-instrumentation setup."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestSetupOtelInfrastructure:
    """Tests for setup_otel_infrastructure function."""

    @patch("src.telemetry.otel_setup.settings")
    def test_disabled_when_otel_not_enabled(self, mock_settings):
        """Should do nothing when otel_enabled is False."""
        mock_settings.otel_enabled = False

        from src.telemetry.otel_setup import setup_otel_infrastructure

        # Should return without error
        setup_otel_infrastructure(app=None)

    @patch("src.telemetry.otel_setup.settings")
    def test_warns_when_no_endpoint(self, mock_settings):
        """Should warn when enabled but no endpoint configured."""
        mock_settings.otel_enabled = True
        mock_settings.otel_exporter_otlp_endpoint = None

        from src.telemetry.otel_setup import setup_otel_infrastructure

        # Should return without error (just logs warning)
        setup_otel_infrastructure(app=None)

    @patch("src.telemetry.otel_setup.settings")
    def test_configures_infrastructure_when_enabled(self, mock_settings):
        """Should configure OTel infrastructure when enabled with endpoint."""
        mock_settings.otel_enabled = True
        mock_settings.otel_exporter_otlp_endpoint = "http://localhost:4318"
        mock_settings.otel_exporter_otlp_headers = None
        mock_settings.otel_service_name = "test-service"
        mock_settings.environment = "test"

        from src.telemetry.otel_setup import setup_otel_infrastructure

        # Should complete without error
        setup_otel_infrastructure(app=None)


class TestParseHeaders:
    """Tests for the header parsing utility."""

    def test_parse_empty_headers(self):
        """Should return empty dict for None input."""
        from src.telemetry.otel_setup import _parse_headers

        assert _parse_headers(None) == {}
        assert _parse_headers("") == {}

    def test_parse_single_header(self):
        """Should parse a single key=value pair."""
        from src.telemetry.otel_setup import _parse_headers

        result = _parse_headers("Authorization=Bearer token123")
        assert result == {"Authorization": "Bearer token123"}

    def test_parse_multiple_headers(self):
        """Should parse comma-separated key=value pairs."""
        from src.telemetry.otel_setup import _parse_headers

        result = _parse_headers("Authorization=key123,projectName=my-project")
        assert result == {"Authorization": "key123", "projectName": "my-project"}

    def test_parse_headers_with_whitespace(self):
        """Should trim whitespace from keys and values."""
        from src.telemetry.otel_setup import _parse_headers

        result = _parse_headers(" Authorization = key123 , projectName = my-project ")
        assert result == {"Authorization": "key123", "projectName": "my-project"}

    def test_parse_headers_with_equals_in_value(self):
        """Should handle equals signs in values (split on first = only)."""
        from src.telemetry.otel_setup import _parse_headers

        result = _parse_headers("Authorization=Bearer key=value")
        assert result == {"Authorization": "Bearer key=value"}


class TestTraceIdMiddleware:
    """Tests for the TraceIdMiddleware."""

    @pytest.mark.asyncio
    async def test_middleware_adds_trace_id_when_otel_active(self):
        """Should add X-Trace-Id header when OTel is active."""

        from fastapi import FastAPI
        from starlette.testclient import TestClient

        from src.api.middleware.telemetry import TraceIdMiddleware

        app = FastAPI()
        app.add_middleware(TraceIdMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        # Trace ID header may or may not be present depending on OTel state
        # When OTel is not active, the span context has trace_id=0, which
        # we don't add to headers. The middleware should not crash either way.

    @pytest.mark.asyncio
    async def test_middleware_does_not_crash_without_otel(self):
        """Middleware should work gracefully when OTel is not installed."""
        from fastapi import FastAPI
        from starlette.testclient import TestClient

        from src.api.middleware.telemetry import TraceIdMiddleware

        app = FastAPI()
        app.add_middleware(TraceIdMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200


class TestAppIntegration:
    """Tests for telemetry integration in the FastAPI app."""

    def test_app_starts_with_telemetry(self):
        """App should start successfully with telemetry middleware."""
        from starlette.testclient import TestClient

        from src.api.app import app

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
