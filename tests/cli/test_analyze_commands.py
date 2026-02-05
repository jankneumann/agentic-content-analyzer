"""Tests for analyze CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


class TestAnalyzeThemes:
    @patch("src.cli.adapters.analyze_themes_sync")
    def test_themes_success(self, mock_analyze):
        mock_theme = MagicMock()
        mock_theme.name = "Large Language Models"
        mock_theme.description = "Advances in LLMs"
        mock_theme.category = MagicMock()
        mock_theme.category.value = "ai_ml"
        mock_theme.trend = MagicMock()
        mock_theme.trend.value = "growing"
        mock_theme.newsletter_ids = [1, 2, 3]
        mock_theme.relevance_score = 0.85

        mock_result = MagicMock()
        mock_result.themes = [mock_theme]
        mock_result.total_themes = 1
        mock_result.newsletter_count = 10
        mock_result.top_theme = "Large Language Models"
        mock_result.cross_theme_insights = ["LLMs are converging with agents"]
        mock_analyze.return_value = mock_result

        result = runner.invoke(app, ["analyze", "themes"])
        assert result.exit_code == 0
        assert "Large Language Models" in result.output

    @patch("src.cli.adapters.analyze_themes_sync")
    def test_themes_with_dates(self, mock_analyze):
        mock_result = MagicMock()
        mock_result.themes = []
        mock_result.total_themes = 0
        mock_analyze.return_value = mock_result

        result = runner.invoke(
            app,
            [
                "analyze",
                "themes",
                "--start",
                "2025-01-01",
                "--end",
                "2025-01-07",
            ],
        )
        assert result.exit_code == 0

    def test_themes_invalid_date(self):
        result = runner.invoke(app, ["analyze", "themes", "--start", "bad-date"])
        assert result.exit_code == 1
        assert "Invalid date" in result.output or "Error" in result.output

    def test_themes_start_after_end(self):
        result = runner.invoke(
            app,
            [
                "analyze",
                "themes",
                "--start",
                "2025-01-10",
                "--end",
                "2025-01-01",
            ],
        )
        assert result.exit_code == 1

    @patch("src.cli.adapters.analyze_themes_sync")
    def test_themes_no_results(self, mock_analyze):
        mock_result = MagicMock()
        mock_result.themes = []
        mock_analyze.return_value = mock_result

        result = runner.invoke(app, ["analyze", "themes"])
        assert result.exit_code == 0
        assert "No themes found" in result.output

    @patch("src.cli.adapters.analyze_themes_sync")
    def test_themes_failure(self, mock_analyze):
        mock_analyze.side_effect = RuntimeError("Analysis error")

        result = runner.invoke(app, ["analyze", "themes"])
        assert result.exit_code == 1
        assert "failed" in result.output.lower() or "error" in result.output.lower()
