"""Shared ingestion orchestrator layer.

Centralizes the "wire up and call" logic for each ingestion source.
CLI, pipeline, and task worker all delegate here instead of independently
importing, instantiating, and calling service classes.

Each function:
- Lazy-imports its service classes (avoids circular imports, defers heavy deps)
- Accepts the same parameters the service expects
- Returns the canonical ``IngestionResponse`` envelope. Round-4 harmonization
  (2026-05-08) closed the last legacy shapes (``int`` for gmail, the small
  ``URLIngestResult`` dataclass for url, and the ad-hoc per-file dict for
  files); every command now produces the same envelope.

Sources: gmail, rss, blog, youtube, podcast, substack, xsearch, perplexity,
url, files, scholar, arxiv, huggingface_papers, readwise

"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from src.telemetry.decorators import observe
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.ingestion.arxiv import ArxivPaperResult
    from src.ingestion.result import IngestionResponse
    from src.ingestion.scholar import ScholarPaperResult

logger = get_logger(__name__)


@observe()
def ingest_gmail(
    *,
    query: str | None = None,
    max_results: int | None = None,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
) -> IngestionResponse:
    """Ingest newsletters from Gmail.

    When query or max_results are None, reads defaults from
    sources.d/gmail.yaml via get_gmail_sources(). The Gmail service still
    returns a bare int internally (its API surface predates the envelope);
    we wrap that count at the orchestrator boundary into the canonical
    envelope so all transports see the same shape.

    Args:
        query: Gmail search query. None = use sources.d config.
        max_results: Maximum number of emails to fetch. None = use sources.d config.
        after_date: Only fetch emails after this date.
        force_reprocess: Force reprocess existing content.

    Returns:
        Canonical IngestionResponse envelope (command='ingest.gmail',
        source='gmail').
    """
    from src.ingestion.gmail import GmailContentIngestionService
    from src.ingestion.result import IngestionResponse

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
    count = service.ingest_content(
        query=query,
        max_results=max_results,
        after_date=after_date,
        force_reprocess=force_reprocess,
    )
    return IngestionResponse(
        command="ingest.gmail",
        source="gmail",
        status="ok",
        items_ingested=count,
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
        derive_status,
    )

    items_ingested = sum(p.items_ingested for p in parts)
    items_skipped = sum(p.items_skipped for p in parts)
    items_failed = sum(p.items_failed for p in parts)
    errors: list[IngestionError] = [e for p in parts for e in p.errors]
    warnings = [w for p in parts for w in p.warnings]

    return _Response(
        command=command,  # type: ignore[arg-type]
        source=source,  # type: ignore[arg-type]
        status=derive_status(
            items_ingested=items_ingested, items_failed=items_failed, errors=errors
        ),
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
    from src.ingestion.result import IngestionError, IngestionResponse, derive_status

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

    return IngestionResponse(
        command="ingest.scholar",
        source="scholar",
        status=derive_status(
            items_ingested=items_ingested, items_failed=items_failed, errors=errors
        ),
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

    from src.ingestion.result import IngestionError, IngestionResponse, derive_status

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

    return IngestionResponse(
        command="ingest.scholar-paper",
        source="scholar_paper",
        status=derive_status(items_ingested=items_ingested, items_failed=0, errors=errors),
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
    from src.ingestion.result import IngestionError, IngestionResponse, derive_status

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

    return IngestionResponse(
        command="ingest.arxiv",
        source="arxiv",
        status=derive_status(
            items_ingested=items_ingested, items_failed=items_failed, errors=errors
        ),
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
    from src.ingestion.result import IngestionError, IngestionResponse, derive_status

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

    return IngestionResponse(
        command="ingest.arxiv-paper",
        source="arxiv_paper",
        status=derive_status(items_ingested=items_ingested, items_failed=0, errors=errors),
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
def ingest_readwise(
    *,
    updated_after: datetime | None = None,
    source_types: list[str] | None = None,
    include_deleted: bool | None = None,
    max_books: int | None = None,
    force_reprocess: bool = False,
    on_result: Callable | None = None,
) -> int:
    """Ingest books and highlights from Readwise.

    Imports every Readwise-connected upstream (Kindle, Instapaper, Pocket,
    Apple Books, Airr, Reader, podcast, supplemental) via the v2 export
    endpoint. Each book becomes a Content row; each highlight becomes a
    Highlight row anchored to that Content.

    Configuration (sources.d/readwise.yaml) supplies defaults for
    ``source_types`` and ``include_deleted`` when not passed explicitly.

    Args:
        updated_after: Only fetch books/highlights updated after this time.
        source_types: Restrict to Readwise upstreams (empty/None = all).
        include_deleted: Include tombstones for soft-delete sync.
        max_books: Cap on books per run (defaults to settings.readwise_max_entries).
        force_reprocess: Reset Content.status=PENDING on existing books.
        on_result: Optional callback receiving the full ReadwiseIngestResult.

    Returns:
        Number of books ingested or updated.
    """
    from src.config.sources import load_sources_config
    from src.ingestion.readwise import ReadwiseContentIngestionService

    # Apply sources.d/readwise.yaml defaults
    if source_types is None or include_deleted is None:
        try:
            config = load_sources_config()
            rw_sources = config.get_readwise_sources()
            if rw_sources:
                rw = rw_sources[0]
                if source_types is None:
                    source_types = rw.source_types or None
                if include_deleted is None:
                    include_deleted = rw.include_deleted
        except Exception:
            logger.debug("Could not load readwise sources config, using defaults")

    service = ReadwiseContentIngestionService()
    try:
        result = service.ingest_content(
            updated_after=updated_after,
            source_types=source_types,
            include_deleted=include_deleted,
            max_books=max_books,
            force_reprocess=force_reprocess,
        )
        if on_result is not None:
            on_result(result)
        return result.items_ingested
    finally:
        service.close()


@observe()
def ingest_url(
    *,
    url: str,
    title: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
    auto_route: bool = True,
) -> IngestionResponse:
    """Ingest a single submitted URL, auto-routing it to the right handler.

    When ``auto_route`` is True (the default) the URL is classified via
    :func:`src.ingestion.url_router.classify_url` and dispatched:

    - YouTube video    -> YouTube transcript/analysis ingestion
    - YouTube playlist -> playlist ingestion
    - RSS / Atom feed  -> RSS feed ingestion
    - anything else    -> generic web-page extraction (Trafilatura)

    Set ``auto_route=False`` to force generic web-page extraction regardless of
    the URL shape (the original ``aca ingest url`` behaviour).

    All branches return the same canonical envelope (command='ingest.url',
    source='url'); ``details.routed_to`` records which handler ran so callers
    can render an appropriate message.

    Args:
        url: The URL to ingest.
        title: Optional title override (web-page route only; URL used as fallback).
        tags: Optional tags for the content.
        notes: Optional user notes.
        auto_route: Classify and route the URL (True) or always treat it as a
            generic web page (False).

    Returns:
        Canonical IngestionResponse envelope (command='ingest.url', source='url').
    """
    from src.ingestion.url_router import RouteKind, classify_url

    kind = classify_url(url) if auto_route else RouteKind.WEBPAGE

    if kind == RouteKind.YOUTUBE_VIDEO:
        return _ingest_routed_youtube_video(url, tags, notes)
    if kind == RouteKind.YOUTUBE_PLAYLIST:
        return _ingest_routed_youtube_playlist(url, tags, notes)
    if kind == RouteKind.RSS_FEED:
        return _ingest_routed_rss(url, tags, notes)
    return _ingest_webpage(url=url, title=title, tags=tags, notes=notes)


def _ingest_routed_youtube_video(
    url: str, tags: list[str] | None, notes: str | None
) -> IngestionResponse:
    """Route a shared YouTube video URL to YouTube ingestion."""
    import asyncio

    from src.ingestion.youtube import YouTubeContentIngestionService

    async def _run() -> IngestionResponse:
        service = YouTubeContentIngestionService()
        return await service.ingest_video(url, tags=tags, notes=notes)

    return asyncio.run(_run())


def _ingest_routed_youtube_playlist(
    url: str, tags: list[str] | None, notes: str | None
) -> IngestionResponse:
    """Route a shared YouTube playlist URL to playlist ingestion."""
    import asyncio

    from src.ingestion.result import IngestionError, IngestionResponse, derive_status
    from src.ingestion.youtube import YouTubeContentIngestionService
    from src.utils.youtube_links import extract_playlist_id

    playlist_id = extract_playlist_id(url)
    if not playlist_id:
        return IngestionResponse(
            command="ingest.url",
            source="url",
            status="error",
            errors=[
                IngestionError(
                    code="invalid_youtube_playlist",
                    message=f"Could not extract a playlist id from: {url}",
                    url=url,
                )
            ],
            details={"routed_to": "youtube_playlist", "url": url},
        )

    async def _run():
        service = YouTubeContentIngestionService()
        return await service.ingest_playlist(playlist_id)

    result = asyncio.run(_run())  # SourceFetchResult
    items = result.items_fetched
    return IngestionResponse(
        command="ingest.url",
        source="url",
        status=derive_status(
            items_ingested=items, items_failed=result.items_failed, errors=result.item_errors
        ),
        items_ingested=items,
        items_failed=result.items_failed,
        errors=result.item_errors,
        details={
            "routed_to": "youtube_playlist",
            "url": url,
            "playlist_id": playlist_id,
            "content_id": None,
            "items_ingested": items,
        },
    )


def _ingest_routed_rss(url: str, tags: list[str] | None, notes: str | None) -> IngestionResponse:
    """Route a shared feed URL to RSS feed ingestion.

    A feed expands to many items, so there is no single ``content_id`` to
    return; ``details.items_ingested`` reports how many entries landed. User
    ``notes`` have no per-entry home and are ignored for feeds; ``tags`` ride
    along on the synthesised source so they attach to every ingested entry.
    """
    from src.config.sources import RSSSource
    from src.ingestion.result import IngestionResponse
    from src.ingestion.rss import RSSContentIngestionService

    service = RSSContentIngestionService()
    try:
        source = RSSSource(url=url, tags=tags or [])
        resp = service.ingest_content(sources=[source])
    finally:
        service.close()

    return IngestionResponse(
        command="ingest.url",
        source="url",
        status=resp.status,
        items_ingested=resp.items_ingested,
        items_skipped=resp.items_skipped,
        items_failed=resp.items_failed,
        errors=resp.errors,
        warnings=resp.warnings,
        details={
            "routed_to": "rss_feed",
            "url": url,
            "content_id": None,
            "items_ingested": resp.items_ingested,
        },
    )


def _ingest_webpage(
    *,
    url: str,
    title: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
) -> IngestionResponse:
    """Ingest a single URL as a generic web page (Trafilatura extraction).

    Creates a Content record (source_type=WEBPAGE) and runs URL extraction
    synchronously. Deduplicates by source_url; a duplicate hit returns
    ``items_skipped=1`` (not ``items_ingested``) — the row already existed
    so nothing new landed.

    Args:
        url: The URL to ingest.
        title: Optional title override (URL used as fallback).
        tags: Optional tags for the content.
        notes: Optional user notes.

    Returns:
        Canonical IngestionResponse envelope (command='ingest.url',
        source='url'). ``details`` carries ``content_id``, ``status``
        ('queued' or 'exists'), ``duplicate`` (bool), and the original ``url``.
    """
    from datetime import UTC, datetime

    from src.ingestion.result import IngestionError, IngestionResponse, derive_status
    from src.models.content import Content, ContentSource, ContentStatus
    from src.storage.database import get_db
    from src.utils.content_hash import generate_markdown_hash

    with get_db() as db:
        # Check for duplicate
        existing = db.query(Content).filter(Content.source_url == url).first()
        if existing:
            logger.info(f"URL already exists: content_id={existing.id}, url={url}")
            return IngestionResponse(
                command="ingest.url",
                source="url",
                status="ok",
                items_skipped=1,
                details={
                    "content_id": existing.id,
                    "status": "exists",
                    "duplicate": True,
                    "url": url,
                },
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

    # Trigger extraction synchronously (CLI context — no event loop running).
    # The Content row is already committed at this point — if extraction
    # raises, the row exists in PENDING state and the envelope must reflect
    # that: items_ingested=1 (a row landed) plus an error entry, yielding
    # status='partial'. Letting the exception propagate would have the
    # transport boundary emit status='error', items_ingested=0 — misleading
    # because the row IS in the DB and is resumable by re-running extraction.
    from src.services.url_extractor import URLExtractor

    extraction_errors: list[IngestionError] = []
    with get_db() as db:
        extractor = URLExtractor(db)
        import asyncio

        try:
            asyncio.run(extractor.extract_content(content_id))
        except Exception as exc:
            logger.warning(
                f"URL extraction failed for content_id={content_id}, url={url}: {exc}",
                exc_info=True,
            )
            extraction_errors.append(
                IngestionError(
                    code="extraction_failed",
                    message=str(exc),
                    url=url,
                )
            )

    items_ingested = 1
    return IngestionResponse(
        command="ingest.url",
        source="url",
        status=derive_status(
            items_ingested=items_ingested, items_failed=0, errors=extraction_errors
        ),
        items_ingested=items_ingested,
        errors=extraction_errors,
        details={
            "content_id": content_id,
            "status": "queued",
            "duplicate": False,
            "url": url,
        },
    )


@observe()
def ingest_files(
    *,
    paths: list[Path],
    publication: str | None = None,
    title: str | None = None,
) -> IngestionResponse:
    """Ingest one or more local files into the content pipeline.

    Loops over the provided paths, parsing each via the FileContentIngestionService
    and persisting markdown content. Per-file failures (file-not-found, parse
    errors, size-limit violations) become ``IngestionError`` entries with
    ``url=str(path)`` so the CLI / HTTP / MCP transports can report which
    file went wrong.

    Args:
        paths: Local file paths to ingest.
        publication: Optional publisher/source name applied to every file.
        title: Optional title override (used only when ``len(paths) == 1``;
               callers should not pass title for multi-file batches —
               the CLI emits a warning and drops the value before calling).

    Returns:
        Canonical IngestionResponse envelope (command='ingest.files',
        source='files'). ``details.results`` carries a list of
        ``{path, content_id, title}`` dicts for the rich-mode summary table.
    """
    import asyncio

    from src.ingestion.files import FileContentIngestionService
    from src.ingestion.result import IngestionError, IngestionResponse, derive_status
    from src.parsers.markitdown_parser import MarkItDownParser
    from src.parsers.router import ParserRouter
    from src.storage.database import get_db

    items_ingested = 0
    items_failed = 0
    errors: list[IngestionError] = []
    results: list[dict] = []

    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            items_failed += 1
            errors.append(
                IngestionError(
                    code="file_not_found",
                    message=f"File not found: {path}",
                    url=str(path),
                )
            )
            continue

        try:
            with get_db() as db:
                markitdown = MarkItDownParser()
                router = ParserRouter(markitdown_parser=markitdown)
                service = FileContentIngestionService(router=router, db=db)
                content = asyncio.run(
                    service.ingest_file(path, publication=publication, title=title)
                )
            items_ingested += 1
            results.append(
                {
                    "path": str(path),
                    "content_id": content.id,
                    "title": content.title,
                }
            )
        except Exception as exc:
            items_failed += 1
            errors.append(
                IngestionError(
                    code="file_ingest_error",
                    message=str(exc),
                    url=str(path),
                )
            )

    return IngestionResponse(
        command="ingest.files",
        source="files",
        status=derive_status(
            items_ingested=items_ingested, items_failed=items_failed, errors=errors
        ),
        items_ingested=items_ingested,
        items_failed=items_failed,
        errors=errors,
        details={"results": results},
    )
