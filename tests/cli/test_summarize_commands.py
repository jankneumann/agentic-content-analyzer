"""Tests for summarize CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


class TestSummarizePending:
    @patch("src.processors.summarizer.ContentSummarizer")
    def test_pending_success(self, mock_cls):
        mock_summarizer = MagicMock()
        mock_summarizer.summarize_pending_contents.return_value = 3
        mock_cls.return_value = mock_summarizer

        result = runner.invoke(app, ["summarize", "pending"])
        assert result.exit_code == 0
        assert "3" in result.output

    @patch("src.processors.summarizer.ContentSummarizer")
    def test_pending_with_limit(self, mock_cls):
        mock_summarizer = MagicMock()
        mock_summarizer.summarize_pending_contents.return_value = 2
        mock_cls.return_value = mock_summarizer

        result = runner.invoke(app, ["summarize", "pending", "--limit", "5"])
        assert result.exit_code == 0
        mock_summarizer.summarize_pending_contents.assert_called_once_with(limit=5)

    @patch("src.processors.summarizer.ContentSummarizer")
    def test_pending_failure(self, mock_cls):
        mock_cls.side_effect = RuntimeError("DB error")

        result = runner.invoke(app, ["summarize", "pending"])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestSummarizeById:
    @patch("src.processors.summarizer.ContentSummarizer")
    def test_by_id_success(self, mock_cls):
        mock_summarizer = MagicMock()
        mock_summarizer.summarize_content.return_value = True
        mock_cls.return_value = mock_summarizer

        result = runner.invoke(app, ["summarize", "id", "42"])
        assert result.exit_code == 0
        assert "42" in result.output

    @patch("src.processors.summarizer.ContentSummarizer")
    def test_by_id_not_found(self, mock_cls):
        mock_summarizer = MagicMock()
        mock_summarizer.summarize_content.return_value = False
        mock_cls.return_value = mock_summarizer

        result = runner.invoke(app, ["summarize", "id", "999"])
        assert result.exit_code == 1
        assert "Failed" in result.output or "Error" in result.output

    @patch("src.processors.summarizer.ContentSummarizer")
    def test_by_id_exception(self, mock_cls):
        mock_cls.side_effect = RuntimeError("API error")

        result = runner.invoke(app, ["summarize", "id", "42"])
        assert result.exit_code == 1


class TestSummarizeList:
    @patch("src.storage.database.get_db")
    def test_list_success(self, mock_get_db):
        mock_summary = MagicMock()
        mock_summary.id = 1
        mock_summary.content_id = 10
        mock_summary.executive_summary = "Test summary"
        mock_summary.key_themes = ["AI", "ML"]
        mock_summary.model_used = "claude"
        mock_summary.created_at = MagicMock()
        mock_summary.created_at.strftime.return_value = "2025-01-01 12:00"
        mock_summary.token_usage = 100

        mock_db = MagicMock()
        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [
            mock_summary
        ]
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = runner.invoke(app, ["summarize", "list"])
        assert result.exit_code == 0

    @patch("src.storage.database.get_db")
    def test_list_empty(self, mock_get_db):
        mock_db = MagicMock()
        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = runner.invoke(app, ["summarize", "list"])
        assert result.exit_code == 0
        assert "No summaries found" in result.output
