"""Tests for digest creation CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


class TestCreateDailyDigest:
    @patch("src.cli.adapters.create_digest_sync")
    def test_daily_default_date(self, mock_create):
        mock_result = MagicMock()
        mock_result.title = "Daily Digest"
        mock_result.newsletter_count = 5
        mock_result.model_used = "claude"
        mock_result.strategic_insights = [1, 2]
        mock_result.technical_developments = [1]
        mock_result.emerging_trends = [1, 2, 3]
        mock_create.return_value = mock_result

        result = runner.invoke(app, ["create-digest", "daily"])
        assert result.exit_code == 0
        assert "Daily digest created" in result.output

    @patch("src.cli.adapters.create_digest_sync")
    def test_daily_specific_date(self, mock_create):
        mock_result = MagicMock()
        mock_result.title = "Digest 2025-01-15"
        mock_result.newsletter_count = 3
        mock_result.model_used = "claude"
        mock_result.strategic_insights = []
        mock_result.technical_developments = []
        mock_result.emerging_trends = []
        mock_create.return_value = mock_result

        result = runner.invoke(app, ["create-digest", "daily", "--date", "2025-01-15"])
        assert result.exit_code == 0

    def test_daily_invalid_date(self):
        result = runner.invoke(app, ["create-digest", "daily", "--date", "not-a-date"])
        assert result.exit_code == 1 or "Invalid date" in result.output

    @patch("src.cli.adapters.create_digest_sync")
    def test_daily_failure(self, mock_create):
        mock_create.side_effect = RuntimeError("No content")

        result = runner.invoke(app, ["create-digest", "daily"])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestCreateWeeklyDigest:
    @patch("src.cli.adapters.create_digest_sync")
    def test_weekly_default(self, mock_create):
        mock_result = MagicMock()
        mock_result.title = "Weekly Digest"
        mock_result.newsletter_count = 20
        mock_result.model_used = "claude"
        mock_result.strategic_insights = [1, 2]
        mock_result.technical_developments = [1, 2, 3]
        mock_result.emerging_trends = [1]
        mock_create.return_value = mock_result

        result = runner.invoke(app, ["create-digest", "weekly"])
        assert result.exit_code == 0
        assert "Weekly digest created" in result.output

    @patch("src.cli.adapters.create_digest_sync")
    def test_weekly_specific_week(self, mock_create):
        mock_result = MagicMock()
        mock_result.title = "Week of 2025-01-13"
        mock_result.newsletter_count = 15
        mock_result.model_used = "claude"
        mock_result.strategic_insights = [1]
        mock_result.technical_developments = [1, 2]
        mock_result.emerging_trends = []
        mock_create.return_value = mock_result

        result = runner.invoke(app, ["create-digest", "weekly", "--week", "2025-01-15"])
        assert result.exit_code == 0

    def test_weekly_invalid_date(self):
        result = runner.invoke(app, ["create-digest", "weekly", "--week", "bad"])
        assert result.exit_code == 1 or "Invalid date" in result.output

    @patch("src.cli.adapters.create_digest_sync")
    def test_weekly_failure(self, mock_create):
        mock_create.side_effect = RuntimeError("Service error")

        result = runner.invoke(app, ["create-digest", "weekly"])
        assert result.exit_code == 1
