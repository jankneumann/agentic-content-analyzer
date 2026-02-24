"""Notification dispatch service.

Emits notification events when pipeline jobs complete or fail.
Events are persisted to the database and pushed to connected SSE clients.

Usage:
    from src.services.notification_service import get_dispatcher

    dispatcher = get_dispatcher()
    await dispatcher.emit(
        event_type=NotificationEventType.DIGEST_CREATION,
        title="Daily Digest Created",
        summary="Your daily AI digest is ready with 12 articles.",
        payload={"digest_id": 42, "url": "/digests/42"},
    )
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from src.models.notification import NotificationEventType
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Global set of subscriber queues for SSE delivery
_sse_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()


class NotificationDispatcher:
    """Dispatch notification events to database and SSE clients.

    Thread-safe: uses asyncio primitives for subscriber management.
    """

    async def emit(
        self,
        *,
        event_type: NotificationEventType,
        title: str,
        summary: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Emit a notification event.

        Stores the event in the database and pushes it to connected SSE
        clients (if the event type is enabled in preferences).

        Returns:
            The serialized event dict, or None if storage failed.
        """
        event_id = uuid.uuid4()
        now = datetime.now(UTC)
        event_payload = payload or {}

        # Store in database (always, regardless of preferences)
        event_record = await self._store_event(
            event_id=event_id,
            event_type=event_type,
            title=title,
            summary=summary,
            payload=event_payload,
            created_at=now,
        )
        if event_record is None:
            return None

        # Check if delivery is enabled for this event type
        if not await self._is_delivery_enabled(event_type):
            logger.debug(f"Notification delivery disabled for {event_type}, stored but not pushed")
            return event_record

        # Push to connected SSE clients
        await self._push_to_subscribers(event_record)

        return event_record

    async def _store_event(
        self,
        *,
        event_id: uuid.UUID,
        event_type: NotificationEventType,
        title: str,
        summary: str | None,
        payload: dict[str, Any],
        created_at: datetime,
    ) -> dict[str, Any] | None:
        """Store a notification event in the database."""
        try:
            from src.models.notification import NotificationEvent
            from src.storage.database import get_db

            with get_db() as db:
                event = NotificationEvent(
                    id=event_id,
                    event_type=event_type.value,
                    title=title,
                    summary=summary,
                    payload=payload,
                    read=False,
                    created_at=created_at,
                )
                db.add(event)
                db.commit()

            event_dict = {
                "id": str(event_id),
                "event_type": event_type.value,
                "title": title,
                "summary": summary,
                "payload": payload,
                "read": False,
                "created_at": created_at.isoformat(),
            }
            logger.info(f"Notification event stored: {event_type.value} - {title}")
            return event_dict

        except Exception:
            logger.error("Failed to store notification event", exc_info=True)
            return None

    async def _is_delivery_enabled(self, event_type: NotificationEventType) -> bool:
        """Check if delivery is enabled for this event type via preferences."""
        try:
            from src.services.settings_service import SettingsService

            service = SettingsService()
            value = service.get(f"notification.{event_type.value}")
            # Default to enabled if no preference is set
            if value is None:
                return True
            return value.lower() == "true"
        except Exception:
            # If we can't check preferences, default to enabled
            return True

    async def _push_to_subscribers(self, event: dict[str, Any]) -> None:
        """Push an event to all connected SSE subscribers."""
        dead_queues: list[asyncio.Queue] = []
        for queue in _sse_subscribers.copy():
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("SSE subscriber queue full, dropping event")
            except Exception:
                dead_queues.append(queue)

        # Clean up dead queues
        for q in dead_queues:
            _sse_subscribers.discard(q)


def subscribe() -> asyncio.Queue[dict[str, Any]]:
    """Subscribe to notification events for SSE delivery.

    Returns an asyncio.Queue that will receive notification events.
    Call unsubscribe() when done.
    """
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
    _sse_subscribers.add(queue)
    logger.debug(f"SSE subscriber added (total: {len(_sse_subscribers)})")
    return queue


def unsubscribe(queue: asyncio.Queue[dict[str, Any]]) -> None:
    """Unsubscribe from notification events."""
    _sse_subscribers.discard(queue)
    logger.debug(f"SSE subscriber removed (total: {len(_sse_subscribers)})")


# Module-level singleton
_dispatcher: NotificationDispatcher | None = None


def get_dispatcher() -> NotificationDispatcher:
    """Get the global notification dispatcher instance."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = NotificationDispatcher()
    return _dispatcher
