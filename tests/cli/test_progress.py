"""Tests for src/cli/progress.py — SSE progress display."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.cli.api_client import SSEEvent
from src.cli.progress import _is_terminal, display_ingest_result, stream_job_progress


class TestIsTerminal:
    """Tests for _is_terminal helper."""

    @pytest.mark.parametrize(
        "status",
        ["completed", "complete", "error", "failed"],
    )
    def test_terminal_statuses(self, status: str) -> None:
        assert _is_terminal({"status": status}) is True

    @pytest.mark.parametrize(
        "status",
        ["queued", "processing", ""],
    )
    def test_non_terminal_statuses(self, status: str) -> None:
        assert _is_terminal({"status": status}) is False

    def test_missing_status_key(self) -> None:
        assert _is_terminal({}) is False


class TestStreamJobProgressJsonMode:
    """Tests for stream_job_progress with json_mode=True."""

    def test_returns_terminal_event_data(self) -> None:
        events = [
            SSEEvent(data='{"status": "processing", "progress": 50}'),
            SSEEvent(data='{"status": "completed", "progress": 100, "processed": 5}'),
        ]
        client = MagicMock()
        client.stream_ingest_status.return_value = iter(events)

        result = stream_job_progress(client, "task-1", "Gmail ingestion", json_mode=True)

        assert result == {"status": "completed", "progress": 100, "processed": 5}
        client.stream_ingest_status.assert_called_once_with("task-1")

    def test_skips_invalid_json_events(self) -> None:
        events = [
            SSEEvent(data="not valid json"),
            SSEEvent(data='{"status": "completed"}'),
        ]
        client = MagicMock()
        client.stream_ingest_status.return_value = iter(events)

        result = stream_job_progress(client, "task-2", "RSS ingestion", json_mode=True)

        assert result == {"status": "completed"}

    def test_returns_empty_dict_when_no_events(self) -> None:
        client = MagicMock()
        client.stream_ingest_status.return_value = iter([])

        result = stream_job_progress(client, "task-3", "RSS ingestion", json_mode=True)

        assert result == {}

    def test_stops_at_first_terminal_event(self) -> None:
        events = [
            SSEEvent(data='{"status": "processing"}'),
            SSEEvent(data='{"status": "error", "error": "timeout"}'),
            SSEEvent(data='{"status": "completed"}'),  # should not be reached
        ]
        client = MagicMock()
        client.stream_ingest_status.return_value = iter(events)

        result = stream_job_progress(client, "task-4", "Test", json_mode=True)

        assert result["status"] == "error"


class TestStreamJobProgressRichMode:
    """Tests for stream_job_progress with json_mode=False (Rich spinner)."""

    @patch("rich.console.Console")
    def test_returns_terminal_data(self, mock_console_cls: MagicMock) -> None:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        mock_status = MagicMock()
        mock_console.status.return_value.__enter__ = MagicMock(return_value=mock_status)
        mock_console.status.return_value.__exit__ = MagicMock(return_value=False)

        events = [
            SSEEvent(data='{"status": "processing", "progress": 50, "message": "Fetching"}'),
            SSEEvent(data='{"status": "completed", "progress": 100, "processed": 3}'),
        ]
        client = MagicMock()
        client.stream_ingest_status.return_value = iter(events)

        result = stream_job_progress(client, "task-1", "Gmail ingestion", json_mode=False)

        assert result == {"status": "completed", "progress": 100, "processed": 3}

    @patch("rich.console.Console")
    def test_updates_status_with_message(self, mock_console_cls: MagicMock) -> None:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        mock_status = MagicMock()
        mock_console.status.return_value.__enter__ = MagicMock(return_value=mock_status)
        mock_console.status.return_value.__exit__ = MagicMock(return_value=False)

        events = [
            SSEEvent(data='{"status": "processing", "progress": 50, "message": "Fetching emails"}'),
            SSEEvent(data='{"status": "completed", "progress": 100}'),
        ]
        client = MagicMock()
        client.stream_ingest_status.return_value = iter(events)

        stream_job_progress(client, "t1", "Gmail", json_mode=False)

        # Verify status.update was called with message content
        update_calls = mock_status.update.call_args_list
        assert any("Fetching emails" in str(call) for call in update_calls)

    @patch("rich.console.Console")
    def test_updates_status_with_status_str_fallback(self, mock_console_cls: MagicMock) -> None:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console
        mock_status = MagicMock()
        mock_console.status.return_value.__enter__ = MagicMock(return_value=mock_status)
        mock_console.status.return_value.__exit__ = MagicMock(return_value=False)

        events = [
            SSEEvent(data='{"status": "processing", "progress": 25}'),
            SSEEvent(data='{"status": "completed", "progress": 100}'),
        ]
        client = MagicMock()
        client.stream_ingest_status.return_value = iter(events)

        stream_job_progress(client, "t1", "Test", json_mode=False)

        update_calls = mock_status.update.call_args_list
        assert any("processing" in str(call) for call in update_calls)


class TestStreamJobProgressStreamTypeRouting:
    """Tests that stream_type selects the correct client method."""

    def test_ingest_stream_type(self) -> None:
        client = MagicMock()
        client.stream_ingest_status.return_value = iter([SSEEvent(data='{"status": "completed"}')])

        stream_job_progress(client, "t1", "Test", stream_type="ingest", json_mode=True)

        client.stream_ingest_status.assert_called_once_with("t1")
        client.stream_summarize_status.assert_not_called()
        client.stream_pipeline_status.assert_not_called()

    def test_summarize_stream_type(self) -> None:
        client = MagicMock()
        client.stream_summarize_status.return_value = iter(
            [SSEEvent(data='{"status": "completed"}')]
        )

        stream_job_progress(client, "t1", "Test", stream_type="summarize", json_mode=True)

        client.stream_summarize_status.assert_called_once_with("t1")
        client.stream_ingest_status.assert_not_called()

    def test_pipeline_stream_type_converts_to_int(self) -> None:
        client = MagicMock()
        client.stream_pipeline_status.return_value = iter(
            [SSEEvent(data='{"status": "completed"}')]
        )

        stream_job_progress(client, "42", "Test", stream_type="pipeline", json_mode=True)

        client.stream_pipeline_status.assert_called_once_with(42)

    def test_unknown_stream_type_falls_back_to_ingest(self) -> None:
        client = MagicMock()
        client.stream_ingest_status.return_value = iter([SSEEvent(data='{"status": "completed"}')])

        stream_job_progress(client, "t1", "Test", stream_type="unknown", json_mode=True)

        client.stream_ingest_status.assert_called_once_with("t1")


class TestDisplayIngestResultJsonMode:
    """Tests for display_ingest_result with json_mode=True."""

    @patch("src.cli.output.output_result")
    def test_outputs_structured_dict(self, mock_output: MagicMock) -> None:
        result = {"status": "completed", "processed": 5, "message": "Done"}

        display_ingest_result(result, "gmail", json_mode=True)

        mock_output.assert_called_once_with(
            {
                "source": "gmail",
                "status": "completed",
                "processed": 5,
                "message": "Done",
            }
        )

    @patch("src.cli.output.output_result")
    def test_defaults_for_missing_fields(self, mock_output: MagicMock) -> None:
        display_ingest_result({}, "rss", json_mode=True)

        mock_output.assert_called_once_with(
            {
                "source": "rss",
                "status": "unknown",
                "processed": 0,
                "message": "",
            }
        )


class TestDisplayIngestResultRichMode:
    """Tests for display_ingest_result with json_mode=False."""

    @patch("rich.console.Console")
    def test_completed_shows_green(self, mock_console_cls: MagicMock) -> None:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console

        result = {"status": "completed", "processed": 7, "message": "All good"}
        display_ingest_result(result, "gmail", json_mode=False)

        calls = mock_console.print.call_args_list
        assert any("[green]" in str(call) and "gmail" in str(call) for call in calls)
        assert any("7" in str(call) for call in calls)

    @patch("rich.console.Console")
    def test_complete_status_also_shows_green(self, mock_console_cls: MagicMock) -> None:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console

        result = {"status": "complete", "processed": 3}
        display_ingest_result(result, "rss", json_mode=False)

        calls = mock_console.print.call_args_list
        assert any("[green]" in str(call) for call in calls)

    @patch("rich.console.Console")
    def test_error_shows_red(self, mock_console_cls: MagicMock) -> None:
        # Console is called twice in error path: once for main, once for stderr
        mock_stdout_console = MagicMock()
        mock_stderr_console = MagicMock()
        mock_console_cls.side_effect = [mock_stdout_console, mock_stderr_console]

        result = {"status": "error", "error": "Connection timeout"}
        display_ingest_result(result, "youtube", json_mode=False)

        calls = mock_stderr_console.print.call_args_list
        assert any("[red]" in str(call) and "Connection timeout" in str(call) for call in calls)

    @patch("rich.console.Console")
    def test_other_status_shows_yellow(self, mock_console_cls: MagicMock) -> None:
        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console

        result = {"status": "cancelled", "message": "User cancelled"}
        display_ingest_result(result, "podcast", json_mode=False)

        calls = mock_console.print.call_args_list
        assert any("[yellow]" in str(call) for call in calls)
