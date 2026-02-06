"""Unit tests for queue setup functions.

Tests cover:
- get_job_status() - Fetch job status by ID
- update_job_progress() - Update job progress in payload
- enqueue_summarization_job() - Enqueue with deduplication

These tests mock the database connection to avoid requiring
a running PostgreSQL instance.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.models.jobs import JobRecord, JobStatus
from src.queue.setup import (
    enqueue_summarization_job,
    get_job_status,
    update_job_progress,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_connection():
    """Create a mock asyncpg connection."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock()
    conn.fetchval = AsyncMock()
    conn.execute = AsyncMock()
    conn.close = AsyncMock()
    return conn


@pytest.fixture
def sample_job_row():
    """Create sample job row data as returned by asyncpg."""
    return {
        "id": 42,
        "entrypoint": "summarize_content",
        "status": "queued",
        "payload": {"content_id": 123, "progress": 0, "message": "Queued"},
        "priority": 0,
        "error": None,
        "retry_count": 0,
        "created_at": datetime(2025, 2, 5, 10, 0, 0, tzinfo=UTC),
        "started_at": None,
        "completed_at": None,
    }


@pytest.fixture
def in_progress_job_row():
    """Create sample in-progress job row data."""
    return {
        "id": 43,
        "entrypoint": "summarize_content",
        "status": "in_progress",
        "payload": {"content_id": 456, "progress": 50, "message": "Processing..."},
        "priority": 0,
        "error": None,
        "retry_count": 0,
        "created_at": datetime(2025, 2, 5, 10, 0, 0, tzinfo=UTC),
        "started_at": datetime(2025, 2, 5, 10, 5, 0, tzinfo=UTC),
        "completed_at": None,
    }


@pytest.fixture
def completed_job_row():
    """Create sample completed job row data."""
    return {
        "id": 44,
        "entrypoint": "summarize_content",
        "status": "completed",
        "payload": {"content_id": 789, "progress": 100, "message": "Done"},
        "priority": 0,
        "error": None,
        "retry_count": 0,
        "created_at": datetime(2025, 2, 5, 10, 0, 0, tzinfo=UTC),
        "started_at": datetime(2025, 2, 5, 10, 5, 0, tzinfo=UTC),
        "completed_at": datetime(2025, 2, 5, 10, 10, 0, tzinfo=UTC),
    }


@pytest.fixture
def failed_job_row():
    """Create sample failed job row data."""
    return {
        "id": 45,
        "entrypoint": "summarize_content",
        "status": "failed",
        "payload": {"content_id": 999, "progress": 25, "message": "Processing..."},
        "priority": 0,
        "error": "Connection timeout",
        "retry_count": 2,
        "created_at": datetime(2025, 2, 5, 10, 0, 0, tzinfo=UTC),
        "started_at": datetime(2025, 2, 5, 10, 5, 0, tzinfo=UTC),
        "completed_at": datetime(2025, 2, 5, 10, 6, 0, tzinfo=UTC),
    }


# =============================================================================
# Tests for get_job_status() - Task 7.1
# =============================================================================


class TestGetJobStatus:
    """Tests for get_job_status() function."""

    @pytest.mark.asyncio
    async def test_get_job_status_returns_job_record(self, mock_connection, sample_job_row):
        """Test that get_job_status returns a JobRecord when job exists."""
        mock_connection.fetchrow.return_value = sample_job_row

        with patch("src.queue.setup._connection", mock_connection):
            result = await get_job_status(42)

        assert result is not None
        assert isinstance(result, JobRecord)
        assert result.id == 42
        assert result.entrypoint == "summarize_content"
        assert result.status == JobStatus.QUEUED
        assert result.payload == {"content_id": 123, "progress": 0, "message": "Queued"}
        assert result.priority == 0
        assert result.error is None
        assert result.retry_count == 0

    @pytest.mark.asyncio
    async def test_get_job_status_returns_none_when_not_found(self, mock_connection):
        """Test that get_job_status returns None when job doesn't exist."""
        mock_connection.fetchrow.return_value = None

        with patch("src.queue.setup._connection", mock_connection):
            result = await get_job_status(999)

        assert result is None
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_job_status_handles_in_progress_job(
        self, mock_connection, in_progress_job_row
    ):
        """Test that get_job_status correctly handles in_progress status."""
        mock_connection.fetchrow.return_value = in_progress_job_row

        with patch("src.queue.setup._connection", mock_connection):
            result = await get_job_status(43)

        assert result is not None
        assert result.status == JobStatus.IN_PROGRESS
        assert result.started_at is not None
        assert result.progress == 50
        assert result.progress_message == "Processing..."

    @pytest.mark.asyncio
    async def test_get_job_status_handles_completed_job(self, mock_connection, completed_job_row):
        """Test that get_job_status correctly handles completed status."""
        mock_connection.fetchrow.return_value = completed_job_row

        with patch("src.queue.setup._connection", mock_connection):
            result = await get_job_status(44)

        assert result is not None
        assert result.status == JobStatus.COMPLETED
        assert result.completed_at is not None
        assert result.progress == 100
        assert result.is_terminal is True

    @pytest.mark.asyncio
    async def test_get_job_status_handles_failed_job(self, mock_connection, failed_job_row):
        """Test that get_job_status correctly handles failed status."""
        mock_connection.fetchrow.return_value = failed_job_row

        with patch("src.queue.setup._connection", mock_connection):
            result = await get_job_status(45)

        assert result is not None
        assert result.status == JobStatus.FAILED
        assert result.error == "Connection timeout"
        assert result.retry_count == 2
        assert result.is_terminal is True

    @pytest.mark.asyncio
    async def test_get_job_status_handles_string_payload(self, mock_connection):
        """Test that get_job_status handles payload as JSON string."""
        row = {
            "id": 46,
            "entrypoint": "summarize_content",
            "status": "queued",
            "payload": '{"content_id": 100, "progress": 0}',  # String, not dict
            "priority": 0,
            "error": None,
            "retry_count": 0,
            "created_at": datetime.now(UTC),
            "started_at": None,
            "completed_at": None,
        }
        mock_connection.fetchrow.return_value = row

        with patch("src.queue.setup._connection", mock_connection):
            result = await get_job_status(46)

        assert result is not None
        assert result.payload == {"content_id": 100, "progress": 0}

    @pytest.mark.asyncio
    async def test_get_job_status_handles_empty_payload(self, mock_connection):
        """Test that get_job_status handles empty/None payload."""
        row = {
            "id": 47,
            "entrypoint": "summarize_content",
            "status": "queued",
            "payload": None,
            "priority": 0,
            "error": None,
            "retry_count": 0,
            "created_at": datetime.now(UTC),
            "started_at": None,
            "completed_at": None,
        }
        mock_connection.fetchrow.return_value = row

        with patch("src.queue.setup._connection", mock_connection):
            result = await get_job_status(47)

        assert result is not None
        assert result.payload == {}

    @pytest.mark.asyncio
    async def test_get_job_status_creates_temp_connection_when_no_global(self):
        """Test that get_job_status creates temporary connection when _connection is None."""
        mock_temp_conn = AsyncMock()
        mock_temp_conn.fetchrow.return_value = None
        mock_temp_conn.close = AsyncMock()

        with (
            patch("src.queue.setup._connection", None),
            patch(
                "src.queue.setup.get_queue_connection_string",
                return_value="postgres://localhost/test",
            ),
            patch("src.queue.setup.asyncpg.connect", AsyncMock(return_value=mock_temp_conn)),
        ):
            result = await get_job_status(999)

        assert result is None
        mock_temp_conn.close.assert_called_once()


# =============================================================================
# Tests for update_job_progress() - Task 7.1
# =============================================================================


class TestUpdateJobProgress:
    """Tests for update_job_progress() function."""

    @pytest.mark.asyncio
    async def test_update_job_progress_executes_update(self, mock_connection):
        """Test that update_job_progress executes the UPDATE query."""
        with patch("src.queue.setup._connection", mock_connection):
            await update_job_progress(42, 50, "Processing content...")

        mock_connection.execute.assert_called_once()
        call_args = mock_connection.execute.call_args
        sql = call_args[0][0]
        progress_data = call_args[0][1]
        job_id = call_args[0][2]

        assert "UPDATE pgqueuer_jobs" in sql
        assert job_id == 42
        # Progress data should be JSON with progress and message
        parsed = json.loads(progress_data)
        assert parsed["progress"] == 50
        assert parsed["message"] == "Processing content..."

    @pytest.mark.asyncio
    async def test_update_job_progress_with_zero_progress(self, mock_connection):
        """Test that update_job_progress works with 0% progress."""
        with patch("src.queue.setup._connection", mock_connection):
            await update_job_progress(42, 0, "Starting...")

        call_args = mock_connection.execute.call_args
        progress_data = json.loads(call_args[0][1])
        assert progress_data["progress"] == 0
        assert progress_data["message"] == "Starting..."

    @pytest.mark.asyncio
    async def test_update_job_progress_with_full_progress(self, mock_connection):
        """Test that update_job_progress works with 100% progress."""
        with patch("src.queue.setup._connection", mock_connection):
            await update_job_progress(42, 100, "Completed successfully")

        call_args = mock_connection.execute.call_args
        progress_data = json.loads(call_args[0][1])
        assert progress_data["progress"] == 100
        assert progress_data["message"] == "Completed successfully"

    @pytest.mark.asyncio
    async def test_update_job_progress_creates_temp_connection_when_no_global(self):
        """Test that update_job_progress creates temporary connection when needed."""
        mock_temp_conn = AsyncMock()
        mock_temp_conn.execute = AsyncMock()
        mock_temp_conn.close = AsyncMock()

        with (
            patch("src.queue.setup._connection", None),
            patch(
                "src.queue.setup.get_queue_connection_string",
                return_value="postgres://localhost/test",
            ),
            patch("src.queue.setup.asyncpg.connect", AsyncMock(return_value=mock_temp_conn)),
        ):
            await update_job_progress(42, 75, "Almost done")

        mock_temp_conn.execute.assert_called_once()
        mock_temp_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_job_progress_handles_special_characters_in_message(self, mock_connection):
        """Test that update_job_progress handles special characters in message."""
        with patch("src.queue.setup._connection", mock_connection):
            await update_job_progress(42, 50, 'Processing "quoted" & special <chars>')

        call_args = mock_connection.execute.call_args
        progress_data = json.loads(call_args[0][1])
        assert progress_data["message"] == 'Processing "quoted" & special <chars>'


# =============================================================================
# Tests for enqueue_summarization_job() - Task 7.6
# =============================================================================


class TestEnqueueSummarizationJob:
    """Tests for enqueue_summarization_job() function - deduplication logic."""

    @pytest.mark.asyncio
    async def test_enqueue_new_job_returns_job_id(self, mock_connection):
        """Test that enqueue returns job_id for new content."""
        # No existing job
        mock_connection.fetchval.side_effect = [None, 100]  # First: check existing, Second: INSERT
        mock_connection.execute = AsyncMock()

        with patch("src.queue.setup._connection", mock_connection):
            result = await enqueue_summarization_job(123)

        assert result == 100
        # Should have called fetchval twice: once for checking existing, once for INSERT
        assert mock_connection.fetchval.call_count == 2

    @pytest.mark.asyncio
    async def test_enqueue_skips_duplicate_queued_job(self, mock_connection):
        """Test that enqueue returns None when content_id already has queued job."""
        # Existing queued job found
        mock_connection.fetchval.return_value = 50  # Existing job ID

        with patch("src.queue.setup._connection", mock_connection):
            result = await enqueue_summarization_job(123)

        assert result is None
        # Should have only checked for existing job, no INSERT
        mock_connection.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_skips_duplicate_in_progress_job(self, mock_connection):
        """Test that enqueue returns None when content_id has in_progress job."""
        # The query checks for both 'queued' and 'in_progress' statuses
        mock_connection.fetchval.return_value = 51  # Existing in_progress job ID

        with patch("src.queue.setup._connection", mock_connection):
            result = await enqueue_summarization_job(456)

        assert result is None

    @pytest.mark.asyncio
    async def test_enqueue_allows_after_completed_job(self, mock_connection):
        """Test that enqueue allows re-enqueueing after job completed."""
        # No active job (completed jobs are not in 'queued' or 'in_progress' status)
        mock_connection.fetchval.side_effect = [None, 101]
        mock_connection.execute = AsyncMock()

        with patch("src.queue.setup._connection", mock_connection):
            result = await enqueue_summarization_job(789)

        assert result == 101

    @pytest.mark.asyncio
    async def test_enqueue_allows_after_failed_job(self, mock_connection):
        """Test that enqueue allows re-enqueueing after job failed."""
        # No active job (failed jobs are not in 'queued' or 'in_progress' status)
        mock_connection.fetchval.side_effect = [None, 102]
        mock_connection.execute = AsyncMock()

        with patch("src.queue.setup._connection", mock_connection):
            result = await enqueue_summarization_job(999)

        assert result == 102

    @pytest.mark.asyncio
    async def test_enqueue_inserts_correct_payload(self, mock_connection):
        """Test that enqueue inserts job with correct payload."""
        mock_connection.fetchval.side_effect = [None, 103]
        mock_connection.execute = AsyncMock()

        with patch("src.queue.setup._connection", mock_connection):
            await enqueue_summarization_job(555)

        # Get the INSERT call
        insert_call = mock_connection.fetchval.call_args_list[1]
        sql = insert_call[0][0]
        payload = insert_call[0][1]

        assert "INSERT INTO pgqueuer_jobs" in sql
        assert "summarize_content" in sql

        parsed = json.loads(payload)
        assert parsed["content_id"] == 555
        assert parsed["progress"] == 0
        assert parsed["message"] == "Queued"

    @pytest.mark.asyncio
    async def test_enqueue_sends_notification(self, mock_connection):
        """Test that enqueue sends pg_notify to wake workers."""
        mock_connection.fetchval.side_effect = [None, 104]
        mock_connection.execute = AsyncMock()

        with patch("src.queue.setup._connection", mock_connection):
            await enqueue_summarization_job(666)

        # Verify pg_notify was called
        mock_connection.execute.assert_called_once()
        call_args = mock_connection.execute.call_args
        assert "pg_notify" in call_args[0][0]
        assert "summarize_content" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_enqueue_creates_temp_connection_when_no_global(self):
        """Test that enqueue creates temporary connection when _connection is None."""
        mock_temp_conn = AsyncMock()
        mock_temp_conn.fetchval.side_effect = [None, 105]
        mock_temp_conn.execute = AsyncMock()
        mock_temp_conn.close = AsyncMock()

        with (
            patch("src.queue.setup._connection", None),
            patch(
                "src.queue.setup.get_queue_connection_string",
                return_value="postgres://localhost/test",
            ),
            patch("src.queue.setup.asyncpg.connect", AsyncMock(return_value=mock_temp_conn)),
        ):
            result = await enqueue_summarization_job(777)

        assert result == 105
        mock_temp_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_idempotency_multiple_calls(self, mock_connection):
        """Test that multiple enqueue calls for same content_id are idempotent."""
        # First call: no existing job, creates new
        # Second call: existing job found, returns None
        mock_connection.fetchval.side_effect = [
            None,
            106,
            106,
        ]  # None for first check, 106 for INSERT, 106 for second check
        mock_connection.execute = AsyncMock()

        with patch("src.queue.setup._connection", mock_connection):
            result1 = await enqueue_summarization_job(888)

        assert result1 == 106

        # Reset for second call - now the job exists
        mock_connection.fetchval.reset_mock()
        mock_connection.fetchval.return_value = 106

        with patch("src.queue.setup._connection", mock_connection):
            result2 = await enqueue_summarization_job(888)

        assert result2 is None

    @pytest.mark.asyncio
    async def test_enqueue_different_content_ids_allowed(self, mock_connection):
        """Test that different content_ids can be enqueued simultaneously."""
        # First content
        mock_connection.fetchval.side_effect = [None, 107]
        mock_connection.execute = AsyncMock()

        with patch("src.queue.setup._connection", mock_connection):
            result1 = await enqueue_summarization_job(1001)

        assert result1 == 107

        # Second content - different content_id
        mock_connection.fetchval.reset_mock()
        mock_connection.execute.reset_mock()
        mock_connection.fetchval.side_effect = [None, 108]

        with patch("src.queue.setup._connection", mock_connection):
            result2 = await enqueue_summarization_job(1002)

        assert result2 == 108


# =============================================================================
# Integration-style tests for edge cases
# =============================================================================


class TestQueueSetupEdgeCases:
    """Edge case tests for queue setup functions."""

    @pytest.mark.asyncio
    async def test_get_job_status_handles_all_job_statuses(self, mock_connection):
        """Test that all JobStatus values are properly handled."""
        for status in JobStatus:
            row = {
                "id": 100,
                "entrypoint": "summarize_content",
                "status": status.value,
                "payload": {},
                "priority": 0,
                "error": None if status != JobStatus.FAILED else "Error",
                "retry_count": 0,
                "created_at": datetime.now(UTC),
                "started_at": None,
                "completed_at": None,
            }
            mock_connection.fetchrow.return_value = row

            with patch("src.queue.setup._connection", mock_connection):
                result = await get_job_status(100)

            assert result is not None
            assert result.status == status

    @pytest.mark.asyncio
    async def test_job_record_terminal_state_detection(self, mock_connection):
        """Test that JobRecord.is_terminal correctly identifies terminal states."""
        # Queued - not terminal
        queued_row = {
            "id": 200,
            "entrypoint": "summarize_content",
            "status": "queued",
            "payload": {},
            "priority": 0,
            "error": None,
            "retry_count": 0,
            "created_at": datetime.now(UTC),
            "started_at": None,
            "completed_at": None,
        }
        mock_connection.fetchrow.return_value = queued_row

        with patch("src.queue.setup._connection", mock_connection):
            result = await get_job_status(200)
            assert not result.is_terminal

        # In progress - not terminal
        in_progress_row = {**queued_row, "status": "in_progress"}
        mock_connection.fetchrow.return_value = in_progress_row

        with patch("src.queue.setup._connection", mock_connection):
            result = await get_job_status(200)
            assert not result.is_terminal

        # Completed - terminal
        completed_row = {**queued_row, "status": "completed"}
        mock_connection.fetchrow.return_value = completed_row

        with patch("src.queue.setup._connection", mock_connection):
            result = await get_job_status(200)
            assert result.is_terminal

        # Failed - terminal
        failed_row = {**queued_row, "status": "failed"}
        mock_connection.fetchrow.return_value = failed_row

        with patch("src.queue.setup._connection", mock_connection):
            result = await get_job_status(200)
            assert result.is_terminal
