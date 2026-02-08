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
    youtube: int | Exception = 1,
    podcast: int | Exception = 1,
    substack: int | Exception = 0,
):
    """Create mock patches for all orchestrator functions used in pipeline."""
    patches = {}
    for name, result in [
        ("ingest_gmail", gmail),
        ("ingest_rss", rss),
        ("ingest_youtube", youtube),
        ("ingest_podcast", podcast),
        ("ingest_substack", substack),
    ]:
        if isinstance(result, Exception):
            patches[name] = patch(f"src.ingestion.orchestrator.{name}", side_effect=result)
        else:
            patches[name] = patch(f"src.ingestion.orchestrator.{name}", return_value=result)
    return patches


class TestDailyPipeline:
    @patch("src.cli.adapters.create_digest_sync")
    @patch("src.processors.summarizer.ContentSummarizer")
    @patch("src.ingestion.orchestrator.ingest_substack", return_value=0)
    @patch("src.ingestion.orchestrator.ingest_podcast", return_value=1)
    @patch("src.ingestion.orchestrator.ingest_youtube", return_value=1)
    @patch("src.ingestion.orchestrator.ingest_rss", return_value=3)
    @patch("src.ingestion.orchestrator.ingest_gmail", return_value=2)
    def test_daily_pipeline_success(
        self,
        mock_gmail,
        mock_rss,
        mock_youtube,
        mock_podcast,
        mock_substack,
        mock_summarizer,
        mock_digest,
    ):
        mock_summarizer.return_value.summarize_pending_contents.return_value = 5

        mock_result = MagicMock()
        mock_result.title = "Daily Digest"
        mock_result.newsletter_count = 7
        mock_digest.return_value = mock_result

        result = runner.invoke(app, ["pipeline", "daily"])
        assert result.exit_code == 0
        assert "completed successfully" in result.output

    @patch("src.ingestion.orchestrator.ingest_substack", side_effect=RuntimeError("fail"))
    @patch("src.ingestion.orchestrator.ingest_podcast", side_effect=RuntimeError("fail"))
    @patch("src.ingestion.orchestrator.ingest_youtube", side_effect=RuntimeError("fail"))
    @patch("src.ingestion.orchestrator.ingest_rss", side_effect=RuntimeError("fail"))
    @patch("src.ingestion.orchestrator.ingest_gmail", side_effect=RuntimeError("fail"))
    def test_daily_pipeline_all_ingestion_fails(
        self, mock_gmail, mock_rss, mock_youtube, mock_podcast, mock_substack
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
    @patch("src.cli.adapters.create_digest_sync")
    @patch("src.processors.summarizer.ContentSummarizer")
    @patch("src.ingestion.orchestrator.ingest_substack", return_value=0)
    @patch("src.ingestion.orchestrator.ingest_podcast", return_value=2)
    @patch("src.ingestion.orchestrator.ingest_youtube", return_value=3)
    @patch("src.ingestion.orchestrator.ingest_rss", return_value=10)
    @patch("src.ingestion.orchestrator.ingest_gmail", return_value=5)
    def test_weekly_pipeline_success(
        self,
        mock_gmail,
        mock_rss,
        mock_youtube,
        mock_podcast,
        mock_substack,
        mock_summarizer,
        mock_digest,
    ):
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
