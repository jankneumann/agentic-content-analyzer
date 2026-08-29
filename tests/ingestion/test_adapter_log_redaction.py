"""Adapter logs must not carry configured-source locators or exception payloads."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.config.sources import (
    RSSSource,
    YouTubePlaylistSource,
    configured_source_public_key,
    source_key,
)
from src.ingestion.log_redaction import (
    UNKEYED_SOURCE,
    adapter_log_extra,
    log_error_type,
    log_source_key,
)
from src.ingestion.result import use_public_source_keys
from src.ingestion.rss import RSSClient
from src.ingestion.youtube import YouTubeClient, YouTubeContentIngestionService

HOSTILE_URL = "https://user:p4ssw0rd@feeds.example.com/secret-feed?token=abc123"
HOSTILE_MAILBOX = "imap://owner:mailbox-secret@mail.example.com/INBOX"
HOSTILE_PLAYLIST_ID = "PLprivatePlaylistId123"
HOSTILE_EXCEPTION = "ANTHROPIC_API_KEY=sk-ant-secret failed contacting https://api.anthropic.com"
SOURCE_SECRET = "configured-source-key-secret-for-tests-xx"


def _log_blob(caplog: pytest.LogCaptureFixture) -> str:
    parts: list[str] = [caplog.text]
    for record in caplog.records:
        parts.append(record.getMessage())
        for key, value in record.__dict__.items():
            if key in {"source_key", "code", "error_type", "msg", "message"}:
                parts.append(str(value))
    return "\n".join(parts)


def _assert_no_secrets(blob: str) -> None:
    for secret in (
        HOSTILE_URL,
        HOSTILE_MAILBOX,
        HOSTILE_PLAYLIST_ID,
        HOSTILE_EXCEPTION,
        "p4ssw0rd",
        "mailbox-secret",
        "sk-ant-secret",
        "token=abc123",
        "feeds.example.com",
        "mail.example.com",
    ):
        assert secret not in blob, f"secret leaked into logs: {secret!r}\n{blob}"


class TestLogRedactionHelpers:
    def test_accepts_opaque_source_keys_only(self):
        assert log_source_key("src_0123456789abcdef0123") == "src_0123456789abcdef0123"
        assert log_source_key(HOSTILE_URL) == UNKEYED_SOURCE
        assert log_source_key(HOSTILE_MAILBOX) == UNKEYED_SOURCE
        assert log_source_key(HOSTILE_PLAYLIST_ID) == UNKEYED_SOURCE
        assert log_source_key(None) == UNKEYED_SOURCE

    def test_error_type_is_class_name_only(self):
        assert log_error_type(RuntimeError(HOSTILE_EXCEPTION)) == "RuntimeError"
        extra = adapter_log_extra(
            source_key=HOSTILE_URL,
            code="playlist_ingest_error",
            error=RuntimeError(HOSTILE_EXCEPTION),
        )
        blob = " ".join(str(v) for v in extra.values())
        _assert_no_secrets(blob)
        assert extra["source_key"] == UNKEYED_SOURCE
        assert extra["code"] == "playlist_ingest_error"
        assert extra["error_type"] == "RuntimeError"


class TestRSSAdapterLogs:
    def test_fetch_logs_omit_url_credentials_and_redirect_target(self, caplog):
        source = RSSSource(url=HOSTILE_URL)
        public_key = configured_source_public_key(source, secret=SOURCE_SECRET)
        feed = MagicMock()
        feed.bozo = True
        feed.bozo_exception = ValueError(HOSTILE_EXCEPTION)
        feed.feed = MagicMock()
        feed.feed.title = "Public Title"
        feed.entries = []

        redirect = MagicMock()
        redirect.content = b"<rss></rss>"
        redirect.url = httpx.URL(HOSTILE_MAILBOX)
        redirect.raise_for_status = MagicMock()

        with (
            caplog.at_level(logging.INFO, logger="src.ingestion.rss"),
            patch("src.ingestion.rss.httpx.Client") as mock_http,
            patch("src.ingestion.rss.feedparser.parse", return_value=feed),
        ):
            mock_http.return_value.get.return_value = redirect
            client = RSSClient()
            client.fetch_content(feed_url=HOSTILE_URL, public_source_key=public_key)

        blob = _log_blob(caplog)
        _assert_no_secrets(blob)
        assert public_key in blob
        assert any(getattr(record, "source_key", None) == public_key for record in caplog.records)
        assert any(getattr(record, "code", None) == "feed_redirected" for record in caplog.records)
        assert any(getattr(record, "code", None) == "parse_error" for record in caplog.records)

    def test_http_error_logs_omit_exception_payload(self, caplog):
        with (
            caplog.at_level(logging.WARNING, logger="src.ingestion.rss"),
            patch("src.ingestion.rss.httpx.Client") as mock_http,
        ):
            mock_http.return_value.get.side_effect = httpx.ConnectError(
                HOSTILE_EXCEPTION,
                request=httpx.Request("GET", HOSTILE_URL),
            )
            client = RSSClient()
            _contents, result = client.fetch_content(feed_url=HOSTILE_URL)

        blob = _log_blob(caplog)
        _assert_no_secrets(blob)
        assert result.success is False
        # Durable result still carries the raw error; the sanitizer owns that surface.
        assert HOSTILE_EXCEPTION in (result.error or "")


class TestYouTubeAdapterLogs:
    @pytest.mark.asyncio
    async def test_playlist_failure_logs_omit_source_id_and_exception(self, caplog):
        source = YouTubePlaylistSource(id=HOSTILE_PLAYLIST_ID, name="Private Inbox")
        public_key = configured_source_public_key(source, secret=SOURCE_SECRET)

        with (
            caplog.at_level(logging.ERROR, logger="src.ingestion.youtube"),
            use_public_source_keys({source_key(source): public_key}),
            patch.object(YouTubeClient, "__init__", lambda self, use_oauth=True: None),
            patch("src.ingestion.youtube.settings") as mock_settings,
            patch.object(
                YouTubeContentIngestionService,
                "ingest_playlist",
                new=AsyncMock(side_effect=RuntimeError(HOSTILE_EXCEPTION)),
            ),
        ):
            mock_settings.youtube_max_concurrent_playlists = 1
            service = YouTubeContentIngestionService()
            service.client = MagicMock()
            service.client.oauth_available = True
            await service.ingest_all_playlists(sources=[source])

        blob = _log_blob(caplog)
        _assert_no_secrets(blob)
        assert public_key in blob
        assert "Private Inbox" not in blob
        assert any(
            getattr(record, "code", None) == "playlist_ingest_error" for record in caplog.records
        )
