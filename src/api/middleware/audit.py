"""Audit logging middleware and `@audited` decorator.

Every `/api/v1/*` request produces an ``audit_log`` row — success or failure,
authenticated or not — per the normative spec ``specs/audit-log/spec.md``.
The middleware sits OUTSIDE ``AuthMiddleware`` so 401/403 responses are still
captured for forensic correlation. It bypasses OPTIONS preflight entirely.

Key design points (see ``openspec/changes/cloud-db-source-of-truth/design.md``):

- **D3a — admin_key_fp policy**: Fingerprint is computed from the raw
  ``X-Admin-Key`` header whenever the header is present (valid OR invalid);
  NULL only when the header is absent. This lets us correlate invalid-key
  attempts across requests.
- **D4b — non-blocking writes**: An audit INSERT failure MUST NOT bubble to
  the caller. We log to stderr and mark ``audit.write_failure=true`` on the
  active OTel span; the original response is returned unchanged.
- **D10 — observability**: ``audit.operation``, ``audit.status_code``, and
  (on error only) ``audit.write_failure`` are set on the active span for
  every audited request.

The ``@audited(operation="<verb>")`` decorator is metadata enrichment only —
it does NOT gate whether a row is written. Every ``/api/v1/*`` request is
logged; decorated routes just get the ``operation`` column populated.
"""

from __future__ import annotations

import functools
import hashlib
import inspect
import ipaddress
import json
import sys
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

try:
    from opentelemetry import trace
except ImportError:  # pragma: no cover - OTel is a hard dep, but be defensive
    trace = None  # type: ignore[assignment]


__all__ = [
    "AUDIT_STATE_ATTR",
    "AuditMiddleware",
    "audited",
]


AUDIT_STATE_ATTR = "audit_operation"
"""Attribute name on ``request.state`` where the decorator stashes operation."""

_API_V1_PREFIX = "/api/v1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash_admin_key(raw: str | None) -> str | None:
    """Return last 8 chars of SHA-256(raw) or None when raw is empty/missing.

    The fingerprint policy is "whenever header is present, compute fingerprint" —
    validity is irrelevant, the middleware runs outside auth.
    """
    if not raw:
        return None
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[-8:]


def _extract_client_ip(request: Request) -> str | None:
    """Resolve the real client IP.

    Priority chain (per spec audit-log §"Client IP is extracted via proxy-aware headers"):
    1. Cf-Connecting-Ip (Cloudflare)
    2. First IP in X-Forwarded-For (take only the leftmost entry)
    3. request.client.host (direct TCP peer)

    IPv4-mapped IPv6 addresses (``::ffff:a.b.c.d``) are normalized to IPv4.
    """
    cf = request.headers.get("Cf-Connecting-Ip")
    if cf:
        return _normalize_ip(cf.strip())

    xff = request.headers.get("X-Forwarded-For")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return _normalize_ip(first)

    if request.client and request.client.host:
        return _normalize_ip(request.client.host)
    return None


def _normalize_ip(value: str) -> str:
    """Convert IPv4-mapped IPv6 forms to plain IPv4. Leave other forms alone."""
    try:
        addr = ipaddress.ip_address(value)
    except ValueError:
        return value
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        return str(addr.ipv4_mapped)
    return str(addr)


def _resolve_request_id(request: Request) -> str:
    """Return request.state.request_id when populated, else derive a fallback.

    Fallback order: OTel trace-id (if recording) → random uuid4.
    """
    rid = getattr(request.state, "request_id", None)
    if isinstance(rid, str) and rid:
        return rid
    if trace is not None:
        try:
            span = trace.get_current_span()
            ctx = span.get_span_context() if span is not None else None
            if ctx and getattr(ctx, "trace_id", 0):
                return format(ctx.trace_id, "032x")
        except Exception:  # pragma: no cover - defensive
            pass
    return uuid.uuid4().hex


def _resolve_operation(request: Request) -> str | None:
    """Return the @audited operation for the matched route, if any.

    Priority:
    1. ``request.state.audit_operation`` (set by the decorator when the handler
       receives a Request-like argument).
    2. Fallback: walk the app's router to locate the matched endpoint and read
       ``__audit_operation__`` off it (covers handlers that don't take a Request
       parameter — FastAPI doesn't inject Request into those, so the decorator
       never runs to stash state).
    """
    stashed = getattr(request.state, AUDIT_STATE_ATTR, None)
    if stashed:
        return stashed
    try:
        scope_route = request.scope.get("route")
        endpoint = getattr(scope_route, "endpoint", None)
        if endpoint is not None:
            op = getattr(endpoint, "__audit_operation__", None)
            if op:
                return op
    except Exception:  # pragma: no cover - defensive
        pass
    return None


def _set_span_attr(key: str, value: Any) -> None:
    """Best-effort OTel span attribute setter. No-op when OTel not available."""
    if trace is None:
        return
    try:
        span = trace.get_current_span()
        if span is None:
            return
        is_recording = getattr(span, "is_recording", None)
        if callable(is_recording) and not is_recording():
            return
        span.set_attribute(key, value)
    except Exception:  # pragma: no cover - defensive
        pass


def _default_writer(**kwargs: Any) -> None:
    """Default audit writer — INSERTs one row into ``audit_log`` via a fresh session.

    Uses a dedicated short-lived session so it never entangles with the route's
    own transaction. Any exception bubbles up — the middleware converts it to a
    best-effort stderr log and never lets it reach the caller.
    """
    from src.storage.database import get_db_session

    session = get_db_session()
    try:
        notes_value = kwargs.get("notes") or {}
        if isinstance(notes_value, dict):
            notes_json = json.dumps(notes_value)
        else:
            notes_json = json.dumps({})

        session.execute(
            text(
                """
                INSERT INTO audit_log
                    (request_id, method, path, operation, admin_key_fp,
                     status_code, body_size, client_ip, notes)
                VALUES
                    (:request_id, :method, :path, :operation, :admin_key_fp,
                     :status_code, :body_size, CAST(:client_ip AS INET),
                     CAST(:notes AS JSONB))
                """
            ),
            {
                "request_id": kwargs.get("request_id"),
                "method": kwargs.get("method"),
                "path": kwargs.get("path"),
                "operation": kwargs.get("operation"),
                "admin_key_fp": kwargs.get("admin_key_fp"),
                "status_code": kwargs.get("status_code"),
                "body_size": kwargs.get("body_size"),
                "client_ip": kwargs.get("client_ip"),
                "notes": notes_json,
            },
        )
        session.commit()
    finally:
        session.close()


# ---------------------------------------------------------------------------
# @audited decorator
# ---------------------------------------------------------------------------


def audited(operation: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that tags a route handler with an ``operation`` name.

    The decorator is metadata enrichment only — it does not gate whether an
    audit row is written (every ``/api/v1/*`` request is logged by the
    middleware). It simply stashes ``operation`` onto ``request.state`` so the
    middleware can populate the row's ``operation`` column.

    Usage::

        @router.post("/kb/purge")
        @audited(operation="kb.purge")
        async def purge(request: Request) -> None:
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        func.__audit_operation__ = operation

        def _stash_on_request(args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
            # Try to locate a Request-like object in args/kwargs.
            for candidate in list(args) + list(kwargs.values()):
                state = getattr(candidate, "state", None)
                if state is None:
                    continue
                try:
                    setattr(state, AUDIT_STATE_ATTR, operation)
                    return
                except AttributeError:
                    continue

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                _stash_on_request(args, kwargs)
                return await func(*args, **kwargs)

            async_wrapper.__audit_operation__ = operation
            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            _stash_on_request(args, kwargs)
            return func(*args, **kwargs)

        sync_wrapper.__audit_operation__ = operation
        return sync_wrapper

    return decorator


# ---------------------------------------------------------------------------
# AuditMiddleware
# ---------------------------------------------------------------------------


class AuditMiddleware(BaseHTTPMiddleware):
    """Log every /api/v1/* request to the audit_log table.

    Positioned OUTSIDE ``AuthMiddleware`` so 401/403 responses are still captured.
    Bypasses OPTIONS preflight per D3a.
    """

    def __init__(self, app: ASGIApp, writer: Callable[..., None] | None = None) -> None:
        super().__init__(app)
        # Allow test injection while falling back to the module-level default.
        # Lookup happens at call-time so monkeypatch can swap the default
        # (used by test_audit_ordering.py).
        self._writer_override = writer

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip paths that aren't under /api/v1
        if not request.url.path.startswith(_API_V1_PREFIX):
            return await call_next(request)

        # OPTIONS preflight bypass (D3a)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Compute fingerprint from raw header BEFORE auth runs.
        raw_admin_key = request.headers.get("X-Admin-Key")
        admin_key_fp = _hash_admin_key(raw_admin_key)

        # Body size from Content-Length header (avoid consuming the stream).
        body_size: int | None = None
        content_length = request.headers.get("Content-Length")
        if content_length is not None:
            try:
                body_size = int(content_length)
            except ValueError:
                body_size = None

        client_ip = _extract_client_ip(request)

        # Run the inner stack — this is where auth will run, then the route, then
        # the ``@audited`` decorator populates request.state.audit_operation.
        # If the inner stack raises, we still record the attempt as status 500.
        status_code: int
        response: Response | None = None
        error: BaseException | None = None
        try:
            response = await call_next(request)
            status_code = int(response.status_code)
        except BaseException as exc:
            error = exc
            status_code = 500

        # Compute notes based on the response status.
        notes: dict[str, Any] = {}
        if status_code == 401 and raw_admin_key is None:
            notes["auth_failure"] = "missing_key"
        elif status_code == 403 and raw_admin_key is not None:
            notes["auth_failure"] = "invalid_key"

        operation = _resolve_operation(request)
        request_id = _resolve_request_id(request)

        # Enrich active OTel span
        _set_span_attr("audit.operation", operation if operation is not None else "")
        _set_span_attr("audit.status_code", status_code)

        # Resolve writer at call time so tests can monkeypatch
        # ``src.api.middleware.audit._default_writer``.
        if self._writer_override is not None:
            writer = self._writer_override
        else:
            import src.api.middleware.audit as _mod  # self-import for patchability

            writer = _mod._default_writer

        try:
            writer(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                operation=operation,
                admin_key_fp=admin_key_fp,
                status_code=status_code,
                body_size=body_size,
                client_ip=client_ip,
                notes=notes or {},
            )
        except Exception as exc:
            # D4b: non-blocking. Log to stderr, mark span, return original response.
            _set_span_attr("audit.write_failure", True)
            print(
                f"[audit] write failure request_id={request_id} "
                f"method={request.method} path={request.url.path} error={exc!r}",
                file=sys.stderr,
            )

        if error is not None:
            raise error
        assert response is not None  # for type checker
        return response
