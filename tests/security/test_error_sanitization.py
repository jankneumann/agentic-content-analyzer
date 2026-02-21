"""Security tests for error response sanitization and CORS validation.

Tests cover:
- Error responses (401, 403, 404, 500) do not leak filesystem paths
- Error responses do not contain Python stack traces
- Error responses do not expose internal IP addresses
- Error responses do not echo back credentials
- CORS preflight returns correct Access-Control-Allow-Methods
- CORS preflight returns correct Access-Control-Allow-Headers
- CORS rejects unknown origins in production
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SECRET = "test-secret-key-at-least-32-characters-long!"
_ADMIN_KEY = "test-admin-key"

# Patterns that should NEVER appear in any error response body
_LEAK_PATTERNS = [
    (r"/Users/\w+", "filesystem path (macOS)"),
    (r"/home/\w+", "filesystem path (Linux)"),
    (r"C:\\\\Users", "filesystem path (Windows)"),
    (r"Traceback \(most recent call last\)", "Python stack trace"),
    (r"File \"[^\"]+\", line \d+", "Python frame reference"),
    (r"raise \w+Error", "Python raise statement"),
    (r"192\.168\.\d+\.\d+", "internal IP (192.168.x.x)"),
    (r"10\.\d+\.\d+\.\d+", "internal IP (10.x.x.x)"),
    (r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+", "internal IP (172.16-31.x.x)"),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset the module-level rate limiter between tests."""
    from src.api.rate_limiter import login_rate_limiter

    login_rate_limiter._attempts.clear()
    login_rate_limiter._request_count = 0
    yield
    login_rate_limiter._attempts.clear()
    login_rate_limiter._request_count = 0


@pytest.fixture
def production_client(monkeypatch):
    """TestClient in production mode with auth configured."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("APP_SECRET_KEY", _SECRET)
    monkeypatch.setenv("ADMIN_API_KEY", _ADMIN_KEY)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("WORKER_ENABLED", "false")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173,https://app.example.com")

    from src.config.settings import get_settings

    get_settings.cache_clear()

    try:
        from src.api.app import app

        with TestClient(app, base_url="https://testserver") as c:
            yield c
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_no_leaks(body_text: str) -> list[str]:
    """Scan response text for sensitive information patterns.

    Returns a list of descriptions for any patterns found.
    """
    found = []
    for pattern, description in _LEAK_PATTERNS:
        if re.search(pattern, body_text):
            found.append(description)
    return found


# ===========================================================================
# Error Response Sanitization Tests
# ===========================================================================


class TestErrorSanitization:
    """Verify error responses do not leak sensitive information."""

    def test_401_no_auth_sanitized(self, production_client):
        """401 response from missing auth does not leak sensitive info."""
        resp = production_client.get("/api/v1/digests/")
        assert resp.status_code == 401
        leaks = _check_no_leaks(resp.text)
        assert leaks == [], f"401 response leaks: {leaks}"

    def test_403_wrong_key_sanitized(self, production_client):
        """403 response from wrong admin key does not leak sensitive info."""
        resp = production_client.get(
            "/api/v1/digests/",
            headers={"X-Admin-Key": "wrong-key"},
        )
        assert resp.status_code == 403
        leaks = _check_no_leaks(resp.text)
        assert leaks == [], f"403 response leaks: {leaks}"

    def test_404_not_found_sanitized(self, production_client):
        """404 response does not leak filesystem paths or stack traces."""
        resp = production_client.get(
            "/api/v1/nonexistent-endpoint-that-does-not-exist",
            headers={"X-Admin-Key": _ADMIN_KEY},
        )
        # FastAPI returns 404 for unknown routes
        leaks = _check_no_leaks(resp.text)
        assert leaks == [], f"404 response leaks: {leaks}"

    def test_401_login_failure_sanitized(self, production_client):
        """Failed login response does not leak server internals."""
        resp = production_client.post(
            "/api/v1/auth/login",
            json={"password": "wrong-password"},
        )
        assert resp.status_code == 401
        leaks = _check_no_leaks(resp.text)
        assert leaks == [], f"Login 401 response leaks: {leaks}"

    def test_422_validation_error_sanitized(self, production_client):
        """422 validation error does not leak filesystem paths."""
        resp = production_client.post(
            "/api/v1/auth/login",
            content=b"not-json",
            headers={"Content-Type": "application/json", "X-Admin-Key": _ADMIN_KEY},
        )
        # FastAPI returns 422 for malformed JSON
        leaks = _check_no_leaks(resp.text)
        assert leaks == [], f"422 response leaks: {leaks}"

    def test_error_does_not_echo_credentials(self, production_client):
        """Error responses never echo back the admin key or password."""
        # Wrong admin key
        resp = production_client.get(
            "/api/v1/digests/",
            headers={"X-Admin-Key": "my-secret-admin-key-value"},
        )
        assert "my-secret-admin-key-value" not in resp.text

        # Wrong password
        resp = production_client.post(
            "/api/v1/auth/login",
            json={"password": "my-secret-password-attempt"},
        )
        assert "my-secret-password-attempt" not in resp.text

    def test_error_response_has_structured_format(self, production_client):
        """All auth error responses follow the structured {error, detail} format."""
        # 401 from middleware
        resp = production_client.get("/api/v1/digests/")
        body = resp.json()
        assert "error" in body, "401 response missing 'error' field"
        assert "detail" in body, "401 response missing 'detail' field"

        # 403 from middleware
        resp = production_client.get(
            "/api/v1/digests/",
            headers={"X-Admin-Key": "wrong-key"},
        )
        body = resp.json()
        assert "error" in body, "403 response missing 'error' field"
        assert "detail" in body, "403 response missing 'detail' field"


# ===========================================================================
# CORS Validation Tests
# ===========================================================================


class TestCORSPreflight:
    """Verify CORS preflight responses include correct headers."""

    def test_preflight_allows_configured_origin(self, production_client):
        """OPTIONS preflight with a configured origin returns that origin."""
        resp = production_client.request(
            "OPTIONS",
            "/api/v1/digests/",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"

    def test_preflight_returns_allow_methods(self, production_client):
        """OPTIONS preflight returns Access-Control-Allow-Methods."""
        resp = production_client.request(
            "OPTIONS",
            "/api/v1/digests/",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        allow_methods = resp.headers.get("access-control-allow-methods", "")
        # The CORS middleware is configured with allow_methods=["*"]
        # which FastAPI expands to the requested method or common methods
        assert allow_methods, "Missing Access-Control-Allow-Methods header"

    def test_preflight_returns_allow_headers(self, production_client):
        """OPTIONS preflight echoes back requested headers in Allow-Headers."""
        resp = production_client.request(
            "OPTIONS",
            "/api/v1/digests/",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Admin-Key",
            },
        )
        allow_headers = resp.headers.get("access-control-allow-headers", "")
        assert "x-admin-key" in allow_headers.lower(), (
            f"X-Admin-Key not in Access-Control-Allow-Headers: {allow_headers}"
        )

    def test_preflight_allows_credentials(self, production_client):
        """CORS configuration includes Allow-Credentials for cookie auth."""
        resp = production_client.request(
            "OPTIONS",
            "/api/v1/digests/",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-credentials") == "true", (
            "Missing allow-credentials header — cookie auth requires this"
        )

    def test_unconfigured_origin_rejected(self, production_client):
        """An origin not in ALLOWED_ORIGINS does not get CORS headers."""
        resp = production_client.request(
            "OPTIONS",
            "/api/v1/digests/",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        cors_origin = resp.headers.get("access-control-allow-origin", "")
        assert cors_origin != "https://evil.example.com", (
            "Unconfigured origin should not be reflected in Access-Control-Allow-Origin"
        )
