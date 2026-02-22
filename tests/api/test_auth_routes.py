"""API tests for authentication endpoints (login, logout, session).

Tests cover:
- Login with correct password -> 200 + session cookie
- Login with wrong password -> 401
- Login with empty password -> 401
- Login when APP_SECRET_KEY not configured -> 500
- Logout -> cookie cleared
- Session check with valid cookie -> {"authenticated": true}
- Session check without cookie -> {"authenticated": false}
- Session check with expired JWT -> {"authenticated": false}
- SameSite cookie attribute based on auth_cookie_cross_origin setting
- Rate limiting after repeated failures
- Logging of successful and failed login attempts
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from src.api.auth_routes import (
    _COOKIE_NAME,
    _JWT_ALGORITHM,
    _JWT_ISSUER,
    _get_jwt_signing_key,
)

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
    """TestClient in production mode with APP_SECRET_KEY configured.

    In development mode the auth middleware bypasses all checks and
    the /session endpoint always returns authenticated=True, so we
    must set ENVIRONMENT=production to exercise the real auth code paths.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-at-least-32-characters-long!")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("WORKER_ENABLED", "false")

    from src.config.settings import get_settings

    get_settings.cache_clear()

    try:
        from src.api.app import app

        # Use HTTPS base URL so Secure cookies are sent back by httpx
        with TestClient(app, base_url="https://testserver") as c:
            yield c
    finally:
        get_settings.cache_clear()


@pytest.fixture
def production_client_no_secret(monkeypatch):
    """TestClient in production mode WITHOUT APP_SECRET_KEY."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("WORKER_ENABLED", "false")
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)

    from src.config.settings import get_settings

    get_settings.cache_clear()

    try:
        from src.api.app import app

        with TestClient(app, base_url="https://testserver") as c:
            yield c
    finally:
        get_settings.cache_clear()


@pytest.fixture
def dev_client(monkeypatch):
    """TestClient in development mode (auth bypassed)."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("WORKER_ENABLED", "false")

    from src.config.settings import get_settings

    get_settings.cache_clear()

    try:
        from src.api.app import app

        with TestClient(app) as c:
            yield c
    finally:
        get_settings.cache_clear()


@pytest.fixture
def cross_origin_client(monkeypatch):
    """TestClient with auth_cookie_cross_origin=True in production mode."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-at-least-32-characters-long!")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("AUTH_COOKIE_CROSS_ORIGIN", "true")
    monkeypatch.setenv("WORKER_ENABLED", "false")

    from src.config.settings import get_settings

    get_settings.cache_clear()

    try:
        from src.api.app import app

        # Use HTTPS base URL so Secure cookies are sent back by httpx
        with TestClient(app, base_url="https://testserver") as c:
            yield c
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

_SECRET = "test-secret-key-at-least-32-characters-long!"


def _login(client: TestClient, password: str = _SECRET) -> object:
    """POST /api/v1/auth/login with the given password."""
    return client.post("/api/v1/auth/login", json={"password": password})


def _make_expired_jwt(app_secret_key: str) -> str:
    """Create a JWT that expired 1 hour ago."""
    now = datetime.now(UTC)
    payload = {
        "iss": _JWT_ISSUER,
        "iat": int((now - timedelta(days=8)).timestamp()),
        "exp": int((now - timedelta(hours=1)).timestamp()),
    }
    signing_key = _get_jwt_signing_key(app_secret_key)
    return jwt.encode(payload, signing_key, algorithm=_JWT_ALGORITHM)


# ===========================================================================
# Login Tests
# ===========================================================================


class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    def test_login_correct_password(self, production_client):
        """Correct password returns 200 and sets session cookie."""
        resp = _login(production_client)
        assert resp.status_code == 200
        assert resp.json() == {"authenticated": True}

        # Session cookie should be present in the response
        assert _COOKIE_NAME in resp.cookies

    def test_login_wrong_password(self, production_client):
        """Wrong password returns 401 with error payload."""
        resp = _login(production_client, password="wrong-password")
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"] == "Invalid credentials"
        assert "incorrect" in body["detail"].lower()

    def test_login_empty_password(self, production_client):
        """Empty password string returns 401."""
        resp = _login(production_client, password="")
        assert resp.status_code == 401

    def test_login_no_app_secret_key(self, production_client_no_secret):
        """Login when APP_SECRET_KEY is not set returns 500."""
        resp = _login(production_client_no_secret, password="anything")
        assert resp.status_code == 500
        body = resp.json()
        assert (
            "not configured" in body["error"].lower() or "not configured" in body["detail"].lower()
        )

    def test_login_sets_httponly_cookie(self, production_client):
        """Session cookie has HttpOnly flag set."""
        resp = _login(production_client)
        assert resp.status_code == 200
        # TestClient stores cookies; check the Set-Cookie header directly
        set_cookie = resp.headers.get("set-cookie", "")
        assert "httponly" in set_cookie.lower()

    def test_login_cookie_path_is_root(self, production_client):
        """Session cookie path is /."""
        resp = _login(production_client)
        set_cookie = resp.headers.get("set-cookie", "")
        assert "path=/" in set_cookie.lower()

    def test_login_success_log(self, production_client, caplog):
        """Successful login logs an INFO message."""
        with caplog.at_level(logging.INFO, logger="src.api.auth_routes"):
            _login(production_client)
        assert any("successful login" in rec.message.lower() for rec in caplog.records)

    def test_login_failure_log(self, production_client, caplog):
        """Failed login logs a WARNING message."""
        with caplog.at_level(logging.WARNING, logger="src.api.auth_routes"):
            _login(production_client, password="bad")
        assert any("failed login" in rec.message.lower() for rec in caplog.records)

    def test_login_rate_limited_after_5_failures(self, production_client):
        """After 5 failed attempts, the 6th is blocked with 429."""
        for _ in range(5):
            resp = _login(production_client, password="bad")
            assert resp.status_code == 401

        # 6th attempt should be rate-limited
        resp = _login(production_client, password="bad")
        assert resp.status_code == 429
        assert "retry-after" in resp.headers

    def test_login_rate_limited_even_with_correct_password(self, production_client):
        """Once rate-limited, even the correct password is blocked."""
        for _ in range(5):
            _login(production_client, password="bad")

        resp = _login(production_client)
        assert resp.status_code == 429


# ===========================================================================
# Logout Tests
# ===========================================================================


class TestLogout:
    """Tests for POST /api/v1/auth/logout."""

    def test_logout_clears_cookie(self, production_client):
        """Logout response clears the session cookie."""
        resp = production_client.post("/api/v1/auth/logout")
        assert resp.status_code == 200
        assert resp.json() == {"authenticated": False}

        # Check Set-Cookie header for cookie deletion (max-age=0 or expires in past)
        set_cookie = resp.headers.get("set-cookie", "")
        # FastAPI delete_cookie sets max-age=0
        assert _COOKIE_NAME in set_cookie
        assert "max-age=0" in set_cookie.lower() or "expires=" in set_cookie.lower()

    def test_logout_works_without_prior_login(self, production_client):
        """Logout is idempotent -- works even if not logged in."""
        resp = production_client.post("/api/v1/auth/logout")
        assert resp.status_code == 200


# ===========================================================================
# Session Check Tests
# ===========================================================================


class TestSessionCheck:
    """Tests for GET /api/v1/auth/session."""

    def test_session_authenticated_with_valid_cookie(self, production_client):
        """After login, /session returns authenticated=true."""
        login_resp = _login(production_client)
        assert login_resp.status_code == 200

        # The TestClient automatically carries cookies between requests
        resp = production_client.get("/api/v1/auth/session")
        assert resp.status_code == 200
        assert resp.json() == {"authenticated": True}

    def test_session_not_authenticated_without_cookie(self, production_client):
        """Without a session cookie, /session returns authenticated=false."""
        # Don't login first -- no cookie
        resp = production_client.get("/api/v1/auth/session")
        assert resp.status_code == 200
        assert resp.json() == {"authenticated": False}

    def test_session_with_expired_jwt(self, production_client):
        """An expired JWT cookie returns authenticated=false."""
        expired_token = _make_expired_jwt(_SECRET)
        production_client.cookies.set(_COOKIE_NAME, expired_token)

        resp = production_client.get("/api/v1/auth/session")
        assert resp.status_code == 200
        assert resp.json() == {"authenticated": False}

    def test_session_without_app_secret_key(self, production_client_no_secret):
        """Without APP_SECRET_KEY configured, session is not authenticated."""
        resp = production_client_no_secret.get("/api/v1/auth/session")
        assert resp.status_code == 200
        assert resp.json() == {"authenticated": False}

    def test_session_dev_mode_always_authenticated(self, dev_client):
        """In development mode, /session always returns authenticated=true."""
        resp = dev_client.get("/api/v1/auth/session")
        assert resp.status_code == 200
        assert resp.json() == {"authenticated": True}


# ===========================================================================
# Cookie Attribute Tests
# ===========================================================================


class TestCookieAttributes:
    """Tests for cookie security flags."""

    def test_samesite_lax_by_default(self, production_client):
        """Default SameSite is Lax (auth_cookie_cross_origin=False)."""
        resp = _login(production_client)
        set_cookie = resp.headers.get("set-cookie", "")
        assert "samesite=lax" in set_cookie.lower()

    def test_samesite_none_when_cross_origin(self, cross_origin_client):
        """SameSite is None when auth_cookie_cross_origin=True."""
        resp = _login(cross_origin_client)
        set_cookie = resp.headers.get("set-cookie", "")
        assert "samesite=none" in set_cookie.lower()

    def test_secure_flag_in_production(self, production_client):
        """Secure flag is set in production mode."""
        resp = _login(production_client)
        set_cookie = resp.headers.get("set-cookie", "")
        assert "secure" in set_cookie.lower()

    def test_no_secure_flag_in_dev(self, dev_client, monkeypatch):
        """Secure flag is NOT set in development mode."""
        monkeypatch.setenv("APP_SECRET_KEY", _SECRET)
        from src.config.settings import get_settings

        get_settings.cache_clear()

        resp = _login(dev_client)
        # In dev mode, login may still succeed (dev bypass via middleware
        # doesn't apply to the login endpoint itself -- it checks password).
        # But the cookie should not have Secure flag in dev.
        set_cookie = resp.headers.get("set-cookie", "")
        if resp.status_code == 200:
            # Secure should not appear OR the cookie behavior is dev-safe
            # Note: set_cookie.lower() splitting is tricky. The key check is
            # that "secure" does NOT appear as a standalone attribute.
            # In dev mode the code sets secure=False.
            parts = [p.strip().lower() for p in set_cookie.split(";")]
            assert "secure" not in parts
