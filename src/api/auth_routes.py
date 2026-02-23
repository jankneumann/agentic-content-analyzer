"""Authentication endpoints for owner login.

Provides password-based login, logout, and session check.
JWT signing key is HMAC-derived from APP_SECRET_KEY.
"""

from __future__ import annotations

import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.rate_limiter import login_rate_limiter
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# JWT configuration
_JWT_ALGORITHM = "HS256"
_JWT_ISSUER = "newsletter-aggregator"
_JWT_EXPIRY_DAYS = 7
_COOKIE_NAME = "session"
_SLIDING_WINDOW_THRESHOLD_SECONDS = 86400  # 1 day


def _get_jwt_signing_key(app_secret_key: str) -> bytes:
    """Derive JWT signing key from the app secret.

    Separates the password (what the user types) from the signing key
    (what proves token authenticity). Knowing the password alone does
    not allow forging tokens without also knowing this derivation.
    """
    return hmac.new(app_secret_key.encode(), b"jwt-signing-key", "sha256").digest()


def _create_jwt(app_secret_key: str) -> str:
    """Create a signed JWT token.

    Args:
        app_secret_key: The APP_SECRET_KEY for key derivation.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(UTC)
    payload = {
        "iss": _JWT_ISSUER,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=_JWT_EXPIRY_DAYS)).timestamp()),
    }
    signing_key = _get_jwt_signing_key(app_secret_key)
    return jwt.encode(payload, signing_key, algorithm=_JWT_ALGORITHM)


def _verify_jwt(token: str, app_secret_key: str) -> dict[str, Any] | None:
    """Verify and decode a JWT token.

    Args:
        token: The JWT string from the session cookie.
        app_secret_key: The APP_SECRET_KEY for key derivation.

    Returns:
        Decoded payload dict, or None if verification fails.
    """
    signing_key = _get_jwt_signing_key(app_secret_key)
    try:
        return jwt.decode(
            token,
            signing_key,
            algorithms=[_JWT_ALGORITHM],
            issuer=_JWT_ISSUER,
        )
    except jwt.InvalidTokenError:
        return None


def _get_trace_id() -> str | None:
    """Extract current OTel trace ID if available."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.trace_id:
            return format(ctx.trace_id, "032x")
    except (ImportError, Exception):
        pass
    return None


def _error_response(status_code: int, error: str, detail: str) -> JSONResponse:
    """Create a JSON error response matching the existing error handler format."""
    body: dict[str, Any] = {"error": error, "detail": detail}
    trace_id = _get_trace_id()
    if trace_id:
        body["trace_id"] = trace_id
    return JSONResponse(status_code=status_code, content=body)


def _set_session_cookie(response: Response, token: str) -> None:
    """Set the session cookie on a response with appropriate security flags."""
    settings = get_settings()
    is_dev = settings.is_development
    cross_origin = settings.auth_cookie_cross_origin

    samesite: str = "none" if cross_origin else "lax"
    secure = not is_dev  # Secure=True in production/staging

    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=_JWT_EXPIRY_DAYS * 86400,
        path="/",
    )


def _get_client_ip(request: Request) -> str:
    """Get client IP from request (proxy-resolved by uvicorn --proxy-headers)."""
    if request.client:
        return request.client.host
    return "unknown"


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
async def login(body: LoginRequest, request: Request) -> Response:
    """Authenticate with the app password.

    Verifies the password against APP_SECRET_KEY and issues a
    JWT session cookie on success.
    """
    settings = get_settings()
    client_ip = _get_client_ip(request)

    # Check if APP_SECRET_KEY is configured
    if not settings.app_secret_key:
        logger.error("Login attempted but APP_SECRET_KEY is not configured")
        return _error_response(
            403,
            "Authentication not configured",
            "APP_SECRET_KEY is not set. Configure it to enable login.",
        )

    # Check rate limit
    if login_rate_limiter.is_blocked(client_ip):
        retry_after = login_rate_limiter.get_retry_after(client_ip)
        logger.warning("Rate-limited login attempt from %s", client_ip)
        response = _error_response(
            429,
            "Too many login attempts",
            f"Try again in {retry_after // 60 + 1} minute(s).",
        )
        response.headers["Retry-After"] = str(retry_after)
        return response

    # Verify password (timing-safe)
    # Compare as bytes to handle non-ASCII passwords (fuzzing/security)
    if not secrets.compare_digest(
        body.password.encode("utf-8"), settings.app_secret_key.encode("utf-8")
    ):
        login_rate_limiter.record_failure(client_ip)
        logger.warning("Failed login attempt from %s", client_ip)
        return _error_response(
            401,
            "Invalid credentials",
            "The password provided is incorrect.",
        )

    # Success
    logger.info("Successful login from %s", client_ip)
    token = _create_jwt(settings.app_secret_key)
    response = JSONResponse(content={"authenticated": True})
    _set_session_cookie(response, token)
    return response


@router.post("/logout")
async def logout() -> Response:
    """Clear the session cookie."""
    response = JSONResponse(content={"authenticated": False})
    response.delete_cookie(
        key=_COOKIE_NAME,
        path="/",
    )
    return response


@router.get("/session")
async def check_session(request: Request) -> dict[str, bool]:
    """Check if the current session is valid.

    Returns {"authenticated": true/false} without triggering
    a 401 — frontend uses this to decide whether to show login page.
    """
    settings = get_settings()

    # In dev mode, always authenticated
    if settings.is_development:
        return {"authenticated": True}

    # No APP_SECRET_KEY configured
    if not settings.app_secret_key:
        return {"authenticated": False}

    token = request.cookies.get(_COOKIE_NAME)
    if not token:
        return {"authenticated": False}

    payload = _verify_jwt(token, settings.app_secret_key)
    if payload is None:
        return {"authenticated": False}

    return {"authenticated": True}
