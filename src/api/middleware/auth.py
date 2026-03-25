"""Authentication middleware for owner access control.

Enforces session cookie or X-Admin-Key on all endpoints except
explicitly exempted paths. In development mode, all requests pass.
"""

from __future__ import annotations

import ipaddress
import logging
import secrets
from datetime import UTC, datetime

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.api.auth_routes import (
    _COOKIE_NAME,
    _SLIDING_WINDOW_THRESHOLD_SECONDS,
    _create_jwt,
    _error_response,
    _set_session_cookie,
    _verify_jwt,
)
from src.config.settings import get_settings

logger = logging.getLogger(__name__)

# Paths that skip authentication entirely
AUTH_EXEMPT_PREFIXES = (
    "/health",
    "/ready",
    "/api/v1/system/config",
    "/api/v1/otel/v1/traces",
    "/api/v1/auth/",
    "/api/v1/auth",  # Exact match for /api/v1/auth without trailing slash
    "/shared/",  # Public shared content (token-gated, rate-limited)
)


def _is_exempt(path: str) -> bool:
    """Check if a request path is exempt from authentication."""
    return any(path.startswith(prefix) for prefix in AUTH_EXEMPT_PREFIXES)


def _is_local_client(request: Request) -> bool:
    """Return True when a request originates from loopback/local test clients.

    Dev-mode auth bypass should only apply to local development traffic to reduce
    accidental public exposure when ENVIRONMENT is misconfigured.
    """
    if not request.client or not request.client.host:
        return False

    host = request.client.host
    if host == "testclient":
        return True

    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        # Non-IP hosts are not considered local by default.
        return False


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces authentication on all non-exempt endpoints.

    Authentication methods (checked in order):
    1. Session cookie (JWT) — for browser/mobile
    2. X-Admin-Key header — for CLI/extensions (backward compat)

    In development mode, all requests pass without auth.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()

        # Dev mode: no auth required (legacy behavior), BUT respect keys if configured.
        # If a user sets APP_SECRET_KEY, they expect auth to work, even in dev.
        keys_configured = settings.app_secret_key or settings.admin_api_key
        if settings.is_development and not keys_configured:
            if not _is_local_client(request):
                return _error_response(
                    401,
                    "Authentication required",
                    "Unauthenticated development mode is restricted to local requests.",
                )
            return await call_next(request)

        # CORS preflight: let OPTIONS through so CORSMiddleware can respond
        if request.method == "OPTIONS":
            return await call_next(request)

        # Exempt paths: health, ready, system config, otel proxy, auth endpoints
        if _is_exempt(request.url.path):
            return await call_next(request)

        # Check session cookie first
        token = request.cookies.get(_COOKIE_NAME)
        if token and settings.app_secret_key:
            payload = _verify_jwt(token, settings.app_secret_key)
            if payload is not None:
                response = await call_next(request)
                # Sliding window: refresh cookie if token is > 1 day old
                iat = payload.get("iat", 0)
                age = datetime.now(UTC).timestamp() - iat
                if age > _SLIDING_WINDOW_THRESHOLD_SECONDS:
                    new_token = _create_jwt(settings.app_secret_key)
                    _set_session_cookie(response, new_token)
                return response

        # Check X-Admin-Key header (backward compat for CLI/extensions)
        admin_key = request.headers.get("X-Admin-Key")
        if admin_key and settings.admin_api_key:
            if secrets.compare_digest(admin_key, settings.admin_api_key):
                return await call_next(request)
            # Explicit invalid key → 403 (spec: "explicit keys are always validated")
            return _error_response(403, "Forbidden", "Invalid admin API key")

        # Neither auth method succeeded
        return _error_response(
            401, "Authentication required", "Please log in or provide X-Admin-Key header."
        )
