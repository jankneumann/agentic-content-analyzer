"""Middleware ordering tests for the audit stack.

The normative contract (spec audit-log §D3a + design §D3a):
- TraceIdMiddleware is outermost (sets X-Trace-Id header on every response).
- AuditMiddleware sits *outside* AuthMiddleware so 401/403 responses are audited.
- AuditMiddleware bypasses OPTIONS preflight so CORS continues to work.

These tests assert:
(a) The production ``src.api.app`` has AuditMiddleware registered.
(b) AuditMiddleware is configured to run before AuthMiddleware resolves the request
    (i.e. Audit sees the raw request incl. any X-Admin-Key header).
(c) An unauthenticated request still produces an audit row with status_code 401
    and notes.auth_failure == "missing_key".
(d) A request with an invalid X-Admin-Key still produces an audit row with
    status_code 403, admin_key_fp set, and notes.auth_failure == "invalid_key".
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


def _get_middleware_class_names() -> list[str]:
    """Return the middleware stack as an ordered list of class names.

    Starlette's ``add_middleware`` calls ``user_middleware.insert(0, ...)`` —
    so the last middleware registered ends up at INDEX 0. That means:

        index 0 == outermost (runs first on the request, last on the response)
        index -1 == innermost (closest to the route)

    We return the list in that order so tests assert ``outer_idx < inner_idx``.
    """
    app_mod = importlib.import_module("src.api.app")
    stack = list(app_mod.app.user_middleware)
    return [m.cls.__name__ for m in stack]


def test_audit_middleware_is_registered():
    names = _get_middleware_class_names()
    assert "AuditMiddleware" in names, (
        f"AuditMiddleware not registered in app.add_middleware stack. Got: {names}"
    )


def test_audit_wraps_auth_middleware():
    """AuditMiddleware must run OUTSIDE (wrap) AuthMiddleware so that 401/403 are audited.

    Per ``_get_middleware_class_names`` docstring: index 0 is outermost, last is
    innermost. So AuditMiddleware must have a SMALLER index than AuthMiddleware.
    """
    names = _get_middleware_class_names()
    assert "AuthMiddleware" in names
    auth_idx = names.index("AuthMiddleware")
    audit_idx = names.index("AuditMiddleware")
    assert audit_idx < auth_idx, (
        f"AuditMiddleware must be registered to run outside AuthMiddleware "
        f"(smaller index = more outer). Got order: {names}"
    )


def test_trace_middleware_is_outermost():
    names = _get_middleware_class_names()
    # TraceIdMiddleware is the X-Trace-Id emitter registered last (index 0 =
    # outermost after Starlette's insert(0, ...) behaviour).
    assert names[0] == "TraceIdMiddleware", (
        f"TraceIdMiddleware must be outermost (added last, index 0). Got: {names}"
    )


@pytest.fixture
def production_client(monkeypatch):
    """Force production mode so AuthMiddleware enforces X-Admin-Key."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-at-least-32-characters-long!")
    monkeypatch.setenv("ADMIN_API_KEY", "right-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic")
    monkeypatch.setenv("WORKER_ENABLED", "false")

    from src.config.settings import get_settings

    get_settings.cache_clear()
    try:
        from src.api.app import app

        with TestClient(app, base_url="https://testserver") as c:
            yield c
    finally:
        get_settings.cache_clear()


def test_401_no_credentials_produces_audit_row(production_client, monkeypatch):
    """When Auth rejects for missing creds, the audit middleware (outer) must still
    capture the attempt with status_code=401 and notes.auth_failure='missing_key'."""

    rows: list[dict] = []

    def _writer(**kwargs):
        rows.append(kwargs)

    # Replace the default writer used by the running middleware instance.
    # AuditMiddleware looks up the writer via a module-level sentinel so tests can
    # patch it without touching the app object.
    monkeypatch.setattr("src.api.middleware.audit._default_writer", _writer)

    resp = production_client.get("/api/v1/kb/compile", headers={})
    # Expect 401 Unauthorized (auth rejects missing credentials)
    assert resp.status_code in (401, 403)
    assert rows, "no audit row captured for unauthenticated request"
    row = rows[-1]
    assert row["status_code"] == 401
    assert row["admin_key_fp"] is None
    assert (row.get("notes") or {}).get("auth_failure") == "missing_key"


def test_403_invalid_key_produces_audit_row_with_fingerprint(production_client, monkeypatch):
    """Invalid admin key should yield 403 + audit row with admin_key_fp set and
    notes.auth_failure='invalid_key'."""

    rows: list[dict] = []

    def _writer(**kwargs):
        rows.append(kwargs)

    monkeypatch.setattr("src.api.middleware.audit._default_writer", _writer)

    import hashlib

    wrong_key = "nope-not-the-right-key"
    resp = production_client.get("/api/v1/kb/compile", headers={"X-Admin-Key": wrong_key})
    assert resp.status_code == 403
    assert rows, "no audit row captured for invalid-key request"
    row = rows[-1]
    assert row["status_code"] == 403
    assert row["admin_key_fp"] == hashlib.sha256(wrong_key.encode()).hexdigest()[-8:]
    assert (row.get("notes") or {}).get("auth_failure") == "invalid_key"
