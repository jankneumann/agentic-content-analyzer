"""Global structured error handler with trace_id correlation."""

from __future__ import annotations

from typing import Any

from asyncpg.exceptions import DataError as AsyncpgDataError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError, IntegrityError

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

    @app.exception_handler(DataError)
    async def data_error_handler(request: Request, exc: DataError) -> JSONResponse:
        """Convert SQLAlchemy DataError to 422 Unprocessable Entity.

        DataError covers PostgreSQL-level input validation failures such as
        invalid timezone offsets, numeric overflow, and invalid text
        representations — all fundamentally bad user input.
        """
        logger.warning(
            f"Database rejected input: {exc.orig}",
            extra={"path": request.url.path},
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": "Unprocessable Entity",
                "detail": f"Invalid parameter value: {exc.orig}",
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        """Convert SQLAlchemy IntegrityError to 409 Conflict.

        Covers unique constraint violations, foreign key violations,
        and check constraint failures — all indicate conflicting state,
        not invalid input format.
        """
        logger.warning(
            f"Database constraint violation: {exc.orig}",
            extra={"path": request.url.path},
        )
        return JSONResponse(
            status_code=409,
            content={
                "error": "Conflict",
                "detail": "Operation conflicts with existing data",
            },
        )

    @app.exception_handler(AsyncpgDataError)
    async def asyncpg_data_error_handler(request: Request, exc: AsyncpgDataError) -> JSONResponse:
        """Convert asyncpg DataError to 422 Unprocessable Entity.

        Catches data validation errors from routes that use asyncpg directly
        (e.g., job queue endpoints): NUL bytes in strings, int64 overflow,
        invalid encodings.
        """
        logger.warning(
            f"asyncpg rejected input: {exc}",
            extra={"path": request.url.path},
        )
        return JSONResponse(
            status_code=422,
            content={
                "error": "Unprocessable Entity",
                "detail": f"Invalid parameter value: {exc}",
            },
        )

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
