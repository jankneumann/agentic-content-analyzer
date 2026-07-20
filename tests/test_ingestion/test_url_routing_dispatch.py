"""Tests for URL routing dispatch in the orchestrator and YouTube service.

These verify that ``ingest_url`` sends a URL to the correct handler based on
its classification, and that ``YouTubeContentIngestionService.ingest_video``
produces the canonical envelope for a shared video link.
"""

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.ingestion.orchestrator import ingest_url
from src.ingestion.result import IngestionResponse
from src.ingestion.youtube import YouTubeContentIngestionService


def _envelope() -> IngestionResponse:
    return IngestionResponse(command="ingest.url", source="url", status="ok")


class TestIngestUrlDispatch:
    """``ingest_url`` routes to the handler chosen by ``classify_url``."""

    def test_youtube_video_routes_to_youtube(self) -> None:
        with (
            patch(
                "src.ingestion.orchestrator._ingest_routed_youtube_video",
                return_value=_envelope(),
            ) as yt,
            patch("src.ingestion.orchestrator._ingest_webpage") as web,
        ):
            ingest_url(url="https://youtu.be/dQw4w9WgXcQ")
        yt.assert_called_once()
        web.assert_not_called()

    def test_playlist_routes_to_playlist(self) -> None:
        with patch(
            "src.ingestion.orchestrator._ingest_routed_youtube_playlist",
            return_value=_envelope(),
        ) as pl:
            ingest_url(url="https://www.youtube.com/playlist?list=PLabc123")
        pl.assert_called_once()

    def test_feed_routes_to_rss(self) -> None:
        with patch(
            "src.ingestion.orchestrator._ingest_routed_rss",
            return_value=_envelope(),
        ) as rss:
            ingest_url(url="https://example.com/feed")
        rss.assert_called_once()

    def test_plain_url_routes_to_webpage(self) -> None:
        with patch(
            "src.ingestion.orchestrator._ingest_webpage",
            return_value=_envelope(),
        ) as web:
            ingest_url(url="https://example.com/article")
        web.assert_called_once()

    def test_auto_route_false_forces_webpage(self) -> None:
        """A YouTube URL with auto_route=False is extracted as a web page."""
        with (
            patch(
                "src.ingestion.orchestrator._ingest_webpage",
                return_value=_envelope(),
            ) as web,
            patch("src.ingestion.orchestrator._ingest_routed_youtube_video") as yt,
        ):
            ingest_url(url="https://youtu.be/dQw4w9WgXcQ", auto_route=False)
        web.assert_called_once()
        yt.assert_not_called()


def _fake_get_db(db):
    @contextmanager
    def _cm():
        yield db

    return _cm


class TestIngestVideo:
    """``YouTubeContentIngestionService.ingest_video`` envelope behaviour."""

    @pytest.mark.asyncio
    async def test_invalid_url_returns_error(self) -> None:
        service = YouTubeContentIngestionService.__new__(YouTubeContentIngestionService)
        service.client = Mock()
        resp = await service.ingest_video("https://example.com/not-a-video")
        assert resp.status == "error"
        assert resp.errors[0].code == "invalid_youtube_url"

    @pytest.mark.asyncio
    async def test_video_not_found_returns_error(self) -> None:
        service = YouTubeContentIngestionService.__new__(YouTubeContentIngestionService)
        service.client = Mock()
        service.client.get_video_metadata = Mock(return_value=None)
        resp = await service.ingest_video("https://youtu.be/dQw4w9WgXcQ")
        assert resp.status == "error"
        assert resp.errors[0].code == "youtube_video_not_found"

    @pytest.mark.asyncio
    async def test_successful_ingest_returns_content_id(self) -> None:
        service = YouTubeContentIngestionService.__new__(YouTubeContentIngestionService)
        service.client = Mock()
        service.client.get_video_metadata = Mock(
            return_value={
                "video_id": "dQw4w9WgXcQ",
                "title": "Test Video",
                "channel_title": "Test Channel",
                "published_date": None,
                "thumbnail_url": None,
                "playlist_id": None,
            }
        )
        service._process_video = AsyncMock(return_value=True)

        # Mock the post-process row lookup.
        row = MagicMock()
        row.id = 99
        row.metadata_json = {}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = row

        with patch("src.ingestion.youtube.get_db", _fake_get_db(db)):
            resp = await service.ingest_video(
                "https://youtu.be/dQw4w9WgXcQ", tags=["ai"], notes="hi"
            )

        assert resp.status == "ok"
        assert resp.items_ingested == 1
        assert resp.details["routed_to"] == "youtube_video"
        assert resp.details["content_id"] == 99
        assert resp.details["video_id"] == "dQw4w9WgXcQ"
        # User tags/notes merged back onto the row after processing.
        assert row.metadata_json["tags"] == ["ai"]
        assert row.metadata_json["notes"] == "hi"

    @pytest.mark.asyncio
    async def test_skipped_existing_marks_duplicate(self) -> None:
        service = YouTubeContentIngestionService.__new__(YouTubeContentIngestionService)
        service.client = Mock()
        service.client.get_video_metadata = Mock(
            return_value={
                "video_id": "dQw4w9WgXcQ",
                "title": "Test Video",
                "channel_title": "Test Channel",
                "published_date": None,
                "thumbnail_url": None,
                "playlist_id": None,
            }
        )
        # _process_video returns False => existing row, nothing rewritten.
        service._process_video = AsyncMock(return_value=False)

        row = MagicMock()
        row.id = 7
        row.metadata_json = {}
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = row

        with patch("src.ingestion.youtube.get_db", _fake_get_db(db)):
            resp = await service.ingest_video("https://youtu.be/dQw4w9WgXcQ")

        assert resp.status == "ok"
        assert resp.items_skipped == 1
        assert resp.details["duplicate"] is True
        assert resp.details["content_id"] == 7
