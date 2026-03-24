"""Tests for summarize CLI commands — HTTP path.

Tests the HTTP (API) code path in summarize_commands.py by mocking
_summarize_via_api so that we never hit real services or fall through
to the direct-mode implementation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import typer
from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


class TestSummarizePendingHTTP:
    """Test the HTTP path for 'aca summarize pending'."""

    @patch("src.cli.summarize_commands._summarize_via_api")
    def test_pending_calls_api_with_empty_params(self, mock_api: MagicMock) -> None:
        """Default invocation passes empty params dict."""
        result = runner.invoke(app, ["summarize", "pending"])
        assert result.exit_code == 0
        mock_api.assert_called_once_with({}, "Summarizing pending content")

    @patch("src.cli.summarize_commands._summarize_via_api")
    def test_pending_with_limit(self, mock_api: MagicMock) -> None:
        """--limit N includes query.limit in params."""
        result = runner.invoke(app, ["summarize", "pending", "--limit", "5"])
        assert result.exit_code == 0
        mock_api.assert_called_once()
        call_args = mock_api.call_args[0]
        params = call_args[0]
        assert params["query"]["limit"] == 5

    @patch("src.cli.summarize_commands._summarize_via_api")
    def test_pending_with_source_filter(self, mock_api: MagicMock) -> None:
        """--source gmail,rss includes query.source_types."""
        result = runner.invoke(app, ["summarize", "pending", "--source", "gmail,rss"])
        assert result.exit_code == 0
        mock_api.assert_called_once()
        params = mock_api.call_args[0][0]
        assert params["query"]["source_types"] == ["gmail", "rss"]

    @patch("src.cli.summarize_commands._summarize_via_api")
    def test_pending_with_dry_run(self, mock_api: MagicMock) -> None:
        """--dry-run sets dry_run=True in params."""
        result = runner.invoke(app, ["summarize", "pending", "--dry-run"])
        assert result.exit_code == 0
        mock_api.assert_called_once()
        params = mock_api.call_args[0][0]
        assert params["dry_run"] is True

    @patch("src.cli.summarize_commands._summarize_via_api")
    def test_pending_with_multiple_filters(self, mock_api: MagicMock) -> None:
        """Multiple filters are all included in query dict."""
        result = runner.invoke(
            app,
            [
                "summarize",
                "pending",
                "--source",
                "youtube",
                "--status",
                "pending",
                "--after",
                "2025-01-01",
                "--before",
                "2025-01-31",
                "--publication",
                "AI Weekly",
                "--search",
                "LLM",
                "--limit",
                "10",
            ],
        )
        assert result.exit_code == 0
        mock_api.assert_called_once()
        params = mock_api.call_args[0][0]
        query = params["query"]
        assert query["source_types"] == ["youtube"]
        assert query["statuses"] == ["pending"]
        assert query["after"] == "2025-01-01"
        assert query["before"] == "2025-01-31"
        assert query["publication"] == "AI Weekly"
        assert query["search"] == "LLM"
        assert query["limit"] == 10

    @patch("src.cli.summarize_commands._summarize_via_api")
    def test_pending_api_exit_code_propagated(self, mock_api: MagicMock) -> None:
        """typer.Exit raised inside _summarize_via_api propagates correctly."""
        mock_api.side_effect = typer.Exit(1)
        result = runner.invoke(app, ["summarize", "pending"])
        assert result.exit_code == 1

    @patch("src.cli.summarize_commands._summarize_pending_direct")
    @patch("src.cli.summarize_commands._summarize_via_api")
    def test_pending_fallback_on_connect_error(
        self, mock_api: MagicMock, mock_direct: MagicMock
    ) -> None:
        """ConnectError triggers fallback to direct mode."""
        mock_api.side_effect = httpx.ConnectError("Connection refused")
        result = runner.invoke(app, ["summarize", "pending"])
        assert result.exit_code == 0
        mock_direct.assert_called_once()


class TestSummarizeByIdHTTP:
    """Test the HTTP path for 'aca summarize id <id>'."""

    @patch("src.cli.summarize_commands._summarize_via_api")
    def test_id_calls_api_with_content_ids(self, mock_api: MagicMock) -> None:
        """summarize id 42 passes content_ids=[42]."""
        result = runner.invoke(app, ["summarize", "id", "42"])
        assert result.exit_code == 0
        mock_api.assert_called_once_with(
            {"content_ids": [42]},
            "Summarizing content 42",
        )

    @patch("src.cli.summarize_commands._summarize_by_id_direct")
    @patch("src.cli.summarize_commands._summarize_via_api")
    def test_id_fallback_on_connect_error(
        self, mock_api: MagicMock, mock_direct: MagicMock
    ) -> None:
        """ConnectError triggers fallback to direct mode for id command."""
        mock_api.side_effect = httpx.ConnectError("Connection refused")
        result = runner.invoke(app, ["summarize", "id", "99"])
        assert result.exit_code == 0
        mock_direct.assert_called_once_with(99, sync=False)

    @patch("src.cli.summarize_commands._summarize_via_api")
    def test_id_general_error_exits_1(self, mock_api: MagicMock) -> None:
        """Non-ConnectError exceptions are caught and exit 1."""
        mock_api.side_effect = RuntimeError("Unexpected")
        result = runner.invoke(app, ["summarize", "id", "10"])
        assert result.exit_code == 1
        assert "Error" in result.output
