"""Tests for extended source types in the ingest_content worker handler.

Verifies that each source type in the handler's source_map correctly dispatches
to the corresponding orchestrator function with the right keyword arguments.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from uuid import UUID

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
async def test_process_job_treats_claim_cancelled_as_expected_outcome(monkeypatch) -> None:
    from src.queue import worker
    from src.queue.execution_claim import ClaimCancelled

    async def handler(_job_id: int, _payload: dict) -> None:
        raise ClaimCancelled("cancel raced domain commit")

    checkpoint = AsyncMock(side_effect=[False, True])
    fail = AsyncMock()
    notification = AsyncMock()
    monkeypatch.setitem(worker._handlers, "test.claim-cancelled", handler)
    monkeypatch.setattr(worker, "_checkpoint_job_cancellation", checkpoint)
    monkeypatch.setattr(worker, "_fail_job", fail)
    monkeypatch.setattr(worker, "_emit_job_notification", notification)
    monkeypatch.setattr("src.queue.setup.touch_job_heartbeat", AsyncMock(return_value=True))

    await worker._process_job(
        AsyncMock(),
        {
            "id": 42,
            "entrypoint": "test.claim-cancelled",
            "payload": {},
            "claim_generation": 7,
            "claim_protocol_version": 2,
        },
    )

    assert checkpoint.await_count == 2
    fail.assert_not_awaited()
    notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_job_drops_superseded_domain_outcome(monkeypatch) -> None:
    from src.queue import worker
    from src.queue.execution_claim import ClaimSuperseded

    async def handler(_job_id: int, _payload: dict) -> None:
        raise ClaimSuperseded("generation changed")

    fail = AsyncMock()
    notification = AsyncMock()
    monkeypatch.setitem(worker._handlers, "test.claim-superseded", handler)
    monkeypatch.setattr(
        worker,
        "_checkpoint_job_cancellation",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(worker, "_fail_job", fail)
    monkeypatch.setattr(worker, "_emit_job_notification", notification)
    monkeypatch.setattr("src.queue.setup.touch_job_heartbeat", AsyncMock(return_value=True))

    await worker._process_job(
        AsyncMock(),
        {
            "id": 42,
            "entrypoint": "test.claim-superseded",
            "payload": {},
            "claim_generation": 7,
            "claim_protocol_version": 2,
        },
    )

    fail.assert_not_awaited()
    notification.assert_not_awaited()


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


@pytest.mark.parametrize(
    ("disposition", "failure_status"),
    (("success", None), ("retry", "exhausted")),
)
@pytest.mark.asyncio
async def test_alert_maintenance_commits_claim_before_sink_io(
    monkeypatch,
    disposition: str,
    failure_status: str | None,
) -> None:
    from src.queue import worker

    event_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    connection = MagicMock()
    connection.fetchval = AsyncMock(return_value=True)
    connection.fetch = AsyncMock(side_effect=[[{"id": event_id}], [{"id": event_id}]])
    connection.execute = AsyncMock(return_value="DELETE 0")
    session_open = False
    sessions: list[MagicMock] = []

    @contextmanager
    def get_db():
        nonlocal session_open
        session = MagicMock()
        sessions.append(session)
        session_open = True
        try:
            yield session
        finally:
            session_open = False

    processor = MagicMock()
    processor.process_pending_event = AsyncMock(return_value=SimpleNamespace())
    processor_type = MagicMock(return_value=processor)
    claim = SimpleNamespace(
        delivery_id=event_id,
        event_id=event_id,
        sink_name="webhook",
        attempt_count=1,
        lease_expires_at=datetime(2026, 8, 1, 12, 1, tzinfo=UTC),
        created_at=datetime(2026, 8, 1, 12, tzinfo=UTC),
        envelope=MagicMock(),
    )
    sink = MagicMock()

    async def deliver(*_args, **_kwargs):
        assert session_open is False
        connection.transaction.return_value.__aexit__.assert_awaited_once()
        return SimpleNamespace(
            disposition=disposition,
            error_code=None if disposition == "success" else "timeout",
            retry_after_seconds=None,
        )

    sink.deliver = AsyncMock(side_effect=deliver)
    monkeypatch.setattr("src.storage.database.get_db", get_db)
    monkeypatch.setattr(
        "src.services.workflow_terminal_event_service.WorkflowTerminalEventService",
        processor_type,
    )
    ensure_delivery = MagicMock()
    claim_due = MagicMock(return_value=[claim])
    mark_succeeded = MagicMock(return_value=True)
    record_failure = MagicMock(return_value=failure_status)
    cleanup = MagicMock(return_value=0)
    alert_logger = MagicMock()
    generic_dispatcher = MagicMock()
    monkeypatch.setattr(
        "src.services.notification_service.get_dispatcher",
        generic_dispatcher,
    )
    monkeypatch.setattr("src.services.workflow_alert_delivery.ensure_delivery", ensure_delivery)
    monkeypatch.setattr("src.services.workflow_alert_delivery.claim_due_deliveries", claim_due)
    monkeypatch.setattr(
        "src.services.workflow_alert_delivery.mark_delivery_succeeded", mark_succeeded
    )
    monkeypatch.setattr(
        "src.services.workflow_alert_delivery.record_delivery_failure", record_failure
    )
    monkeypatch.setattr("src.services.workflow_alert_delivery.cleanup_terminal_deliveries", cleanup)
    monkeypatch.setattr(worker, "_build_workflow_alert_sink", MagicMock(return_value=sink))
    monkeypatch.setattr(worker, "logger", alert_logger)
    settings = _alert_settings()

    assert await worker._run_workflow_alert_maintenance_tick(
        connection,
        alert_settings=settings,
    )

    processor.process_pending_event.assert_awaited_once_with(event_id)
    pending_query = connection.fetch.await_args_list[0].args[0]
    assert "job.parent_job_id IS NULL" in pending_query
    assert "child_cohort" in pending_query
    assert "UNION ALL" in pending_query
    ensure_delivery.assert_called_once()
    claim_due.assert_called_once()
    sink.deliver.assert_awaited_once()
    if disposition == "success":
        mark_succeeded.assert_called_once()
        record_failure.assert_not_called()
        alert_logger.error.assert_not_called()
    else:
        mark_succeeded.assert_not_called()
        record_failure.assert_called_once()
        alert_logger.error.assert_called_once_with(
            "workflow alert delivery exhausted delivery_id=%s event_id=%s",
            claim.delivery_id,
            claim.event_id,
        )
    generic_dispatcher.assert_not_called()
    assert len(sessions) >= 4
    # The tick takes the transaction-scoped leader lock FIRST. It now also
    # evaluates backup freshness inside the same locked section (which may issue
    # its own fetchval to enqueue a system_check event), so this asserts the lock
    # is the first fetchval rather than the only one.
    assert connection.fetchval.await_args_list[0].args == (
        "SELECT pg_try_advisory_xact_lock($1::bigint)",
        worker._WORKFLOW_ALERT_MAINTENANCE_ADVISORY_LOCK,
    )
    assert not any(
        call.args[0].startswith("SELECT pg_advisory_unlock")
        for call in connection.execute.await_args_list
    )


@pytest.mark.asyncio
async def test_alert_delivery_window_has_no_lease_queue_wait_and_persists_fast_first(
    monkeypatch,
) -> None:
    from src.queue import worker

    first_id = UUID("11111111-1111-4111-8111-111111111111")
    second_id = UUID("22222222-2222-4222-8222-222222222222")
    first_started = asyncio.Event()
    second_started = asyncio.Event()
    release_first = asyncio.Event()
    second_persisted = asyncio.Event()
    connection = MagicMock()
    connection.fetchval = AsyncMock(return_value=True)
    connection.fetch = AsyncMock(side_effect=[[], []])
    connection.execute = AsyncMock(return_value="DELETE 0")

    @contextmanager
    def get_db():
        yield MagicMock()

    def claim(delivery_id: UUID) -> SimpleNamespace:
        return SimpleNamespace(
            delivery_id=delivery_id,
            event_id=delivery_id,
            sink_name="webhook",
            attempt_count=1,
            lease_expires_at=datetime(2026, 8, 1, 12, 1, tzinfo=UTC),
            created_at=datetime(2026, 8, 1, 12, tzinfo=UTC),
            envelope=MagicMock(),
        )

    claims = [claim(first_id), claim(second_id)]
    claim_due = MagicMock(return_value=claims)

    async def deliver(envelope, **_kwargs):
        connection.transaction.return_value.__aexit__.assert_awaited_once()
        if envelope is claims[0].envelope:
            first_started.set()
            await release_first.wait()
        else:
            second_started.set()
        return SimpleNamespace(
            disposition="success",
            error_code=None,
            retry_after_seconds=None,
        )

    def mark_succeeded(_db, *, claim, now):
        del now
        if claim.delivery_id == second_id:
            second_persisted.set()
        return True

    sink = MagicMock()
    sink.deliver = AsyncMock(side_effect=deliver)
    monkeypatch.setattr("src.storage.database.get_db", get_db)
    monkeypatch.setattr("src.services.workflow_alert_delivery.ensure_delivery", MagicMock())
    monkeypatch.setattr("src.services.workflow_alert_delivery.claim_due_deliveries", claim_due)
    monkeypatch.setattr(
        "src.services.workflow_alert_delivery.mark_delivery_succeeded", mark_succeeded
    )
    monkeypatch.setattr(
        "src.services.workflow_alert_delivery.cleanup_terminal_deliveries", MagicMock()
    )
    monkeypatch.setattr(worker, "_build_workflow_alert_sink", MagicMock(return_value=sink))

    task = asyncio.create_task(
        worker._run_workflow_alert_maintenance_tick(
            connection,
            alert_settings=_alert_settings(),
        )
    )
    try:
        await asyncio.wait_for(first_started.wait(), timeout=1)
        await asyncio.wait_for(second_started.wait(), timeout=1)
        await asyncio.wait_for(second_persisted.wait(), timeout=1)
        assert not task.done()
    finally:
        release_first.set()
        await task

    assert claim_due.call_args.kwargs["batch_size"] <= 8


@pytest.mark.asyncio
async def test_alert_delivery_cancellation_leaves_started_claim_for_lease_recovery(
    monkeypatch,
) -> None:
    from src.queue import worker

    event_id = UUID("33333333-3333-4333-8333-333333333333")
    connection = MagicMock()
    connection.fetchval = AsyncMock(return_value=True)
    connection.fetch = AsyncMock(side_effect=[[], []])
    connection.execute = AsyncMock(return_value="DELETE 0")
    delivery_started = asyncio.Event()

    @contextmanager
    def get_db():
        yield MagicMock()

    claim = SimpleNamespace(
        delivery_id=event_id,
        event_id=event_id,
        sink_name="webhook",
        attempt_count=1,
        lease_expires_at=datetime(2026, 8, 1, 12, 1, tzinfo=UTC),
        created_at=datetime(2026, 8, 1, 12, tzinfo=UTC),
        envelope=MagicMock(),
    )

    async def deliver(*_args, **_kwargs):
        delivery_started.set()
        await asyncio.Event().wait()

    sink = MagicMock()
    sink.deliver = AsyncMock(side_effect=deliver)
    mark_succeeded = MagicMock()
    record_failure = MagicMock()
    monkeypatch.setattr("src.storage.database.get_db", get_db)
    monkeypatch.setattr("src.services.workflow_alert_delivery.ensure_delivery", MagicMock())
    monkeypatch.setattr(
        "src.services.workflow_alert_delivery.claim_due_deliveries",
        MagicMock(return_value=[claim]),
    )
    monkeypatch.setattr(
        "src.services.workflow_alert_delivery.mark_delivery_succeeded", mark_succeeded
    )
    monkeypatch.setattr(
        "src.services.workflow_alert_delivery.record_delivery_failure", record_failure
    )
    monkeypatch.setattr(
        "src.services.workflow_alert_delivery.cleanup_terminal_deliveries", MagicMock()
    )
    monkeypatch.setattr(worker, "_build_workflow_alert_sink", MagicMock(return_value=sink))

    task = asyncio.create_task(
        worker._run_workflow_alert_maintenance_tick(
            connection,
            alert_settings=_alert_settings(),
        )
    )
    await asyncio.wait_for(delivery_started.wait(), timeout=1)
    connection.transaction.return_value.__aexit__.assert_awaited_once()
    assert not any(
        call.args[0].startswith("SELECT pg_advisory_unlock")
        for call in connection.execute.await_args_list
    )
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    mark_succeeded.assert_not_called()
    record_failure.assert_not_called()


@pytest.mark.asyncio
async def test_alert_delivery_outer_deadline_covers_hanging_sink_resolution() -> None:
    from src.queue import worker

    event_id = UUID("44444444-4444-4444-8444-444444444444")
    claim = SimpleNamespace(
        delivery_id=event_id,
        event_id=event_id,
        envelope=MagicMock(),
    )

    async def hang(*_args, **_kwargs):
        await asyncio.Event().wait()

    sink = MagicMock()
    sink.deliver = AsyncMock(side_effect=hang)

    returned_claim, result = await asyncio.wait_for(
        worker._deliver_workflow_alert_claim(sink, claim, timeout_seconds=0.01),
        timeout=0.5,
    )

    assert returned_claim is claim
    assert result.disposition == "retry"
    assert result.error_code == "timeout"


@pytest.mark.asyncio
async def test_late_alert_success_is_fenced_without_burning_another_attempt(monkeypatch) -> None:
    from src.queue import worker

    event_id = UUID("55555555-5555-4555-8555-555555555555")
    claim = SimpleNamespace(
        delivery_id=event_id,
        event_id=event_id,
        sink_name="webhook",
        attempt_count=1,
        lease_expires_at=datetime(2026, 8, 1, 12, 1, tzinfo=UTC),
        created_at=datetime(2026, 8, 1, 12, tzinfo=UTC),
        envelope=MagicMock(),
    )

    @contextmanager
    def get_db():
        yield MagicMock()

    sink = MagicMock()
    sink.deliver = AsyncMock(
        return_value=SimpleNamespace(
            disposition="success",
            error_code=None,
            retry_after_seconds=None,
        )
    )
    mark_succeeded = MagicMock(return_value=False)
    record_failure = MagicMock()
    alert_logger = MagicMock()
    monkeypatch.setattr("src.storage.database.get_db", get_db)
    monkeypatch.setattr(
        "src.services.workflow_alert_delivery.claim_due_deliveries",
        MagicMock(return_value=[claim]),
    )
    monkeypatch.setattr(
        "src.services.workflow_alert_delivery.mark_delivery_succeeded", mark_succeeded
    )
    monkeypatch.setattr(
        "src.services.workflow_alert_delivery.record_delivery_failure", record_failure
    )
    monkeypatch.setattr(worker, "_build_workflow_alert_sink", MagicMock(return_value=sink))
    monkeypatch.setattr(worker, "logger", alert_logger)

    assert await worker._drain_workflow_alert_deliveries(alert_settings=_alert_settings()) == 0

    mark_succeeded.assert_called_once()
    record_failure.assert_not_called()
    alert_logger.warning.assert_called_once_with(
        "workflow alert result missed lease delivery_id=%s event_id=%s",
        claim.delivery_id,
        claim.event_id,
    )


def test_alert_event_retention_never_selects_ready_without_delivery() -> None:
    from src.queue import worker

    query = worker._WORKFLOW_ALERT_ORPHAN_EVENT_CLEANUP_QUERY

    assert "classification_status IN ('telemetry_only', 'rejected')" in query
    assert "classification_status IN ('ready'" not in query


def test_alert_classification_reserves_child_slice_during_sustained_root_backlog() -> None:
    from src.queue import worker

    root_limit, child_limit = worker._workflow_alert_cohort_sizes(50)

    assert root_limit + child_limit == 50
    assert root_limit >= 1
    assert child_limit >= 1


def test_alert_classification_reserves_root_for_deferred_child_even_at_minimum_batch() -> None:
    from src.queue import worker

    root_limit, child_limit = worker._workflow_alert_cohort_sizes(1)

    assert (root_limit, child_limit) == (1, 1)


@pytest.mark.asyncio
async def test_alert_maintenance_cancellation_releases_transaction_leader_lock(monkeypatch) -> None:
    from src.queue import worker

    event_id = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    connection = MagicMock()
    connection.fetchval = AsyncMock(return_value=True)
    connection.fetch = AsyncMock(return_value=[{"id": event_id}])
    connection.execute = AsyncMock()
    started = asyncio.Event()

    async def block_until_cancelled(_event_id):
        started.set()
        await asyncio.Event().wait()

    processor = MagicMock()
    processor.process_pending_event = AsyncMock(side_effect=block_until_cancelled)
    monkeypatch.setattr(
        "src.services.workflow_terminal_event_service.WorkflowTerminalEventService",
        MagicMock(return_value=processor),
    )

    task = asyncio.create_task(
        worker._run_workflow_alert_maintenance_tick(
            connection,
            alert_settings=_alert_settings(),
        )
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    connection.transaction.return_value.__aexit__.assert_awaited_once()
    assert not any(
        call.args[0].startswith("SELECT pg_advisory_unlock")
        for call in connection.execute.await_args_list
    )


def _alert_settings() -> SimpleNamespace:
    return SimpleNamespace(
        workflow_alert_sink="webhook",
        workflow_alert_diagnostic_origin="https://ops.example.com",
        workflow_alert_webhook_endpoint="https://alerts.example.com/hook",
        workflow_alert_webhook_secret=None,
        workflow_alert_timeout_seconds=10,
        workflow_alert_lease_seconds=60,
        workflow_alert_max_attempts=5,
        workflow_alert_base_backoff_seconds=30,
        workflow_alert_max_backoff_seconds=3600,
        workflow_alert_max_retry_after_seconds=3600,
        workflow_alert_delivery_max_age_seconds=604800,
        workflow_alert_retention_days=30,
        workflow_alert_exhausted_retention_days=90,
        workflow_alert_batch_size=50,
        get_workflow_alert_allowed_hosts=lambda: ("alerts.example.com",),
        is_development=False,
    )


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
