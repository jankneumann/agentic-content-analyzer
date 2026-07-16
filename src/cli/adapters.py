"""Sync adapters for async service methods.

CLI commands are synchronous (top-level entry points), but many services
use async methods. These thin wrappers bridge the gap using asyncio.run().

This is safe because CLI commands are always the top-level entry point —
there is no existing event loop to conflict with.
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)


def run_async(coro: Any) -> Any:
    """Run an async coroutine synchronously.

    Args:
        coro: Awaitable coroutine to execute

    Returns:
        The coroutine's return value
    """
    return asyncio.run(coro)


def _emit_notification_sync(
    event_type: str,
    title: str,
    summary: str | None = None,
    payload: dict | None = None,
) -> None:
    """Best-effort sync notification emission for CLI adapters."""
    try:
        from src.models.notification import NotificationEventType
        from src.services.notification_service import get_dispatcher

        dispatcher = get_dispatcher()
        run_async(
            dispatcher.emit(
                event_type=NotificationEventType(event_type),
                title=title,
                summary=summary,
                payload=payload or {},
            )
        )
    except Exception:
        logger.debug("Failed to emit notification from CLI adapter", exc_info=True)


# --- Review Service ---


def list_pending_reviews_sync() -> Any:
    """List pending reviews synchronously."""
    from src.services.review_service import ReviewService

    service = ReviewService()
    return run_async(service.list_pending_reviews())


def get_digest_sync(digest_id: int) -> Any:
    """Get digest by ID synchronously."""
    from src.services.review_service import ReviewService

    service = ReviewService()
    return run_async(service.get_digest(digest_id))


def start_revision_session_sync(digest_id: int, session_id: str, reviewer: str) -> Any:
    """Start revision session synchronously."""
    from src.services.review_service import ReviewService

    service = ReviewService()
    return run_async(service.start_revision_session(digest_id, session_id, reviewer))


def process_revision_turn_sync(
    context: Any, user_input: str, conversation_history: list, session_id: str
) -> Any:
    """Process a single revision turn synchronously."""
    from src.services.review_service import ReviewService

    service = ReviewService()
    return run_async(
        service.process_revision_turn(context, user_input, conversation_history, session_id)
    )


def finalize_review_sync(
    digest_id: int,
    action: str,
    revision_history: dict | None,
    reviewer: str,
    review_notes: str | None = None,
) -> Any:
    """Finalize review synchronously."""
    from src.services.review_service import ReviewService

    service = ReviewService()
    return run_async(
        service.finalize_review(digest_id, action, revision_history, reviewer, review_notes)
    )


# --- Knowledge Graph ---


def search_graph_sync(query: str, limit: int = 10) -> Any:
    """Search knowledge graph synchronously."""

    async def _search() -> Any:
        from src.storage.graph_provider import GraphBackendUnavailableError
        from src.storage.graphiti_client import GraphitiClient

        try:
            client = await GraphitiClient.create()
        except GraphBackendUnavailableError:
            logger.warning("Graph backend unavailable, returning empty results")
            return []
        return await client.search_related_concepts(query, limit=limit)

    return run_async(_search())


def extract_themes_from_graph_sync(
    start_date: Any, end_date: Any, query: str = "AI and technology themes"
) -> Any:
    """Extract themes from knowledge graph synchronously."""

    async def _extract() -> Any:
        from src.storage.graph_provider import GraphBackendUnavailableError
        from src.storage.graphiti_client import GraphitiClient

        try:
            client = await GraphitiClient.create()
        except GraphBackendUnavailableError:
            logger.warning("Graph backend unavailable, returning empty results")
            return []
        return await client.extract_themes_from_range(start_date, end_date, query=query)

    return run_async(_extract())
