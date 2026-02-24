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


# --- Digest Creation ---


def create_digest_sync(request: Any) -> Any:
    """Create a digest synchronously.

    Args:
        request: DigestRequest instance

    Returns:
        DigestData
    """
    from src.processors.digest_creator import DigestCreator

    creator = DigestCreator()
    result = run_async(creator.create_digest(request))

    if result:
        digest_type = getattr(request, "digest_type", "daily")
        _emit_notification_sync(
            event_type="digest_creation",
            title=f"{digest_type.capitalize()} Digest Created",
            summary=f"Your {digest_type} digest is ready.",
            payload={
                "digest_type": str(digest_type),
                "url": "/digests",
            },
        )

    return result


# --- Theme Analysis ---


def analyze_themes_sync(request: Any, include_historical: bool = True) -> Any:
    """Run theme analysis synchronously.

    Args:
        request: ThemeAnalysisRequest instance
        include_historical: Whether to include historical context

    Returns:
        ThemeAnalysisResult
    """
    from src.processors.theme_analyzer import ThemeAnalyzer

    analyzer = ThemeAnalyzer()
    result = run_async(
        analyzer.analyze_themes(request, include_historical_context=include_historical)
    )

    if result:
        theme_count = len(getattr(result, "themes", []))
        _emit_notification_sync(
            event_type="theme_analysis",
            title="Theme Analysis Complete",
            summary=f"Identified {theme_count} themes across recent content.",
            payload={
                "theme_count": theme_count,
                "url": "/themes",
            },
        )

    return result


# --- Podcast ---


def generate_podcast_script_sync(request: Any) -> Any:
    """Generate podcast script synchronously.

    Args:
        request: PodcastRequest instance

    Returns:
        PodcastScriptRecord
    """
    from src.processors.podcast_creator import PodcastCreator

    creator = PodcastCreator()
    result = run_async(creator.generate_script(request))

    if result:
        script_id = getattr(result, "id", None)
        _emit_notification_sync(
            event_type="script_generation",
            title="Podcast Script Generated",
            summary="A new podcast script is ready for review.",
            payload={
                "script_id": script_id,
                "url": f"/scripts/{script_id}" if script_id else "/scripts",
            },
        )

    return result


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
    from src.storage.graphiti_client import GraphitiClient

    client = GraphitiClient()
    return run_async(client.search_related_concepts(query, limit=limit))


def extract_themes_from_graph_sync(
    start_date: Any, end_date: Any, query: str = "AI and technology themes"
) -> Any:
    """Extract themes from knowledge graph synchronously."""
    from src.storage.graphiti_client import GraphitiClient

    client = GraphitiClient()
    return run_async(client.extract_themes_from_range(start_date, end_date, query=query))


# --- File Ingestion ---


def ingest_file_sync(
    file_path: Any,
    publication: str | None = None,
    title: str | None = None,
) -> Any:
    """Ingest a file synchronously."""
    from src.ingestion.files import FileContentIngestionService
    from src.parsers.markitdown_parser import MarkItDownParser
    from src.parsers.router import ParserRouter
    from src.storage.database import get_db

    with get_db() as db:
        markitdown = MarkItDownParser()
        router = ParserRouter(markitdown_parser=markitdown)
        service = FileContentIngestionService(router=router, db=db)
        return run_async(service.ingest_file(file_path, publication=publication, title=title))
