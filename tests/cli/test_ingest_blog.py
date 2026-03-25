"""Tests for aca ingest blog CLI command."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


class TestBlogCommand:
    """Tests for the blog ingest CLI command."""

    @patch("src.cli.ingest_commands.is_direct_mode", return_value=True)
    @patch("src.ingestion.orchestrator.ingest_blog", return_value=5)
    def test_blog_direct_mode(self, mock_ingest, mock_direct):
        """Blog command works in direct mode."""
        result = runner.invoke(app, ["ingest", "blog", "--max", "10"])
        assert result.exit_code == 0
        mock_ingest.assert_called_once()
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["max_entries_per_source"] == 10

    @patch("src.cli.ingest_commands.is_direct_mode", return_value=True)
    @patch("src.ingestion.orchestrator.ingest_blog", return_value=3)
    def test_blog_with_days_filter(self, mock_ingest, mock_direct):
        """Blog command passes after_date when --days specified."""
        result = runner.invoke(app, ["ingest", "blog", "--days", "7"])
        assert result.exit_code == 0
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["after_date"] is not None

    @patch("src.cli.ingest_commands.is_direct_mode", return_value=True)
    @patch("src.ingestion.orchestrator.ingest_blog", return_value=0)
    def test_blog_with_force(self, mock_ingest, mock_direct):
        """Blog command passes force_reprocess flag."""
        result = runner.invoke(app, ["ingest", "blog", "--force"])
        assert result.exit_code == 0
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["force_reprocess"] is True

    @patch("src.cli.ingest_commands.is_direct_mode", return_value=True)
    @patch("src.ingestion.orchestrator.ingest_blog", return_value=0)
    def test_blog_defaults(self, mock_ingest, mock_direct):
        """Blog command uses sensible defaults."""
        result = runner.invoke(app, ["ingest", "blog"])
        assert result.exit_code == 0
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["max_entries_per_source"] == 10
        assert call_kwargs["after_date"] is None
        assert call_kwargs["force_reprocess"] is False

    def test_blog_help(self):
        """Blog command shows help text."""
        result = runner.invoke(app, ["ingest", "blog", "--help"])
        assert result.exit_code == 0
        assert "blog" in result.output.lower()
