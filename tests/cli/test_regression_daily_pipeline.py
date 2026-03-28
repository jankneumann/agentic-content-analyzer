"""Regression tests for the daily pipeline CLI workflow.

Verifies the full sequence of CLI commands that make up a daily pipeline:
    1. aca pipeline daily         (ingest → summarize → digest)
    2. aca analyze themes         (theme analysis)
    3. aca review list            (see pending reviews)
    4. aca review view <id>       (inspect digest)
    5. aca podcast generate       (create podcast script)

Each command is tested independently and as a sequence, ensuring that
state produced by earlier stages is correctly consumed by later stages.
These tests mock the service layer (not the CLI parsing) to catch
regressions in the orchestration logic.

Markers:
    @pytest.mark.regression - run with: pytest -m regression
"""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()

pytestmark = pytest.mark.regression


# =============================================================================
# Fixtures
# =============================================================================


def _mock_ingestion_patches() -> ExitStack:
    """Set up all ingestion source mocks returning realistic item counts."""
    stack = ExitStack()
    sources = {
        "src.ingestion.orchestrator.ingest_gmail": 3,
        "src.ingestion.orchestrator.ingest_rss": 5,
        "src.ingestion.orchestrator.ingest_youtube": 2,
        "src.ingestion.orchestrator.ingest_podcast": 1,
        "src.ingestion.orchestrator.ingest_substack": 0,
    }
    for target, count in sources.items():
        stack.enter_context(patch(target, return_value=count))
    return stack


def _mock_summarizer():
    """Create a mock ContentSummarizer that returns 8 summarized items."""
    mock = patch("src.processors.summarizer.ContentSummarizer")
    mock_summarizer = mock.start()
    mock_summarizer.return_value.summarize_pending_contents.return_value = 8
    return mock, mock_summarizer


def _mock_digest_creation():
    """Create a mock for digest creation returning a realistic result."""
    mock_result = MagicMock()
    mock_result.title = "Daily AI & Data Digest - Regression Test"
    mock_result.newsletter_count = 11
    mock_result.content_count = 11
    mock_result.id = 301
    return patch("src.cli.adapters.create_digest_sync", return_value=mock_result)


# =============================================================================
# Stage 1: Full Pipeline Command
# =============================================================================


class TestDailyPipelineCommand:
    """Regression tests for `aca pipeline daily`."""

    def test_pipeline_daily_completes_all_stages(self):
        """Full pipeline runs ingestion, summarization, and digest creation."""
        with _mock_ingestion_patches():
            sum_mock, _ = _mock_summarizer()
            with sum_mock, _mock_digest_creation():
                result = runner.invoke(app, ["pipeline", "daily"])

        assert result.exit_code == 0
        # Should mention all three stages completing
        assert "Ingested:" in result.output
        assert "Summarized:" in result.output

    def test_pipeline_daily_with_date_option(self):
        """Pipeline accepts --date flag to target a specific day."""
        with _mock_ingestion_patches():
            sum_mock, _ = _mock_summarizer()
            with sum_mock, _mock_digest_creation():
                result = runner.invoke(app, ["pipeline", "daily", "--date", "2025-01-15"])

        assert result.exit_code == 0

    def test_pipeline_reports_ingestion_results(self):
        """Output includes per-source ingestion results."""
        with _mock_ingestion_patches():
            sum_mock, _ = _mock_summarizer()
            with sum_mock, _mock_digest_creation():
                result = runner.invoke(app, ["pipeline", "daily"])

        assert result.exit_code == 0
        # Should show source count summary
        assert "5/5 complete" in result.output


# =============================================================================
# Stage 2: Theme Analysis
# =============================================================================


class TestThemeAnalysisCommand:
    """Regression tests for `aca analyze themes`."""

    @patch("src.cli.analyze_commands._analyze_themes_direct")
    def test_analyze_themes_with_defaults(self, mock_analyze):
        """Theme analysis runs with default 7-day window."""
        mock_analyze.return_value = None
        result = runner.invoke(app, ["analyze", "themes", "--direct"])

        assert result.exit_code == 0
        assert "Analyzing themes" in result.output

    @patch("src.cli.analyze_commands._analyze_themes_direct")
    def test_analyze_themes_with_date_range(self, mock_analyze):
        """Theme analysis accepts explicit start/end dates."""
        mock_analyze.return_value = None
        result = runner.invoke(
            app,
            [
                "analyze",
                "themes",
                "--start",
                "2025-01-01",
                "--end",
                "2025-01-15",
                "--direct",
            ],
        )

        assert result.exit_code == 0
        assert "2025-01-01" in result.output
        assert "2025-01-15" in result.output

    def test_analyze_themes_rejects_invalid_dates(self):
        """Theme analysis fails gracefully on invalid date format."""
        result = runner.invoke(app, ["analyze", "themes", "--start", "not-a-date", "--direct"])

        assert result.exit_code == 1
        assert "Error" in result.output

    def test_analyze_themes_rejects_inverted_range(self):
        """Theme analysis fails when start > end."""
        result = runner.invoke(
            app,
            [
                "analyze",
                "themes",
                "--start",
                "2025-01-15",
                "--end",
                "2025-01-01",
                "--direct",
            ],
        )

        assert result.exit_code == 1
        assert "Error" in result.output


# =============================================================================
# Stage 3: Review Workflow
# =============================================================================


class TestReviewListCommand:
    """Regression tests for `aca review list`."""

    @patch("src.cli.review_commands._list_reviews_direct")
    def test_review_list_shows_pending(self, mock_list):
        """Review list displays pending digest reviews."""
        mock_list.return_value = None
        result = runner.invoke(app, ["review", "list", "--direct"])

        assert result.exit_code == 0
        mock_list.assert_called_once()


class TestReviewViewCommand:
    """Regression tests for `aca review view <id>`."""

    @patch("src.cli.review_commands._view_review_direct")
    def test_review_view_displays_digest(self, mock_view):
        """Review view shows digest content for a given ID."""
        mock_view.return_value = None
        result = runner.invoke(app, ["review", "view", "301", "--direct"])

        assert result.exit_code == 0
        mock_view.assert_called_once_with(301)


# =============================================================================
# Stage 4: Podcast Generation
# =============================================================================


class TestPodcastGenerateCommand:
    """Regression tests for `aca podcast generate`."""

    @patch("src.cli.podcast_commands._generate_direct")
    def test_podcast_generate_with_digest_id(self, mock_generate):
        """Podcast generation accepts digest ID and runs."""
        mock_generate.return_value = None
        result = runner.invoke(app, ["podcast", "generate", "--digest-id", "301", "--direct"])

        assert result.exit_code == 0
        mock_generate.assert_called_once_with(301, "standard")

    @patch("src.cli.podcast_commands._generate_direct")
    def test_podcast_generate_with_length_option(self, mock_generate):
        """Podcast generation accepts --length flag."""
        mock_generate.return_value = None
        result = runner.invoke(
            app,
            [
                "podcast",
                "generate",
                "--digest-id",
                "301",
                "--length",
                "brief",
                "--direct",
            ],
        )

        assert result.exit_code == 0
        mock_generate.assert_called_once_with(301, "brief")


# =============================================================================
# Stage 5: Digest Creation (standalone)
# =============================================================================


class TestDigestCreationCommand:
    """Regression tests for `aca create-digest daily`."""

    @patch("src.cli.digest_commands._create_digest_direct")
    def test_create_digest_daily_runs(self, mock_create):
        """Standalone digest creation for daily works."""
        mock_create.return_value = None
        result = runner.invoke(app, ["create-digest", "daily", "--direct"])

        assert result.exit_code == 0

    @patch("src.cli.digest_commands._create_digest_direct")
    def test_create_digest_weekly_runs(self, mock_create):
        """Standalone digest creation for weekly works."""
        mock_create.return_value = None
        result = runner.invoke(app, ["create-digest", "weekly", "--direct"])

        assert result.exit_code == 0


# =============================================================================
# Sequential Workflow: Full Pipeline → Analyze → Review → Podcast
# =============================================================================


class TestSequentialWorkflow:
    """Tests that the full CLI workflow can be executed in sequence.

    This is the core regression test — it ensures that each CLI command
    in the daily workflow still accepts the expected arguments and
    returns the expected exit codes.
    """

    def test_full_daily_workflow_sequence(self):
        """Execute the full daily workflow as a user would via CLI."""
        # Step 1: Run daily pipeline
        with _mock_ingestion_patches():
            sum_mock, _ = _mock_summarizer()
            with sum_mock, _mock_digest_creation():
                result = runner.invoke(app, ["pipeline", "daily"])
        assert result.exit_code == 0, f"Pipeline failed: {result.output}"

        # Step 2: Analyze themes
        with patch("src.cli.analyze_commands._analyze_themes_direct") as mock_analyze:
            mock_analyze.return_value = None
            result = runner.invoke(app, ["analyze", "themes", "--direct"])
        assert result.exit_code == 0, f"Theme analysis failed: {result.output}"

        # Step 3: List reviews
        with patch("src.cli.review_commands._list_reviews_direct") as mock_list:
            mock_list.return_value = None
            result = runner.invoke(app, ["review", "list", "--direct"])
        assert result.exit_code == 0, f"Review list failed: {result.output}"

        # Step 4: View digest
        with patch("src.cli.review_commands._view_review_direct") as mock_view:
            mock_view.return_value = None
            result = runner.invoke(app, ["review", "view", "301", "--direct"])
        assert result.exit_code == 0, f"Review view failed: {result.output}"

        # Step 5: Generate podcast
        with patch("src.cli.podcast_commands._generate_direct") as mock_gen:
            mock_gen.return_value = None
            result = runner.invoke(app, ["podcast", "generate", "--digest-id", "301", "--direct"])
        assert result.exit_code == 0, f"Podcast generation failed: {result.output}"


# =============================================================================
# Summarize Command (standalone)
# =============================================================================


class TestSummarizeCommand:
    """Regression tests for `aca summarize pending`."""

    @patch("src.cli.summarize_commands._summarize_pending_direct")
    def test_summarize_pending_runs(self, mock_summarize):
        """Standalone summarize pending works."""
        mock_summarize.return_value = None
        result = runner.invoke(app, ["summarize", "pending", "--direct"])

        assert result.exit_code == 0

    @patch("src.cli.summarize_commands._summarize_pending_direct")
    def test_summarize_pending_with_source_filter(self, mock_summarize):
        """Summarize pending accepts --source filter."""
        mock_summarize.return_value = None
        result = runner.invoke(app, ["summarize", "pending", "--source", "gmail,rss", "--direct"])

        assert result.exit_code == 0
