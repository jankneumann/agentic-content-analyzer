"""Tests for pipeline CLI commands.

After the orchestrator refactor, the pipeline delegates to orchestrator functions.
Tests mock at `src.ingestion.orchestrator.<func>` instead of individual service classes.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


def _mock_all_orchestrator_functions(
    *,
    gmail: int | Exception = 2,
    rss: int | Exception = 3,
    youtube_playlist: int | Exception = 1,
    youtube_rss: int | Exception = 0,
    podcast: int | Exception = 1,
    substack: int | Exception = 0,
):
    """Create mock patches for all orchestrator functions used in pipeline."""
    patches = {}
    for name, result in [
        ("ingest_gmail", gmail),
        ("ingest_rss", rss),
        ("ingest_youtube_playlist", youtube_playlist),
        ("ingest_youtube_rss", youtube_rss),
        ("ingest_podcast", podcast),
        ("ingest_substack", substack),
    ]:
        if isinstance(result, Exception):
            patches[name] = patch(f"src.ingestion.orchestrator.{name}", side_effect=result)
        else:
            patches[name] = patch(f"src.ingestion.orchestrator.{name}", return_value=result)
    return patches


class TestDailyPipeline:
    @patch("src.cli.adapters._emit_notification_sync")
    @patch("src.cli.adapters.create_digest_sync")
    @patch("src.processors.summarizer.ContentSummarizer")
    @patch("src.ingestion.orchestrator.ingest_substack", return_value=0)
    @patch("src.ingestion.orchestrator.ingest_podcast", return_value=1)
    @patch("src.ingestion.orchestrator.ingest_youtube_rss", return_value=0)
    @patch("src.ingestion.orchestrator.ingest_youtube_playlist", return_value=1)
    @patch("src.ingestion.orchestrator.ingest_rss", return_value=3)
    @patch("src.ingestion.orchestrator.ingest_gmail", return_value=2)
    def test_daily_pipeline_success(
        self,
        mock_gmail,
        mock_rss,
        mock_youtube_playlist,
        mock_youtube_rss,
        mock_podcast,
        mock_substack,
        mock_summarizer,
        mock_digest,
        mock_emit,
    ):
        mock_summarizer.return_value.summarize_pending_contents.return_value = 5

        mock_result = MagicMock()
        mock_result.title = "Daily Digest"
        mock_result.newsletter_count = 7
        mock_digest.return_value = mock_result

        result = runner.invoke(app, ["pipeline", "daily"])
        assert result.exit_code == 0
        assert "completed successfully" in result.output

    @patch("src.cli.adapters._emit_notification_sync")
    @patch("src.cli.adapters.create_digest_sync")
    @patch("src.processors.summarizer.ContentSummarizer")
    @patch("src.ingestion.orchestrator.ingest_substack", return_value=0)
    @patch("src.ingestion.orchestrator.ingest_podcast", return_value=1)
    @patch("src.ingestion.orchestrator.ingest_youtube_rss", return_value=0)
    @patch("src.ingestion.orchestrator.ingest_youtube_playlist", return_value=1)
    @patch("src.ingestion.orchestrator.ingest_rss", return_value=3)
    @patch("src.ingestion.orchestrator.ingest_gmail", return_value=2)
    def test_daily_pipeline_emits_pipeline_completion(
        self,
        mock_gmail,
        mock_rss,
        mock_youtube_playlist,
        mock_youtube_rss,
        mock_podcast,
        mock_substack,
        mock_summarizer,
        mock_digest,
        mock_emit,
    ):
        mock_summarizer.return_value.summarize_pending_contents.return_value = 5
        mock_result = MagicMock()
        mock_result.title = "Daily Digest"
        mock_result.newsletter_count = 7
        mock_digest.return_value = mock_result

        result = runner.invoke(app, ["pipeline", "daily"])
        assert result.exit_code == 0

        # _emit_notification_sync is called twice:
        # 1. By create_digest_sync (for digest_creation) — but that's mocked
        # 2. By the pipeline command (for pipeline_completion)
        # Since create_digest_sync is fully mocked, only the pipeline call remains
        mock_emit.assert_called_once()
        call_kwargs = mock_emit.call_args
        assert call_kwargs[1]["event_type"] == "pipeline_completion"
        assert call_kwargs[1]["title"] == "Daily Pipeline Complete"
        assert call_kwargs[1]["payload"]["pipeline_type"] == "daily"
        assert call_kwargs[1]["payload"]["total_ingested"] == 7  # 2+3+1+0+1+0
        assert call_kwargs[1]["payload"]["summarized_count"] == 5
        assert call_kwargs[1]["payload"]["url"] == "/digests"

    @patch("src.ingestion.orchestrator.ingest_substack", side_effect=RuntimeError("fail"))
    @patch("src.ingestion.orchestrator.ingest_podcast", side_effect=RuntimeError("fail"))
    @patch("src.ingestion.orchestrator.ingest_youtube_rss", side_effect=RuntimeError("fail"))
    @patch("src.ingestion.orchestrator.ingest_youtube_playlist", side_effect=RuntimeError("fail"))
    @patch("src.ingestion.orchestrator.ingest_rss", side_effect=RuntimeError("fail"))
    @patch("src.ingestion.orchestrator.ingest_gmail", side_effect=RuntimeError("fail"))
    def test_daily_pipeline_all_ingestion_fails(
        self, mock_gmail, mock_rss, mock_yt_playlist, mock_yt_rss, mock_podcast, mock_substack
    ):
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
    @patch("src.cli.adapters._emit_notification_sync")
    @patch("src.cli.adapters.create_digest_sync")
    @patch("src.processors.summarizer.ContentSummarizer")
    @patch("src.ingestion.orchestrator.ingest_substack", return_value=0)
    @patch("src.ingestion.orchestrator.ingest_podcast", return_value=2)
    @patch("src.ingestion.orchestrator.ingest_youtube_rss", return_value=1)
    @patch("src.ingestion.orchestrator.ingest_youtube_playlist", return_value=2)
    @patch("src.ingestion.orchestrator.ingest_rss", return_value=10)
    @patch("src.ingestion.orchestrator.ingest_gmail", return_value=5)
    def test_weekly_pipeline_success(
        self,
        mock_gmail,
        mock_rss,
        mock_youtube_playlist,
        mock_youtube_rss,
        mock_podcast,
        mock_substack,
        mock_summarizer,
        mock_digest,
        mock_emit,
    ):
        mock_summarizer.return_value.summarize_pending_contents.return_value = 15

        mock_result = MagicMock()
        mock_result.title = "Weekly Digest"
        mock_result.newsletter_count = 20
        mock_digest.return_value = mock_result

        result = runner.invoke(app, ["pipeline", "weekly"])
        assert result.exit_code == 0
        assert "completed successfully" in result.output

    @patch("src.cli.adapters._emit_notification_sync")
    @patch("src.cli.adapters.create_digest_sync")
    @patch("src.processors.summarizer.ContentSummarizer")
    @patch("src.ingestion.orchestrator.ingest_substack", return_value=0)
    @patch("src.ingestion.orchestrator.ingest_podcast", return_value=2)
    @patch("src.ingestion.orchestrator.ingest_youtube_rss", return_value=1)
    @patch("src.ingestion.orchestrator.ingest_youtube_playlist", return_value=2)
    @patch("src.ingestion.orchestrator.ingest_rss", return_value=10)
    @patch("src.ingestion.orchestrator.ingest_gmail", return_value=5)
    def test_weekly_pipeline_emits_pipeline_completion(
        self,
        mock_gmail,
        mock_rss,
        mock_youtube_playlist,
        mock_youtube_rss,
        mock_podcast,
        mock_substack,
        mock_summarizer,
        mock_digest,
        mock_emit,
    ):
        mock_summarizer.return_value.summarize_pending_contents.return_value = 15
        mock_result = MagicMock()
        mock_result.title = "Weekly Digest"
        mock_result.newsletter_count = 20
        mock_digest.return_value = mock_result

        result = runner.invoke(app, ["pipeline", "weekly"])
        assert result.exit_code == 0

        mock_emit.assert_called_once()
        call_kwargs = mock_emit.call_args
        assert call_kwargs[1]["event_type"] == "pipeline_completion"
        assert call_kwargs[1]["title"] == "Weekly Pipeline Complete"
        assert call_kwargs[1]["payload"]["pipeline_type"] == "weekly"
        assert call_kwargs[1]["payload"]["total_ingested"] == 20  # 5+10+2+1+2+0
        assert call_kwargs[1]["payload"]["summarized_count"] == 15
        assert call_kwargs[1]["payload"]["url"] == "/digests"

    def test_weekly_pipeline_invalid_week(self):
        result = runner.invoke(app, ["pipeline", "weekly", "--week", "invalid"])
        assert result.exit_code == 1
