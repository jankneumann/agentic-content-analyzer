"""Tests for pipeline CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.app import app
from src.ingestion.rss import IngestionResult

runner = CliRunner()


def _mock_ingestion_services():
    """Create mock patches for all ingestion services used in pipeline."""
    return {
        "gmail": patch(
            "src.ingestion.gmail.GmailContentIngestionService",
            return_value=MagicMock(ingest_content=MagicMock(return_value=2)),
        ),
        "rss": patch(
            "src.ingestion.rss.RSSContentIngestionService",
            return_value=MagicMock(
                ingest_content=MagicMock(return_value=IngestionResult(items_ingested=3))
            ),
        ),
        "youtube": patch(
            "src.ingestion.youtube.YouTubeContentIngestionService",
            return_value=MagicMock(ingest_all_playlists=MagicMock(return_value=1)),
        ),
        "podcast": patch(
            "src.ingestion.podcast.PodcastContentIngestionService",
            return_value=MagicMock(ingest_all_feeds=MagicMock(return_value=1)),
        ),
    }


class TestDailyPipeline:
    @patch("src.cli.adapters.create_digest_sync")
    @patch("src.processors.summarizer.ContentSummarizer")
    @patch("src.ingestion.podcast.PodcastContentIngestionService")
    @patch("src.ingestion.youtube.YouTubeContentIngestionService")
    @patch("src.ingestion.rss.RSSContentIngestionService")
    @patch("src.ingestion.gmail.GmailContentIngestionService")
    def test_daily_pipeline_success(
        self, mock_gmail, mock_rss, mock_youtube, mock_podcast, mock_summarizer, mock_digest
    ):
        mock_gmail.return_value.ingest_content.return_value = 2
        mock_rss.return_value.ingest_content.return_value = IngestionResult(items_ingested=3)
        mock_youtube.return_value.ingest_all_playlists.return_value = 1
        mock_podcast.return_value.ingest_all_feeds.return_value = 1
        mock_summarizer.return_value.summarize_pending_contents.return_value = 5

        mock_result = MagicMock()
        mock_result.title = "Daily Digest"
        mock_result.newsletter_count = 7
        mock_digest.return_value = mock_result

        result = runner.invoke(app, ["pipeline", "daily"])
        assert result.exit_code == 0
        assert "completed successfully" in result.output

    @patch("src.ingestion.gmail.GmailContentIngestionService")
    @patch("src.ingestion.rss.RSSContentIngestionService")
    @patch("src.ingestion.youtube.YouTubeContentIngestionService")
    @patch("src.ingestion.podcast.PodcastContentIngestionService")
    def test_daily_pipeline_all_ingestion_fails(
        self, mock_podcast, mock_youtube, mock_rss, mock_gmail
    ):
        mock_gmail.side_effect = RuntimeError("fail")
        mock_rss.side_effect = RuntimeError("fail")
        mock_youtube.side_effect = RuntimeError("fail")
        mock_podcast.side_effect = RuntimeError("fail")

        result = runner.invoke(app, ["pipeline", "daily"])
        assert result.exit_code == 1
        assert "failed" in result.output.lower()

    def test_daily_pipeline_invalid_date(self):
        result = runner.invoke(app, ["pipeline", "daily", "--date", "bad-date"])
        assert result.exit_code == 1

    def test_daily_pipeline_help(self):
        result = runner.invoke(app, ["pipeline", "daily", "--help"])
        assert result.exit_code == 0
        assert "daily" in result.output.lower()


class TestWeeklyPipeline:
    @patch("src.cli.adapters.create_digest_sync")
    @patch("src.processors.summarizer.ContentSummarizer")
    @patch("src.ingestion.podcast.PodcastContentIngestionService")
    @patch("src.ingestion.youtube.YouTubeContentIngestionService")
    @patch("src.ingestion.rss.RSSContentIngestionService")
    @patch("src.ingestion.gmail.GmailContentIngestionService")
    def test_weekly_pipeline_success(
        self, mock_gmail, mock_rss, mock_youtube, mock_podcast, mock_summarizer, mock_digest
    ):
        mock_gmail.return_value.ingest_content.return_value = 5
        mock_rss.return_value.ingest_content.return_value = IngestionResult(items_ingested=10)
        mock_youtube.return_value.ingest_all_playlists.return_value = 3
        mock_podcast.return_value.ingest_all_feeds.return_value = 2
        mock_summarizer.return_value.summarize_pending_contents.return_value = 15

        mock_result = MagicMock()
        mock_result.title = "Weekly Digest"
        mock_result.newsletter_count = 20
        mock_digest.return_value = mock_result

        result = runner.invoke(app, ["pipeline", "weekly"])
        assert result.exit_code == 0
        assert "completed successfully" in result.output

    def test_weekly_pipeline_invalid_week(self):
        result = runner.invoke(app, ["pipeline", "weekly", "--week", "invalid"])
        assert result.exit_code == 1
