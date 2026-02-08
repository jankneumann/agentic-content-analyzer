"""Tests for ingest CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.app import app
from src.ingestion.rss import IngestionResult

runner = CliRunner()


def _make_rss_result(items_ingested: int = 0) -> IngestionResult:
    """Create an IngestionResult for test mocking."""
    return IngestionResult(items_ingested=items_ingested)


class TestIngestGmail:
    @patch("src.ingestion.gmail.GmailContentIngestionService")
    def test_gmail_success(self, mock_cls):
        mock_service = MagicMock()
        mock_service.ingest_content.return_value = 5
        mock_cls.return_value = mock_service

        result = runner.invoke(app, ["ingest", "gmail"])
        assert result.exit_code == 0
        assert "5" in result.output
        assert "Gmail ingestion complete" in result.output

    @patch("src.ingestion.gmail.GmailContentIngestionService")
    def test_gmail_with_options(self, mock_cls):
        mock_service = MagicMock()
        mock_service.ingest_content.return_value = 3
        mock_cls.return_value = mock_service

        result = runner.invoke(
            app,
            [
                "ingest",
                "gmail",
                "--query",
                "label:test",
                "--max",
                "5",
                "--days",
                "7",
                "--force",
            ],
        )
        assert result.exit_code == 0
        mock_service.ingest_content.assert_called_once()
        call_kwargs = mock_service.ingest_content.call_args[1]
        assert call_kwargs["query"] == "label:test"
        assert call_kwargs["max_results"] == 5
        assert call_kwargs["after_date"] is not None
        assert call_kwargs["force_reprocess"] is True

    @patch("src.ingestion.gmail.GmailContentIngestionService")
    def test_gmail_failure(self, mock_cls):
        mock_cls.side_effect = RuntimeError("Auth failed")

        result = runner.invoke(app, ["ingest", "gmail"])
        assert result.exit_code == 1
        assert "Gmail ingestion failed" in result.output

    @patch("src.ingestion.gmail.GmailContentIngestionService")
    def test_gmail_json_mode(self, mock_cls):
        mock_service = MagicMock()
        mock_service.ingest_content.return_value = 2
        mock_cls.return_value = mock_service

        result = runner.invoke(app, ["--json", "ingest", "gmail"])
        assert result.exit_code == 0
        assert '"source": "gmail"' in result.output
        assert '"ingested": 2' in result.output


class TestIngestRss:
    @patch("src.ingestion.rss.RSSContentIngestionService")
    def test_rss_success(self, mock_cls):
        mock_service = MagicMock()
        mock_service.ingest_content.return_value = _make_rss_result(10)
        mock_cls.return_value = mock_service

        result = runner.invoke(app, ["ingest", "rss"])
        assert result.exit_code == 0
        assert "10" in result.output
        assert "RSS ingestion complete" in result.output

    @patch("src.ingestion.rss.RSSContentIngestionService")
    def test_rss_failure(self, mock_cls):
        mock_cls.side_effect = ConnectionError("Network error")

        result = runner.invoke(app, ["ingest", "rss"])
        assert result.exit_code == 1
        assert "RSS ingestion failed" in result.output


class TestIngestYoutube:
    @patch("src.ingestion.youtube.YouTubeRSSIngestionService")
    @patch("src.ingestion.youtube.YouTubeContentIngestionService")
    def test_youtube_success(self, mock_cls, mock_rss_cls):
        mock_service = MagicMock()
        mock_service.ingest_all_playlists.return_value = 3
        mock_service.ingest_channels.return_value = 2
        mock_cls.return_value = mock_service

        mock_rss_service = MagicMock()
        mock_rss_service.ingest_all_feeds.return_value = 1
        mock_rss_cls.return_value = mock_rss_service

        result = runner.invoke(app, ["ingest", "youtube"])
        assert result.exit_code == 0
        assert "6" in result.output  # total = 3 + 2 + 1
        assert "YouTube ingestion complete" in result.output

    @patch("src.ingestion.youtube.YouTubeRSSIngestionService")
    @patch("src.ingestion.youtube.YouTubeContentIngestionService")
    def test_youtube_public_only(self, mock_cls, mock_rss_cls):
        mock_service = MagicMock()
        mock_service.ingest_all_playlists.return_value = 1
        mock_service.ingest_channels.return_value = 0
        mock_cls.return_value = mock_service

        mock_rss_service = MagicMock()
        mock_rss_service.ingest_all_feeds.return_value = 0
        mock_rss_cls.return_value = mock_rss_service

        result = runner.invoke(app, ["ingest", "youtube", "--public-only"])
        assert result.exit_code == 0
        mock_cls.assert_called_once_with(use_oauth=False)

    @patch("src.ingestion.youtube.YouTubeContentIngestionService")
    def test_youtube_failure(self, mock_cls):
        mock_cls.side_effect = RuntimeError("API error")

        result = runner.invoke(app, ["ingest", "youtube"])
        assert result.exit_code == 1
        assert "YouTube ingestion failed" in result.output


class TestIngestPodcast:
    @patch("src.ingestion.podcast.PodcastContentIngestionService")
    def test_podcast_success(self, mock_cls):
        mock_service = MagicMock()
        mock_service.ingest_all_feeds.return_value = 4
        mock_cls.return_value = mock_service

        result = runner.invoke(app, ["ingest", "podcast"])
        assert result.exit_code == 0
        assert "4" in result.output
        assert "Podcast ingestion complete" in result.output

    @patch("src.ingestion.podcast.PodcastContentIngestionService")
    def test_podcast_failure(self, mock_cls):
        mock_cls.side_effect = RuntimeError("Feed error")

        result = runner.invoke(app, ["ingest", "podcast"])
        assert result.exit_code == 1
        assert "Podcast ingestion failed" in result.output


class TestIngestFiles:
    @patch("src.cli.adapters.ingest_file_sync")
    def test_files_success(self, mock_ingest, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        mock_content = MagicMock()
        mock_content.id = 42
        mock_content.title = "Test File"
        mock_ingest.return_value = mock_content

        result = runner.invoke(app, ["ingest", "files", str(test_file)])
        assert result.exit_code == 0
        assert "1 file(s) ingested" in result.output

    def test_files_not_found(self, tmp_path):
        result = runner.invoke(app, ["ingest", "files", str(tmp_path / "nonexistent.txt")])
        assert result.exit_code == 1
        assert "File not found" in result.output

    @patch("src.cli.adapters.ingest_file_sync")
    def test_files_title_warning_multiple(self, mock_ingest, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("a")
        f2.write_text("b")

        mock_content = MagicMock()
        mock_content.id = 1
        mock_content.title = "A"
        mock_ingest.return_value = mock_content

        result = runner.invoke(
            app,
            [
                "ingest",
                "files",
                str(f1),
                str(f2),
                "--title",
                "Ignored",
            ],
        )
        assert result.exit_code == 0
        assert "Warning" in result.output

    def test_files_help(self):
        result = runner.invoke(app, ["ingest", "files", "--help"])
        assert result.exit_code == 0
        assert "Ingest one or more local files" in result.output
