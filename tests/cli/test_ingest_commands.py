"""Tests for ingest CLI commands.

After the orchestrator refactor, CLI commands delegate to orchestrator functions.
Tests mock at `src.ingestion.orchestrator.<func>` instead of individual service classes.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


class TestIngestGmail:
    @patch("src.ingestion.orchestrator.ingest_gmail")
    def test_gmail_success(self, mock_ingest):
        mock_ingest.return_value = 5

        result = runner.invoke(app, ["ingest", "gmail"])
        assert result.exit_code == 0
        assert "5" in result.output
        assert "Gmail ingestion complete" in result.output

    @patch("src.ingestion.orchestrator.ingest_gmail")
    def test_gmail_with_options(self, mock_ingest):
        mock_ingest.return_value = 3

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
        mock_ingest.assert_called_once()
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["query"] == "label:test"
        assert call_kwargs["max_results"] == 5
        assert call_kwargs["after_date"] is not None
        assert call_kwargs["force_reprocess"] is True

    @patch("src.ingestion.orchestrator.ingest_gmail")
    def test_gmail_failure(self, mock_ingest):
        mock_ingest.side_effect = RuntimeError("Auth failed")

        result = runner.invoke(app, ["ingest", "gmail"])
        assert result.exit_code == 1
        assert "Gmail ingestion failed" in result.output

    @patch("src.ingestion.orchestrator.ingest_gmail")
    def test_gmail_json_mode(self, mock_ingest):
        mock_ingest.return_value = 2

        result = runner.invoke(app, ["--json", "ingest", "gmail"])
        assert result.exit_code == 0
        assert '"source": "gmail"' in result.output
        assert '"ingested": 2' in result.output


class TestIngestRss:
    @patch("src.ingestion.orchestrator.ingest_rss")
    def test_rss_success(self, mock_ingest):
        mock_ingest.return_value = 10

        result = runner.invoke(app, ["ingest", "rss"])
        assert result.exit_code == 0
        assert "10" in result.output
        assert "RSS ingestion complete" in result.output

    @patch("src.ingestion.orchestrator.ingest_rss")
    def test_rss_failure(self, mock_ingest):
        mock_ingest.side_effect = ConnectionError("Network error")

        result = runner.invoke(app, ["ingest", "rss"])
        assert result.exit_code == 1
        assert "RSS ingestion failed" in result.output

    @patch("src.ingestion.orchestrator.ingest_rss")
    def test_rss_passes_on_result_callback(self, mock_ingest):
        """Verify that the CLI passes an on_result callback to the orchestrator."""
        mock_ingest.return_value = 5

        runner.invoke(app, ["ingest", "rss"])

        mock_ingest.assert_called_once()
        call_kwargs = mock_ingest.call_args[1]
        assert "on_result" in call_kwargs
        assert callable(call_kwargs["on_result"])


class TestIngestYoutube:
    @patch("src.ingestion.orchestrator.ingest_youtube")
    def test_youtube_success(self, mock_ingest):
        mock_ingest.return_value = 6

        result = runner.invoke(app, ["ingest", "youtube"])
        assert result.exit_code == 0
        assert "6" in result.output
        assert "YouTube ingestion complete" in result.output

    @patch("src.ingestion.orchestrator.ingest_youtube")
    def test_youtube_public_only(self, mock_ingest):
        mock_ingest.return_value = 1

        result = runner.invoke(app, ["ingest", "youtube", "--public-only"])
        assert result.exit_code == 0
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["use_oauth"] is False

    @patch("src.ingestion.orchestrator.ingest_youtube")
    def test_youtube_failure(self, mock_ingest):
        mock_ingest.side_effect = RuntimeError("API error")

        result = runner.invoke(app, ["ingest", "youtube"])
        assert result.exit_code == 1
        assert "YouTube ingestion failed" in result.output


class TestIngestYoutubePlaylist:
    @patch("src.ingestion.orchestrator.ingest_youtube_playlist")
    def test_youtube_playlist_success(self, mock_ingest):
        mock_ingest.return_value = 3

        result = runner.invoke(app, ["ingest", "youtube-playlist"])
        assert result.exit_code == 0
        assert "3" in result.output
        assert "YouTube playlist ingestion complete" in result.output

    @patch("src.ingestion.orchestrator.ingest_youtube_playlist")
    def test_youtube_playlist_with_options(self, mock_ingest):
        mock_ingest.return_value = 2

        result = runner.invoke(
            app,
            ["ingest", "youtube-playlist", "--max", "5", "--days", "3", "--force"],
        )
        assert result.exit_code == 0
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["max_videos"] == 5
        assert call_kwargs["after_date"] is not None
        assert call_kwargs["force_reprocess"] is True

    @patch("src.ingestion.orchestrator.ingest_youtube_playlist")
    def test_youtube_playlist_public_only(self, mock_ingest):
        mock_ingest.return_value = 1

        result = runner.invoke(app, ["ingest", "youtube-playlist", "--public-only"])
        assert result.exit_code == 0
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["use_oauth"] is False

    @patch("src.ingestion.orchestrator.ingest_youtube_playlist")
    def test_youtube_playlist_failure(self, mock_ingest):
        mock_ingest.side_effect = RuntimeError("API error")

        result = runner.invoke(app, ["ingest", "youtube-playlist"])
        assert result.exit_code == 1
        assert "YouTube playlist ingestion failed" in result.output

    @patch("src.ingestion.orchestrator.ingest_youtube_playlist")
    def test_youtube_playlist_json_mode(self, mock_ingest):
        mock_ingest.return_value = 4

        result = runner.invoke(app, ["--json", "ingest", "youtube-playlist"])
        assert result.exit_code == 0
        assert '"source": "youtube-playlist"' in result.output
        assert '"ingested": 4' in result.output


class TestIngestYoutubeRss:
    @patch("src.ingestion.orchestrator.ingest_youtube_rss")
    def test_youtube_rss_success(self, mock_ingest):
        mock_ingest.return_value = 15

        result = runner.invoke(app, ["ingest", "youtube-rss"])
        assert result.exit_code == 0
        assert "15" in result.output
        assert "YouTube RSS ingestion complete" in result.output

    @patch("src.ingestion.orchestrator.ingest_youtube_rss")
    def test_youtube_rss_with_options(self, mock_ingest):
        mock_ingest.return_value = 8

        result = runner.invoke(
            app,
            ["ingest", "youtube-rss", "--max", "20", "--days", "14", "--force"],
        )
        assert result.exit_code == 0
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["max_videos"] == 20
        assert call_kwargs["force_reprocess"] is True

    @patch("src.ingestion.orchestrator.ingest_youtube_rss")
    def test_youtube_rss_failure(self, mock_ingest):
        mock_ingest.side_effect = RuntimeError("Rate limited")

        result = runner.invoke(app, ["ingest", "youtube-rss"])
        assert result.exit_code == 1
        assert "YouTube RSS ingestion failed" in result.output

    @patch("src.ingestion.orchestrator.ingest_youtube_rss")
    def test_youtube_rss_json_mode(self, mock_ingest):
        mock_ingest.return_value = 7

        result = runner.invoke(app, ["--json", "ingest", "youtube-rss"])
        assert result.exit_code == 0
        assert '"source": "youtube-rss"' in result.output
        assert '"ingested": 7' in result.output

    @patch("src.ingestion.orchestrator.ingest_youtube_rss")
    def test_youtube_rss_no_public_only_flag(self, mock_ingest):
        """youtube-rss should NOT have a --public-only flag (RSS doesn't use OAuth)."""
        mock_ingest.return_value = 0

        result = runner.invoke(app, ["ingest", "youtube-rss", "--public-only"])
        # Should fail because --public-only is not a valid option for youtube-rss
        assert result.exit_code != 0


class TestIngestPodcast:
    @patch("src.ingestion.orchestrator.ingest_podcast")
    def test_podcast_success(self, mock_ingest):
        mock_ingest.return_value = 4

        result = runner.invoke(app, ["ingest", "podcast"])
        assert result.exit_code == 0
        assert "4" in result.output
        assert "Podcast ingestion complete" in result.output

    @patch("src.ingestion.orchestrator.ingest_podcast")
    def test_podcast_failure(self, mock_ingest):
        mock_ingest.side_effect = RuntimeError("Feed error")

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


class TestIngestUrl:
    @patch("src.ingestion.orchestrator.ingest_url")
    def test_url_success(self, mock_ingest):
        from src.ingestion.orchestrator import URLIngestResult

        mock_ingest.return_value = URLIngestResult(content_id=42, status="queued", duplicate=False)

        result = runner.invoke(app, ["ingest", "url", "https://example.com/article"])
        assert result.exit_code == 0
        assert "URL ingested" in result.output
        assert "42" in result.output

    @patch("src.ingestion.orchestrator.ingest_url")
    def test_url_duplicate(self, mock_ingest):
        from src.ingestion.orchestrator import URLIngestResult

        mock_ingest.return_value = URLIngestResult(content_id=99, status="exists", duplicate=True)

        result = runner.invoke(app, ["ingest", "url", "https://example.com/article"])
        assert result.exit_code == 0
        assert "already exists" in result.output
        assert "99" in result.output

    @patch("src.ingestion.orchestrator.ingest_url")
    def test_url_with_options(self, mock_ingest):
        from src.ingestion.orchestrator import URLIngestResult

        mock_ingest.return_value = URLIngestResult(content_id=1, status="queued", duplicate=False)

        result = runner.invoke(
            app,
            [
                "ingest",
                "url",
                "https://example.com",
                "--title",
                "My Article",
                "--tag",
                "ai",
                "--tag",
                "news",
                "--notes",
                "Important",
            ],
        )
        assert result.exit_code == 0
        mock_ingest.assert_called_once()
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["url"] == "https://example.com"
        assert call_kwargs["title"] == "My Article"
        assert call_kwargs["tags"] == ["ai", "news"]
        assert call_kwargs["notes"] == "Important"

    @patch("src.ingestion.orchestrator.ingest_url")
    def test_url_failure(self, mock_ingest):
        mock_ingest.side_effect = RuntimeError("Connection refused")

        result = runner.invoke(app, ["ingest", "url", "https://example.com"])
        assert result.exit_code == 1
        assert "URL ingestion failed" in result.output

    @patch("src.ingestion.orchestrator.ingest_url")
    def test_url_json_mode(self, mock_ingest):
        from src.ingestion.orchestrator import URLIngestResult

        mock_ingest.return_value = URLIngestResult(content_id=7, status="queued", duplicate=False)

        result = runner.invoke(app, ["--json", "ingest", "url", "https://example.com"])
        assert result.exit_code == 0
        assert '"source": "url"' in result.output
        assert '"content_id": 7' in result.output
        assert '"duplicate": false' in result.output

    @patch("src.ingestion.orchestrator.ingest_url")
    def test_url_json_mode_duplicate(self, mock_ingest):
        from src.ingestion.orchestrator import URLIngestResult

        mock_ingest.return_value = URLIngestResult(content_id=99, status="exists", duplicate=True)

        result = runner.invoke(app, ["--json", "ingest", "url", "https://example.com"])
        assert result.exit_code == 0
        assert '"duplicate": true' in result.output
        assert '"status": "exists"' in result.output

    def test_url_no_argument(self):
        result = runner.invoke(app, ["ingest", "url"])
        assert result.exit_code != 0

    def test_url_help(self):
        result = runner.invoke(app, ["ingest", "url", "--help"])
        assert result.exit_code == 0
        assert "Ingest a single URL" in result.output
