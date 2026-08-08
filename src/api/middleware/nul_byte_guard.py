"""Reject requests carrying NUL bytes in the URL path, query string, or JSON body.

PostgreSQL text values can never contain a NUL byte (``\\x00``): psycopg2
raises ``ValueError("A string literal cannot contain NUL (0x00) characters.")``
before the statement is even sent. A request carrying one is therefore *always*
invalid input, and there is no handler anywhere in the app that could
meaningfully act on it.

Without this guard those requests surface as HTTP 500 rather than 4xx, by three
different routes:

1. A ``str`` query param flows into a Pydantic field constrained with
   ``pattern=^[^\\x00]*$`` (``QueryText``). Pydantic raises ``ValidationError``,
   which subclasses ``ValueError`` — so it lands in the generic ``ValueError``
   handler, which answers 422 for RFC-7807 "problem" paths but **500** for
   legacy paths.
2. An unconstrained ``str`` query param reaches psycopg2 directly and raises a
   bare ``ValueError``, hitting that same handler and the same 500.
3. A JSON body field reaches psycopg2 the same way — e.g. ``prompt`` on
   ``POST /api/v1/agent/task`` (persisted by ``AgentTaskService.create_task``)
   or ``question`` on ``POST /api/v1/kb/query`` (fed into an ILIKE). The two
   drivers disagree here: asyncpg raises ``UntranslatableCharacterError``, a
   subclass of ``asyncpg.exceptions.DataError`` that *is* mapped to 422, while
   psycopg2's bare ``ValueError`` is not. Guarding at the boundary is one choke
   point instead of one handler per driver quirk, and covers write paths that
   do not exist yet.

Body inspection scope
---------------------
Only JSON bodies are inspected, and only the *escaped* form matters. A raw NUL
byte inside a JSON string is not legal JSON, and the strict ``json.loads``
FastAPI uses already rejects it with 422 on its own; the sequence that survives
parsing and reaches the driver is the ``\\u0000`` escape.

Non-JSON bodies are passed through untouched. Multipart uploads carry arbitrary
file bytes where a NUL is entirely valid, and buffering megabytes of binary to
scan for a legal byte would be both wrong and expensive.

Placement: registered so it sits *inside* CORS — so rejections still carry CORS
headers — and *outside* :class:`AuditMiddleware`, so a request that can never be
persisted is never handed to the audit writer. See ``src/api/app.py`` and
``tests/api/test_audit_ordering.py`` for the full middleware ordering contract.
"""

from __future__ import annotations

import json
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.api.middleware.error_handler import _is_problem_path, _problem_body

NUL = "\x00"
NUL_BYTE = b"\x00"

_URL_DETAIL = "Query parameters and paths must not contain NUL (0x00) bytes"
_BODY_DETAIL = "Request body must not contain NUL (0x00) bytes"

# Cheap pre-filter: the ASCII tail of the JSON escape that decodes to a NUL.
# Any NUL in a decoded JSON document comes either from a raw NUL byte or from
# that escape, so a body containing neither cannot possibly yield one. Scanning
# is a single memchr-class pass over the buffer; only a hit pays for a full
# parse, which keeps the common request untouched. A body carrying the six
# literal characters (valid text — a doc mentioning the escape) hits the filter
# and is then cleared by the exact check, never rejected.
_ESCAPED_NUL_HINT = b"u0000"

# Never buffer more than this to inspect. Matches the smallest body limit the
# app enforces for itself (``otel_proxy_routes.MAX_BODY_SIZE``) so the guard can
# never out-buffer a route's own cap. Larger bodies, and chunked requests that
# declare no Content-Length, pass through uninspected — accepted, because every
# JSON body this API actually receives is orders of magnitude below the cap.
_MAX_INSPECTED_BODY_BYTES = 1 * 1024 * 1024


def _request_contains_nul(request: Request) -> bool:
    """Return True when the decoded path or any query key/value holds a NUL."""
    if NUL in request.url.path:
        return True
    # `request.url.query` is still percent-encoded; `query_params` is decoded,
    # so inspect the decoded view. multi_items() covers repeated keys.
    return any(NUL in key or NUL in value for key, value in request.query_params.multi_items())


def _is_json_content_type(raw_content_type: str) -> bool:
    """Return True for `application/json` and any `*+json` media type."""
    base = raw_content_type.split(";", 1)[0].strip().lower()
    return base == "application/json" or base.endswith("+json")


def _decoded_contains_nul(value: Any) -> bool:
    """Walk a parsed JSON document for a NUL in any string, including keys."""
    stack: list[Any] = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            if NUL in item:
                return True
        elif isinstance(item, dict):
            for key, child in item.items():
                if isinstance(key, str) and NUL in key:
                    return True
                stack.append(child)
        elif isinstance(item, list):
            stack.extend(item)
    return False


async def _body_contains_nul(request: Request) -> bool:
    """Return True when an inspectable JSON body decodes to a NUL anywhere.

    Reading the body here is safe: Starlette's ``BaseHTTPMiddleware`` hands
    ``dispatch`` a ``_CachedRequest``, which caches a body consumed in the
    middleware and replays it to the downstream app. Asserted by
    ``tests/api/test_nul_byte_request_body.py``.
    """
    if not _is_json_content_type(request.headers.get("content-type", "")):
        return False

    declared_length = request.headers.get("content-length")
    if declared_length is None:
        return False
    try:
        if int(declared_length) > _MAX_INSPECTED_BODY_BYTES:
            return False
    except ValueError:
        return False

    raw = await request.body()
    if _ESCAPED_NUL_HINT not in raw and NUL_BYTE not in raw:
        return False

    try:
        decoded = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        # Malformed JSON is FastAPI's to reject (422 json_invalid), not ours.
        return False
    return _decoded_contains_nul(decoded)


class NulByteGuardMiddleware(BaseHTTPMiddleware):
    """Answer 422 for requests containing NUL bytes in the path, query, or body."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            has_nul = _request_contains_nul(request)
        except (UnicodeDecodeError, ValueError):
            # A URL we cannot even decode is likewise not actionable input.
            has_nul = True
        detail = _URL_DETAIL

        if not has_nul:
            try:
                has_nul = await _body_contains_nul(request)
            except (UnicodeDecodeError, ValueError):
                # An undecodable body is FastAPI's to reject, not ours.
                has_nul = False
            detail = _BODY_DETAIL

        if not has_nul:
            return await call_next(request)

        if _is_problem_path(request.url.path):
            return JSONResponse(
                status_code=422,
                content=_problem_body(
                    title="Unprocessable Entity",
                    status=422,
                    detail=detail,
                    # Never echo the offending byte back to the caller.
                    instance=request.url.path.replace(NUL, ""),
                ),
                media_type="application/problem+json",
            )
        return JSONResponse(
            status_code=422,
            content={"error": "Unprocessable Entity", "detail": detail},
        )
