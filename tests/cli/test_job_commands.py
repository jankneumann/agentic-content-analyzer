"""Tests for CLI job commands, specifically the `aca jobs history` command.

Tests cover:
- Default output (Rich table)
- JSON mode output
- Filter flags: --since, --type, --status, --last
- Type alias resolution
- Error handling for invalid inputs
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from src.cli.app import app
from src.models.jobs import JobHistoryItem, JobStatus

runner = CliRunner()


def _make_history_items(count: int = 3) -> list[JobHistoryItem]:
    """Create sample history items for testing."""
    items = []
    for i in range(count):
        items.append(
            JobHistoryItem(
                id=i + 1,
                entrypoint="summarize_content",
                task_label="Summarize",
                status=JobStatus.COMPLETED,
                content_id=100 + i,
                description=f"Newsletter #{i + 1}",
                error=None,
                created_at=datetime.now(UTC),
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
        )
    return items


class TestJobsHistoryCommand:
    """Tests for `aca jobs history`."""

    def test_history_default_output(self):
        """Test default Rich table output."""
        items = _make_history_items()
        with patch(
            "src.queue.setup.list_job_history",
            new_callable=AsyncMock,
            return_value=(items, 3),
        ):
            result = runner.invoke(app, ["jobs", "history"])

        assert result.exit_code == 0
        assert "Task History" in result.output
        assert "Summarize" in result.output
        # Rich table may wrap long descriptions across lines
        assert "Newsletter" in result.output

    def test_history_json_mode(self):
        """Test JSON output mode."""
        items = _make_history_items(2)
        with patch(
            "src.queue.setup.list_job_history",
            new_callable=AsyncMock,
            return_value=(items, 2),
        ):
            result = runner.invoke(app, ["--json", "jobs", "history"])

        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert "jobs" in data
        assert len(data["jobs"]) == 2
        assert data["total"] == 2
        assert data["jobs"][0]["task_label"] == "Summarize"

    def test_history_empty_results(self):
        """Test empty results display."""
        with patch(
            "src.queue.setup.list_job_history",
            new_callable=AsyncMock,
            return_value=([], 0),
        ):
            result = runner.invoke(app, ["jobs", "history"])

        assert result.exit_code == 0
        assert "No jobs found" in result.output

    def test_history_empty_results_json(self):
        """Test empty results in JSON mode."""
        with patch(
            "src.queue.setup.list_job_history",
            new_callable=AsyncMock,
            return_value=([], 0),
        ):
            result = runner.invoke(app, ["--json", "jobs", "history"])

        assert result.exit_code == 0
        import json

        data = json.loads(result.output)
        assert data["jobs"] == []
        assert data["total"] == 0

    def test_history_since_shorthand(self):
        """Test --since with day shorthand."""
        items = _make_history_items(1)
        with patch(
            "src.queue.setup.list_job_history",
            new_callable=AsyncMock,
            return_value=(items, 1),
        ) as mock_fn:
            result = runner.invoke(app, ["jobs", "history", "--since", "7d"])

        assert result.exit_code == 0
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["since"] is not None

    def test_history_since_invalid(self):
        """Test --since with invalid format."""
        result = runner.invoke(app, ["jobs", "history", "--since", "invalid"])

        assert result.exit_code == 1
        assert "Invalid --since format" in result.output

    def test_history_type_alias(self):
        """Test --type resolves aliases to entrypoints."""
        items = _make_history_items(1)
        with patch(
            "src.queue.setup.list_job_history",
            new_callable=AsyncMock,
            return_value=(items, 1),
        ) as mock_fn:
            result = runner.invoke(app, ["jobs", "history", "--type", "summarize"])

        assert result.exit_code == 0
        mock_fn.assert_called_once()
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["entrypoint"] == "summarize_content"

    def test_history_type_ingest(self):
        """Test --type ingest resolves correctly."""
        items = [
            JobHistoryItem(
                id=1,
                entrypoint="ingest_content",
                task_label="Ingest",
                status=JobStatus.COMPLETED,
                content_id=None,
                description="Gmail ingestion",
                error=None,
                created_at=datetime.now(UTC),
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
        ]
        with patch(
            "src.queue.setup.list_job_history",
            new_callable=AsyncMock,
            return_value=(items, 1),
        ) as mock_fn:
            result = runner.invoke(app, ["jobs", "history", "--type", "ingest"])

        assert result.exit_code == 0
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["entrypoint"] == "ingest_content"

    def test_history_type_invalid(self):
        """Test --type with unknown alias."""
        result = runner.invoke(app, ["jobs", "history", "--type", "nonexistent"])

        assert result.exit_code == 1
        assert "Unknown --type" in result.output

    def test_history_status_filter(self):
        """Test --status filter."""
        items = _make_history_items(1)
        with patch(
            "src.queue.setup.list_job_history",
            new_callable=AsyncMock,
            return_value=(items, 1),
        ) as mock_fn:
            result = runner.invoke(app, ["jobs", "history", "--status", "completed"])

        assert result.exit_code == 0
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["status"] == JobStatus.COMPLETED

    def test_history_status_invalid(self):
        """Test --status with invalid value."""
        result = runner.invoke(app, ["jobs", "history", "--status", "invalid"])

        assert result.exit_code == 1
        assert "Invalid status" in result.output

    def test_history_last_n(self):
        """Test --last N flag sets limit."""
        items = _make_history_items(2)
        with patch(
            "src.queue.setup.list_job_history",
            new_callable=AsyncMock,
            return_value=(items, 10),
        ) as mock_fn:
            result = runner.invoke(app, ["jobs", "history", "--last", "2"])

        assert result.exit_code == 0
        call_kwargs = mock_fn.call_args.kwargs
        assert call_kwargs["limit"] == 2

    def test_history_with_errors(self):
        """Test display of failed items with errors."""
        items = [
            JobHistoryItem(
                id=1,
                entrypoint="summarize_content",
                task_label="Summarize",
                status=JobStatus.FAILED,
                content_id=42,
                description="AI Weekly Newsletter",
                error="Connection timeout",
                created_at=datetime.now(UTC),
                started_at=datetime.now(UTC),
                completed_at=None,
            )
        ]
        with patch(
            "src.queue.setup.list_job_history",
            new_callable=AsyncMock,
            return_value=(items, 1),
        ):
            result = runner.invoke(app, ["jobs", "history"])

        assert result.exit_code == 0
        assert "failed" in result.output.lower()
