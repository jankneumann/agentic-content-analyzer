"""Global structured error handler with trace_id correlation."""

from __future__ import annotations

from typing import Any

from asyncpg.exceptions import DataError as AsyncpgDataError
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError, IntegrityError

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Endpoints introduced by the cloud-db-source-of-truth change emit RFC 7807
# application/problem+json on errors. Every other legacy endpoint keeps its
# historical `{error, detail}` JSON shape so existing web/CLI clients don't
# break mid-release.
#
# VF-H1 (gemini VAL_REVIEW VR-001): we can NOT use broad prefix matches like
# "/api/v1/kb/" because that catches the legacy `/api/v1/kb/topics/*`,
# `/api/v1/kb/compile`, `/api/v1/kb/index`, `/api/v1/kb/query` routes that
# existing web clients already depend on. We match the NEW paths exactly
# (with prefix semantics only where the new endpoint has sub-paths like
# `/lint/fix` under `/lint`).
_PROBLEM_PATH_PREFIXES = (
    "/api/v1/kb/search",
    "/api/v1/kb/lint",  # covers /lint and /lint/fix
    "/api/v1/graph/query",
    "/api/v1/graph/extract-entities",
    "/api/v1/references/extract",
    "/api/v1/references/resolve",
    "/api/v1/audit",  # covers /audit and /audit/
)


def _is_problem_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _PROBLEM_PATH_PREFIXES)


def _problem_body(
    *, title: str, status: int, detail: str | None = None, instance: str | None = None
) -> dict[str, Any]:
    body: dict[str, Any] = {"title": title, "status": status}
    if detail is not None:
        body["detail"] = detail
    if instance is not None:
        body["instance"] = instance
    trace_id = _get_trace_id()
    if trace_id is not None:
        body["trace_id"] = trace_id
    return body


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
                "detail": "Invalid parameter value",
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
                "detail": "Invalid parameter value",
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Convert HTTPException → RFC 7807 Problem for /api/v1/{kb,graph,references,audit}.

        Other endpoints fall through to FastAPI's default handler, which returns
        the historical `{detail: ...}` shape. Keeping the scope narrow means the
        cloud-db-source-of-truth contract is honored without breaking legacy
        client expectations on other endpoints.
        """
        if _is_problem_path(request.url.path):
            title_map = {
                400: "Bad Request",
                401: "Unauthorized",
                403: "Forbidden",
                404: "Not Found",
                409: "Conflict",
                422: "Unprocessable Entity",
                500: "Internal Server Error",
                502: "Bad Gateway",
                503: "Service Unavailable",
                504: "Gateway Timeout",
            }
            title = title_map.get(exc.status_code, "Error")
            detail = exc.detail if isinstance(exc.detail, str) else None
            body = _problem_body(title=title, status=exc.status_code, detail=detail)
            return JSONResponse(
                status_code=exc.status_code,
                content=body,
                media_type="application/problem+json",
                headers=exc.headers,
            )
        # Legacy path: preserve FastAPI default shape.
        body_legacy: dict[str, Any] = {"detail": exc.detail}
        return JSONResponse(status_code=exc.status_code, content=body_legacy, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Convert Pydantic validation errors → RFC 7807 on Problem-path endpoints."""

        # Pydantic error entries sometimes carry non-JSON-serializable ``ctx``
        # fields (e.g., the raw ValueError instance for custom validators).
        # Strip those before emitting.
        def _safe_errors(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
            safe: list[dict[str, Any]] = []
            for err in raw:
                cleaned = {
                    k: v
                    for k, v in err.items()
                    if k != "ctx" and isinstance(v, (str, int, float, bool, list, dict, type(None)))
                }
                safe.append(cleaned)
            return safe

        if _is_problem_path(request.url.path):
            body = _problem_body(
                title="Unprocessable Entity",
                status=422,
                detail="Request validation failed",
            )
            body["errors"] = _safe_errors(exc.errors())
            return JSONResponse(
                status_code=422, content=body, media_type="application/problem+json"
            )
        # Legacy path: default FastAPI 422 shape.
        return JSONResponse(status_code=422, content={"detail": _safe_errors(exc.errors())})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        trace_id = _get_trace_id()
        logger.error(
            f"Unhandled exception: {exc}",
            extra={"trace_id": trace_id, "path": request.url.path},
            exc_info=True,
        )
        if _is_problem_path(request.url.path):
            body = _problem_body(
                title="Internal Server Error",
                status=500,
                detail="An internal error occurred",
            )
            return JSONResponse(
                status_code=500, content=body, media_type="application/problem+json"
            )
        body_legacy: dict[str, Any] = {
            "error": "Internal Server Error",
            "detail": "An internal error occurred",
        }
        if trace_id:
            body_legacy["trace_id"] = trace_id
        return JSONResponse(status_code=500, content=body_legacy)
