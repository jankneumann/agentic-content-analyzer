"""Reject requests carrying NUL bytes in the URL path or query string.

PostgreSQL text values can never contain a NUL byte (``\\x00``): psycopg2
raises ``ValueError("A string literal cannot contain NUL (0x00) characters.")``
before the statement is even sent. A request carrying one is therefore *always*
invalid input, and there is no handler anywhere in the app that could
meaningfully act on it.

Without this guard those requests surface as HTTP 500 rather than 4xx, by two
different routes:

1. A ``str`` query param flows into a Pydantic field constrained with
   ``pattern=^[^\\x00]*$`` (``QueryText``). Pydantic raises ``ValidationError``,
   which subclasses ``ValueError`` — so it lands in the generic ``ValueError``
   handler, which answers 422 for RFC-7807 "problem" paths but **500** for
   legacy paths.
2. An unconstrained ``str`` query param reaches psycopg2 directly and raises a
   bare ``ValueError``, hitting that same handler and the same 500.

Rejecting at the request boundary fixes both classes uniformly, and keeps NUL
bytes out of the audit-log writer (which also casts the path into a Postgres
column and would fail on them).

Placement: registered so it sits *inside* CORS — so rejections still carry CORS
headers — and *outside* :class:`AuditMiddleware`, so a request that can never be
persisted is never handed to the audit writer. See ``src/api/app.py`` and
``tests/api/test_audit_ordering.py`` for the full middleware ordering contract.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.api.middleware.error_handler import _is_problem_path, _problem_body

NUL = "\x00"

_DETAIL = "Query parameters and paths must not contain NUL (0x00) bytes"


def _request_contains_nul(request: Request) -> bool:
    """Return True when the decoded path or any query key/value holds a NUL."""
    if NUL in request.url.path:
        return True
    # `request.url.query` is still percent-encoded; `query_params` is decoded,
    # so inspect the decoded view. multi_items() covers repeated keys.
    return any(NUL in key or NUL in value for key, value in request.query_params.multi_items())


class NulByteGuardMiddleware(BaseHTTPMiddleware):
    """Answer 422 for requests containing NUL bytes in the path or query."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            has_nul = _request_contains_nul(request)
        except (UnicodeDecodeError, ValueError):
            # A URL we cannot even decode is likewise not actionable input.
            has_nul = True

        if not has_nul:
            return await call_next(request)

        if _is_problem_path(request.url.path):
            return JSONResponse(
                status_code=422,
                content=_problem_body(
                    title="Unprocessable Entity",
                    status=422,
                    detail=_DETAIL,
                    # Never echo the offending byte back to the caller.
                    instance=request.url.path.replace(NUL, ""),
                ),
                media_type="application/problem+json",
            )
        return JSONResponse(
            status_code=422,
            content={"error": "Unprocessable Entity", "detail": _DETAIL},
        )
