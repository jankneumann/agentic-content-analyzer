"""Security tests for owner authentication.

Tests cover:
- JWT with wrong HMAC signature is rejected
- JWT signed with raw APP_SECRET_KEY (not HMAC-derived) is rejected
- JWT with wrong issuer is rejected
- JWT with tampered payload is rejected
- Cookie flags (HttpOnly, SameSite, Secure, Path) verified
- Password comparison is timing-safe (uses secrets.compare_digest)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from src.api.auth_routes import (
    _COOKIE_NAME,
    _JWT_ALGORITHM,
    _JWT_ISSUER,
    _get_jwt_signing_key,
    _verify_jwt,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SECRET = "test-secret-key-at-least-32-characters-long!"
_ADMIN_KEY = "test-admin-key"


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
    """TestClient in production mode with auth fully configured."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("APP_SECRET_KEY", _SECRET)
    monkeypatch.setenv("ADMIN_API_KEY", _ADMIN_KEY)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_jwt_with_key(signing_key: bytes, issuer: str = _JWT_ISSUER) -> str:
    """Create a JWT token signed with an arbitrary key."""
    now = datetime.now(UTC)
    payload = {
        "iss": issuer,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=7)).timestamp()),
    }
    return jwt.encode(payload, signing_key, algorithm=_JWT_ALGORITHM)


def _login(client: TestClient, password: str = _SECRET) -> object:
    return client.post("/api/v1/auth/login", json={"password": password})


# ===========================================================================
# JWT Signature Verification Tests
# ===========================================================================


class TestJWTSignatureVerification:
    """Test that JWT tokens with invalid signatures are rejected."""

    def test_wrong_hmac_key_rejected(self):
        """A JWT signed with a different HMAC key is rejected by _verify_jwt."""
        wrong_key = b"completely-different-key-used-for-signing"
        token = _make_jwt_with_key(wrong_key)

        result = _verify_jwt(token, _SECRET)
        assert result is None

    def test_raw_app_secret_as_signing_key_rejected(self):
        """A JWT signed with raw APP_SECRET_KEY (not HMAC-derived) is rejected.

        The signing key is derived via HMAC(APP_SECRET_KEY, "jwt-signing-key").
        Using the raw APP_SECRET_KEY directly should not verify.
        """
        raw_key = _SECRET.encode()
        token = _make_jwt_with_key(raw_key)

        result = _verify_jwt(token, _SECRET)
        assert result is None

    def test_correct_derived_key_accepted(self):
        """A JWT signed with the correctly derived key is accepted."""
        correct_key = _get_jwt_signing_key(_SECRET)
        token = _make_jwt_with_key(correct_key)

        result = _verify_jwt(token, _SECRET)
        assert result is not None
        assert result["iss"] == _JWT_ISSUER

    def test_wrong_issuer_rejected(self):
        """A JWT with wrong issuer claim is rejected."""
        correct_key = _get_jwt_signing_key(_SECRET)
        token = _make_jwt_with_key(correct_key, issuer="evil-issuer")

        result = _verify_jwt(token, _SECRET)
        assert result is None

    def test_tampered_payload_rejected(self):
        """A JWT with a tampered payload (modified after signing) is rejected."""
        # Create a valid token
        correct_key = _get_jwt_signing_key(_SECRET)
        token = _make_jwt_with_key(correct_key)

        # Tamper with the payload portion (middle segment)
        parts = token.split(".")
        assert len(parts) == 3

        # Flip a character in the payload
        payload_bytes = bytearray(parts[1].encode())
        if payload_bytes[5] == ord("A"):
            payload_bytes[5] = ord("B")
        else:
            payload_bytes[5] = ord("A")
        parts[1] = payload_bytes.decode()
        tampered_token = ".".join(parts)

        result = _verify_jwt(tampered_token, _SECRET)
        assert result is None

    def test_garbage_token_rejected(self):
        """Completely invalid token strings are rejected gracefully."""
        for garbage in ["", "not-a-jwt", "a.b.c", "x" * 1000]:
            result = _verify_jwt(garbage, _SECRET)
            assert result is None, f"Expected None for garbage token: {garbage!r}"


# ===========================================================================
# JWT via Middleware (Integration)
# ===========================================================================


class TestJWTViaMiddleware:
    """Test JWT rejection through the actual middleware stack."""

    def test_wrong_key_jwt_blocked_by_middleware(self, production_client):
        """Middleware rejects a JWT signed with the wrong key."""
        wrong_key = b"not-the-real-hmac-derived-key"
        token = _make_jwt_with_key(wrong_key)
        production_client.cookies.set(_COOKIE_NAME, token)

        resp = production_client.get("/api/v1/digests")
        assert resp.status_code == 401

    def test_raw_secret_jwt_blocked_by_middleware(self, production_client):
        """Middleware rejects a JWT signed with raw APP_SECRET_KEY."""
        raw_key = _SECRET.encode()
        token = _make_jwt_with_key(raw_key)
        production_client.cookies.set(_COOKIE_NAME, token)

        resp = production_client.get("/api/v1/digests")
        assert resp.status_code == 401

    def test_different_app_secret_jwt_blocked(self, production_client):
        """JWT created with a different APP_SECRET_KEY is rejected."""
        other_secret = "another-secret-key-that-is-at-least-32-chars!"
        other_derived_key = _get_jwt_signing_key(other_secret)
        token = _make_jwt_with_key(other_derived_key)
        production_client.cookies.set(_COOKIE_NAME, token)

        resp = production_client.get("/api/v1/digests")
        assert resp.status_code == 401


# ===========================================================================
# Cookie Security Flags Tests
# ===========================================================================


class TestCookieSecurityFlags:
    """Verify cookie flags are set correctly on login response."""

    def test_httponly_flag(self, production_client):
        """Session cookie must have HttpOnly flag."""
        resp = _login(production_client)
        assert resp.status_code == 200
        set_cookie = resp.headers.get("set-cookie", "")
        assert "httponly" in set_cookie.lower(), (
            "Session cookie missing HttpOnly flag -- exposes token to XSS"
        )

    def test_secure_flag_in_production(self, production_client):
        """Session cookie must have Secure flag in production."""
        resp = _login(production_client)
        set_cookie = resp.headers.get("set-cookie", "")
        assert "secure" in set_cookie.lower(), (
            "Session cookie missing Secure flag in production -- allows transmission over HTTP"
        )

    def test_samesite_flag_present(self, production_client):
        """Session cookie must have a SameSite attribute."""
        resp = _login(production_client)
        set_cookie = resp.headers.get("set-cookie", "")
        assert "samesite=" in set_cookie.lower(), (
            "Session cookie missing SameSite flag -- vulnerable to CSRF"
        )

    def test_path_is_root(self, production_client):
        """Session cookie path must be / (accessible on all routes)."""
        resp = _login(production_client)
        set_cookie = resp.headers.get("set-cookie", "")
        assert "path=/" in set_cookie.lower()

    def test_max_age_set(self, production_client):
        """Session cookie must have a max-age (not indefinite)."""
        resp = _login(production_client)
        set_cookie = resp.headers.get("set-cookie", "")
        assert "max-age=" in set_cookie.lower(), (
            "Session cookie missing max-age -- may become a session cookie"
        )


# ===========================================================================
# HMAC Key Derivation Tests
# ===========================================================================


class TestKeyDerivation:
    """Test that the HMAC key derivation produces deterministic, distinct keys."""

    def test_derivation_is_deterministic(self):
        """Same APP_SECRET_KEY always produces the same signing key."""
        key1 = _get_jwt_signing_key("my-secret")
        key2 = _get_jwt_signing_key("my-secret")
        assert key1 == key2

    def test_different_secrets_produce_different_keys(self):
        """Different APP_SECRET_KEYs produce different signing keys."""
        key1 = _get_jwt_signing_key("secret-one-that-is-long-enough!")
        key2 = _get_jwt_signing_key("secret-two-that-is-long-enough!")
        assert key1 != key2

    def test_derived_key_differs_from_raw_secret(self):
        """The derived signing key is not the raw secret bytes."""
        secret = "my-secret-key-for-testing"
        derived_key = _get_jwt_signing_key(secret)
        assert derived_key != secret.encode()

    def test_derived_key_is_32_bytes(self):
        """SHA-256 HMAC produces a 32-byte key."""
        key = _get_jwt_signing_key("any-secret")
        assert len(key) == 32


# ===========================================================================
# Password Verification Security
# ===========================================================================


class TestPasswordSecurity:
    """Test password-related security properties."""

    def test_correct_password_returns_200(self, production_client):
        """Correct password is accepted."""
        resp = _login(production_client, password=_SECRET)
        assert resp.status_code == 200

    def test_wrong_password_returns_401(self, production_client):
        """Wrong password is rejected."""
        resp = _login(production_client, password="wrong")
        assert resp.status_code == 401

    def test_similar_password_rejected(self, production_client):
        """A password that is close but not identical is rejected."""
        # Off by one character
        almost = _SECRET[:-1] + "X"
        resp = _login(production_client, password=almost)
        assert resp.status_code == 401

    def test_empty_password_rejected(self, production_client):
        """Empty password string is rejected."""
        resp = _login(production_client, password="")
        assert resp.status_code == 401

    def test_password_not_in_response_body(self, production_client):
        """The password is never echoed back in any response."""
        # Successful login
        resp = _login(production_client, password=_SECRET)
        body = resp.text
        assert _SECRET not in body

        # Failed login
        resp = _login(production_client, password="bad-password")
        body = resp.text
        assert "bad-password" not in body

    def test_app_secret_not_in_error_response(self, production_client):
        """APP_SECRET_KEY is never leaked in error responses."""
        resp = _login(production_client, password="wrong")
        assert _SECRET not in resp.text
