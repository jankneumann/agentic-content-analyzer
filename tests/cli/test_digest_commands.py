"""Tests for digest creation CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.app import app
from src.models.query import ContentQuery, ContentQueryPreview

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


class TestDigestWithFilters:
    """Tests for digest creation with content query filters."""

    @patch("src.cli.adapters.create_digest_sync")
    def test_daily_with_source_filter(self, mock_create):
        mock_result = MagicMock()
        mock_result.title = "Filtered Digest"
        mock_result.newsletter_count = 3
        mock_result.model_used = "claude"
        mock_result.strategic_insights = [1]
        mock_result.technical_developments = []
        mock_result.emerging_trends = []
        mock_create.return_value = mock_result

        result = runner.invoke(
            app,
            [
                "create-digest",
                "daily",
                "--date",
                "2026-01-15",
                "--source",
                "gmail",
            ],
        )
        assert result.exit_code == 0
        # Verify request has content_query
        call_args = mock_create.call_args[0][0]
        assert call_args.content_query is not None
        assert call_args.content_query.source_types is not None

    @patch("src.cli.adapters.create_digest_sync")
    def test_daily_with_publication_filter(self, mock_create):
        mock_result = MagicMock()
        mock_result.title = "Publication Filtered"
        mock_result.newsletter_count = 2
        mock_result.model_used = "claude"
        mock_result.strategic_insights = []
        mock_result.technical_developments = []
        mock_result.emerging_trends = []
        mock_create.return_value = mock_result

        result = runner.invoke(
            app,
            [
                "create-digest",
                "daily",
                "--publication",
                "The Batch",
            ],
        )
        assert result.exit_code == 0
        call_args = mock_create.call_args[0][0]
        assert call_args.content_query.publication_search == "The Batch"

    @patch("src.services.content_query.ContentQueryService")
    def test_daily_dry_run(self, mock_svc_cls):
        preview = ContentQueryPreview(
            total_count=8,
            by_source={"gmail": 5, "rss": 3},
            by_status={"COMPLETED": 8},
            date_range={"earliest": "2026-01-15", "latest": "2026-01-15"},
            sample_titles=["Title 1", "Title 2"],
            query=ContentQuery(),
        )
        mock_svc_cls.return_value.preview.return_value = preview

        result = runner.invoke(
            app,
            [
                "create-digest",
                "daily",
                "--date",
                "2026-01-15",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "8" in result.output

    @patch("src.services.content_query.ContentQueryService")
    def test_daily_dry_run_no_digest_created(self, mock_svc_cls):
        preview = ContentQueryPreview(
            total_count=0,
            by_source={},
            by_status={},
            date_range={},
            sample_titles=[],
            query=ContentQuery(),
        )
        mock_svc_cls.return_value.preview.return_value = preview

        with patch("src.cli.adapters.create_digest_sync") as mock_create:
            result = runner.invoke(app, ["create-digest", "daily", "--dry-run"])
            assert result.exit_code == 0
            mock_create.assert_not_called()

    @patch("src.cli.adapters.create_digest_sync")
    def test_weekly_with_source_filter(self, mock_create):
        mock_result = MagicMock()
        mock_result.title = "Weekly Filtered"
        mock_result.newsletter_count = 10
        mock_result.model_used = "claude"
        mock_result.strategic_insights = [1]
        mock_result.technical_developments = [1, 2]
        mock_result.emerging_trends = []
        mock_create.return_value = mock_result

        result = runner.invoke(
            app,
            [
                "create-digest",
                "weekly",
                "--week",
                "2026-01-15",
                "--source",
                "rss,youtube",
            ],
        )
        assert result.exit_code == 0
        call_args = mock_create.call_args[0][0]
        assert call_args.content_query is not None
        assert len(call_args.content_query.source_types) == 2

    @patch("src.cli.adapters.create_digest_sync")
    def test_default_behavior_unchanged(self, mock_create):
        """No filters = no content_query on request (regression)."""
        mock_result = MagicMock()
        mock_result.title = "Default Digest"
        mock_result.newsletter_count = 5
        mock_result.model_used = "claude"
        mock_result.strategic_insights = []
        mock_result.technical_developments = []
        mock_result.emerging_trends = []
        mock_create.return_value = mock_result

        result = runner.invoke(app, ["create-digest", "daily"])
        assert result.exit_code == 0
        call_args = mock_create.call_args[0][0]
        assert call_args.content_query is None

    def test_invalid_source_exits_with_error(self):
        result = runner.invoke(
            app,
            [
                "create-digest",
                "daily",
                "--source",
                "badvalue",
            ],
        )
        assert result.exit_code != 0
