"""Tests for review CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


def _make_mock_digest(**overrides):
    """Create a mock digest object with sensible defaults."""
    digest = MagicMock()
    digest.id = overrides.get("id", 1)
    digest.digest_type = overrides.get("digest_type", "daily")
    digest.title = overrides.get("title", "Test Digest")
    digest.status = overrides.get("status", "pending_review")
    digest.period_start = MagicMock()
    digest.period_start.strftime.return_value = "2025-01-01"
    digest.period_end = MagicMock()
    digest.period_end.strftime.return_value = "2025-01-02"
    digest.newsletter_count = overrides.get("newsletter_count", 5)
    digest.revision_count = overrides.get("revision_count", 0)
    digest.created_at = MagicMock()
    digest.created_at.strftime.return_value = "2025-01-01 12:00"
    digest.reviewed_by = None
    digest.reviewed_at = None
    digest.model_used = "claude"
    digest.markdown_content = overrides.get("markdown_content", "# Test Content")
    digest.executive_overview = "Test overview"
    digest.strategic_insights = []
    digest.technical_developments = []
    digest.emerging_trends = []
    digest.actionable_recommendations = {}
    return digest


class TestReviewList:
    @patch("src.cli.review_commands.list_pending_reviews_sync")
    def test_list_with_results(self, mock_list):
        mock_list.return_value = [_make_mock_digest(), _make_mock_digest(id=2)]

        result = runner.invoke(app, ["review", "list"])
        assert result.exit_code == 0
        assert "2 digest(s) pending review" in result.output

    @patch("src.cli.review_commands.list_pending_reviews_sync")
    def test_list_empty(self, mock_list):
        mock_list.return_value = []

        result = runner.invoke(app, ["review", "list"])
        assert result.exit_code == 0
        assert "No digests pending review" in result.output

    @patch("src.cli.review_commands.list_pending_reviews_sync")
    def test_list_failure(self, mock_list):
        mock_list.side_effect = RuntimeError("DB error")

        result = runner.invoke(app, ["review", "list"])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestReviewView:
    @patch("src.cli.review_commands.get_digest_sync")
    def test_view_success(self, mock_get):
        mock_get.return_value = _make_mock_digest()

        result = runner.invoke(app, ["review", "view", "1"])
        assert result.exit_code == 0

    @patch("src.cli.review_commands.get_digest_sync")
    def test_view_not_found(self, mock_get):
        mock_get.return_value = None

        result = runner.invoke(app, ["review", "view", "999"])
        assert result.exit_code == 1
        assert "not found" in result.output

    @patch("src.cli.review_commands.get_digest_sync")
    def test_view_error(self, mock_get):
        mock_get.side_effect = RuntimeError("Connection error")

        result = runner.invoke(app, ["review", "view", "1"])
        assert result.exit_code == 1


class TestReviewRevise:
    @patch("src.cli.review_commands.finalize_review_sync")
    @patch("src.cli.review_commands.start_revision_session_sync")
    @patch("src.cli.review_commands.get_digest_sync")
    def test_revise_immediate_done(self, mock_get, mock_start, mock_finalize):
        mock_get.return_value = _make_mock_digest()
        mock_start.return_value = MagicMock()

        # Simulate user typing "done" immediately
        result = runner.invoke(app, ["review", "revise", "1"], input="done\n")
        assert result.exit_code == 0
        assert "finalized" in result.output.lower() or "approved" in result.output.lower()
        mock_finalize.assert_called_once()

    @patch("src.cli.review_commands.finalize_review_sync")
    @patch("src.cli.review_commands.process_revision_turn_sync")
    @patch("src.cli.review_commands.start_revision_session_sync")
    @patch("src.cli.review_commands.get_digest_sync")
    def test_revise_with_turn(self, mock_get, mock_start, mock_process, mock_finalize):
        mock_get.return_value = _make_mock_digest()
        mock_start.return_value = MagicMock()

        mock_turn_result = MagicMock()
        mock_turn_result.section_modified = "executive_overview"
        mock_turn_result.explanation = "Made it more concise"
        mock_turn_result.confidence_score = 0.9
        mock_turn_result.revised_content = "Updated overview text"
        mock_process.return_value = mock_turn_result

        result = runner.invoke(
            app,
            ["review", "revise", "1"],
            input="Make it shorter\ndone\n",
        )
        assert result.exit_code == 0
        mock_process.assert_called_once()

    @patch("src.cli.review_commands.get_digest_sync")
    def test_revise_digest_not_found(self, mock_get):
        mock_get.return_value = None

        result = runner.invoke(app, ["review", "revise", "999"])
        assert result.exit_code == 1
        assert "not found" in result.output
