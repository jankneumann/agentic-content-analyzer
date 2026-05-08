"""Shared ingestion orchestrator layer.

Centralizes the "wire up and call" logic for each ingestion source.
CLI, pipeline, and task worker all delegate here instead of independently
importing, instantiating, and calling service classes.

Each function:
- Lazy-imports its service classes (avoids circular imports, defers heavy deps)
- Accepts the same parameters the service expects
- Returns either the canonical ``IngestionResponse`` envelope (rss, blog,
  huggingface_papers, substack, xsearch, perplexity-search, youtube,
  youtube-rss, youtube-playlist, podcast, scholar, scholar-paper,
  scholar-refs, arxiv, arxiv-paper — the harmonized sources) or a legacy
  shape (``int`` count for gmail, or a small result dataclass like
  ``URLIngestResult`` for url) for sources not yet migrated. Migration to
  ``IngestionResponse`` is in progress.

Sources: gmail, rss, blog, youtube, podcast, substack, xsearch, perplexity, url, scholar, arxiv, huggingface_papers

"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from src.telemetry.decorators import observe
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.ingestion.arxiv import ArxivPaperResult
    from src.ingestion.result import IngestionResponse
    from src.ingestion.scholar import ScholarPaperResult

logger = get_logger(__name__)


@dataclass
class URLIngestResult:
    """Result of a direct URL ingestion."""

    content_id: int
    status: str  # "queued" or "exists"
    duplicate: bool


@observe()
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


@observe()
def ingest_rss(
    *,
    max_entries_per_feed: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    on_result: Callable[[IngestionResponse], None] | None = None,
) -> IngestionResponse:
    """Ingest articles from configured RSS feeds.

    Args:
        max_entries_per_feed: Maximum entries per feed.
        after_date: Only fetch entries after this date.
        force_reprocess: Force reprocess existing content.
        on_result: Optional legacy callback that receives the full IngestionResponse.
                   Prefer using the return value directly; on_result will be removed
                   when all CLI direct paths consume the canonical envelope.

    Returns:
        Canonical IngestionResponse envelope with status, items_ingested,
        errors, and warnings populated from per-source diagnostics.
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
    return result


@observe()
def ingest_blog(
    *,
    max_entries_per_source: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    on_result: Callable[[IngestionResponse], None] | None = None,
) -> IngestionResponse:
    """Ingest blog posts from configured blog sources.

    Discovers post links from blog index pages, extracts content
    via Trafilatura, and persists with deduplication.

    Args:
        max_entries_per_source: Maximum posts per blog source.
        after_date: Only fetch posts after this date.
        force_reprocess: Force reprocess existing content.
        on_result: Optional legacy callback. Prefer the return value directly.

    Returns:
        Canonical IngestionResponse envelope.
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
    return result


def _merge_youtube_envelopes(
    *,
    command: str,
    source: str,
    parts: list[IngestionResponse],
) -> IngestionResponse:
    """Merge multiple IngestionResponse parts into a single combined envelope.

    Used by ``ingest_youtube_playlist`` (playlists + channels share the
    youtube-playlist command) and ``ingest_youtube`` (playlist + RSS).
    Preserves all per-source errors / warnings so consumers can still see
    which feed or playlist failed; status is recomputed from the merged
    counts so a partial-success across the union is correctly classified.
    """
    from src.ingestion.result import (
        IngestionError,
        IngestionResponse as _Response,
        IngestionStatus,
    )

    items_ingested = sum(p.items_ingested for p in parts)
    items_skipped = sum(p.items_skipped for p in parts)
    items_failed = sum(p.items_failed for p in parts)
    errors: list[IngestionError] = [e for p in parts for e in p.errors]
    warnings = [w for p in parts for w in p.warnings]

    has_failure = bool(errors) or items_failed > 0
    if not has_failure:
        status: IngestionStatus = "ok"
    elif items_ingested > 0:
        status = "partial"
    else:
        status = "error"

    return _Response(
        command=command,  # type: ignore[arg-type]
        source=source,  # type: ignore[arg-type]
        status=status,
        items_ingested=items_ingested,
        items_skipped=items_skipped,
        items_failed=items_failed,
        errors=errors,
        warnings=warnings,
    )


@observe()
def ingest_youtube_playlist(
    *,
    max_videos: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    use_oauth: bool = True,
) -> IngestionResponse:
    """Ingest content from YouTube playlists and channels.

    Uses YouTubeContentIngestionService to process playlists (via YouTube
    Data API) and channels. Supports both Gemini native video extraction
    and transcript-based fallback.  Service methods are async; this function
    bridges via asyncio.run() to keep callers synchronous. The two service
    calls return separate envelopes which we merge into one combined envelope
    for the youtube-playlist command.

    Args:
        max_videos: Maximum videos per playlist/channel.
        after_date: Only fetch videos after this date.
        force_reprocess: Force reprocess existing content.
        use_oauth: Use OAuth for private content (False = API key only).

    Returns:
        Canonical IngestionResponse envelope (command='ingest.youtube-playlist',
        source='youtube-playlist').
    """
    import asyncio

    from src.ingestion.youtube import YouTubeContentIngestionService

    async def _run() -> tuple[IngestionResponse, IngestionResponse]:
        service = YouTubeContentIngestionService(use_oauth=use_oauth)
        playlist_response = await service.ingest_all_playlists(
            max_videos_per_playlist=max_videos,
            after_date=after_date,
            force_reprocess=force_reprocess,
        )
        channel_response = await service.ingest_channels(
            max_videos_per_channel=max_videos,
            after_date=after_date,
            force_reprocess=force_reprocess,
        )
        return playlist_response, channel_response

    playlist_response, channel_response = asyncio.run(_run())
    return _merge_youtube_envelopes(
        command="ingest.youtube-playlist",
        source="youtube-playlist",
        parts=[playlist_response, channel_response],
    )


@observe()
def ingest_youtube_rss(
    *,
    max_videos: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
) -> IngestionResponse:
    """Ingest content from YouTube RSS feeds.

    Uses YouTubeRSSIngestionService to process channel RSS feeds.
    Supports Gemini native video extraction (with low resolution by default)
    and transcript-based fallback. Service methods are async; this function
    bridges via asyncio.run() to keep callers synchronous.

    Args:
        max_videos: Maximum videos per feed.
        after_date: Only fetch videos after this date.
        force_reprocess: Force reprocess existing content.

    Returns:
        Canonical IngestionResponse envelope (command='ingest.youtube-rss',
        source='youtube-rss').
    """
    import asyncio

    from src.ingestion.youtube import YouTubeRSSIngestionService

    async def _run() -> IngestionResponse:
        service = YouTubeRSSIngestionService()
        return await service.ingest_all_feeds(
            max_entries_per_feed=max_videos,
            after_date=after_date,
            force_reprocess=force_reprocess,
        )

    return asyncio.run(_run())


@observe()
def ingest_youtube(
    *,
    max_videos: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    use_oauth: bool = True,
) -> IngestionResponse:
    """Ingest from all YouTube sources (playlists, channels, and RSS feeds).

    Backward-compatible combined function that runs playlists first,
    then RSS feeds. Playlists run first because they are higher priority
    (curated content) and have fewer videos. The two sub-envelopes
    are merged so the consumer sees one canonical youtube envelope.

    Args:
        max_videos: Maximum videos per playlist/channel/feed.
        after_date: Only fetch videos after this date.
        force_reprocess: Force reprocess existing content.
        use_oauth: Use OAuth for private content (False = API key only).

    Returns:
        Canonical IngestionResponse envelope (command='ingest.youtube',
        source='youtube'). All errors/warnings from both sub-envelopes
        are concatenated in order (playlist first, then RSS).
    """
    playlist_response = ingest_youtube_playlist(
        max_videos=max_videos,
        after_date=after_date,
        force_reprocess=force_reprocess,
        use_oauth=use_oauth,
    )
    rss_response = ingest_youtube_rss(
        max_videos=max_videos,
        after_date=after_date,
        force_reprocess=force_reprocess,
    )
    return _merge_youtube_envelopes(
        command="ingest.youtube",
        source="youtube",
        parts=[playlist_response, rss_response],
    )


@observe()
def ingest_podcast(
    *,
    max_entries_per_feed: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
) -> IngestionResponse:
    """Ingest episodes from configured podcast feeds.

    Args:
        max_entries_per_feed: Maximum episodes per feed.
        after_date: Only fetch episodes after this date.
        force_reprocess: Force reprocess existing content.

    Returns:
        Canonical IngestionResponse envelope.
    """
    from src.ingestion.podcast import PodcastContentIngestionService

    service = PodcastContentIngestionService()
    return service.ingest_all_feeds(
        max_entries_per_feed=max_entries_per_feed,
        after_date=after_date,
        force_reprocess=force_reprocess,
    )


@observe()
def ingest_substack(
    *,
    max_entries_per_source: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    session_cookie: str | None = None,
) -> IngestionResponse:
    """Ingest posts from Substack sources.

    Handles service.close() in a try/finally block to ensure cleanup.

    Args:
        max_entries_per_source: Maximum posts per Substack source.
        after_date: Only fetch posts after this date.
        force_reprocess: Force reprocess existing content.
        session_cookie: Override SUBSTACK_SESSION_COOKIE value.

    Returns:
        Canonical IngestionResponse envelope.
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


@observe()
def ingest_xsearch(
    *,
    prompt: str | None = None,
    max_threads: int | None = None,
    force_reprocess: bool = False,
    on_result: Callable[[IngestionResponse], None] | None = None,
) -> IngestionResponse:
    """Ingest X posts/threads via Grok API search.

    Uses the xAI SDK with the x_search tool to discover AI-relevant
    content on X. The search prompt is configurable via the prompt
    management system (pipeline.xsearch.search_prompt).

    Args:
        prompt: Override the default search prompt.
        max_threads: Maximum threads to ingest (default from settings).
        force_reprocess: Re-ingest threads that already exist.
        on_result: Optional legacy callback that receives the full
                   IngestionResponse. Prefer the return value directly.

    Returns:
        Canonical IngestionResponse envelope. ``details`` carries the
        xsearch-specific ``tool_calls_made`` and ``threads_found`` extras.
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
        return result
    finally:
        service.close()


@observe()
def ingest_perplexity_search(
    *,
    prompt: str | None = None,
    max_results: int | None = None,
    force_reprocess: bool = False,
    recency_filter: str | None = None,
    context_size: str | None = None,
    on_result: Callable[[IngestionResponse], None] | None = None,
) -> IngestionResponse:
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
        on_result: Optional legacy callback that receives the full
                   IngestionResponse. Prefer the return value directly.

    Returns:
        Canonical IngestionResponse envelope. ``details`` carries the
        perplexity-specific ``queries_made`` and ``citations_found`` extras.
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
        return result
    finally:
        service.close()


@observe()
def ingest_scholar(
    *,
    max_entries: int = 20,
) -> IngestionResponse:
    """Ingest academic papers from configured scholar sources.

    Loads scholar sources from sources.d/scholar.yaml and runs search-based
    ingestion for each enabled source via the ScholarContentIngestionService.
    Each source's ``ScholarSearchResult`` is folded into the canonical
    envelope: ``papers_ingested`` accumulates as ``items_ingested``,
    duplicates and filter rejections collapse into ``items_skipped``,
    and per-paper failures populate ``items_failed``. Source-level
    exceptions become ``IngestionError`` entries (one per source).

    Args:
        max_entries: Maximum papers per source.

    Returns:
        Canonical IngestionResponse envelope (command='ingest.scholar',
        source='scholar').
    """
    import asyncio

    from src.config.sources import load_sources_config
    from src.ingestion.result import IngestionError, IngestionResponse, IngestionStatus

    try:
        config = load_sources_config()
        sources = config.get_scholar_sources()
    except Exception:
        logger.debug("Could not load scholar sources config")
        return IngestionResponse(
            command="ingest.scholar", source="scholar", status="ok", items_ingested=0
        )

    if not sources:
        return IngestionResponse(
            command="ingest.scholar", source="scholar", status="ok", items_ingested=0
        )

    async def _run() -> tuple[int, int, int, list[IngestionError]]:
        from src.ingestion.scholar import ScholarContentIngestionService

        service = ScholarContentIngestionService()
        ingested = 0
        skipped = 0
        failed = 0
        errors: list[IngestionError] = []
        try:
            for source in sources:
                if not source.enabled:
                    continue
                try:
                    result = await service.ingest_from_search(source, force_reprocess=False)
                    ingested += result.papers_ingested
                    skipped += result.papers_skipped_duplicate + result.papers_skipped_filter
                    failed += result.papers_failed
                except Exception as exc:
                    logger.error(f"Scholar source '{source.name}' failed: {exc}")
                    errors.append(
                        IngestionError(
                            code="scholar_source_error",
                            message=str(exc),
                            url=source.name,
                        )
                    )
        finally:
            await service.close()
        return ingested, skipped, failed, errors

    items_ingested, items_skipped, items_failed, errors = asyncio.run(_run())

    has_failure = bool(errors) or items_failed > 0
    if not has_failure:
        status: IngestionStatus = "ok"
    elif items_ingested > 0:
        status = "partial"
    else:
        status = "error"

    return IngestionResponse(
        command="ingest.scholar",
        source="scholar",
        status=status,
        items_ingested=items_ingested,
        items_skipped=items_skipped,
        items_failed=items_failed,
        errors=errors,
    )


@observe()
def ingest_scholar_paper(
    *,
    identifier: str,
    with_refs: bool = False,
) -> IngestionResponse:
    """Ingest a single academic paper by identifier.

    Resolves the identifier (DOI, arXiv ID, S2 paper ID, or URL) to a
    Semantic Scholar paper and ingests it. Optionally ingests referenced
    papers as well; in that mode the seed paper plus its references are
    counted together under ``items_ingested``.

    Args:
        identifier: DOI, arXiv ID, S2 paper ID, or URL.
        with_refs: Also ingest papers referenced by this paper.

    Returns:
        Canonical IngestionResponse envelope (command='ingest.scholar-paper',
        source='scholar_paper'). ``details`` carries the original identifier,
        the resolved S2 paper id (when available), the ``with_refs`` flag,
        and ``refs_ingested`` (subset of items_ingested that came from the
        references walk).
    """
    import asyncio

    from src.ingestion.result import (
        IngestionError,
        IngestionResponse,
        IngestionStatus,
    )

    async def _run() -> ScholarPaperResult:
        from src.ingestion.scholar import ScholarContentIngestionService

        service = ScholarContentIngestionService()
        try:
            return await service.ingest_paper(identifier, with_refs=with_refs)
        finally:
            await service.close()

    result = asyncio.run(_run())

    refs_ingested = result.refs_ingested if with_refs else 0
    items_ingested = (1 if result.ingested else 0) + refs_ingested
    items_skipped = 1 if result.already_exists else 0

    errors: list[IngestionError] = []
    if result.error:
        errors.append(
            IngestionError(
                code="scholar_paper_error",
                message=result.error,
                url=identifier,
            )
        )

    has_failure = bool(errors)
    if not has_failure:
        status: IngestionStatus = "ok"
    elif items_ingested > 0:
        status = "partial"
    else:
        status = "error"

    return IngestionResponse(
        command="ingest.scholar-paper",
        source="scholar_paper",
        status=status,
        items_ingested=items_ingested,
        items_skipped=items_skipped,
        errors=errors,
        details={
            "identifier": identifier,
            "paper_id": result.paper_id,
            "with_refs": with_refs,
            "refs_ingested": refs_ingested,
        },
    )


@observe()
def ingest_scholar_refs(
    *,
    after: datetime | None = None,
    before: datetime | None = None,
    source_types: list[str] | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> IngestionResponse:
    """Extract and ingest academic paper references from existing content.

    Scans existing content records for arXiv IDs, DOIs, and Semantic Scholar
    URLs, then resolves and ingests the referenced papers. Reference-extraction
    counters from ``ReferenceExtractionResult`` (content_scanned, references_found,
    references_resolved/unresolved) land in ``details``; ``papers_ingested`` is
    additionally surfaced in ``details`` for backward-compatible JSON consumers
    (per the reserved-key registry in ``result.py``).

    Args:
        after: Only scan content ingested after this date.
        before: Only scan content ingested before this date.
        source_types: Filter content by source types (e.g., ["rss", "gmail"]).
        dry_run: If True, report what would be ingested without actually ingesting.
        limit: Maximum number of references to ingest.

    Returns:
        Canonical IngestionResponse envelope (command='ingest.scholar-refs',
        source='scholar-refs').
    """
    import asyncio

    from src.ingestion.reference_extractor import ReferenceExtractor
    from src.ingestion.result import IngestionResponse
    from src.services.reference_extractor import ReferenceExtractionResult

    async def _run() -> ReferenceExtractionResult:
        extractor = ReferenceExtractor()
        try:
            return await extractor.ingest_extracted_references(
                after=after,
                before=before,
                source_types=source_types,
                dry_run=dry_run,
                limit=limit,
            )
        finally:
            await extractor.close()

    result = asyncio.run(_run())

    return IngestionResponse(
        command="ingest.scholar-refs",
        source="scholar-refs",
        status="ok",
        items_ingested=result.papers_ingested,
        items_skipped=result.papers_skipped_duplicate,
        details={
            "papers_ingested": result.papers_ingested,
            "content_scanned": result.content_scanned,
            "references_found": result.references_found,
            "references_resolved": result.references_resolved,
            "references_unresolved": result.references_unresolved,
            "dry_run": dry_run,
        },
    )


@observe()
def ingest_arxiv(
    *,
    max_results: int = 20,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    no_pdf: bool = False,
) -> IngestionResponse:
    """Ingest papers from configured arXiv sources.

    Loads sources from sources.d/arxiv.yaml and runs search-based
    ingestion for each enabled source. Each source's ``ArxivIngestionResult``
    folds into the canonical envelope:
      - ``papers_ingested + papers_updated_version + papers_enriched_scholar``
        all count as ``items_ingested`` (newer or richer content landed in
        the DB)
      - ``papers_skipped_duplicate`` becomes ``items_skipped``
      - ``papers_failed`` becomes ``items_failed``; the per-paper messages
        in ``ArxivIngestionResult.errors`` are flattened into structured
        ``IngestionError`` entries

    Args:
        max_results: Maximum papers per source.
        after_date: Only ingest papers published after this date.
        force_reprocess: Force re-ingest existing papers.
        no_pdf: Skip PDF download, use abstract-only.

    Returns:
        Canonical IngestionResponse envelope (command='ingest.arxiv',
        source='arxiv').
    """
    from src.config.sources import load_sources_config
    from src.ingestion.arxiv import ArxivContentIngestionService
    from src.ingestion.result import IngestionError, IngestionResponse, IngestionStatus

    try:
        config = load_sources_config()
        sources = config.get_arxiv_sources()
    except Exception:
        logger.debug("Could not load arxiv sources config")
        return IngestionResponse(
            command="ingest.arxiv", source="arxiv", status="ok", items_ingested=0
        )

    if not sources:
        return IngestionResponse(
            command="ingest.arxiv", source="arxiv", status="ok", items_ingested=0
        )

    # Override pdf_extraction if --no-pdf
    if no_pdf:
        for s in sources:
            s.pdf_extraction = False

    # Override max_entries
    for s in sources:
        if s.max_entries is None or max_results != 20:
            s.max_entries = max_results

    items_ingested = 0
    items_skipped = 0
    items_failed = 0
    errors: list[IngestionError] = []

    service = ArxivContentIngestionService()
    try:
        for source in sources:
            if not source.enabled:
                continue
            try:
                result = service.ingest_from_search(
                    source,
                    force_reprocess=force_reprocess,
                    after_date=after_date,
                )
                items_ingested += (
                    result.papers_ingested
                    + result.papers_updated_version
                    + result.papers_enriched_scholar
                )
                items_skipped += result.papers_skipped_duplicate
                items_failed += result.papers_failed
                for err_msg in result.errors:
                    errors.append(IngestionError(code="arxiv_paper_error", message=err_msg))
            except Exception as exc:
                logger.error(f"arXiv source '{source.name}' failed: {exc}")
                errors.append(
                    IngestionError(
                        code="arxiv_source_error",
                        message=str(exc),
                        url=source.name,
                    )
                )
    finally:
        service.close()

    has_failure = bool(errors) or items_failed > 0
    if not has_failure:
        status: IngestionStatus = "ok"
    elif items_ingested > 0:
        status = "partial"
    else:
        status = "error"

    return IngestionResponse(
        command="ingest.arxiv",
        source="arxiv",
        status=status,
        items_ingested=items_ingested,
        items_skipped=items_skipped,
        items_failed=items_failed,
        errors=errors,
    )


@observe()
def ingest_arxiv_paper(
    *,
    identifier: str,
    pdf_extraction: bool = True,
    force_reprocess: bool = False,
) -> IngestionResponse:
    """Ingest a single arXiv paper by identifier.

    Args:
        identifier: arXiv ID, URL, or DOI.
        pdf_extraction: Whether to download and parse the PDF.
        force_reprocess: Force re-ingest.

    Returns:
        Canonical IngestionResponse envelope (command='ingest.arxiv-paper',
        source='arxiv_paper'). ``details`` carries the original identifier,
        the resolved base ``arxiv_id``, and the ``version_updated`` flag.
    """
    from src.ingestion.arxiv import ArxivContentIngestionService
    from src.ingestion.result import (
        IngestionError,
        IngestionResponse,
        IngestionStatus,
    )

    service = ArxivContentIngestionService()
    try:
        result: ArxivPaperResult = service.ingest_paper(
            identifier,
            pdf_extraction=pdf_extraction,
            force_reprocess=force_reprocess,
        )
    finally:
        service.close()

    items_ingested = 1 if result.ingested else 0
    items_skipped = 1 if result.already_exists else 0

    errors: list[IngestionError] = []
    if result.error:
        errors.append(
            IngestionError(
                code="arxiv_paper_error",
                message=result.error,
                url=identifier,
            )
        )

    has_failure = bool(errors)
    if not has_failure:
        status: IngestionStatus = "ok"
    elif items_ingested > 0:
        status = "partial"
    else:
        status = "error"

    return IngestionResponse(
        command="ingest.arxiv-paper",
        source="arxiv_paper",
        status=status,
        items_ingested=items_ingested,
        items_skipped=items_skipped,
        errors=errors,
        details={
            "identifier": identifier,
            "arxiv_id": result.arxiv_id,
            "version_updated": result.version_updated,
        },
    )


@observe()
def ingest_huggingface_papers(
    *,
    max_papers: int = 30,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    on_result: Callable[[IngestionResponse], None] | None = None,
) -> IngestionResponse:
    """Ingest daily papers from HuggingFace Papers.

    Fetches the daily papers listing page, discovers paper links, extracts
    content (title, authors, abstract), and persists with deduplication.

    Args:
        max_papers: Maximum papers to ingest per source.
        after_date: Only fetch papers after this date.
        force_reprocess: Force reprocess existing content.
        on_result: Optional legacy callback. Prefer the return value directly.

    Returns:
        Canonical IngestionResponse envelope.
    """
    from src.ingestion.huggingface_papers import HuggingFacePapersContentIngestionService

    service = HuggingFacePapersContentIngestionService()
    result = service.ingest_content(
        max_papers=max_papers,
        after_date=after_date,
        force_reprocess=force_reprocess,
    )
    if on_result:
        on_result(result)
    return result


@observe()
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
