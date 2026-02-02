"""Tests for the OTLP proxy endpoint (/api/v1/otel/v1/traces).

Tests validate:
- Proxy returns 204 when OTLP endpoint is configured
- Proxy returns 404 when otel_enabled=false
- Proxy rejects oversized body (>1MB)
- Proxy validates content-type header
- Proxy forwards authentication headers to upstream
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture
def proxy_client() -> TestClient:
    """Create a TestClient without database fixtures (proxy doesn't need DB)."""
    return TestClient(app)


class TestOtelProxyDisabled:
    """Tests when OTel is disabled (default)."""

    def test_returns_404_when_otel_disabled(self, proxy_client: TestClient):
        """Proxy returns 404 when otel_enabled=false."""
        with patch("src.api.otel_proxy_routes.settings") as mock_settings:
            mock_settings.otel_enabled = False
            response = proxy_client.post(
                "/api/v1/otel/v1/traces",
                content=b'{"resourceSpans": []}',
                headers={"content-type": "application/json"},
            )
        assert response.status_code == 404
        assert "not enabled" in response.json()["detail"]


class TestOtelProxyEnabled:
    """Tests when OTel is enabled with a configured endpoint."""

    @pytest.fixture(autouse=True)
    def _enable_otel(self):
        """Enable OTel for all tests in this class."""
        with patch("src.api.otel_proxy_routes.settings") as mock_settings:
            mock_settings.otel_enabled = True
            mock_settings.otel_exporter_otlp_endpoint = "https://collector.example.com"
            mock_settings.otel_exporter_otlp_headers = "Authorization=Bearer test-key"
            self.mock_settings = mock_settings
            yield

    def test_returns_204_on_successful_forward(self, proxy_client: TestClient):
        """Proxy returns 204 when upstream accepts the traces."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = ""

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "src.api.otel_proxy_routes.httpx.AsyncClient", return_value=mock_client_instance
        ):
            response = proxy_client.post(
                "/api/v1/otel/v1/traces",
                content=b'{"resourceSpans": []}',
                headers={"content-type": "application/json"},
            )

        assert response.status_code == 204

        # Verify the upstream request included auth headers
        call_kwargs = mock_client_instance.post.call_args
        upstream_headers = call_kwargs.kwargs.get("headers", {})
        assert upstream_headers["Authorization"] == "Bearer test-key"

    def test_forwards_to_correct_upstream_url(self, proxy_client: TestClient):
        """Proxy builds correct upstream URL from settings."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = ""

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "src.api.otel_proxy_routes.httpx.AsyncClient", return_value=mock_client_instance
        ):
            proxy_client.post(
                "/api/v1/otel/v1/traces",
                content=b'{"resourceSpans": []}',
                headers={"content-type": "application/json"},
            )

        call_args = mock_client_instance.post.call_args
        assert call_args.args[0] == "https://collector.example.com/v1/traces"

    def test_rejects_invalid_content_type(self, proxy_client: TestClient):
        """Proxy returns 415 for unsupported content types."""
        response = proxy_client.post(
            "/api/v1/otel/v1/traces",
            content=b"some text data",
            headers={"content-type": "text/plain"},
        )
        assert response.status_code == 415
        assert "Unsupported content type" in response.json()["detail"]

    def test_accepts_protobuf_content_type(self, proxy_client: TestClient):
        """Proxy accepts application/x-protobuf content type."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = ""

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "src.api.otel_proxy_routes.httpx.AsyncClient", return_value=mock_client_instance
        ):
            response = proxy_client.post(
                "/api/v1/otel/v1/traces",
                content=b"\x0a\x00",
                headers={"content-type": "application/x-protobuf"},
            )

        assert response.status_code == 204

    def test_rejects_oversized_body(self, proxy_client: TestClient):
        """Proxy returns 413 for payloads exceeding 1MB."""
        oversized_body = b"x" * (1024 * 1024 + 1)
        response = proxy_client.post(
            "/api/v1/otel/v1/traces",
            content=oversized_body,
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 413
        assert "too large" in response.json()["detail"].lower()

    def test_returns_502_on_upstream_error(self, proxy_client: TestClient):
        """Proxy returns 502 when upstream collector returns an error."""
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "src.api.otel_proxy_routes.httpx.AsyncClient", return_value=mock_client_instance
        ):
            response = proxy_client.post(
                "/api/v1/otel/v1/traces",
                content=b'{"resourceSpans": []}',
                headers={"content-type": "application/json"},
            )

        assert response.status_code == 502

    def test_returns_502_on_timeout(self, proxy_client: TestClient):
        """Proxy returns 502 when upstream request times out."""
        import httpx

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "src.api.otel_proxy_routes.httpx.AsyncClient", return_value=mock_client_instance
        ):
            response = proxy_client.post(
                "/api/v1/otel/v1/traces",
                content=b'{"resourceSpans": []}',
                headers={"content-type": "application/json"},
            )

        assert response.status_code == 502
        assert "timed out" in response.json()["detail"].lower()

    def test_returns_503_when_endpoint_not_configured(self, proxy_client: TestClient):
        """Proxy returns 503 when otel_enabled but no endpoint configured."""
        self.mock_settings.otel_exporter_otlp_endpoint = None

        response = proxy_client.post(
            "/api/v1/otel/v1/traces",
            content=b'{"resourceSpans": []}',
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]
