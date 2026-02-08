"""Tests for the ingestion orchestrator module.

Each orchestrator function is tested with mocked service classes
to verify correct wiring: lazy import, instantiation, call, and return type.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.rss import IngestionResult


class TestIngestGmail:
    @patch("src.ingestion.gmail.GmailContentIngestionService")
    def test_returns_int(self, mock_cls):
        from src.ingestion.orchestrator import ingest_gmail

        mock_cls.return_value.ingest_content.return_value = 5
        result = ingest_gmail()
        assert result == 5
        assert isinstance(result, int)

    @patch("src.ingestion.gmail.GmailContentIngestionService")
    def test_passes_parameters(self, mock_cls):
        from src.ingestion.orchestrator import ingest_gmail

        mock_service = MagicMock()
        mock_service.ingest_content.return_value = 3
        mock_cls.return_value = mock_service
        after = datetime(2025, 1, 1, tzinfo=UTC)

        ingest_gmail(query="label:test", max_results=5, after_date=after, force_reprocess=True)

        mock_service.ingest_content.assert_called_once_with(
            query="label:test",
            max_results=5,
            after_date=after,
            force_reprocess=True,
        )


class TestIngestRss:
    @patch("src.ingestion.rss.RSSContentIngestionService")
    def test_returns_int(self, mock_cls):
        from src.ingestion.orchestrator import ingest_rss

        mock_cls.return_value.ingest_content.return_value = IngestionResult(items_ingested=10)
        result = ingest_rss()
        assert result == 10
        assert isinstance(result, int)

    @patch("src.ingestion.rss.RSSContentIngestionService")
    def test_on_result_callback_receives_ingestion_result(self, mock_cls):
        from src.ingestion.orchestrator import ingest_rss

        ingestion_result = IngestionResult(items_ingested=7)
        mock_cls.return_value.ingest_content.return_value = ingestion_result

        callback = MagicMock()
        ingest_rss(on_result=callback)

        callback.assert_called_once_with(ingestion_result)

    @patch("src.ingestion.rss.RSSContentIngestionService")
    def test_on_result_not_called_when_none(self, mock_cls):
        from src.ingestion.orchestrator import ingest_rss

        mock_cls.return_value.ingest_content.return_value = IngestionResult(items_ingested=3)
        # Should not raise when on_result is None (default)
        result = ingest_rss()
        assert result == 3

    @patch("src.ingestion.rss.RSSContentIngestionService")
    def test_passes_parameters(self, mock_cls):
        from src.ingestion.orchestrator import ingest_rss

        mock_service = MagicMock()
        mock_service.ingest_content.return_value = IngestionResult(items_ingested=0)
        mock_cls.return_value = mock_service
        after = datetime(2025, 1, 1, tzinfo=UTC)

        ingest_rss(max_entries_per_feed=20, after_date=after, force_reprocess=True)

        mock_service.ingest_content.assert_called_once_with(
            max_entries_per_feed=20,
            after_date=after,
            force_reprocess=True,
        )


class TestIngestYoutube:
    @patch("src.ingestion.youtube.YouTubeRSSIngestionService")
    @patch("src.ingestion.youtube.YouTubeContentIngestionService")
    def test_calls_all_three_methods_across_two_services(self, mock_content_cls, mock_rss_cls):
        from src.ingestion.orchestrator import ingest_youtube

        mock_content = MagicMock()
        mock_content.ingest_all_playlists.return_value = 3
        mock_content.ingest_channels.return_value = 2
        mock_content_cls.return_value = mock_content

        mock_rss = MagicMock()
        mock_rss.ingest_all_feeds.return_value = 1
        mock_rss_cls.return_value = mock_rss

        result = ingest_youtube()

        assert result == 6  # 3 + 2 + 1
        mock_content.ingest_all_playlists.assert_called_once()
        mock_content.ingest_channels.assert_called_once()
        mock_rss.ingest_all_feeds.assert_called_once()

    @patch("src.ingestion.youtube.YouTubeRSSIngestionService")
    @patch("src.ingestion.youtube.YouTubeContentIngestionService")
    def test_returns_int(self, mock_content_cls, mock_rss_cls):
        from src.ingestion.orchestrator import ingest_youtube

        mock_content_cls.return_value.ingest_all_playlists.return_value = 0
        mock_content_cls.return_value.ingest_channels.return_value = 0
        mock_rss_cls.return_value.ingest_all_feeds.return_value = 0

        result = ingest_youtube()
        assert result == 0
        assert isinstance(result, int)

    @patch("src.ingestion.youtube.YouTubeRSSIngestionService")
    @patch("src.ingestion.youtube.YouTubeContentIngestionService")
    def test_passes_use_oauth(self, mock_content_cls, mock_rss_cls):
        from src.ingestion.orchestrator import ingest_youtube

        mock_content_cls.return_value.ingest_all_playlists.return_value = 0
        mock_content_cls.return_value.ingest_channels.return_value = 0
        mock_rss_cls.return_value.ingest_all_feeds.return_value = 0

        ingest_youtube(use_oauth=False)

        mock_content_cls.assert_called_once_with(use_oauth=False)

    @patch("src.ingestion.youtube.YouTubeRSSIngestionService")
    @patch("src.ingestion.youtube.YouTubeContentIngestionService")
    def test_passes_parameters_to_all_calls(self, mock_content_cls, mock_rss_cls):
        from src.ingestion.orchestrator import ingest_youtube

        mock_content = MagicMock()
        mock_content.ingest_all_playlists.return_value = 0
        mock_content.ingest_channels.return_value = 0
        mock_content_cls.return_value = mock_content

        mock_rss = MagicMock()
        mock_rss.ingest_all_feeds.return_value = 0
        mock_rss_cls.return_value = mock_rss

        after = datetime(2025, 1, 1, tzinfo=UTC)
        ingest_youtube(max_videos=20, after_date=after, force_reprocess=True)

        mock_content.ingest_all_playlists.assert_called_once_with(
            max_videos_per_playlist=20,
            after_date=after,
            force_reprocess=True,
        )
        mock_content.ingest_channels.assert_called_once_with(
            max_videos_per_channel=20,
            after_date=after,
            force_reprocess=True,
        )
        mock_rss.ingest_all_feeds.assert_called_once_with(
            max_entries_per_feed=20,
            after_date=after,
            force_reprocess=True,
        )


class TestIngestPodcast:
    @patch("src.ingestion.podcast.PodcastContentIngestionService")
    def test_returns_int(self, mock_cls):
        from src.ingestion.orchestrator import ingest_podcast

        mock_cls.return_value.ingest_all_feeds.return_value = 4
        result = ingest_podcast()
        assert result == 4
        assert isinstance(result, int)

    @patch("src.ingestion.podcast.PodcastContentIngestionService")
    def test_passes_parameters(self, mock_cls):
        from src.ingestion.orchestrator import ingest_podcast

        mock_service = MagicMock()
        mock_service.ingest_all_feeds.return_value = 0
        mock_cls.return_value = mock_service
        after = datetime(2025, 1, 1, tzinfo=UTC)

        ingest_podcast(max_entries_per_feed=5, after_date=after, force_reprocess=True)

        mock_service.ingest_all_feeds.assert_called_once_with(
            max_entries_per_feed=5,
            after_date=after,
            force_reprocess=True,
        )


class TestIngestSubstack:
    @patch("src.ingestion.substack.SubstackContentIngestionService")
    def test_returns_int(self, mock_cls):
        from src.ingestion.orchestrator import ingest_substack

        mock_cls.return_value.ingest_content.return_value = 6
        result = ingest_substack()
        assert result == 6
        assert isinstance(result, int)

    @patch("src.ingestion.substack.SubstackContentIngestionService")
    def test_calls_close_on_success(self, mock_cls):
        from src.ingestion.orchestrator import ingest_substack

        mock_service = MagicMock()
        mock_service.ingest_content.return_value = 2
        mock_cls.return_value = mock_service

        ingest_substack()

        mock_service.close.assert_called_once()

    @patch("src.ingestion.substack.SubstackContentIngestionService")
    def test_calls_close_on_exception(self, mock_cls):
        from src.ingestion.orchestrator import ingest_substack

        mock_service = MagicMock()
        mock_service.ingest_content.side_effect = RuntimeError("API error")
        mock_cls.return_value = mock_service

        with pytest.raises(RuntimeError, match="API error"):
            ingest_substack()

        mock_service.close.assert_called_once()

    @patch("src.ingestion.substack.SubstackContentIngestionService")
    def test_passes_session_cookie(self, mock_cls):
        from src.ingestion.orchestrator import ingest_substack

        mock_cls.return_value.ingest_content.return_value = 0

        ingest_substack(session_cookie="test-cookie")

        mock_cls.assert_called_once_with(session_cookie="test-cookie")

    @patch("src.ingestion.substack.SubstackContentIngestionService")
    def test_passes_parameters(self, mock_cls):
        from src.ingestion.orchestrator import ingest_substack

        mock_service = MagicMock()
        mock_service.ingest_content.return_value = 0
        mock_cls.return_value = mock_service
        after = datetime(2025, 1, 1, tzinfo=UTC)

        ingest_substack(max_entries_per_source=15, after_date=after, force_reprocess=True)

        mock_service.ingest_content.assert_called_once_with(
            max_entries_per_source=15,
            after_date=after,
            force_reprocess=True,
        )
