"""Tests for the AuditMiddleware.

Covers the normative spec scenarios from `specs/audit-log/spec.md`:
- Every /api/v1/* request creates an audit row
- OPTIONS preflight bypass (no row written)
- admin_key_fp derivation (header present valid, header present invalid, header absent)
- body_size capture from request content-length
- 401 no-credentials: notes.auth_failure == "missing_key", admin_key_fp NULL
- 403 invalid-key: notes.auth_failure == "invalid_key", admin_key_fp SET
- client_ip priority chain: Cf-Connecting-Ip > X-Forwarded-For > request.client.host
- Non-blocking audit write failure (stderr log, original response returned,
  OTel attribute audit.write_failure=true)
"""

from __future__ import annotations

import hashlib
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware.audit import AuditMiddleware, _hash_admin_key, audited


def _expected_fp(raw_key: str) -> str:
    """Compute the canonical admin_key_fp the middleware should produce."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[-8:]


class _RecordingWriter:
    """Stand-in for the audit writer — records kwargs instead of touching the DB."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.raise_on_next: bool = False

    def __call__(self, **kwargs: Any) -> None:
        if self.raise_on_next:
            self.raise_on_next = False
            raise RuntimeError("simulated audit write failure")
        self.rows.append(kwargs)

    def last(self) -> dict[str, Any]:
        assert self.rows, "no audit row recorded"
        return self.rows[-1]


@pytest.fixture
def recorder():
    return _RecordingWriter()


@pytest.fixture
def app_factory(recorder):
    """Factory that builds a FastAPI app with AuditMiddleware wired to `recorder`."""

    def _build(*, include_auth: bool = False, admin_key: str | None = None) -> FastAPI:
        app = FastAPI()

        @app.get("/api/v1/echo")
        async def echo() -> dict[str, str]:
            return {"ok": "true"}

        @app.post("/api/v1/write")
        @audited(operation="test.write")
        async def write() -> dict[str, str]:
            return {"ok": "written"}

        @app.get("/api/v1/boom")
        async def boom() -> dict[str, str]:
            raise RuntimeError("boom")

        @app.get("/other/not-audited")
        async def other() -> dict[str, str]:
            return {"skipped": "true"}

        # Optional fake auth inner middleware (inner → runs AFTER audit sees request)
        if include_auth:
            from starlette.middleware.base import (
                BaseHTTPMiddleware,
                RequestResponseEndpoint,
            )
            from starlette.requests import Request
            from starlette.responses import JSONResponse

            class FakeAuth(BaseHTTPMiddleware):
                async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
                    key = request.headers.get("X-Admin-Key")
                    if not key:
                        return JSONResponse({"detail": "no creds"}, status_code=401)
                    if admin_key and key != admin_key:
                        return JSONResponse({"detail": "invalid"}, status_code=403)
                    return await call_next(request)

            app.add_middleware(FakeAuth)

        # AuditMiddleware wraps FakeAuth (outer)
        app.add_middleware(AuditMiddleware, writer=recorder)

        return app

    return _build


def test_writes_row_for_simple_get(app_factory, recorder):
    app = app_factory()
    with TestClient(app) as c:
        resp = c.get("/api/v1/echo")
    assert resp.status_code == 200
    assert len(recorder.rows) == 1
    row = recorder.last()
    assert row["method"] == "GET"
    assert row["path"] == "/api/v1/echo"
    assert row["status_code"] == 200
    assert row["operation"] is None
    # request_id is always populated (falls back to uuid4 when not preset)
    assert isinstance(row["request_id"], str) and row["request_id"]


def test_options_preflight_is_not_logged(app_factory, recorder):
    app = app_factory()
    with TestClient(app) as c:
        resp = c.options(
            "/api/v1/echo",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert resp.status_code in (200, 405)
    assert recorder.rows == []


def test_admin_key_fp_set_when_header_present_valid(app_factory, recorder):
    app = app_factory()
    key = "real-admin-key"
    with TestClient(app) as c:
        c.get("/api/v1/echo", headers={"X-Admin-Key": key})
    assert recorder.last()["admin_key_fp"] == _expected_fp(key)


def test_admin_key_fp_set_when_header_present_invalid(app_factory, recorder):
    app = app_factory(include_auth=True, admin_key="good-key")
    wrong = "this-is-wrong"
    with TestClient(app) as c:
        resp = c.get("/api/v1/echo", headers={"X-Admin-Key": wrong})
    assert resp.status_code == 403
    row = recorder.last()
    assert row["status_code"] == 403
    assert row["admin_key_fp"] == _expected_fp(wrong)
    assert (row.get("notes") or {}).get("auth_failure") == "invalid_key"


def test_admin_key_fp_null_when_header_absent(app_factory, recorder):
    app = app_factory(include_auth=True, admin_key="good-key")
    with TestClient(app) as c:
        resp = c.get("/api/v1/echo")  # no X-Admin-Key
    assert resp.status_code == 401
    row = recorder.last()
    assert row["status_code"] == 401
    assert row["admin_key_fp"] is None
    assert (row.get("notes") or {}).get("auth_failure") == "missing_key"


def test_body_size_is_captured(app_factory, recorder):
    app = app_factory()
    payload = b'{"x":' + (b"0" * 32) + b"}"
    with TestClient(app) as c:
        c.post("/api/v1/write", content=payload, headers={"Content-Type": "application/json"})
    # body_size should equal byte length of payload
    assert recorder.last()["body_size"] == len(payload)


def test_decorated_endpoint_records_operation(app_factory, recorder):
    app = app_factory()
    with TestClient(app) as c:
        c.post("/api/v1/write", json={})
    assert recorder.last()["operation"] == "test.write"


def test_non_decorated_endpoint_operation_is_null(app_factory, recorder):
    app = app_factory()
    with TestClient(app) as c:
        c.get("/api/v1/echo")
    assert recorder.last()["operation"] is None


def test_non_api_v1_paths_are_not_logged(app_factory, recorder):
    app = app_factory()
    with TestClient(app) as c:
        c.get("/other/not-audited")
    assert recorder.rows == []


def test_failure_response_still_logged(app_factory, recorder):
    app = app_factory()
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.get("/api/v1/boom")
    assert resp.status_code == 500
    assert recorder.last()["status_code"] == 500


def test_client_ip_prefers_cf_connecting_ip(app_factory, recorder):
    app = app_factory()
    with TestClient(app) as c:
        c.get(
            "/api/v1/echo",
            headers={
                "Cf-Connecting-Ip": "203.0.113.7",
                "X-Forwarded-For": "198.51.100.9, 10.0.0.1",
            },
        )
    assert recorder.last()["client_ip"] == "203.0.113.7"


def test_client_ip_falls_back_to_xff_first_entry(app_factory, recorder):
    app = app_factory()
    with TestClient(app) as c:
        c.get(
            "/api/v1/echo",
            headers={"X-Forwarded-For": "198.51.100.9, 10.0.0.1"},
        )
    assert recorder.last()["client_ip"] == "198.51.100.9"


def test_client_ip_falls_back_to_request_client_host(app_factory, recorder):
    app = app_factory()
    with TestClient(app) as c:
        c.get("/api/v1/echo")
    # TestClient default host is "testclient"
    assert recorder.last()["client_ip"] == "testclient"


def test_ipv4_mapped_ipv6_is_normalized(app_factory, recorder):
    app = app_factory()
    with TestClient(app) as c:
        c.get("/api/v1/echo", headers={"Cf-Connecting-Ip": "::ffff:1.2.3.4"})
    assert recorder.last()["client_ip"] == "1.2.3.4"


def test_write_failure_is_non_blocking(app_factory, recorder, capsys):
    app = app_factory()
    recorder.raise_on_next = True
    with TestClient(app) as c:
        resp = c.get("/api/v1/echo")
    # Original response unaffected
    assert resp.status_code == 200
    # Nothing appended to rows because write raised
    assert recorder.rows == []
    # Error surfaced to stderr
    captured = capsys.readouterr()
    assert "audit" in captured.err.lower()


def test_hash_admin_key_returns_last_8_of_sha256():
    assert _hash_admin_key("abc") == hashlib.sha256(b"abc").hexdigest()[-8:]
    assert _hash_admin_key(None) is None
    assert _hash_admin_key("") is None


def test_write_failure_sets_otel_span_attribute(app_factory, recorder):
    """audit.write_failure=true must be set when the audit INSERT raises."""
    app = app_factory()
    recorder.raise_on_next = True

    attrs_captured: dict[str, Any] = {}

    class _FakeSpan:
        def set_attribute(self, key: str, value: Any) -> None:
            attrs_captured[key] = value

        def is_recording(self) -> bool:  # pragma: no cover - defensive
            return True

    with patch("src.api.middleware.audit.trace.get_current_span", return_value=_FakeSpan()):
        with TestClient(app) as c:
            resp = c.get("/api/v1/echo")

    assert resp.status_code == 200
    assert attrs_captured.get("audit.write_failure") is True
