"""Shared ingestion orchestrator layer.

Centralizes the "wire up and call" logic for each ingestion source.
CLI, pipeline, and task worker all delegate here instead of independently
importing, instantiating, and calling service classes.

Each function:
- Lazy-imports its service classes (avoids circular imports, defers heavy deps)
- Accepts the same parameters the service expects
- Returns int (number of items ingested) or a result dataclass
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.ingestion.rss import IngestionResult

logger = get_logger(__name__)


@dataclass
class URLIngestResult:
    """Result of a direct URL ingestion."""

    content_id: int
    status: str  # "queued" or "exists"
    duplicate: bool


def ingest_gmail(
    *,
    query: str = "label:newsletters-ai",
    max_results: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
) -> int:
    """Ingest newsletters from Gmail.

    Args:
        query: Gmail search query.
        max_results: Maximum number of emails to fetch.
        after_date: Only fetch emails after this date.
        force_reprocess: Force reprocess existing content.

    Returns:
        Number of items ingested.
    """
    from src.ingestion.gmail import GmailContentIngestionService

    service = GmailContentIngestionService()
    return service.ingest_content(
        query=query,
        max_results=max_results,
        after_date=after_date,
        force_reprocess=force_reprocess,
    )


def ingest_rss(
    *,
    max_entries_per_feed: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    on_result: Callable[[IngestionResult], None] | None = None,
) -> int:
    """Ingest articles from configured RSS feeds.

    Args:
        max_entries_per_feed: Maximum entries per feed.
        after_date: Only fetch entries after this date.
        force_reprocess: Force reprocess existing content.
        on_result: Optional callback that receives the full IngestionResult
                   (for rich result reporting in CLI).

    Returns:
        Number of items ingested.
    """
    from src.ingestion.rss import RSSContentIngestionService

    service = RSSContentIngestionService()
    result = service.ingest_content(
        max_entries_per_feed=max_entries_per_feed,
        after_date=after_date,
        force_reprocess=force_reprocess,
    )
    if on_result:
        on_result(result)
    return result.items_ingested


def ingest_youtube_playlist(
    *,
    max_videos: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    use_oauth: bool = True,
) -> int:
    """Ingest content from YouTube playlists and channels.

    Uses YouTubeContentIngestionService to process playlists (via YouTube
    Data API) and channels. Supports both Gemini native video extraction
    and transcript-based fallback.

    Args:
        max_videos: Maximum videos per playlist/channel.
        after_date: Only fetch videos after this date.
        force_reprocess: Force reprocess existing content.
        use_oauth: Use OAuth for private content (False = API key only).

    Returns:
        Number of items ingested from playlists and channels.
    """
    from src.ingestion.youtube import YouTubeContentIngestionService

    service = YouTubeContentIngestionService(use_oauth=use_oauth)
    playlist_count = service.ingest_all_playlists(
        max_videos_per_playlist=max_videos,
        after_date=after_date,
        force_reprocess=force_reprocess,
    )
    channel_count = service.ingest_channels(
        max_videos_per_channel=max_videos,
        after_date=after_date,
        force_reprocess=force_reprocess,
    )

    return playlist_count + channel_count


def ingest_youtube_rss(
    *,
    max_videos: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
) -> int:
    """Ingest content from YouTube RSS feeds.

    Uses YouTubeRSSIngestionService to process channel RSS feeds.
    Supports Gemini native video extraction (with low resolution by default)
    and transcript-based fallback.

    Args:
        max_videos: Maximum videos per feed.
        after_date: Only fetch videos after this date.
        force_reprocess: Force reprocess existing content.

    Returns:
        Number of items ingested from RSS feeds.
    """
    from src.ingestion.youtube import YouTubeRSSIngestionService

    service = YouTubeRSSIngestionService()
    return service.ingest_all_feeds(
        max_entries_per_feed=max_videos,
        after_date=after_date,
        force_reprocess=force_reprocess,
    )


def ingest_youtube(
    *,
    max_videos: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    use_oauth: bool = True,
) -> int:
    """Ingest from all YouTube sources (playlists, channels, and RSS feeds).

    Backward-compatible combined function that runs playlists first,
    then RSS feeds. Playlists run first because they are higher priority
    (curated content) and have fewer videos.

    Args:
        max_videos: Maximum videos per playlist/channel/feed.
        after_date: Only fetch videos after this date.
        force_reprocess: Force reprocess existing content.
        use_oauth: Use OAuth for private content (False = API key only).

    Returns:
        Total number of items ingested across all YouTube source types.
    """
    playlist_count = ingest_youtube_playlist(
        max_videos=max_videos,
        after_date=after_date,
        force_reprocess=force_reprocess,
        use_oauth=use_oauth,
    )
    rss_count = ingest_youtube_rss(
        max_videos=max_videos,
        after_date=after_date,
        force_reprocess=force_reprocess,
    )
    return playlist_count + rss_count


def ingest_podcast(
    *,
    max_entries_per_feed: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
) -> int:
    """Ingest episodes from configured podcast feeds.

    Args:
        max_entries_per_feed: Maximum episodes per feed.
        after_date: Only fetch episodes after this date.
        force_reprocess: Force reprocess existing content.

    Returns:
        Number of episodes ingested.
    """
    from src.ingestion.podcast import PodcastContentIngestionService

    service = PodcastContentIngestionService()
    return service.ingest_all_feeds(
        max_entries_per_feed=max_entries_per_feed,
        after_date=after_date,
        force_reprocess=force_reprocess,
    )


def ingest_substack(
    *,
    max_entries_per_source: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    session_cookie: str | None = None,
) -> int:
    """Ingest posts from Substack sources.

    Handles service.close() in a try/finally block to ensure cleanup.

    Args:
        max_entries_per_source: Maximum posts per Substack source.
        after_date: Only fetch posts after this date.
        force_reprocess: Force reprocess existing content.
        session_cookie: Override SUBSTACK_SESSION_COOKIE value.

    Returns:
        Number of items ingested.
    """
    from src.ingestion.substack import SubstackContentIngestionService

    service = SubstackContentIngestionService(session_cookie=session_cookie)
    try:
        return service.ingest_content(
            max_entries_per_source=max_entries_per_source,
            after_date=after_date,
            force_reprocess=force_reprocess,
        )
    finally:
        service.close()


def ingest_url(
    *,
    url: str,
    title: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
) -> URLIngestResult:
    """Ingest a single URL using the save-url workflow.

    Creates a Content record (source_type=WEBPAGE) and enqueues background
    extraction via URLExtractor. Deduplicates by source_url.

    Args:
        url: The URL to ingest.
        title: Optional title override (URL used as fallback).
        tags: Optional tags for the content.
        notes: Optional user notes.

    Returns:
        URLIngestResult with content_id, status, and duplicate flag.
    """
    from datetime import UTC, datetime

    from src.models.content import Content, ContentSource, ContentStatus
    from src.storage.database import get_db
    from src.utils.content_hash import generate_markdown_hash

    with get_db() as db:
        # Check for duplicate
        existing = db.query(Content).filter(Content.source_url == url).first()
        if existing:
            logger.info(f"URL already exists: content_id={existing.id}, url={url}")
            return URLIngestResult(
                content_id=existing.id,
                status="exists",
                duplicate=True,
            )

        # Build metadata
        metadata: dict = {"capture_source": "cli"}
        if tags:
            metadata["tags"] = tags
        if notes:
            metadata["notes"] = notes

        content = Content(
            source_type=ContentSource.WEBPAGE,
            source_id=f"webpage:{url}",
            source_url=url,
            title=title or url,
            markdown_content="",
            content_hash=generate_markdown_hash(""),
            status=ContentStatus.PENDING,
            metadata_json=metadata,
            ingested_at=datetime.now(UTC),
        )

        db.add(content)
        db.commit()
        db.refresh(content)

        content_id = content.id
        logger.info(f"Created content record: id={content_id}, url={url}")

    # Trigger extraction synchronously (CLI context — no event loop running)
    from src.services.url_extractor import URLExtractor

    with get_db() as db:
        extractor = URLExtractor(db)
        import asyncio

        asyncio.run(extractor.extract_content(content_id))

    return URLIngestResult(
        content_id=content_id,
        status="queued",
        duplicate=False,
    )
