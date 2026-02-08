"""Shared ingestion orchestrator layer.

Centralizes the "wire up and call" logic for each ingestion source.
CLI, pipeline, and task worker all delegate here instead of independently
importing, instantiating, and calling service classes.

Each function:
- Lazy-imports its service classes (avoids circular imports, defers heavy deps)
- Accepts the same parameters the service expects
- Returns int (number of items ingested)
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.ingestion.rss import IngestionResult

logger = get_logger(__name__)


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


def ingest_youtube(
    *,
    max_videos: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    use_oauth: bool = True,
) -> int:
    """Ingest transcripts from YouTube playlists, channels, and RSS feeds.

    Encapsulates the 3-call pattern across 2 service classes:
    1. YouTubeContentIngestionService.ingest_all_playlists()
    2. YouTubeContentIngestionService.ingest_channels()
    3. YouTubeRSSIngestionService.ingest_all_feeds()

    Args:
        max_videos: Maximum videos per playlist/channel/feed.
        after_date: Only fetch videos after this date.
        force_reprocess: Force reprocess existing content.
        use_oauth: Use OAuth for private content (False = API key only).

    Returns:
        Total number of items ingested across all YouTube source types.
    """
    from src.ingestion.youtube import (
        YouTubeContentIngestionService,
        YouTubeRSSIngestionService,
    )

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

    rss_service = YouTubeRSSIngestionService()
    feed_count = rss_service.ingest_all_feeds(
        max_entries_per_feed=max_videos,
        after_date=after_date,
        force_reprocess=force_reprocess,
    )

    return playlist_count + channel_count + feed_count


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
