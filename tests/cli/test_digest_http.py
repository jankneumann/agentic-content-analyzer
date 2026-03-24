"""Tests for digest creation CLI commands — HTTP path.

Tests the HTTP (API) code path in digest_commands.py by mocking
_digest_via_api so that we never hit real services or fall through
to the direct-mode implementation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


class TestCreateDailyDigestHTTP:
    """Test the HTTP path for 'aca create-digest daily'."""

    @patch("src.cli.digest_commands._digest_via_api")
    def test_daily_default(self, mock_api: MagicMock) -> None:
        """Default daily digest passes digest_type='daily' with no period."""
        result = runner.invoke(app, ["create-digest", "daily"])
        assert result.exit_code == 0
        mock_api.assert_called_once()
        params = mock_api.call_args[0][0]
        assert params["digest_type"] == "daily"
        # No date specified, so no period_start/end
        assert "period_start" not in params
        assert "period_end" not in params

    @patch("src.cli.digest_commands._digest_via_api")
    def test_daily_with_date(self, mock_api: MagicMock) -> None:
        """--date flag includes period_start and period_end (next day)."""
        result = runner.invoke(app, ["create-digest", "daily", "--date", "2025-01-15"])
        assert result.exit_code == 0
        mock_api.assert_called_once()
        params = mock_api.call_args[0][0]
        assert params["digest_type"] == "daily"
        assert "2025-01-15" in params["period_start"]
        assert "2025-01-16" in params["period_end"]

    @patch("src.cli.digest_commands._digest_via_api")
    def test_daily_with_dry_run(self, mock_api: MagicMock) -> None:
        """--dry-run sets dry_run=True in params."""
        result = runner.invoke(app, ["create-digest", "daily", "--dry-run"])
        assert result.exit_code == 0
        mock_api.assert_called_once()
        params = mock_api.call_args[0][0]
        assert params["dry_run"] is True

    @patch("src.cli.digest_commands._digest_via_api")
    def test_daily_with_source_filter(self, mock_api: MagicMock) -> None:
        """--source includes content_query.source_types in params."""
        result = runner.invoke(app, ["create-digest", "daily", "--source", "gmail,rss"])
        assert result.exit_code == 0
        params = mock_api.call_args[0][0]
        assert params["content_query"]["source_types"] == ["gmail", "rss"]

    @patch("src.cli.digest_commands._create_digest_direct")
    @patch("src.cli.digest_commands._digest_via_api")
    def test_daily_fallback_on_connect_error(
        self, mock_api: MagicMock, mock_direct: MagicMock
    ) -> None:
        """ConnectError triggers fallback to direct mode."""
        mock_api.side_effect = httpx.ConnectError("Connection refused")
        result = runner.invoke(app, ["create-digest", "daily"])
        assert result.exit_code == 0
        mock_direct.assert_called_once()
        # Verify it falls back with digest_type="daily"
        assert mock_direct.call_args[0][0] == "daily"

    @patch("src.cli.digest_commands._digest_via_api")
    def test_daily_general_error_exits_1(self, mock_api: MagicMock) -> None:
        """Non-ConnectError exceptions exit with code 1."""
        mock_api.side_effect = RuntimeError("Something broke")
        result = runner.invoke(app, ["create-digest", "daily"])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestCreateWeeklyDigestHTTP:
    """Test the HTTP path for 'aca create-digest weekly'."""

    @patch("src.cli.digest_commands._digest_via_api")
    def test_weekly_default(self, mock_api: MagicMock) -> None:
        """Default weekly digest passes digest_type='weekly' with no period."""
        result = runner.invoke(app, ["create-digest", "weekly"])
        assert result.exit_code == 0
        mock_api.assert_called_once()
        params = mock_api.call_args[0][0]
        assert params["digest_type"] == "weekly"
        assert "period_start" not in params

    @patch("src.cli.digest_commands._digest_via_api")
    def test_weekly_with_week_date(self, mock_api: MagicMock) -> None:
        """--week date computes Monday-to-Monday period.

        2025-01-15 is a Wednesday; Monday of that week is 2025-01-13,
        period_end is 2025-01-20 (7 days later).
        """
        result = runner.invoke(app, ["create-digest", "weekly", "--week", "2025-01-15"])
        assert result.exit_code == 0
        mock_api.assert_called_once()
        params = mock_api.call_args[0][0]
        assert params["digest_type"] == "weekly"
        assert "2025-01-13" in params["period_start"]
        assert "2025-01-20" in params["period_end"]

    @patch("src.cli.digest_commands._digest_via_api")
    def test_weekly_with_dry_run(self, mock_api: MagicMock) -> None:
        """--dry-run sets dry_run=True."""
        result = runner.invoke(app, ["create-digest", "weekly", "--dry-run"])
        assert result.exit_code == 0
        params = mock_api.call_args[0][0]
        assert params["dry_run"] is True

    @patch("src.cli.digest_commands._digest_via_api")
    def test_weekly_with_publication_filter(self, mock_api: MagicMock) -> None:
        """--publication includes content_query.publication in params."""
        result = runner.invoke(app, ["create-digest", "weekly", "--publication", "The Batch"])
        assert result.exit_code == 0
        params = mock_api.call_args[0][0]
        assert params["content_query"]["publication"] == "The Batch"

    @patch("src.cli.digest_commands._digest_via_api")
    def test_weekly_with_search_filter(self, mock_api: MagicMock) -> None:
        """--search includes content_query.search in params."""
        result = runner.invoke(app, ["create-digest", "weekly", "--search", "transformer"])
        assert result.exit_code == 0
        params = mock_api.call_args[0][0]
        assert params["content_query"]["search"] == "transformer"

    @patch("src.cli.digest_commands._create_digest_direct")
    @patch("src.cli.digest_commands._digest_via_api")
    def test_weekly_fallback_on_connect_error(
        self, mock_api: MagicMock, mock_direct: MagicMock
    ) -> None:
        """ConnectError triggers fallback to direct mode."""
        mock_api.side_effect = httpx.ConnectError("Connection refused")
        result = runner.invoke(app, ["create-digest", "weekly"])
        assert result.exit_code == 0
        mock_direct.assert_called_once()
        assert mock_direct.call_args[0][0] == "weekly"
