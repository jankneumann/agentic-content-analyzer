"""Unit tests for queue setup functions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.jobs import JobRecord, JobStatus
from src.queue.setup import (
    REQUIRED_QUEUE_COLUMNS,
    enqueue_queue_job,
    enqueue_summarization_job,
    get_job_status,
    init_queue_schema,
    update_job_progress,
)


@pytest.fixture
def mock_connection():
    class Transaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    conn = MagicMock()
    conn.fetchrow = AsyncMock()
    conn.fetchval = AsyncMock()
    conn.execute = AsyncMock()
    conn.close = AsyncMock()
    conn.transaction.return_value = Transaction()
    return conn


def _job_row(status: str = "queued") -> dict:
    return {
        "id": 42,
        "entrypoint": "summarize_content",
        "status": status,
        "payload": {"content_id": 123, "progress": 0, "message": "Queued"},
        "priority": 0,
        "error": None,
        "retry_count": 0,
        "claim_generation": 3,
        "claim_protocol_version": 2,
        "parent_job_id": None,
        "heartbeat_at": datetime(2025, 2, 5, 10, 0, 0, tzinfo=UTC),
        "created_at": datetime(2025, 2, 5, 10, 0, 0, tzinfo=UTC),
        "started_at": None,
        "completed_at": None,
    }


class TestGetJobStatus:
    @pytest.mark.asyncio
    async def test_get_job_status_returns_job_record(self, mock_connection):
        mock_connection.fetchrow.return_value = _job_row()
        with patch("src.queue.setup._connection", mock_connection):
            result = await get_job_status(42)

        assert isinstance(result, JobRecord)
        assert result.id == 42
        assert result.status == JobStatus.QUEUED
        assert result.parent_job_id is None
        assert result.claim_generation == 3
        assert result.claim_protocol_version == 2

    @pytest.mark.asyncio
    async def test_get_job_status_handles_missing_new_columns_for_backward_compat(
        self, mock_connection
    ):
        row = _job_row()
        row.pop("parent_job_id")
        row.pop("heartbeat_at")
        row.pop("claim_generation")
        row.pop("claim_protocol_version")
        mock_connection.fetchrow.return_value = row

        with patch("src.queue.setup._connection", mock_connection):
            result = await get_job_status(42)

        assert result is not None
        assert result.parent_job_id is None
        assert result.heartbeat_at is None
        assert result.claim_generation == 0
        assert result.claim_protocol_version == 1


class TestQueueOwnershipBootstrap:
    def test_required_queue_columns_include_claim_fence(self):
        assert {"claim_generation", "claim_protocol_version"} <= REQUIRED_QUEUE_COLUMNS

    @pytest.mark.asyncio
    async def test_bootstrap_installs_claim_defaults_and_triggers(self):
        connection = AsyncMock()
        connection.close = AsyncMock()
        with (
            patch("src.queue.setup.get_queue_connection_string", return_value="postgresql://db"),
            patch("src.queue.setup.asyncpg.connect", AsyncMock(return_value=connection)),
        ):
            await init_queue_schema()

        ddl = "\n".join(call.args[0] for call in connection.execute.await_args_list)
        assert "claim_generation BIGINT NOT NULL DEFAULT 0" in ddl
        assert "claim_protocol_version SMALLINT NOT NULL DEFAULT 1" in ddl
        assert "pgqueuer_jobs_advance_claim_generation" in ddl
        assert "pgqueuer_jobs_reset_claim_protocol" in ddl

    @pytest.mark.asyncio
    async def test_get_job_status_returns_none_when_missing(self, mock_connection):
        mock_connection.fetchrow.return_value = None
        with patch("src.queue.setup._connection", mock_connection):
            result = await get_job_status(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_job_status_parses_string_payload(self, mock_connection):
        row = _job_row()
        row["payload"] = '{"content_id": 123, "progress": 33}'
        mock_connection.fetchrow.return_value = row

        with patch("src.queue.setup._connection", mock_connection):
            result = await get_job_status(42)

        assert result is not None
        assert result.payload["progress"] == 33


class TestUpdateJobProgress:
    @pytest.mark.asyncio
    async def test_update_job_progress_requires_exact_claim_generation(self, mock_connection):
        mock_connection.fetchval.return_value = 42
        with patch("src.queue.setup._connection", mock_connection):
            updated = await update_job_progress(
                42,
                50,
                "Processing",
                claim_generation=3,
            )

        sql, progress_data, job_id, claim_generation = mock_connection.fetchval.call_args[0]
        assert "UPDATE pgqueuer_jobs" in sql
        assert "heartbeat_at = NOW()" in sql
        assert "status = 'in_progress'" in sql
        assert "claim_generation = $3" in sql
        assert job_id == 42
        assert claim_generation == 3
        assert json.loads(progress_data) == {"progress": 50, "message": "Processing"}
        assert updated is True


class TestEnqueueQueueJob:
    @pytest.mark.asyncio
    async def test_enqueue_queue_job_creates_job(self, mock_connection):
        mock_connection.fetchrow.return_value = {"id": 77}

        with patch("src.queue.setup._connection", mock_connection):
            job_id, created = await enqueue_queue_job("summarize_content", {"content_id": 123})

        assert (job_id, created) == (77, True)
        insert_call = mock_connection.fetchrow.call_args
        assert "ON CONFLICT (entrypoint, idempotency_key)" in insert_call[0][0]
        payload = json.loads(insert_call[0][2])
        assert payload["content_id"] == 123
        assert payload["schema_version"] == 1

    @pytest.mark.asyncio
    async def test_enqueue_queue_job_returns_existing_active_duplicate(self, mock_connection):
        mock_connection.fetchrow.return_value = None
        mock_connection.fetchval.return_value = 88

        with patch("src.queue.setup._connection", mock_connection):
            job_id, created = await enqueue_queue_job("summarize_content", {"content_id": 123})

        assert (job_id, created) == (88, False)

    @pytest.mark.asyncio
    async def test_enqueue_queue_job_rejects_invalid_payload(self, mock_connection):
        with patch("src.queue.setup._connection", mock_connection):
            with pytest.raises(ValueError):
                await enqueue_queue_job("summarize_content", {})

    @pytest.mark.asyncio
    async def test_child_enqueue_locks_and_revalidates_its_graph_root(self, mock_connection):
        mock_connection.fetchval.side_effect = [41, None, 41]
        mock_connection.fetchrow.return_value = {"id": 77}

        with patch("src.queue.setup._connection", mock_connection):
            result = await enqueue_queue_job(
                "summarize_content",
                {"content_id": 123},
                parent_job_id=43,
            )

        assert result == (77, True)
        assert mock_connection.fetchval.await_count == 3
        first_query = mock_connection.fetchval.await_args_list[0].args[0]
        lock_query = mock_connection.fetchval.await_args_list[1].args[0]
        recheck_query = mock_connection.fetchval.await_args_list[2].args[0]
        assert "WITH RECURSIVE lineage" in first_query
        assert "pg_advisory_xact_lock" in lock_query
        assert "WITH RECURSIVE lineage" in recheck_query
        assert mock_connection.fetchrow.await_args.args[4] == 43

    @pytest.mark.asyncio
    async def test_child_enqueue_rejects_lineage_removed_while_waiting(self, mock_connection):
        mock_connection.fetchval.side_effect = [41, None, None]

        with patch("src.queue.setup._connection", mock_connection):
            with pytest.raises(RuntimeError, match="live operation graph"):
                await enqueue_queue_job(
                    "summarize_content",
                    {"content_id": 123},
                    parent_job_id=43,
                )

        mock_connection.fetchrow.assert_not_awaited()


class TestEnqueueSummarizationJob:
    @pytest.mark.asyncio
    async def test_enqueue_summarization_job_returns_none_for_duplicate(self, mock_connection):
        mock_connection.fetchrow.return_value = None
        mock_connection.fetchval.return_value = 55

        with patch("src.queue.setup._connection", mock_connection):
            result = await enqueue_summarization_job(123)

        assert result is None

    @pytest.mark.asyncio
    async def test_enqueue_summarization_job_returns_job_id_for_new_job(self, mock_connection):
        mock_connection.fetchrow.return_value = {"id": 66}

        with patch("src.queue.setup._connection", mock_connection):
            result = await enqueue_summarization_job(123)

        assert result == 66


class TestQueueSetupEdgeCases:
    @pytest.mark.asyncio
    async def test_get_job_status_handles_all_statuses(self, mock_connection):
        for status in JobStatus:
            row = _job_row(status=status.value)
            mock_connection.fetchrow.return_value = row
            with patch("src.queue.setup._connection", mock_connection):
                result = await get_job_status(42)
            assert result is not None
            assert result.status == status

    @pytest.mark.asyncio
    async def test_job_record_terminal_state_detection(self, mock_connection):
        for status, expected in [
            ("queued", False),
            ("in_progress", False),
            ("completed", True),
            ("failed", True),
        ]:
            mock_connection.fetchrow.return_value = _job_row(status=status)
            with patch("src.queue.setup._connection", mock_connection):
                result = await get_job_status(42)
            assert result is not None
            assert result.is_terminal is expected
