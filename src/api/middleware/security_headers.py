"""Security headers middleware for HTTP response hardening.

Adds standard security headers to all responses, including error responses.
HSTS is only added in production to avoid breaking local development.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Headers applied to all responses regardless of environment
_COMMON_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "0",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy-Report-Only": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https:; "
        "font-src 'self'; "
        "frame-ancestors 'none'"
    ),
}

# HSTS header value (1 year with subdomains)
_HSTS_VALUE = "max-age=31536000; includeSubDomains"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to all HTTP responses.

    Adds standard security headers (X-Content-Type-Options, X-Frame-Options,
    Referrer-Policy, Permissions-Policy, CSP report-only) to every response.
    HSTS is only added when environment is "production" to avoid interfering
    with local development over HTTP.
    """

    def __init__(self, app, environment: str = "development") -> None:
        super().__init__(app)
        self.environment = environment

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request and add security headers to response."""
        response = await call_next(request)

        for header, value in _COMMON_HEADERS.items():
            response.headers[header] = value

        if self.environment == "production":
            response.headers["Strict-Transport-Security"] = _HSTS_VALUE

        return response
