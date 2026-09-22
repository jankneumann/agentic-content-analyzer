"""The Substack adapter resolves substack.sid through the live CredentialProvider."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

import src.config.bao_secrets as bao_mod
from src.config.credentials import SUBSTACK_SESSION_COOKIE, CredentialProvider
from src.ingestion.substack import SubstackClient, SubstackContentIngestionService

BOOT_COOKIE = "sid-boot-value-aaa"
ROTATED_COOKIE = "sid-rotated-value-bbb"
OVERRIDE_COOKIE = "sid-override-value-ccc"


@pytest.fixture(autouse=True)
def _isolate() -> Iterator[None]:
    bao_mod.clear_bao_cache()
    yield
    bao_mod.clear_bao_cache()


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class _Recorder:
    """httpx MockTransport handler that records the substack.sid of each request."""

    def __init__(self) -> None:
        self.sids: list[str | None] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        cookie_header = request.headers.get("cookie", "")
        sids = [
            part.split("=", 1)[1]
            for part in (p.strip() for p in cookie_header.split(";"))
            if part.startswith("substack.sid=")
        ]
        assert len(sids) <= 1, "more than one substack.sid sent"
        self.sids.append(sids[0] if sids else None)
        return httpx.Response(200, json=[{"id": 1, "title": "Post"}])


def _fake_bao(data: dict[str, str]) -> tuple[MagicMock, dict[str, str]]:
    client = MagicMock()
    client.is_authenticated.return_value = True
    client.secrets.kv.v2.read_secret_version.side_effect = lambda **_: {
        "data": {"data": dict(data)}
    }
    hvac = MagicMock()
    hvac.Client.return_value = client
    return hvac, data


def _settings(cookie: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(substack_session_cookie=cookie, x_auth_token=None, x_ct0=None)


def test_rotated_cookie_reaches_client_between_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BAO_ADDR", "http://bao.test:8200")
    monkeypatch.setenv("BAO_TOKEN", "fake-root-token")
    monkeypatch.delenv("BAO_ROLE_ID", raising=False)
    hvac, data = _fake_bao({SUBSTACK_SESSION_COOKIE: BOOT_COOKIE})
    recorder = _Recorder()
    provider = CredentialProvider(settings_factory=_settings)

    handler = _ListHandler()
    src_logger = logging.getLogger("src")
    previous = src_logger.level
    src_logger.setLevel(logging.DEBUG)
    src_logger.addHandler(handler)
    try:
        with patch("src.config.bao_secrets.hvac", hvac):
            client = SubstackClient(
                credentials=provider,
                http_client=httpx.Client(transport=httpx.MockTransport(recorder)),
            )
            try:
                assert client._fetch_posts_from_http("https://one.substack.com", 1)

                data[SUBSTACK_SESSION_COOKIE] = ROTATED_COOKIE
                assert provider.refresh(min_interval_s=0) is True

                assert client._fetch_posts_from_http("https://one.substack.com", 1)
            finally:
                client.close()
    finally:
        src_logger.removeHandler(handler)
        src_logger.setLevel(previous)

    assert recorder.sids[-2:] == [BOOT_COOKIE, ROTATED_COOKIE]
    blob = "\n".join(f"{r.getMessage()} {r.args!r}" for r in handler.records)
    assert "substack.session_cookie_changed" in blob, "log capture is not wired"
    for value in (BOOT_COOKIE, ROTATED_COOKIE):
        assert value not in blob


def test_settings_fallback_and_explicit_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BAO_ADDR", raising=False)
    recorder = _Recorder()
    provider = CredentialProvider(settings_factory=lambda: _settings(BOOT_COOKIE))

    fallback = SubstackClient(
        credentials=provider,
        http_client=httpx.Client(transport=httpx.MockTransport(recorder)),
    )
    override = SubstackClient(
        session_cookie=OVERRIDE_COOKIE,
        credentials=provider,
        http_client=httpx.Client(transport=httpx.MockTransport(recorder)),
    )
    try:
        fallback._fetch_posts_from_http("https://one.substack.com", 1)
        override._fetch_posts_from_http("https://one.substack.com", 1)
    finally:
        fallback.close()
        override.close()
    assert recorder.sids == [BOOT_COOKIE, OVERRIDE_COOKIE]


def test_missing_cookie_sends_none_and_skips_subscription_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BAO_ADDR", raising=False)
    recorder = _Recorder()
    provider = CredentialProvider(settings_factory=lambda: _settings(""))
    client = SubstackClient(
        credentials=provider,
        http_client=httpx.Client(transport=httpx.MockTransport(recorder)),
    )
    try:
        assert client.session_cookie is None
        assert client.fetch_subscriptions() == []
        client._fetch_posts_from_http("https://one.substack.com", 1)
    finally:
        client.close()
    assert recorder.sids == [None]


def test_ingestion_service_uses_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BAO_ADDR", raising=False)
    provider = CredentialProvider(settings_factory=lambda: _settings(BOOT_COOKIE))
    service = SubstackContentIngestionService(credentials=provider)
    try:
        assert service.client.session_cookie == BOOT_COOKIE
    finally:
        service.close()


def test_adapter_source_does_not_read_frozen_settings_cookie() -> None:
    source = (Path(__file__).resolve().parents[2] / "src/ingestion/substack.py").read_text()
    assert "settings.substack_session_cookie" not in source
