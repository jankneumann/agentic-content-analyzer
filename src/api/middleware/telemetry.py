"""Telemetry middleware for stable HTTP response trace correlation."""

from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class TraceIdMiddleware(BaseHTTPMiddleware):
    """Continue an active trace or install a valid synthetic request context."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            from opentelemetry import trace
            from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, TraceState
        except ImportError:
            response = await call_next(request)
            response.headers["X-Trace-Id"] = secrets.token_hex(16)
            return response

        current = trace.get_current_span().get_span_context()
        if current.is_valid:
            response = await call_next(request)
            response.headers["X-Trace-Id"] = format(current.trace_id, "032x")
            return response

        trace_id = secrets.randbits(128) or 1
        span_id = secrets.randbits(64) or 1
        try:
            synthetic = NonRecordingSpan(
                SpanContext(
                    trace_id=trace_id,
                    span_id=span_id,
                    is_remote=False,
                    trace_flags=TraceFlags(TraceFlags.SAMPLED),
                    trace_state=TraceState(),
                )
            )
            span_scope = trace.use_span(synthetic, end_on_exit=False)
        except Exception:
            response = await call_next(request)
            response.headers["X-Trace-Id"] = format(trace_id, "032x")
            return response

        with span_scope:
            response = await call_next(request)
        response.headers["X-Trace-Id"] = format(trace_id, "032x")
        return response
