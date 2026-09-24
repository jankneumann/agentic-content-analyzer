"""Tests for ``PUT /api/v1/browser-sessions/{substack,x}``.

Network-free: the one validation request goes to an ``httpx.MockTransport``,
OpenBao is a fake KV v2 adapter applying RFC 7386 merge-patch to an in-memory
secret, and audit rows are captured by replacing the middleware's writer.
Cookie values are sentinels that must never appear in a response, a log
record, an audit row or the OpenAPI document.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from src.api import browser_session_routes
from src.api.rate_limiter_base import EndpointRateLimiter
from src.cli import secret_sinks
from src.config import bao_secrets
from src.config.credentials import reset_credential_provider
from src.services import browser_session_sync

ADMIN_KEY = "right-admin-key"
APP_SECRET = "test-secret-key-at-least-32-characters-long!"

SUBSTACK_SENTINEL = "s%3ASENTINELsubstackSID.0123456789abcdef"
X_AUTH_SENTINEL = "SENTINELauthtoken0123456789abcdef01234567"
X_CT0_SENTINEL = "SENTINELct0" + "f" * 40
SENTINELS = (SUBSTACK_SENTINEL, X_AUTH_SENTINEL, X_CT0_SENTINEL)

X_BODY = {"auth_token": X_AUTH_SENTINEL, "ct0": X_CT0_SENTINEL}
SUBSTACK_BODY = {"substack_sid": SUBSTACK_SENTINEL}

SIBLINGS = {
    "ANTHROPIC_API_KEY": "sk-ant-sibling-value",
    "GMAIL_TOKEN_JSON": '{"refresh_token": "sibling", "nested": [1, 2]}',
    "X_AUTH_TOKEN_SAVED_AT": "2026-01-01T00:00:00+00:00",
    "EMPTY_ONE": "",
}


def _assert_no_sentinel(*texts: str) -> None:
    for text in texts:
        for sentinel in SENTINELS:
            assert sentinel not in text


class FakeKvV2Adapter:
    """``client.adapter`` of an hvac client over one KV v2 secret.

    Applies ``PATCH`` as JSON merge-patch (RFC 7386) the way OpenBao does, and
    fails any other verb so a full-document write would be caught.
    """

    def __init__(self, data: dict[str, str], *, error: Exception | None = None) -> None:
        self.data = dict(data)
        self.requests: list[tuple[str, str, dict[str, Any]]] = []
        self.error = error

    def request(self, method: str, url: str, **kwargs: Any) -> None:
        self.requests.append((method, url, copy.deepcopy(kwargs)))
        if self.error is not None:
            raise self.error
        assert method == "PATCH", f"unexpected {method}: only merge-patch is allowed"
        assert url == "/v1/secret/data/newsletter"
        assert kwargs["headers"]["Content-Type"] == "application/merge-patch+json"
        for key, value in kwargs["json"]["data"].items():
            if value is None:
                self.data.pop(key, None)
            else:
                self.data[key] = value


class Forbidden(Exception):  # noqa: N818 - mirrors hvac.exceptions.Forbidden's name
    """Same class name as hvac's, which BaoSink maps to a capability hint."""


@dataclass
class Harness:
    client: TestClient
    kv: FakeKvV2Adapter
    audit_rows: list[dict[str, Any]]
    http_calls: list[httpx.Request] = field(default_factory=list)
    handler: Callable[[httpx.Request], httpx.Response] | None = None

    def put(self, site: str, body: Any, **kwargs: Any) -> httpx.Response:
        headers = kwargs.pop("headers", {"X-Admin-Key": ADMIN_KEY})
        return self.client.put(f"/api/v1/browser-sessions/{site}", json=body, headers=headers)


def _ok(request: httpx.Request) -> httpx.Response:
    if request.url.host == "x.com":
        return httpx.Response(200, json={"screen_name": "operator"})
    return httpx.Response(200, json={"subscriptions": [], "publications": []})


def _configure_bao(monkeypatch: pytest.MonkeyPatch, configured: bool) -> None:
    for name in ("BAO_ADDR", "BAO_TOKEN", "BAO_ROLE_ID", "BAO_SECRET_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("BAO_MOUNT_PATH", raising=False)
    monkeypatch.delenv("BAO_SECRET_PATH", raising=False)
    if configured:
        monkeypatch.setenv("BAO_ADDR", "http://127.0.0.1:8200")
        monkeypatch.setenv("BAO_TOKEN", "bao-token-not-a-cookie")
        # The client library is optional ('.[vault]'); the fake client stands in.
        monkeypatch.setattr(bao_secrets, "hvac", SimpleNamespace())
    # Treat the boot-time OpenBao load as done with an empty cache: no network.
    monkeypatch.setattr(bao_secrets, "_bao_checked", True)
    monkeypatch.setattr(bao_secrets, "_bao_cache", {})


@pytest.fixture
def make_harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., Harness]]:
    from src.config.settings import get_settings

    opened: list[TestClient] = []

    def build(
        *,
        environment: str = "production",
        admin_key: str | None = ADMIN_KEY,
        app_secret: str | None = APP_SECRET,
        bao_configured: bool = True,
        kv: FakeKvV2Adapter | None = None,
        handler: Callable[[httpx.Request], httpx.Response] = _ok,
    ) -> Harness:
        monkeypatch.setenv("ENVIRONMENT", environment)
        monkeypatch.setenv("WORKER_ENABLED", "false")
        for name, value in (("ADMIN_API_KEY", admin_key), ("APP_SECRET_KEY", app_secret)):
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)
        _configure_bao(monkeypatch, bao_configured)
        get_settings.cache_clear()
        reset_credential_provider()

        audit_rows: list[dict[str, Any]] = []
        monkeypatch.setattr(
            "src.api.middleware.audit._default_writer", lambda **row: audit_rows.append(row)
        )
        monkeypatch.setattr(
            browser_session_routes,
            "browser_session_rate_limiter",
            EndpointRateLimiter(max_requests=100, window_seconds=60),
        )

        fake_kv = kv if kv is not None else FakeKvV2Adapter(SIBLINGS)
        monkeypatch.setattr(
            secret_sinks,
            "_default_bao_client",
            lambda: SimpleNamespace(adapter=fake_kv, is_authenticated=lambda: True),
        )

        harness_calls: list[httpx.Request] = []

        def recording(request: httpx.Request) -> httpx.Response:
            harness_calls.append(request)
            return handler(request)

        monkeypatch.setattr(
            browser_session_sync,
            "new_validation_client",
            lambda: httpx.Client(transport=httpx.MockTransport(recording)),
        )

        from src.api.app import app

        client = TestClient(app, base_url="https://testserver")
        client.__enter__()
        opened.append(client)
        return Harness(client=client, kv=fake_kv, audit_rows=audit_rows, http_calls=harness_calls)

    yield build

    for client in opened:
        client.__exit__(None, None, None)
    get_settings.cache_clear()
    reset_credential_provider()


def _row_for(harness: Harness, site: str) -> dict[str, Any]:
    rows = [r for r in harness.audit_rows if r["path"] == f"/api/v1/browser-sessions/{site}"]
    assert rows, "no audit row for the browser-session request"
    return rows[-1]


# ─── Authentication and audit ──────────────────────────────────────────


def test_missing_admin_key_is_401_and_audited(make_harness: Callable[..., Harness]) -> None:
    harness = make_harness()

    response = harness.put("x", X_BODY, headers={})

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    row = _row_for(harness, "x")
    assert row["status_code"] == 401
    assert row["admin_key_fp"] is None
    assert row["notes"]["auth_failure"] == "missing_key"
    assert harness.kv.requests == []
    assert harness.http_calls == []
    _assert_no_sentinel(response.text, json.dumps(harness.audit_rows, default=str))


def test_invalid_admin_key_is_403_and_audited_with_fingerprint(
    make_harness: Callable[..., Harness],
) -> None:
    harness = make_harness()
    wrong = "not-the-admin-key"

    response = harness.put("x", X_BODY, headers={"X-Admin-Key": wrong})

    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")
    row = _row_for(harness, "x")
    assert row["status_code"] == 403
    assert row["admin_key_fp"] == hashlib.sha256(wrong.encode()).hexdigest()[-8:]
    assert row["notes"]["auth_failure"] == "invalid_key"
    assert harness.kv.requests == []
    _assert_no_sentinel(response.text, json.dumps(harness.audit_rows, default=str))


def test_web_session_cookie_is_not_enough(make_harness: Callable[..., Harness]) -> None:
    """A logged-in browser tab must not be able to write credentials."""
    from src.api.auth_routes import _COOKIE_NAME, _create_jwt

    harness = make_harness()
    harness.client.cookies.set(_COOKIE_NAME, _create_jwt(APP_SECRET))

    response = harness.put("substack", SUBSTACK_BODY, headers={})

    assert response.status_code == 401
    assert "X-Admin-Key" in response.json()["detail"]
    assert harness.kv.requests == []
    assert harness.http_calls == []


def test_unauthenticated_development_mode_is_refused(
    make_harness: Callable[..., Harness],
) -> None:
    """The dev no-key bypass admits the web UI, never a credential write."""
    harness = make_harness(environment="development", admin_key=None, app_secret=None)

    response = harness.put("x", X_BODY, headers={"X-Admin-Key": "anything"})

    assert response.status_code == 401
    assert harness.kv.requests == []
    assert harness.http_calls == []


# ─── Happy path ────────────────────────────────────────────────────────


def test_x_session_is_validated_then_patched_once(
    make_harness: Callable[..., Harness], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    harness = make_harness()
    before = copy.deepcopy(harness.kv.data)

    response = harness.put("x", X_BODY)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["site"] == "x"
    assert body["keys_written"] == [
        "X_AUTH_TOKEN",
        "X_CT0",
        "X_AUTH_TOKEN_SAVED_AT",
        "X_CT0_SAVED_AT",
    ]

    # One validation request, carrying the pair.
    assert len(harness.http_calls) == 1
    call = harness.http_calls[0]
    assert call.url.host == "x.com"
    assert call.headers["x-csrf-token"] == X_CT0_SENTINEL

    # Exactly one merge-PATCH with both keys and one saved_at.
    assert len(harness.kv.requests) == 1
    method, url, kwargs = harness.kv.requests[0]
    assert (method, url) == ("PATCH", "/v1/secret/data/newsletter")
    patched = kwargs["json"]["data"]
    assert patched == {
        "X_AUTH_TOKEN": X_AUTH_SENTINEL,
        "X_CT0": X_CT0_SENTINEL,
        "X_AUTH_TOKEN_SAVED_AT": patched["X_CT0_SAVED_AT"],
        "X_CT0_SAVED_AT": patched["X_CT0_SAVED_AT"],
    }
    assert body["saved_at"].replace("Z", "+00:00") == patched["X_CT0_SAVED_AT"]

    # Every other key at secret/newsletter is byte-identical.
    for key, value in before.items():
        if key not in patched:
            assert harness.kv.data[key].encode() == value.encode()
    assert set(harness.kv.data) == set(before) | set(patched)

    # This process sees the new pair and the same saved_at without a restart.
    cache = bao_secrets.get_bao_secrets()
    assert cache["X_AUTH_TOKEN"] == X_AUTH_SENTINEL
    assert cache["X_CT0"] == X_CT0_SENTINEL
    assert cache["X_CT0_SAVED_AT"] == patched["X_CT0_SAVED_AT"]

    row = _row_for(harness, "x")
    assert row["status_code"] == 200
    assert row["operation"] == "browser_sessions.sync"
    assert row["admin_key_fp"] == hashlib.sha256(ADMIN_KEY.encode()).hexdigest()[-8:]
    assert row["notes"]["site"] == "x"
    assert row["notes"]["outcome"] == "written"
    assert "X_CT0" in row["notes"]["keys"]

    _assert_no_sentinel(response.text, caplog.text, json.dumps(harness.audit_rows, default=str))


def test_substack_session_patches_only_its_key(
    make_harness: Callable[..., Harness], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    harness = make_harness()

    response = harness.put("substack", SUBSTACK_BODY)

    assert response.status_code == 200, response.text
    assert response.json()["keys_written"] == [
        "SUBSTACK_SESSION_COOKIE",
        "SUBSTACK_SESSION_COOKIE_SAVED_AT",
    ]
    assert len(harness.http_calls) == 1
    assert harness.http_calls[0].url.host == "substack.com"
    assert len(harness.kv.requests) == 1
    patched = harness.kv.requests[0][2]["json"]["data"]
    assert set(patched) == {"SUBSTACK_SESSION_COOKIE", "SUBSTACK_SESSION_COOKIE_SAVED_AT"}
    for key, value in SIBLINGS.items():
        assert harness.kv.data[key] == value
    _assert_no_sentinel(response.text, caplog.text, json.dumps(harness.audit_rows, default=str))


# ─── Refusals that write nothing ───────────────────────────────────────


@pytest.mark.parametrize(
    ("upstream", "reason"),
    [
        (httpx.Response(401, json={"errors": [{"code": 32}]}), "http_status"),
        (httpx.Response(302, headers={"location": "https://x.com/login"}), "http_status"),
        (httpx.Response(200, text="<html>log in</html>"), "not_json"),
        (httpx.Response(200, json={"screen_name": ""}), "unexpected_json"),
    ],
)
def test_invalid_session_is_422_and_writes_nothing(
    make_harness: Callable[..., Harness],
    caplog: pytest.LogCaptureFixture,
    upstream: httpx.Response,
    reason: str,
) -> None:
    caplog.set_level(logging.DEBUG)
    harness = make_harness(handler=lambda request: upstream)

    response = harness.put("x", X_BODY)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["code"] == "session_invalid"
    assert problem["reason"] == reason
    assert "Nothing was written" in problem["detail"]
    assert len(harness.http_calls) == 1
    assert harness.kv.requests == []
    assert bao_secrets.get_bao_secrets() == {}
    assert _row_for(harness, "x")["notes"]["outcome"] == "session_invalid"
    _assert_no_sentinel(response.text, caplog.text, json.dumps(harness.audit_rows, default=str))


@pytest.mark.parametrize("status", [429, 503])
def test_site_failure_is_502_not_an_invalid_session(
    make_harness: Callable[..., Harness], status: int
) -> None:
    harness = make_harness(handler=lambda request: httpx.Response(status))

    response = harness.put("substack", SUBSTACK_BODY)

    assert response.status_code == 502
    assert response.json()["code"] == "session_validation_unavailable"
    assert harness.kv.requests == []


def test_unreachable_site_is_502_and_writes_nothing(
    make_harness: Callable[..., Harness], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    harness = make_harness(handler=refuse)

    response = harness.put("x", X_BODY)

    assert response.status_code == 502
    assert response.json()["code"] == "session_validation_unavailable"
    assert "ConnectError" in response.json()["detail"]
    assert harness.kv.requests == []
    _assert_no_sentinel(response.text, caplog.text)


def test_openbao_unconfigured_is_typed_503_without_any_request(
    make_harness: Callable[..., Harness], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    harness = make_harness(bao_configured=False)

    response = harness.put("x", X_BODY)

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["code"] == "openbao_not_configured"
    assert "BAO_ADDR" in problem["missing"]
    assert "OpenBao" in problem["detail"]
    assert harness.http_calls == []
    assert harness.kv.requests == []
    assert _row_for(harness, "x")["notes"]["outcome"] == "openbao_not_configured"
    _assert_no_sentinel(response.text, caplog.text)


def test_openbao_refusal_is_502_with_a_value_free_hint(
    make_harness: Callable[..., Harness], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    kv = FakeKvV2Adapter(SIBLINGS, error=Forbidden(f"permission denied {X_AUTH_SENTINEL}"))
    harness = make_harness(kv=kv)

    response = harness.put("x", X_BODY)

    assert response.status_code == 502
    problem = response.json()
    assert problem["code"] == "openbao_write_failed"
    assert "patch" in problem["detail"]
    assert len(kv.requests) == 1
    assert kv.data == SIBLINGS
    assert bao_secrets.get_bao_secrets() == {}
    _assert_no_sentinel(response.text, caplog.text, json.dumps(harness.audit_rows, default=str))


# ─── Request-body contract ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("site", "body"),
    [
        ("x", {**X_BODY, "twid": SUBSTACK_SENTINEL}),
        ("x", {"auth_token": X_AUTH_SENTINEL}),
        ("substack", {**SUBSTACK_BODY, "X_AUTH_TOKEN": X_AUTH_SENTINEL}),
        ("substack", {"substack.sid": SUBSTACK_SENTINEL}),
        ("x", {"auth_token": X_AUTH_SENTINEL + ";", "ct0": X_CT0_SENTINEL}),
        ("x", {"auth_token": X_AUTH_SENTINEL, "ct0": X_CT0_SENTINEL + "\r\nx-evil: 1"}),
        ("x", {"auth_token": X_AUTH_SENTINEL + "\n", "ct0": X_CT0_SENTINEL}),
        ("substack", {"substack_sid": SUBSTACK_SENTINEL + "\u00e9"}),
        ("substack", {"substack_sid": ""}),
        ("substack", {"substack_sid": SUBSTACK_SENTINEL * 200}),
    ],
)
def test_bad_body_is_422_without_echoing_input(
    make_harness: Callable[..., Harness],
    caplog: pytest.LogCaptureFixture,
    site: str,
    body: dict[str, str],
) -> None:
    caplog.set_level(logging.DEBUG)
    harness = make_harness()

    response = harness.put(site, body)

    assert response.status_code == 422, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "validation_error"
    assert harness.http_calls == []
    assert harness.kv.requests == []
    _assert_no_sentinel(response.text, caplog.text, json.dumps(harness.audit_rows, default=str))


def test_oversized_body_is_413(make_harness: Callable[..., Harness]) -> None:
    harness = make_harness()
    padded = json.dumps({**X_BODY, "pad": "a" * (browser_session_routes.MAX_BODY_BYTES + 1)})

    response = harness.client.put(
        "/api/v1/browser-sessions/x",
        content=padded,
        headers={"X-Admin-Key": ADMIN_KEY, "Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert harness.kv.requests == []
    _assert_no_sentinel(response.text)


def test_unknown_site_is_not_routed(make_harness: Callable[..., Harness]) -> None:
    harness = make_harness()

    response = harness.put("gmail", SUBSTACK_BODY)

    assert response.status_code in (404, 405)
    assert harness.kv.requests == []


def test_rate_limit_is_429(
    make_harness: Callable[..., Harness], monkeypatch: pytest.MonkeyPatch
) -> None:
    harness = make_harness()
    monkeypatch.setattr(
        browser_session_routes,
        "browser_session_rate_limiter",
        EndpointRateLimiter(max_requests=1, window_seconds=300),
    )

    assert harness.put("substack", SUBSTACK_BODY).status_code == 200
    response = harness.put("substack", SUBSTACK_BODY)

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) >= 1
    assert len(harness.kv.requests) == 1


# ─── OpenAPI ───────────────────────────────────────────────────────────


def test_openapi_marks_cookies_write_only_and_carries_no_examples() -> None:
    from src.api.app import app

    spec = app.openapi()
    paths = spec["paths"]
    assert set(paths["/api/v1/browser-sessions/x"]) == {"put"}
    assert set(paths["/api/v1/browser-sessions/substack"]) == {"put"}
    schemas = spec["components"]["schemas"]
    for name, fields in (
        ("XSessionSyncRequest", {"auth_token", "ct0"}),
        ("SubstackSessionSyncRequest", {"substack_sid"}),
    ):
        schema = schemas[name]
        assert schema["additionalProperties"] is False
        assert set(schema["properties"]) == fields
        for prop in schema["properties"].values():
            assert prop["writeOnly"] is True
            assert prop["format"] == "password"
            assert prop["maxLength"] == browser_session_routes.MAX_COOKIE_VALUE_LENGTH
    document = json.dumps(
        {
            "paths": {k: v for k, v in paths.items() if "browser-sessions" in k},
            "schemas": {
                k: schemas[k] for k in ("XSessionSyncRequest", "SubstackSessionSyncRequest")
            },
        }
    )
    assert '"example' not in document
    _assert_no_sentinel(json.dumps(spec))


def test_handlers_carry_the_audit_operation() -> None:
    for handler in (
        browser_session_routes.sync_x_session,
        browser_session_routes.sync_substack_session,
    ):
        assert handler.__audit_operation__ == "browser_sessions.sync"
