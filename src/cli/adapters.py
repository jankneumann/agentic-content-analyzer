"""Sync adapters for async service methods.

CLI commands are synchronous (top-level entry points), but many services
use async methods. These thin wrappers bridge the gap using asyncio.run().

This is safe because CLI commands are always the top-level entry point —
there is no existing event loop to conflict with.
"""

from __future__ import annotations

import asyncio
from typing import Any


def run_async(coro: Any) -> Any:
    """Run an async coroutine synchronously.

    Args:
        coro: Awaitable coroutine to execute

    Returns:
        The coroutine's return value
    """
    return asyncio.run(coro)


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
    return run_async(creator.create_digest(request))


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
    return run_async(
        analyzer.analyze_themes(request, include_historical_context=include_historical)
    )


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
    return run_async(creator.generate_script(request))


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
