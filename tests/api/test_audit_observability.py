"""Observability tests for AuditMiddleware.

Spec: audit-log §"Audit middleware observability attributes" (D10):
- audit.operation (string, nullable) on every audited span
- audit.status_code (integer) on every audited span
- audit.write_failure (bool) only when the audit INSERT raises
- request.state.request_id (populated upstream) flows into audit_log.request_id
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware.audit import AuditMiddleware, audited


class _RecordingWriter:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.raise_on_next = False

    def __call__(self, **kwargs: Any) -> None:
        if self.raise_on_next:
            self.raise_on_next = False
            raise RuntimeError("simulated")
        self.rows.append(kwargs)


class _RecordingSpan:
    def __init__(self) -> None:
        self.attrs: dict[str, Any] = {}

    def set_attribute(self, key: str, value: Any) -> None:
        self.attrs[key] = value

    def is_recording(self) -> bool:
        return True


@pytest.fixture
def audited_app():
    writer = _RecordingWriter()
    app = FastAPI()

    @app.get("/api/v1/plain")
    async def plain() -> dict[str, str]:
        return {"ok": "true"}

    @app.post("/api/v1/kb/lint/fix")
    @audited(operation="kb.lint.fix")
    async def lint_fix() -> dict[str, str]:
        return {"ok": "fixed"}

    app.add_middleware(AuditMiddleware, writer=writer)
    return app, writer


def test_audit_operation_and_status_code_on_success(audited_app):
    app, _writer = audited_app
    span = _RecordingSpan()
    with patch("src.api.middleware.audit.trace.get_current_span", return_value=span):
        with TestClient(app) as c:
            resp = c.post("/api/v1/kb/lint/fix", json={})
    assert resp.status_code == 200
    assert span.attrs.get("audit.operation") == "kb.lint.fix"
    assert span.attrs.get("audit.status_code") == 200
    # Not set on success
    assert "audit.write_failure" not in span.attrs


def test_audit_operation_null_for_plain_endpoint(audited_app):
    app, _writer = audited_app
    span = _RecordingSpan()
    with patch("src.api.middleware.audit.trace.get_current_span", return_value=span):
        with TestClient(app) as c:
            c.get("/api/v1/plain")
    # Operation attr is either unset or explicitly None — both acceptable per spec
    assert span.attrs.get("audit.operation") in (None, "", ...)
    assert span.attrs.get("audit.status_code") == 200


def test_audit_write_failure_attribute_set_on_error(audited_app):
    app, writer = audited_app
    writer.raise_on_next = True
    span = _RecordingSpan()
    with patch("src.api.middleware.audit.trace.get_current_span", return_value=span):
        with TestClient(app) as c:
            resp = c.get("/api/v1/plain")
    # Response is unaffected
    assert resp.status_code == 200
    assert span.attrs.get("audit.write_failure") is True


def test_request_state_request_id_flows_to_audit_row(audited_app):
    """If TraceMiddleware (upstream) sets request.state.request_id, the middleware
    must write that value verbatim into the audit row."""
    app, writer = audited_app

    from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
    from starlette.requests import Request

    class _InjectRequestId(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
            request.state.request_id = "req-abc-123"
            return await call_next(request)

    # Register AFTER AuditMiddleware so it runs BEFORE audit dispatch (outer wraps
    # inner; first-added is innermost).
    app.add_middleware(_InjectRequestId)

    with TestClient(app) as c:
        c.get("/api/v1/plain")

    assert writer.rows, "no audit row captured"
    assert writer.rows[-1]["request_id"] == "req-abc-123"


def test_request_id_falls_back_when_not_preset(audited_app):
    """When no upstream middleware sets request.state.request_id, AuditMiddleware
    must still record a non-empty request_id (fallback: OTel trace id or uuid4)."""
    app, writer = audited_app
    with TestClient(app) as c:
        c.get("/api/v1/plain")
    row = writer.rows[-1]
    assert isinstance(row["request_id"], str) and row["request_id"]
