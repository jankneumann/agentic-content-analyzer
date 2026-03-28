"""Shared ingestion orchestrator layer.

Centralizes the "wire up and call" logic for each ingestion source.
CLI, pipeline, and task worker all delegate here instead of independently
importing, instantiating, and calling service classes.

Each function:
- Lazy-imports its service classes (avoids circular imports, defers heavy deps)
- Accepts the same parameters the service expects
- Returns int (number of items ingested) or a result dataclass

Sources: gmail, rss, blog, youtube, podcast, substack, xsearch, perplexity, url, scholar, arxiv
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
    query: str | None = None,
    max_results: int | None = None,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
) -> int:
    """Ingest newsletters from Gmail.

    When query or max_results are None, reads defaults from
    sources.d/gmail.yaml via get_gmail_sources().

    Args:
        query: Gmail search query. None = use sources.d config.
        max_results: Maximum number of emails to fetch. None = use sources.d config.
        after_date: Only fetch emails after this date.
        force_reprocess: Force reprocess existing content.

    Returns:
        Number of items ingested.
    """
    from src.ingestion.gmail import GmailContentIngestionService

    # Apply sources.d/gmail.yaml defaults when params not explicitly set
    if query is None or max_results is None:
        try:
            from src.config.sources import load_sources_config

            config = load_sources_config()
            gmail_sources = config.get_gmail_sources()
            if gmail_sources:
                source = gmail_sources[0]
                if query is None:
                    query = source.query
                if max_results is None:
                    max_results = source.max_results
        except Exception:
            logger.debug("Could not load gmail sources config, using defaults")

    # Fallback defaults if config loading failed or no sources defined
    query = query or "label:newsletters-ai"
    max_results = max_results or 50

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


def ingest_blog(
    *,
    max_entries_per_source: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    on_result: Callable[[IngestionResult], None] | None = None,
) -> int:
    """Ingest blog posts from configured blog sources.

    Discovers post links from blog index pages, extracts content
    via Trafilatura, and persists with deduplication.

    Args:
        max_entries_per_source: Maximum posts per blog source.
        after_date: Only fetch posts after this date.
        force_reprocess: Force reprocess existing content.
        on_result: Optional callback for rich result reporting in CLI.

    Returns:
        Number of items ingested.
    """
    from src.ingestion.blog_scraper import BlogContentIngestionService

    service = BlogContentIngestionService()
    result = service.ingest_content(
        max_entries_per_source=max_entries_per_source,
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
    and transcript-based fallback.  Service methods are async; this function
    bridges via asyncio.run() to keep callers synchronous.

    Args:
        max_videos: Maximum videos per playlist/channel.
        after_date: Only fetch videos after this date.
        force_reprocess: Force reprocess existing content.
        use_oauth: Use OAuth for private content (False = API key only).

    Returns:
        Number of items ingested from playlists and channels.
    """
    import asyncio

    from src.ingestion.youtube import YouTubeContentIngestionService

    async def _run() -> int:
        service = YouTubeContentIngestionService(use_oauth=use_oauth)
        playlist_count = await service.ingest_all_playlists(
            max_videos_per_playlist=max_videos,
            after_date=after_date,
            force_reprocess=force_reprocess,
        )
        channel_count = await service.ingest_channels(
            max_videos_per_channel=max_videos,
            after_date=after_date,
            force_reprocess=force_reprocess,
        )
        return playlist_count + channel_count

    return asyncio.run(_run())


def ingest_youtube_rss(
    *,
    max_videos: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
) -> int:
    """Ingest content from YouTube RSS feeds.

    Uses YouTubeRSSIngestionService to process channel RSS feeds.
    Supports Gemini native video extraction (with low resolution by default)
    and transcript-based fallback.  Service methods are async; this function
    bridges via asyncio.run() to keep callers synchronous.

    Args:
        max_videos: Maximum videos per feed.
        after_date: Only fetch videos after this date.
        force_reprocess: Force reprocess existing content.

    Returns:
        Number of items ingested from RSS feeds.
    """
    import asyncio

    from src.ingestion.youtube import YouTubeRSSIngestionService

    async def _run() -> int:
        service = YouTubeRSSIngestionService()
        return await service.ingest_all_feeds(
            max_entries_per_feed=max_videos,
            after_date=after_date,
            force_reprocess=force_reprocess,
        )

    return asyncio.run(_run())


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


def ingest_xsearch(
    *,
    prompt: str | None = None,
    max_threads: int | None = None,
    force_reprocess: bool = False,
    on_result: Callable | None = None,
) -> int:
    """Ingest X posts/threads via Grok API search.

    Uses the xAI SDK with the x_search tool to discover AI-relevant
    content on X. The search prompt is configurable via the prompt
    management system (pipeline.xsearch.search_prompt).

    Args:
        prompt: Override the default search prompt.
        max_threads: Maximum threads to ingest (default from settings).
        force_reprocess: Re-ingest threads that already exist.
        on_result: Optional callback that receives the full XSearchResult
                   (for rich result reporting in CLI).

    Returns:
        Number of items ingested.
    """
    from src.ingestion.xsearch import GrokXContentIngestionService

    service = GrokXContentIngestionService()
    try:
        result = service.ingest_threads(
            prompt=prompt,
            max_threads=max_threads,
            force_reprocess=force_reprocess,
        )
        if on_result is not None:
            on_result(result)
        return result.items_ingested
    finally:
        service.close()


def ingest_perplexity_search(
    *,
    prompt: str | None = None,
    max_results: int | None = None,
    force_reprocess: bool = False,
    recency_filter: str | None = None,
    context_size: str | None = None,
    on_result: Callable | None = None,
) -> int:
    """Ingest web content via Perplexity Sonar API search.

    Uses Perplexity's AI-powered web search to discover articles with
    citations. The search prompt is configurable via the prompt management
    system (pipeline.perplexity_search.search_prompt).

    Args:
        prompt: Override the default search prompt.
        max_results: Maximum results to ingest (default from settings).
        force_reprocess: Re-ingest content that already exists.
        recency_filter: Override recency filter (hour/day/week/month).
        context_size: Override context size (low/medium/high).
        on_result: Optional callback that receives the full PerplexitySearchResult.

    Returns:
        Number of items ingested.
    """
    from src.ingestion.perplexity_search import PerplexityContentIngestionService

    service = PerplexityContentIngestionService()
    try:
        result = service.ingest_content(
            prompt=prompt,
            max_results=max_results,
            force_reprocess=force_reprocess,
            recency_filter=recency_filter,
            context_size=context_size,
        )
        if on_result is not None:
            on_result(result)
        return result.items_ingested
    finally:
        service.close()


def ingest_scholar(
    *,
    max_entries: int = 20,
) -> int:
    """Ingest academic papers from configured scholar sources.

    Loads scholar sources from sources.d/scholar.yaml and runs search-based
    ingestion for each enabled source via the ScholarContentIngestionService.

    Args:
        max_entries: Maximum papers per source.

    Returns:
        Number of papers ingested.
    """
    import asyncio

    from src.config.sources import load_sources_config
    from src.ingestion.scholar import ScholarContentIngestionService

    try:
        config = load_sources_config()
        sources = config.get_scholar_sources()
    except Exception:
        logger.debug("Could not load scholar sources config")
        return 0

    if not sources:
        return 0

    async def _run() -> int:
        service = ScholarContentIngestionService()
        try:
            total = 0
            for source in sources:
                if not source.enabled:
                    continue
                try:
                    result = await service.ingest_from_search(source)
                    total += result.papers_ingested
                except Exception as exc:
                    logger.error(f"Scholar source '{source.name}' failed: {exc}")
            return total
        finally:
            await service.close()

    return asyncio.run(_run())


def ingest_scholar_paper(
    *,
    identifier: str,
    with_refs: bool = False,
) -> int:
    """Ingest a single academic paper by identifier.

    Resolves the identifier (DOI, arXiv ID, S2 paper ID, or URL) to a
    Semantic Scholar paper and ingests it. Optionally ingests referenced
    papers as well.

    Args:
        identifier: DOI, arXiv ID, S2 paper ID, or URL.
        with_refs: Also ingest papers referenced by this paper.

    Returns:
        Number of papers ingested (1 if successful, 0 if not).
    """
    import asyncio

    from src.ingestion.scholar import ScholarContentIngestionService

    async def _run() -> int:
        service = ScholarContentIngestionService()
        try:
            result = await service.ingest_paper(identifier, with_refs=with_refs)
            return 1 if result.ingested else 0
        finally:
            await service.close()

    return asyncio.run(_run())


def ingest_scholar_refs(
    *,
    after: datetime | None = None,
    before: datetime | None = None,
    source_types: list[str] | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> int:
    """Extract and ingest academic paper references from existing content.

    Scans existing content records for arXiv IDs, DOIs, and Semantic Scholar
    URLs, then resolves and ingests the referenced papers.

    Args:
        after: Only scan content ingested after this date.
        before: Only scan content ingested before this date.
        source_types: Filter content by source types (e.g., ["rss", "gmail"]).
        dry_run: If True, report what would be ingested without actually ingesting.
        limit: Maximum number of references to ingest.

    Returns:
        Number of papers ingested from extracted references.
    """
    import asyncio

    from src.ingestion.reference_extractor import ReferenceExtractor

    async def _run() -> int:
        extractor = ReferenceExtractor()
        try:
            result = await extractor.ingest_extracted_references(
                after=after,
                before=before,
                source_types=source_types,
                dry_run=dry_run,
                limit=limit,
            )
            return result.papers_ingested
        finally:
            await extractor.close()

    return asyncio.run(_run())


def ingest_arxiv(
    *,
    max_results: int = 20,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    no_pdf: bool = False,
) -> int:
    """Ingest papers from configured arXiv sources.

    Loads sources from sources.d/arxiv.yaml and runs search-based
    ingestion for each enabled source.

    Args:
        max_results: Maximum papers per source.
        after_date: Only ingest papers published after this date.
        force_reprocess: Force re-ingest existing papers.
        no_pdf: Skip PDF download, use abstract-only.

    Returns:
        Number of papers ingested.
    """
    from src.config.sources import load_sources_config
    from src.ingestion.arxiv import ArxivContentIngestionService

    try:
        config = load_sources_config()
        sources = config.get_arxiv_sources()
    except Exception:
        logger.debug("Could not load arxiv sources config")
        return 0

    if not sources:
        return 0

    # Override pdf_extraction if --no-pdf
    if no_pdf:
        for s in sources:
            s.pdf_extraction = False

    # Override max_entries
    for s in sources:
        if s.max_entries is None or max_results != 20:
            s.max_entries = max_results

    service = ArxivContentIngestionService()
    try:
        return service.ingest_content(
            sources=sources,
            after_date=after_date,
            force_reprocess=force_reprocess,
        )
    finally:
        service.close()


def ingest_arxiv_paper(
    *,
    identifier: str,
    pdf_extraction: bool = True,
    force_reprocess: bool = False,
) -> int:
    """Ingest a single arXiv paper by identifier.

    Args:
        identifier: arXiv ID, URL, or DOI.
        pdf_extraction: Whether to download and parse the PDF.
        force_reprocess: Force re-ingest.

    Returns:
        1 if ingested, 0 otherwise.
    """
    from src.ingestion.arxiv import ArxivContentIngestionService

    service = ArxivContentIngestionService()
    try:
        result = service.ingest_paper(
            identifier,
            pdf_extraction=pdf_extraction,
            force_reprocess=force_reprocess,
        )
        return 1 if result.ingested else 0
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
