"""Tests for SecurityHeadersMiddleware."""

from __future__ import annotations

from unittest.mock import patch

from starlette.testclient import TestClient

from src.api.app import app


class TestSecurityHeaders:
    """Tests for security headers on normal responses."""

    def test_standard_security_headers_present(self):
        """All standard security headers should be present on a normal GET."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "0"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"

    def test_csp_report_only_header_present(self):
        """Content-Security-Policy-Report-Only header should be present."""
        client = TestClient(app)
        response = client.get("/health")
        csp = response.headers["Content-Security-Policy-Report-Only"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_hsts_not_present_in_development(self):
        """HSTS header should NOT be present in development environment."""
        client = TestClient(app)
        response = client.get("/health")
        assert "Strict-Transport-Security" not in response.headers

    @patch("src.api.app.settings")
    def test_hsts_present_in_production(self, mock_settings):
        """HSTS header should be present when environment is production."""
        mock_settings.environment = "production"
        mock_settings.get_allowed_origins_list.return_value = ["https://example.com"]
        mock_settings.worker_enabled = False
        mock_settings.enable_search_indexing = False

        # Build a minimal app with production environment to test HSTS
        from fastapi import FastAPI
        from starlette.responses import JSONResponse

        from src.api.middleware.security_headers import SecurityHeadersMiddleware

        test_app = FastAPI()
        test_app.add_middleware(SecurityHeadersMiddleware, environment="production")

        @test_app.get("/test")
        async def test_endpoint():
            return JSONResponse({"status": "ok"})

        client = TestClient(test_app)
        response = client.get("/test")
        assert (
            response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
        )

    def test_security_headers_on_error_response(self):
        """Security headers should appear on error (404) responses.

        Uses /health/ prefix which is auth-exempt but the sub-path doesn't exist.
        """
        client = TestClient(app)
        # /health is exempt from auth; a sub-path under it returns 404/405
        response = client.get("/health/nonexistent")
        assert response.status_code in (404, 405)
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "0"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
        assert "Content-Security-Policy-Report-Only" in response.headers

    def test_hsts_not_present_on_error_in_development(self):
        """HSTS should not appear on error responses in development."""
        client = TestClient(app)
        response = client.get("/health/nonexistent")
        assert "Strict-Transport-Security" not in response.headers
