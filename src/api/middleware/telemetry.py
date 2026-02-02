"""Telemetry middleware for adding trace context to HTTP responses.

Adds X-Trace-Id header to all responses when OpenTelemetry is active,
enabling correlation between frontend requests and backend traces.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.utils.logging import get_logger

logger = get_logger(__name__)


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Middleware that adds X-Trace-Id header from OTel span context.

    When OTel is active, extracts the current trace ID from the span context
    and adds it as an X-Trace-Id response header. This enables:
    - Frontend to correlate requests with backend traces
    - Error responses to reference trace IDs for debugging
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request and add trace ID to response headers."""
        response = await call_next(request)

        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            context = span.get_span_context()
            if context and context.trace_id:
                # Format as 32-char hex string
                trace_id = format(context.trace_id, "032x")
                response.headers["X-Trace-Id"] = trace_id
        except ImportError:
            pass  # OTel not installed — skip silently
        except Exception:
            pass  # Don't fail requests due to tracing errors

        return response
