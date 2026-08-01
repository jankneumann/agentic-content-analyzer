"""Tests for extended source types in the ingest_content worker handler.

Verifies that each source type in the handler's source_map correctly dispatches
to the corresponding orchestrator function with the right keyword arguments.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from src.queue.worker import (
    _checkpoint_job_cancellation,
    _claim_jobs,
    _complete_job,
    _fail_job,
    _handlers,
    register_all_handlers,
)


@pytest.fixture(autouse=True)
def _register():
    """Ensure all handlers are registered before each test."""
    register_all_handlers()


@pytest.fixture(autouse=True)
def _mock_progress():
    """Mock update_job_progress to avoid DB connections."""
    with patch("src.queue.setup.update_job_progress", new_callable=AsyncMock):
        yield


# ---------------------------------------------------------------------------
# ingest_content handler — source dispatch tests
# ---------------------------------------------------------------------------


@patch("src.ingestion.orchestrator.ingest_xsearch")
@pytest.mark.asyncio
async def test_ingest_xsearch(mock_xsearch):
    mock_xsearch.return_value = 3
    handler = _handlers["ingest_content"]
    await handler(1, {"source": "xsearch", "prompt": "AI news", "max_threads": 5})
    mock_xsearch.assert_called_once()
    assert mock_xsearch.call_args[1].get("prompt") == "AI news"
    assert mock_xsearch.call_args[1].get("max_threads") == 5


@patch("src.ingestion.orchestrator.ingest_perplexity_search")
@pytest.mark.asyncio
async def test_ingest_perplexity(mock_perplexity):
    mock_perplexity.return_value = 5
    handler = _handlers["ingest_content"]
    await handler(
        1,
        {
            "source": "perplexity",
            "prompt": "latest AI",
            "recency_filter": "week",
            "context_size": "high",
        },
    )
    mock_perplexity.assert_called_once()
    kwargs = mock_perplexity.call_args[1]
    assert kwargs.get("prompt") == "latest AI"
    assert kwargs.get("recency_filter") == "week"
    assert kwargs.get("context_size") == "high"


@patch("src.ingestion.orchestrator.ingest_url")
@pytest.mark.asyncio
async def test_ingest_url(mock_url):
    mock_url.return_value = True
    handler = _handlers["ingest_content"]
    await handler(
        1,
        {
            "source": "url",
            "url": "https://example.com/article",
            "title": "Test Article",
            "tags": ["ai", "ml"],
            "notes": "Interesting read",
        },
    )
    mock_url.assert_called_once()
    kwargs = mock_url.call_args[1]
    assert kwargs["url"] == "https://example.com/article"
    assert kwargs["title"] == "Test Article"
    assert kwargs["tags"] == ["ai", "ml"]
    assert kwargs["notes"] == "Interesting read"


@patch("src.ingestion.orchestrator.ingest_gmail")
@pytest.mark.asyncio
async def test_ingest_gmail(mock_gmail):
    mock_gmail.return_value = 10
    handler = _handlers["ingest_content"]
    await handler(1, {"source": "gmail", "days_back": 3})
    mock_gmail.assert_called_once()


@patch("src.ingestion.orchestrator.ingest_rss")
@pytest.mark.asyncio
async def test_ingest_rss(mock_rss):
    mock_rss.return_value = 7
    handler = _handlers["ingest_content"]
    await handler(1, {"source": "rss", "max_results": 20})
    mock_rss.assert_called_once()
    assert mock_rss.call_args[1].get("max_entries_per_feed") == 20


@patch("src.ingestion.orchestrator.ingest_youtube")
@pytest.mark.asyncio
async def test_ingest_youtube(mock_yt):
    mock_yt.return_value = 4
    handler = _handlers["ingest_content"]
    await handler(1, {"source": "youtube", "public_only": True})
    mock_yt.assert_called_once()
    # public_only=True → use_oauth=False
    assert mock_yt.call_args[1].get("use_oauth") is False


@patch("src.ingestion.orchestrator.ingest_youtube_playlist")
@pytest.mark.asyncio
async def test_ingest_youtube_playlist(mock_ytp):
    mock_ytp.return_value = 2
    handler = _handlers["ingest_content"]
    await handler(1, {"source": "youtube-playlist", "max_results": 10})
    mock_ytp.assert_called_once()
    assert mock_ytp.call_args[1].get("max_videos") == 10


@patch("src.ingestion.orchestrator.ingest_youtube_rss")
@pytest.mark.asyncio
async def test_ingest_youtube_rss(mock_ytr):
    mock_ytr.return_value = 6
    handler = _handlers["ingest_content"]
    await handler(1, {"source": "youtube-rss"})
    mock_ytr.assert_called_once()


@patch("src.ingestion.orchestrator.ingest_podcast")
@pytest.mark.asyncio
async def test_ingest_podcast(mock_podcast):
    mock_podcast.return_value = 3
    handler = _handlers["ingest_content"]
    await handler(1, {"source": "podcast", "max_results": 5})
    mock_podcast.assert_called_once()
    assert mock_podcast.call_args[1].get("max_entries_per_feed") == 5


@patch("src.ingestion.orchestrator.ingest_substack")
@pytest.mark.asyncio
async def test_ingest_substack(mock_sub):
    mock_sub.return_value = 8
    handler = _handlers["ingest_content"]
    await handler(
        1,
        {"source": "substack", "session_cookie": "abc123", "max_results": 15},
    )
    mock_sub.assert_called_once()
    kwargs = mock_sub.call_args[1]
    assert kwargs.get("session_cookie") == "abc123"
    assert kwargs.get("max_entries_per_source") == 15


@patch("src.ingestion.orchestrator.ingest_readwise")
@pytest.mark.asyncio
async def test_ingest_readwise(mock_readwise):
    mock_readwise.return_value = 4
    handler = _handlers["ingest_content"]
    await handler(
        1,
        {
            "source": "readwise",
            "days_back": 14,
            "source_types": ["kindle", "pocket"],
            "include_deleted": True,
            "max_books": 25,
            "force_reprocess": True,
        },
    )
    mock_readwise.assert_called_once()
    kwargs = mock_readwise.call_args[1]
    assert kwargs.get("source_types") == ["kindle", "pocket"]
    assert kwargs.get("include_deleted") is True
    assert kwargs.get("max_books") == 25
    assert kwargs.get("force_reprocess") is True
    # days_back present → window applied via updated_after
    assert kwargs.get("updated_after") is not None
    # readwise uses updated_after, never the generic after_date kwarg
    assert "after_date" not in kwargs


@patch("src.ingestion.orchestrator.ingest_readwise")
@pytest.mark.asyncio
async def test_ingest_readwise_full_sync_without_days_back(mock_readwise):
    mock_readwise.return_value = 0
    handler = _handlers["ingest_content"]
    await handler(1, {"source": "readwise"})
    mock_readwise.assert_called_once()
    kwargs = mock_readwise.call_args[1]
    # No days_back → no window narrowing (parity with direct mode full sync)
    assert "updated_after" not in kwargs


@pytest.mark.asyncio
async def test_ingest_unknown_source_raises():
    handler = _handlers["ingest_content"]
    with pytest.raises(ValueError, match="Unsupported source"):
        await handler(1, {"source": "nonexistent"})


class _RetentionConnection:
    def __init__(self, *, acquired: bool) -> None:
        self.fetchval = AsyncMock(return_value=acquired)
        self.execute = AsyncMock()


def _retention_settings() -> SimpleNamespace:
    return SimpleNamespace(
        job_retention_days=30,
        failed_job_retention_days=90,
        job_retention_batch_size=25,
    )


@pytest.mark.asyncio
async def test_retention_tick_lock_loser_skips_cleanup(monkeypatch) -> None:
    from src.queue import worker

    connection = _RetentionConnection(acquired=False)
    cleanup = AsyncMock()
    monkeypatch.setattr("src.queue.setup.cleanup_old_jobs", cleanup)

    ran = await worker._run_retention_maintenance_tick(
        connection,
        retention_settings=_retention_settings(),
    )

    assert ran is False
    cleanup.assert_not_awaited()
    connection.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_retention_tick_runs_without_gemini_and_emits_metrics(monkeypatch) -> None:
    from src.queue import worker

    connection = _RetentionConnection(acquired=True)
    cleanup = AsyncMock(return_value=7)
    metrics = MagicMock()
    monkeypatch.setattr("src.queue.setup.cleanup_old_jobs", cleanup)
    monkeypatch.setattr(worker, "_record_retention_metrics", metrics)

    ran = await worker._run_retention_maintenance_tick(
        connection,
        retention_settings=_retention_settings(),
    )

    assert ran is True
    cleanup.assert_awaited_once_with(
        older_than_days=30,
        failed_older_than_days=90,
        batch_size=25,
        conn=connection,
    )
    metrics.assert_called_once()
    assert metrics.call_args.kwargs["deleted_count"] == 7
    assert metrics.call_args.kwargs["duration_seconds"] >= 0
    connection.execute.assert_awaited_once_with(
        "SELECT pg_advisory_unlock($1::bigint)",
        worker._RETENTION_MAINTENANCE_ADVISORY_LOCK,
    )


def test_retention_schedule_runs_at_startup_and_only_after_interval() -> None:
    from src.queue.worker import _retention_tick_due

    assert _retention_tick_due(now=100.0, last_run_at=None, interval_seconds=3600)
    assert not _retention_tick_due(now=3699.0, last_run_at=100.0, interval_seconds=3600)
    assert _retention_tick_due(now=3700.0, last_run_at=100.0, interval_seconds=3600)


@pytest.mark.asyncio
async def test_claim_jobs_activates_current_claim_protocol_and_returns_fence() -> None:
    connection = MagicMock()
    connection.fetch = AsyncMock(
        return_value=[
            {
                "id": 42,
                "entrypoint": "digest.create",
                "payload": {},
                "claim_generation": 7,
                "claim_protocol_version": 2,
            }
        ]
    )

    jobs = await _claim_jobs(connection, batch_size=1)

    query = connection.fetch.await_args.args[0]
    assert "claim_protocol_version = 2" in query
    assert "claim_generation" in query
    assert "claim_protocol_version" in query
    assert jobs[0]["claim_generation"] == 7
    assert jobs[0]["claim_protocol_version"] == 2


@pytest.mark.asyncio
async def test_worker_lifecycle_writes_require_exact_claim_generation() -> None:
    connection = MagicMock()
    connection.fetchval = AsyncMock(return_value=42)
    connection.fetchrow = AsyncMock(return_value={"id": 42})

    assert await _complete_job(connection, 42, 7) is True
    assert await _checkpoint_job_cancellation(connection, 42, 7) is True
    assert await _fail_job(connection, 42, 7, "boom") is True

    complete_query = connection.fetchval.await_args.args[0]
    cancel_query = connection.fetchrow.await_args.args[0]
    fail_query = connection.fetchval.await_args_list[-1].args[0]
    for query in (complete_query, cancel_query, fail_query):
        assert "status = 'in_progress'" in query
        assert "claim_generation = $2" in query
    assert connection.fetchval.await_args_list[-1].args[1:] == (42, 7, "boom")


@pytest.mark.asyncio
async def test_process_job_checkpoints_cancellation_before_handler(monkeypatch) -> None:
    from src.queue import worker

    handler = AsyncMock()
    checkpoint = AsyncMock(return_value=True)
    heartbeat = AsyncMock()
    monkeypatch.setitem(worker._handlers, "test.preflight", handler)
    monkeypatch.setattr(worker, "_checkpoint_job_cancellation", checkpoint)
    monkeypatch.setattr("src.queue.setup.touch_job_heartbeat", heartbeat)

    await worker._process_job(
        AsyncMock(),
        {
            "id": 42,
            "entrypoint": "test.preflight",
            "payload": {"cancel_requested": True},
            "claim_generation": 7,
            "claim_protocol_version": 2,
        },
    )

    checkpoint.assert_awaited_once_with(ANY, 42, 7)
    heartbeat.assert_not_awaited()
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_job_generation_loss_prevents_handler(monkeypatch) -> None:
    from src.queue import worker

    handler = AsyncMock()
    monkeypatch.setitem(worker._handlers, "test.preflight", handler)
    monkeypatch.setattr(worker, "_checkpoint_job_cancellation", AsyncMock(return_value=False))
    monkeypatch.setattr(
        "src.queue.setup.touch_job_heartbeat",
        AsyncMock(return_value=False),
    )

    await worker._process_job(
        AsyncMock(),
        {
            "id": 42,
            "entrypoint": "test.preflight",
            "payload": {},
            "claim_generation": 7,
            "claim_protocol_version": 2,
        },
    )

    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_stale_handler_exception_emits_no_failure_notification(monkeypatch) -> None:
    from src.queue import worker

    handler = AsyncMock(side_effect=RuntimeError("late worker"))
    checkpoint = AsyncMock(side_effect=[False, False])
    fail = AsyncMock(return_value=False)
    notification = AsyncMock()
    monkeypatch.setitem(worker._handlers, "test.stale", handler)
    monkeypatch.setattr(worker, "_checkpoint_job_cancellation", checkpoint)
    monkeypatch.setattr(worker, "_fail_job", fail)
    monkeypatch.setattr(worker, "_emit_job_notification", notification)
    monkeypatch.setattr(
        "src.queue.setup.touch_job_heartbeat",
        AsyncMock(return_value=True),
    )

    await worker._process_job(
        AsyncMock(),
        {
            "id": 42,
            "entrypoint": "test.stale",
            "payload": {},
            "claim_generation": 7,
            "claim_protocol_version": 2,
        },
    )

    fail.assert_awaited_once_with(ANY, 42, 7, "Job failed due to an internal error")
    notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_claimed_job_uses_a_dedicated_lifecycle_connection(monkeypatch) -> None:
    from src.queue import worker

    connection = AsyncMock()
    connect = AsyncMock(return_value=connection)
    process = AsyncMock()
    monkeypatch.setattr(worker.asyncpg, "connect", connect)
    monkeypatch.setattr(worker, "_process_job", process)
    job = {
        "id": 42,
        "entrypoint": "test.claim",
        "payload": {},
        "claim_generation": 7,
        "claim_protocol_version": 2,
    }

    await worker._process_claimed_job("postgres://queue", job)

    connect.assert_awaited_once_with("postgres://queue")
    process.assert_awaited_once_with(connection, job)
    connection.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# run_pipeline handler
# ---------------------------------------------------------------------------


@patch("src.pipeline.runner.run_pipeline", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_run_pipeline_handler(mock_run):
    handler = _handlers["run_pipeline"]
    await handler(1, {"pipeline_type": "daily", "sources": ["gmail", "rss"]})
    mock_run.assert_called_once()
    assert mock_run.call_args[1]["pipeline_type"] == "daily"
    assert mock_run.call_args[1]["sources"] == ["gmail", "rss"]
