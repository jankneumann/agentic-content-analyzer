"""Tests for notification dispatch service.

Tests cover:
- Event emission (store + push to subscribers)
- Delivery preference checking
- SSE subscriber pub/sub management
- Singleton dispatcher
"""

import asyncio
from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.models.notification import NotificationEventType
from src.services.notification_service import (
    NotificationDispatcher,
    _sse_subscribers,
    get_dispatcher,
    subscribe,
    unsubscribe,
)


@pytest.fixture(autouse=True)
def cleanup_subscribers():
    """Clean up SSE subscribers and dispatcher singleton between tests."""
    _sse_subscribers.clear()
    import src.services.notification_service as mod

    mod._dispatcher = None
    yield
    _sse_subscribers.clear()
    mod._dispatcher = None


# ============================================================================
# Subscribe / Unsubscribe
# ============================================================================


def test_subscribe_adds_queue():
    """subscribe() creates a queue and adds it to the global set."""
    queue = subscribe()
    assert queue in _sse_subscribers
    assert isinstance(queue, asyncio.Queue)


def test_unsubscribe_removes_queue():
    """unsubscribe() removes the queue from the global set."""
    queue = subscribe()
    assert queue in _sse_subscribers
    unsubscribe(queue)
    assert queue not in _sse_subscribers


def test_unsubscribe_idempotent():
    """Unsubscribing a non-existent queue doesn't raise."""
    queue: asyncio.Queue = asyncio.Queue()
    unsubscribe(queue)  # Should not raise


# ============================================================================
# Singleton
# ============================================================================


def test_get_dispatcher_returns_singleton():
    """get_dispatcher() returns the same instance on repeated calls."""
    d1 = get_dispatcher()
    d2 = get_dispatcher()
    assert d1 is d2
    assert isinstance(d1, NotificationDispatcher)


# ============================================================================
# Push to Subscribers
# ============================================================================


@pytest.mark.asyncio
async def test_push_to_subscribers():
    """_push_to_subscribers puts event data on all subscriber queues."""
    dispatcher = NotificationDispatcher()
    queue = subscribe()
    event = {"id": "test-id", "title": "Test Event"}

    await dispatcher._push_to_subscribers(event)

    assert not queue.empty()
    received = queue.get_nowait()
    assert received == event


@pytest.mark.asyncio
async def test_push_to_full_queue():
    """A full subscriber queue does not crash the push."""
    dispatcher = NotificationDispatcher()
    queue = asyncio.Queue(maxsize=1)
    _sse_subscribers.add(queue)

    # Fill the queue
    queue.put_nowait({"id": "old"})

    # This should not raise
    await dispatcher._push_to_subscribers({"id": "new"})

    # Queue should still contain the old event (new was dropped)
    assert queue.get_nowait() == {"id": "old"}


# ============================================================================
# Delivery Enabled
# ============================================================================


@pytest.mark.asyncio
async def test_is_delivery_enabled_default():
    """When no preference is set, delivery defaults to enabled."""
    dispatcher = NotificationDispatcher()

    mock_service = MagicMock()
    mock_service.get.return_value = None

    with patch("src.services.settings_service.SettingsService", return_value=mock_service):
        result = await dispatcher._is_delivery_enabled(NotificationEventType.DIGEST_CREATION)
    assert result is True


@pytest.mark.asyncio
async def test_is_delivery_enabled_false():
    """When preference is set to 'false', delivery is disabled."""
    dispatcher = NotificationDispatcher()

    mock_service = MagicMock()
    mock_service.get.return_value = "false"

    with patch("src.services.settings_service.SettingsService", return_value=mock_service):
        result = await dispatcher._is_delivery_enabled(NotificationEventType.DIGEST_CREATION)
    assert result is False


@pytest.mark.asyncio
async def test_is_delivery_enabled_true():
    """When preference is set to 'true', delivery is enabled."""
    dispatcher = NotificationDispatcher()

    mock_service = MagicMock()
    mock_service.get.return_value = "true"

    with patch("src.services.settings_service.SettingsService", return_value=mock_service):
        result = await dispatcher._is_delivery_enabled(NotificationEventType.BATCH_SUMMARY)
    assert result is True


@pytest.mark.asyncio
async def test_is_delivery_enabled_error_returns_true():
    """On exception, delivery defaults to enabled (fail-open)."""
    dispatcher = NotificationDispatcher()

    with patch(
        "src.services.settings_service.SettingsService",
        side_effect=Exception("DB error"),
    ):
        result = await dispatcher._is_delivery_enabled(NotificationEventType.JOB_FAILURE)
    assert result is True


# ============================================================================
# Store Event
# ============================================================================


@pytest.mark.asyncio
async def test_store_event_creates_record():
    """_store_event creates a NotificationEvent in the database."""
    dispatcher = NotificationDispatcher()
    mock_session = MagicMock()

    @contextmanager
    def mock_get_db():
        yield mock_session

    with patch("src.storage.database.get_db", mock_get_db):
        import uuid

        event_id = uuid.uuid4()
        result = await dispatcher._store_event(
            event_id=event_id,
            event_type=NotificationEventType.DIGEST_CREATION,
            title="Test Digest",
            summary="A test digest was created",
            payload={"digest_id": 1},
            created_at=datetime.now(UTC),
        )

    assert result is not None
    assert result["id"] == str(event_id)
    assert result["event_type"] == "digest_creation"
    assert result["title"] == "Test Digest"
    assert result["read"] is False
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_store_event_returns_none_on_error():
    """_store_event returns None when DB operation fails."""
    dispatcher = NotificationDispatcher()

    @contextmanager
    def mock_get_db():
        raise Exception("DB connection error")
        yield  # unreachable, but required for contextmanager

    with patch("src.storage.database.get_db", mock_get_db):
        import uuid

        result = await dispatcher._store_event(
            event_id=uuid.uuid4(),
            event_type=NotificationEventType.JOB_FAILURE,
            title="Failed Job",
            summary=None,
            payload={},
            created_at=datetime.now(UTC),
        )

    assert result is None


# ============================================================================
# Emit
# ============================================================================


@pytest.mark.asyncio
async def test_emit_stores_and_pushes():
    """emit() stores the event and pushes to subscribers."""
    dispatcher = NotificationDispatcher()
    queue = subscribe()

    stored_event = {
        "id": "test-uuid",
        "event_type": "digest_creation",
        "title": "Digest Created",
        "summary": None,
        "payload": {},
        "read": False,
        "created_at": "2025-01-15T12:00:00+00:00",
    }

    with (
        patch.object(dispatcher, "_store_event", return_value=stored_event),
        patch.object(dispatcher, "_is_delivery_enabled", return_value=True),
    ):
        result = await dispatcher.emit(
            event_type=NotificationEventType.DIGEST_CREATION,
            title="Digest Created",
        )

    assert result == stored_event
    assert not queue.empty()
    assert queue.get_nowait() == stored_event


@pytest.mark.asyncio
async def test_emit_returns_none_on_storage_failure():
    """emit() returns None when storage fails."""
    dispatcher = NotificationDispatcher()

    with patch.object(dispatcher, "_store_event", return_value=None):
        result = await dispatcher.emit(
            event_type=NotificationEventType.DIGEST_CREATION,
            title="Digest Created",
        )

    assert result is None


@pytest.mark.asyncio
async def test_emit_skips_push_when_delivery_disabled():
    """emit() stores but does not push when delivery is disabled."""
    dispatcher = NotificationDispatcher()
    queue = subscribe()

    stored_event = {
        "id": "test-uuid",
        "event_type": "digest_creation",
        "title": "Digest Created",
        "summary": None,
        "payload": {},
        "read": False,
        "created_at": "2025-01-15T12:00:00+00:00",
    }

    with (
        patch.object(dispatcher, "_store_event", return_value=stored_event),
        patch.object(dispatcher, "_is_delivery_enabled", return_value=False),
    ):
        result = await dispatcher.emit(
            event_type=NotificationEventType.DIGEST_CREATION,
            title="Digest Created",
        )

    # Event is returned (stored) but not pushed to queue
    assert result == stored_event
    assert queue.empty()
