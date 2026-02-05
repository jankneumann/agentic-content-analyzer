"""Global structured error handler with trace_id correlation."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.utils.logging import get_logger

logger = get_logger(__name__)


def _get_trace_id() -> str | None:
    """Extract the current OTel trace ID, if available."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.trace_id:
            return format(ctx.trace_id, "032x")
    except (ImportError, Exception):
        pass
    return None


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app.

    Unhandled exceptions are returned as structured JSON:
    {
        "error": "Internal Server Error",
        "detail": "...",
        "trace_id": "abc123..." | null
    }
    """

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        trace_id = _get_trace_id()
        logger.error(
            f"Unhandled exception: {exc}",
            extra={"trace_id": trace_id, "path": request.url.path},
            exc_info=True,
        )
        body: dict[str, Any] = {
            "error": "Internal Server Error",
            "detail": "An internal error occurred",
        }
        if trace_id:
            body["trace_id"] = trace_id
        return JSONResponse(status_code=500, content=body)
