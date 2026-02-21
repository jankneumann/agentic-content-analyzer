"""Authentication middleware for owner access control.

Enforces session cookie or X-Admin-Key on all endpoints except
explicitly exempted paths. In development mode, all requests pass.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.api.auth_routes import (
    _COOKIE_NAME,
    _SLIDING_WINDOW_THRESHOLD_SECONDS,
    _create_jwt,
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
)


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


def _unauthorized_response() -> JSONResponse:
    """Create a 401 JSON response matching the existing error handler format."""
    body: dict[str, Any] = {
        "error": "Authentication required",
        "detail": "Please log in or provide X-Admin-Key header.",
    }
    trace_id = _get_trace_id()
    if trace_id:
        body["trace_id"] = trace_id
    return JSONResponse(status_code=401, content=body)


def _is_exempt(path: str) -> bool:
    """Check if a request path is exempt from authentication."""
    return any(path.startswith(prefix) for prefix in AUTH_EXEMPT_PREFIXES)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces authentication on all non-exempt endpoints.

    Authentication methods (checked in order):
    1. Session cookie (JWT) — for browser/mobile
    2. X-Admin-Key header — for CLI/extensions (backward compat)

    In development mode, all requests pass without auth.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()

        # Dev mode: no auth required (unchanged from pre-auth behavior)
        if settings.is_development:
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
            body: dict[str, Any] = {
                "error": "Forbidden",
                "detail": "Invalid admin API key",
            }
            trace_id = _get_trace_id()
            if trace_id:
                body["trace_id"] = trace_id
            return JSONResponse(status_code=403, content=body)

        # Neither auth method succeeded
        return _unauthorized_response()
