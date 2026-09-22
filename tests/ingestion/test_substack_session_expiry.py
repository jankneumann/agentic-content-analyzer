"""A dead Substack session fails the run closed with ``session_expired``.

Network-free: every Substack answer comes from an ``httpx.MockTransport`` and
the substack-api library path is stubbed. No test sends or prints a real cookie.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

import src.config.bao_secrets as bao_mod
import src.config.credentials as credentials_mod
from src.config.credentials import SUBSTACK_SESSION_COOKIE, CredentialProvider
from src.config.sources import SubstackSource
from src.ingestion.credential_failures import (
    CREDENTIALS_MISSING,
    SESSION_EXPIRED,
    SessionExpiredError,
)
from src.ingestion.registry import SOURCE_REGISTRY
from src.ingestion.result_sanitizer import (
    SAFE_INGESTION_DIAGNOSTIC_CODES,
    sanitize_ingestion_metadata,
)
from src.ingestion.substack import (
    SESSION_PROBE_URL,
    SUBSTACK_REFRESH_COMMAND,
    SubstackClient,
    SubstackContentIngestionService,
    is_dead_session_response,
)

DEAD_COOKIE = "sid-dead-value-aaa"
FRESH_COOKIE = "sid-fresh-value-bbb"
OVERRIDE_COOKIE = "sid-override-value-ccc"
ALL_COOKIES = (DEAD_COOKIE, FRESH_COOKIE, OVERRIDE_COOKIE)

PUBLICATION = "https://paid.substack.com"
ARCHIVE_URL = f"{PUBLICATION}/api/v1/archive"
SOURCE = SubstackSource(name="Paid", url=PUBLICATION)


# -- fakes -----------------------------------------------------------------


def _settings(cookie: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(substack_session_cookie=cookie, x_auth_token=None, x_ct0=None)


class _FakeBao:
    """In-memory OpenBao: ``remote`` is the KV path, ``cache`` the worker's copy."""

    def __init__(self, cookie: str | None) -> None:
        self.remote: dict[str, str] = {SUBSTACK_SESSION_COOKIE: cookie} if cookie else {}
        self.cache: dict[str, str] = dict(self.remote)
        self.refreshes = 0

    def read(self) -> dict[str, str]:
        return dict(self.cache)

    def refresh(self, *, min_interval_s: float = 0.0) -> bool:
        self.refreshes += 1
        changed = self.cache != self.remote
        self.cache = dict(self.remote)
        return changed

    def provider(self) -> CredentialProvider:
        return CredentialProvider(
            settings_factory=_settings,
            bao_reader=self.read,
            bao_refresher=self.refresh,
        )


def _sid(request: httpx.Request) -> str | None:
    for part in request.headers.get("cookie", "").split(";"):
        name, _, value = part.strip().partition("=")
        if name == "substack.sid":
            return value
    return None


type Answer = Callable[[httpx.Request], httpx.Response]


class _Substack:
    """Mock transport: ``dead(sid)`` decides whether a cookie is refused, and how."""

    def __init__(self, dead: Callable[[str | None], bool], refusal: Answer) -> None:
        self.dead = dead
        self.refusal = refusal
        self.calls: list[tuple[str, str | None]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        sid = _sid(request)
        self.calls.append((str(request.url.copy_with(query=None)), sid))
        if sid is not None and self.dead(sid):
            return self.refusal(request)
        if str(request.url).startswith(SESSION_PROBE_URL):
            return httpx.Response(200, json={"subscriptions": [], "publications": []})
        return httpx.Response(200, json=[_post(1), _post(2)])


def _post(post_id: int) -> dict[str, Any]:
    return {
        "id": post_id,
        "title": f"Paid post {post_id}",
        "canonical_url": f"{PUBLICATION}/p/post-{post_id}",
        "body_html": f"<p>Full paid body {post_id}</p>",
        "post_date": "2026-09-20T10:00:00Z",
    }


def login_redirect(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(302, headers={"location": "https://substack.com/sign-in?redirect=%2F"})


def html_login_page(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": "text/html; charset=utf-8"},
        text="<html><body><form action='/sign-in'>Sign in</form></body></html>",
    )


def unauthorized(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(401, json={"error": "Not authorized"})


def _client(
    provider: CredentialProvider, transport: Answer, *, cookie: str | None = None
) -> SubstackClient:
    return SubstackClient(
        session_cookie=cookie,
        credentials=provider,
        http_client=httpx.Client(transport=httpx.MockTransport(transport)),
    )


def _service(provider: CredentialProvider, transport: Answer) -> SubstackContentIngestionService:
    service = SubstackContentIngestionService(credentials=provider)
    service.client.close()
    service.client = _client(provider, transport)
    return service


@contextmanager
def _captured_logs() -> Iterator[list[logging.LogRecord]]:
    records: list[logging.LogRecord] = []

    class _Handler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Handler(level=logging.DEBUG)
    root = logging.getLogger("src")
    previous = root.level
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    try:
        yield records
    finally:
        root.removeHandler(handler)
        root.setLevel(previous)


def _assert_no_cookie(*texts: object) -> None:
    blob = "\n".join(str(text) for text in texts)
    for value in ALL_COOKIES:
        assert value not in blob


def _log_blob(records: list[logging.LogRecord]) -> str:
    return "\n".join(f"{r.getMessage()} {r.args!r}" for r in records)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    bao_mod.clear_bao_cache()
    monkeypatch.setattr(credentials_mod, "_default_provider", None)
    yield
    bao_mod.clear_bao_cache()


@pytest.fixture
def no_library_fetch() -> Iterator[MagicMock]:
    """The substack-api path is unauthenticated; force the cookie-bearing fallback."""
    with patch.object(SubstackClient, "_fetch_posts_from_api", return_value=None) as mocked:
        yield mocked


# -- the predicate -----------------------------------------------------------


@pytest.mark.parametrize(
    ("response", "dead"),
    [
        (httpx.Response(401), True),
        (httpx.Response(403), True),
        (httpx.Response(403, headers={"cf-mitigated": "challenge"}), False),
        (httpx.Response(302, headers={"location": "https://substack.com/sign-in?r=1"}), True),
        (httpx.Response(302, headers={"location": "/sign-in"}), True),
        (httpx.Response(301, headers={"location": "https://substack.com/account/login"}), True),
        (httpx.Response(301, headers={"location": "https://paid.example.com/api/v1/x"}), False),
        (httpx.Response(302, headers={"location": "https://substack.com/sign-into-art"}), False),
        (httpx.Response(200, headers={"content-type": "text/html"}, text="<html/>"), True),
        (httpx.Response(200, json={"ok": True}), False),
        (httpx.Response(404), False),
        (httpx.Response(429), False),
        (httpx.Response(503, headers={"content-type": "text/html"}), False),
    ],
)
def test_dead_session_predicate_is_conservative(response: httpx.Response, dead: bool) -> None:
    assert is_dead_session_response(response) is dead


# -- refresh once, retry once, then fail closed ------------------------------


@pytest.mark.parametrize("refusal", [login_redirect, html_login_page, unauthorized])
def test_refresh_retry_then_session_expired(refusal: Answer, no_library_fetch: MagicMock) -> None:
    bao = _FakeBao(DEAD_COOKIE)
    bao.remote[SUBSTACK_SESSION_COOKIE] = FRESH_COOKIE  # rotated, but also refused
    provider = bao.provider()
    substack = _Substack(dead=lambda sid: True, refusal=refusal)
    service = _service(provider, substack)

    with (
        _captured_logs() as records,
        patch("src.ingestion.substack.get_db") as get_db,
    ):
        response = service.ingest_content(sources=[SOURCE])
    service.close()

    assert bao.refreshes == 1
    assert substack.calls == [(SESSION_PROBE_URL, DEAD_COOKIE), (SESSION_PROBE_URL, FRESH_COOKIE)]
    assert response.status == "error"
    assert response.items_ingested == 0
    assert [error.code for error in response.errors] == [SESSION_EXPIRED]
    get_db.assert_not_called()  # zero rows: persistence never opened
    no_library_fetch.assert_not_called()  # no source was fetched after the refusal

    message = response.errors[0].message
    assert "substack.sid" in message
    assert SUBSTACK_REFRESH_COMMAND in message
    _assert_no_cookie(response.model_dump_json(), _log_blob(records))

    metadata = provider.metadata(SUBSTACK_SESSION_COOKIE)
    assert metadata.rejected_at is not None
    assert metadata.last_verified_at is None


def test_unchanged_cookie_after_refresh_fails_without_a_second_request() -> None:
    bao = _FakeBao(DEAD_COOKIE)  # OpenBao still holds the same dead cookie
    provider = bao.provider()
    substack = _Substack(dead=lambda sid: True, refusal=unauthorized)
    client = _client(provider, substack)

    with pytest.raises(SessionExpiredError) as excinfo:
        client.verify_session()
    client.close()

    assert bao.refreshes == 1
    assert substack.calls == [(SESSION_PROBE_URL, DEAD_COOKIE)]
    assert excinfo.value.code == SESSION_EXPIRED
    assert excinfo.value.credential_label == "substack.sid"
    _assert_no_cookie(str(excinfo.value), repr(excinfo.value), excinfo.value.args)


def test_session_dying_mid_run_still_persists_zero_rows(no_library_fetch: MagicMock) -> None:
    """The probe is inconclusive; a later archive answers with a sign-in redirect."""
    provider = _FakeBao(DEAD_COOKIE).provider()

    def answer(request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(SESSION_PROBE_URL):
            return httpx.Response(503)
        if str(request.url).startswith(ARCHIVE_URL):
            return httpx.Response(200, json=[_post(1)])
        return login_redirect(request)

    service = _service(provider, answer)
    second = SubstackSource(name="Second", url="https://second.substack.com")

    with patch("src.ingestion.substack.get_db") as get_db:
        response = service.ingest_content(sources=[SOURCE, second])
    service.close()

    assert response.status == "error"
    assert response.items_ingested == 0
    assert [error.code for error in response.errors] == [SESSION_EXPIRED]
    get_db.assert_not_called()


def test_explicit_override_is_not_refreshed_or_recorded_on_the_provider() -> None:
    bao = _FakeBao(FRESH_COOKIE)
    provider = bao.provider()
    substack = _Substack(dead=lambda sid: sid == OVERRIDE_COOKIE, refusal=unauthorized)
    client = _client(provider, substack, cookie=OVERRIDE_COOKIE)

    with pytest.raises(SessionExpiredError):
        client.verify_session()
    client.close()

    assert bao.refreshes == 0
    assert substack.calls == [(SESSION_PROBE_URL, OVERRIDE_COOKIE)]
    assert provider.metadata(SUBSTACK_SESSION_COOKIE).rejected_at is None


def test_requests_without_a_cookie_are_never_judged() -> None:
    provider = _FakeBao(None).provider()
    substack = _Substack(dead=lambda sid: True, refusal=unauthorized)
    client = _client(provider, substack)
    try:
        assert client.verify_session() is False
        response = client._get_with_session(SESSION_PROBE_URL)
    finally:
        client.close()
    assert response.status_code == 200  # logged out is the expected state
    assert substack.calls == [(SESSION_PROBE_URL, None)]


# -- recovery ------------------------------------------------------------------


def _fake_db() -> tuple[MagicMock, Callable[[], Any]]:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    @contextmanager
    def get_db() -> Iterator[MagicMock]:
        yield db

    return db, get_db


def test_refreshed_cookie_recovers_the_run_and_is_marked_verified(
    no_library_fetch: MagicMock,
) -> None:
    bao = _FakeBao(DEAD_COOKIE)
    bao.remote[SUBSTACK_SESSION_COOKIE] = FRESH_COOKIE
    provider = bao.provider()
    substack = _Substack(dead=lambda sid: sid == DEAD_COOKIE, refusal=unauthorized)
    service = _service(provider, substack)
    db, get_db = _fake_db()

    with (
        _captured_logs() as records,
        patch("src.ingestion.substack.get_db", get_db),
        patch("src.ingestion.substack.find_existing_substack_content", return_value=None),
        patch("src.services.indexing.index_content"),
    ):
        response = service.ingest_content(sources=[SOURCE])
    service.close()

    assert bao.refreshes == 1
    assert response.status == "ok"
    assert response.items_ingested == 2
    assert db.add.call_count == 2
    assert substack.calls[:2] == [
        (SESSION_PROBE_URL, DEAD_COOKIE),
        (SESSION_PROBE_URL, FRESH_COOKIE),
    ]
    assert substack.calls[2] == (ARCHIVE_URL, FRESH_COOKIE)

    metadata = provider.metadata(SUBSTACK_SESSION_COOKIE)
    assert metadata.last_verified_at is not None
    assert metadata.rejected_at is None
    _assert_no_cookie(response.model_dump_json(), _log_blob(records))


def test_public_archive_success_does_not_verify_the_session() -> None:
    provider = _FakeBao(FRESH_COOKIE).provider()
    substack = _Substack(dead=lambda sid: False, refusal=unauthorized)
    client = _client(provider, substack)
    try:
        assert client._fetch_posts_from_http(PUBLICATION, 2)
        assert provider.metadata(SUBSTACK_SESSION_COOKIE).last_verified_at is None
        assert client.verify_session() is True
    finally:
        client.close()
    assert provider.metadata(SUBSTACK_SESSION_COOKIE).last_verified_at is not None


def test_subscription_sync_raises_instead_of_returning_no_subscriptions() -> None:
    """An empty list would make sync rewrite substack.yaml with zero sources."""
    provider = _FakeBao(DEAD_COOKIE).provider()
    client = _client(provider, _Substack(dead=lambda sid: True, refusal=login_redirect))
    try:
        with pytest.raises(SessionExpiredError):
            client.fetch_subscriptions()
    finally:
        client.close()


# -- no cookie: public posts still arrive, flagged on the envelope -------------


def test_cookie_less_run_keeps_public_posts_and_warns(no_library_fetch: MagicMock) -> None:
    provider = _FakeBao(None).provider()
    substack = _Substack(dead=lambda sid: True, refusal=unauthorized)
    service = _service(provider, substack)
    _db, get_db = _fake_db()

    with (
        patch("src.ingestion.substack.get_db", get_db),
        patch("src.ingestion.substack.find_existing_substack_content", return_value=None),
        patch("src.services.indexing.index_content"),
    ):
        response = service.ingest_content(sources=[SOURCE])
    service.close()

    assert response.status == "ok"
    assert response.items_ingested == 2
    assert [warning.code for warning in response.warnings] == [CREDENTIALS_MISSING]
    assert all(url != SESSION_PROBE_URL for url, _ in substack.calls)  # no probe without cookie


# -- readiness -----------------------------------------------------------------


def test_readiness_reads_the_provider_live(monkeypatch: pytest.MonkeyPatch) -> None:
    bao = _FakeBao(None)
    provider = bao.provider()
    monkeypatch.setattr(credentials_mod, "_default_provider", provider)
    descriptor = SOURCE_REGISTRY.get("substack")

    missing = descriptor.resolve_readiness(SOURCE)
    assert (missing.ready, missing.code) == (False, CREDENTIALS_MISSING)

    bao.remote[SUBSTACK_SESSION_COOKIE] = bao.cache[SUBSTACK_SESSION_COOKIE] = DEAD_COOKIE
    assert descriptor.resolve_readiness(SOURCE).ready is True

    client = _client(provider, _Substack(dead=lambda sid: True, refusal=login_redirect))
    with pytest.raises(SessionExpiredError):
        client.verify_session()
    client.close()
    expired = descriptor.resolve_readiness(SOURCE)
    assert (expired.ready, expired.code) == (False, SESSION_EXPIRED)

    # A fresh cookie patched into the cache flips readiness with no restart.
    bao.cache[SUBSTACK_SESSION_COOKIE] = FRESH_COOKIE
    assert descriptor.resolve_readiness(SOURCE).ready is True


def test_readiness_flips_after_an_openbao_refresh_without_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real bao_secrets cache behind the process-wide provider (fake hvac client)."""
    monkeypatch.setenv("BAO_ADDR", "http://bao.test:8200")
    monkeypatch.setenv("BAO_TOKEN", "fake-root-token")
    monkeypatch.delenv("BAO_ROLE_ID", raising=False)
    remote = {SUBSTACK_SESSION_COOKIE: DEAD_COOKIE}
    hvac_client = MagicMock()
    hvac_client.is_authenticated.return_value = True
    hvac_client.secrets.kv.v2.read_secret_version.side_effect = lambda **_: {
        "data": {"data": dict(remote)}
    }
    hvac = MagicMock()
    hvac.Client.return_value = hvac_client
    provider = CredentialProvider(settings_factory=_settings)
    monkeypatch.setattr(credentials_mod, "_default_provider", provider)
    descriptor = SOURCE_REGISTRY.get("substack")

    with patch("src.config.bao_secrets.hvac", hvac):
        client = _client(provider, _Substack(dead=lambda sid: True, refusal=login_redirect))
        with pytest.raises(SessionExpiredError):
            client.verify_session()
        client.close()
        assert descriptor.resolve_readiness(SOURCE).code == SESSION_EXPIRED

        remote[SUBSTACK_SESSION_COOKIE] = FRESH_COOKIE
        assert provider.refresh(min_interval_s=0) is True
        readiness = descriptor.resolve_readiness(SOURCE)

    assert (readiness.ready, readiness.code) == (True, None)


# -- the durable result keeps the stable code ----------------------------------


def test_session_codes_survive_the_durable_projection() -> None:
    error = SessionExpiredError(
        source="substack",
        credential_label="substack.sid",
        refresh_command=SUBSTACK_REFRESH_COMMAND,
    ).to_ingestion_error()
    projection = sanitize_ingestion_metadata(
        errors=[error.model_dump()],
        warnings=[{"code": CREDENTIALS_MISSING, "message": "missing"}],
    )

    assert {SESSION_EXPIRED, CREDENTIALS_MISSING} <= SAFE_INGESTION_DIAGNOSTIC_CODES
    assert projection["errors"][0]["code"] == SESSION_EXPIRED
    assert projection["warnings"][0]["code"] == CREDENTIALS_MISSING
