"""Tests for summarize CLI commands."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from src.cli.app import app

runner = CliRunner()


class TestSummarizePending:
    @patch("src.processors.summarizer.ContentSummarizer")
    def test_pending_sync_success(self, mock_cls):
        mock_summarizer = MagicMock()
        mock_summarizer.summarize_pending_contents.return_value = 3
        mock_cls.return_value = mock_summarizer

        result = runner.invoke(app, ["summarize", "pending", "--sync"])
        assert result.exit_code == 0
        assert "3" in result.output

    @patch("src.processors.summarizer.ContentSummarizer")
    def test_pending_sync_with_limit(self, mock_cls):
        mock_summarizer = MagicMock()
        mock_summarizer.summarize_pending_contents.return_value = 2
        mock_cls.return_value = mock_summarizer

        result = runner.invoke(app, ["summarize", "pending", "--sync", "--limit", "5"])
        assert result.exit_code == 0
        mock_summarizer.summarize_pending_contents.assert_called_once_with(limit=5, query=None)

    @patch("src.processors.summarizer.ContentSummarizer")
    def test_pending_sync_failure(self, mock_cls):
        mock_cls.side_effect = RuntimeError("DB error")

        result = runner.invoke(app, ["summarize", "pending", "--sync"])
        assert result.exit_code == 1
        assert "Error" in result.output

    @patch("src.processors.summarizer.ContentSummarizer")
    def test_pending_queue_success(self, mock_cls):
        mock_summarizer = MagicMock()
        mock_summarizer.enqueue_pending_contents = AsyncMock(
            return_value={
                "enqueued_count": 5,
                "skipped_count": 1,
                "job_ids": [101, 102, 103, 104, 105],
            }
        )
        mock_cls.return_value = mock_summarizer

        result = runner.invoke(app, ["summarize", "pending"])
        assert result.exit_code == 0
        assert "5" in result.output
        assert "1 already in queue" in result.output

    @patch("src.processors.summarizer.ContentSummarizer")
    def test_pending_queue_with_limit(self, mock_cls):
        mock_summarizer = MagicMock()
        mock_summarizer.enqueue_pending_contents = AsyncMock(
            return_value={
                "enqueued_count": 3,
                "skipped_count": 0,
                "job_ids": [101, 102, 103],
            }
        )
        mock_cls.return_value = mock_summarizer

        result = runner.invoke(app, ["summarize", "pending", "--limit", "3"])
        assert result.exit_code == 0
        mock_summarizer.enqueue_pending_contents.assert_called_once_with(limit=3, query=None)


class TestSummarizePendingWithFilters:
    """Tests for summarize pending with content query filters."""

    @patch("src.processors.summarizer.ContentSummarizer")
    def test_source_filter_builds_query(self, mock_cls):
        mock_summarizer = MagicMock()
        mock_summarizer.summarize_pending_contents.return_value = 2
        mock_cls.return_value = mock_summarizer

        result = runner.invoke(app, ["summarize", "pending", "--sync", "--source", "gmail"])
        assert result.exit_code == 0
        call_kwargs = mock_summarizer.summarize_pending_contents.call_args[1]
        assert call_kwargs["query"] is not None
        assert call_kwargs["query"].source_types is not None

    @patch("src.processors.summarizer.ContentSummarizer")
    def test_combined_filters(self, mock_cls):
        mock_summarizer = MagicMock()
        mock_summarizer.summarize_pending_contents.return_value = 1
        mock_cls.return_value = mock_summarizer

        result = runner.invoke(
            app,
            [
                "summarize",
                "pending",
                "--sync",
                "--source",
                "gmail,rss",
                "--publication",
                "The Batch",
                "--search",
                "transformer",
            ],
        )
        assert result.exit_code == 0
        call_kwargs = mock_summarizer.summarize_pending_contents.call_args[1]
        q = call_kwargs["query"]
        assert q is not None
        assert len(q.source_types) == 2
        assert q.publication_search == "The Batch"
        assert q.search == "transformer"

    def test_invalid_source_exits_with_error(self):
        result = runner.invoke(app, ["summarize", "pending", "--sync", "--source", "badvalue"])
        assert result.exit_code != 0

    @patch("src.services.content_query.ContentQueryService")
    def test_dry_run_shows_preview(self, mock_svc_cls):
        from src.models.query import ContentQuery, ContentQueryPreview

        preview = ContentQueryPreview(
            total_count=5,
            by_source={"gmail": 3, "rss": 2},
            by_status={"PENDING": 5},
            date_range={"earliest": "2026-01-01", "latest": "2026-02-28"},
            sample_titles=["Title A", "Title B"],
            query=ContentQuery(),
        )
        mock_svc_cls.return_value.preview.return_value = preview

        result = runner.invoke(app, ["summarize", "pending", "--dry-run"])
        assert result.exit_code == 0
        assert "5" in result.output
        assert "Preview" in result.output or "Matching" in result.output

    @patch("src.services.content_query.ContentQueryService")
    def test_dry_run_no_summarize_called(self, mock_svc_cls):
        from src.models.query import ContentQuery, ContentQueryPreview

        preview = ContentQueryPreview(
            total_count=0,
            by_source={},
            by_status={},
            date_range={},
            sample_titles=[],
            query=ContentQuery(),
        )
        mock_svc_cls.return_value.preview.return_value = preview

        with patch("src.processors.summarizer.ContentSummarizer") as mock_sum_cls:
            result = runner.invoke(app, ["summarize", "pending", "--dry-run"])
            assert result.exit_code == 0
            mock_sum_cls.assert_not_called()

    @patch("src.processors.summarizer.ContentSummarizer")
    def test_date_filters(self, mock_cls):
        mock_summarizer = MagicMock()
        mock_summarizer.summarize_pending_contents.return_value = 1
        mock_cls.return_value = mock_summarizer

        result = runner.invoke(
            app,
            [
                "summarize",
                "pending",
                "--sync",
                "--after",
                "2026-01-01",
                "--before",
                "2026-02-01",
            ],
        )
        assert result.exit_code == 0
        call_kwargs = mock_summarizer.summarize_pending_contents.call_args[1]
        q = call_kwargs["query"]
        assert q.start_date is not None
        assert q.end_date is not None

    @patch("src.processors.summarizer.ContentSummarizer")
    def test_queue_mode_with_filters(self, mock_cls):
        mock_summarizer = MagicMock()
        mock_summarizer.enqueue_pending_contents = AsyncMock(
            return_value={"enqueued_count": 2, "skipped_count": 0, "job_ids": [1, 2]}
        )
        mock_cls.return_value = mock_summarizer

        result = runner.invoke(app, ["summarize", "pending", "--source", "rss"])
        assert result.exit_code == 0
        call_kwargs = mock_summarizer.enqueue_pending_contents.call_args[1]
        assert call_kwargs["query"] is not None


class TestSummarizeById:
    @patch("src.processors.summarizer.ContentSummarizer")
    def test_by_id_sync_success(self, mock_cls):
        mock_summarizer = MagicMock()
        mock_summarizer.summarize_content.return_value = True
        mock_cls.return_value = mock_summarizer

        result = runner.invoke(app, ["summarize", "id", "42", "--sync"])
        assert result.exit_code == 0
        assert "42" in result.output

    @patch("src.processors.summarizer.ContentSummarizer")
    def test_by_id_sync_not_found(self, mock_cls):
        mock_summarizer = MagicMock()
        mock_summarizer.summarize_content.return_value = False
        mock_cls.return_value = mock_summarizer

        result = runner.invoke(app, ["summarize", "id", "999", "--sync"])
        assert result.exit_code == 1
        assert "Failed" in result.output or "Error" in result.output

    @patch("src.processors.summarizer.ContentSummarizer")
    def test_by_id_sync_exception(self, mock_cls):
        mock_cls.side_effect = RuntimeError("API error")

        result = runner.invoke(app, ["summarize", "id", "42", "--sync"])
        assert result.exit_code == 1

    @patch("src.queue.setup.enqueue_summarization_job", new_callable=AsyncMock)
    def test_by_id_queue_success(self, mock_enqueue):
        mock_enqueue.return_value = 101

        result = runner.invoke(app, ["summarize", "id", "42"])
        assert result.exit_code == 0
        assert "101" in result.output
        assert "42" in result.output
        mock_enqueue.assert_called_once_with(42)

    @patch("src.queue.setup.enqueue_summarization_job", new_callable=AsyncMock)
    def test_by_id_queue_already_queued(self, mock_enqueue):
        mock_enqueue.return_value = None

        result = runner.invoke(app, ["summarize", "id", "42"])
        assert result.exit_code == 0
        assert "already queued" in result.output


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
