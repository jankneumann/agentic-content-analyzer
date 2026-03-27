"""MCP server exposing newsletter aggregator capabilities.

Provides tools for content ingestion, summarization, digest creation,
search, theme analysis, podcast generation, and review management.

Usage:
    # stdio transport (Claude Desktop, Cursor, etc.)
    python -m src.mcp_server

    # Or via the entry point
    aca-mcp

    # SSE transport (ChatGPT, web clients)
    aca-mcp --transport sse --port 8100
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "Newsletter Aggregator",
    instructions=(
        "AI newsletter aggregation system. Use these tools to ingest content "
        "from various sources (Gmail, RSS, YouTube, podcasts, etc.), summarize "
        "articles, create daily/weekly digests, search across all content, "
        "analyze themes, and generate podcast scripts."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize(obj: Any) -> str:
    """Serialize a result object to JSON string for MCP response."""
    if obj is None:
        return json.dumps({"result": None})
    if isinstance(obj, (str, int, float, bool)):
        return json.dumps({"result": obj})
    if isinstance(obj, dict):
        return json.dumps(obj, default=str)
    if isinstance(obj, list):
        return json.dumps([_to_dict(item) for item in obj], default=str)
    return json.dumps(_to_dict(obj), default=str)


def _to_dict(obj: Any) -> Any:
    """Convert an object to a dict, handling Pydantic models and SQLAlchemy."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return str(obj)


def _parse_date(date_str: str | None) -> datetime | None:
    """Parse an ISO date string to datetime, or None."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return None


# ===========================================================================
# INGESTION TOOLS
# ===========================================================================


@mcp.tool()
def ingest_gmail(
    query: str | None = None,
    max_results: int | None = None,
    after_date: str | None = None,
    force_reprocess: bool = False,
) -> str:
    """Ingest newsletters from Gmail.

    Fetches emails matching the query from Gmail and stores them for processing.
    Uses sources.d/gmail.yaml defaults when parameters are not specified.

    Args:
        query: Gmail search query (e.g., 'label:newsletters-ai'). None = use config default.
        max_results: Maximum emails to fetch. None = use config default.
        after_date: Only fetch emails after this ISO date (e.g., '2025-01-15').
        force_reprocess: Re-process emails that were already ingested.

    Returns:
        JSON with the number of items ingested.
    """
    from src.ingestion.orchestrator import ingest_gmail as _ingest

    count = _ingest(
        query=query,
        max_results=max_results,
        after_date=_parse_date(after_date),
        force_reprocess=force_reprocess,
    )
    return _serialize({"items_ingested": count, "source": "gmail"})


@mcp.tool()
def ingest_rss(
    max_entries_per_feed: int = 10,
    after_date: str | None = None,
    force_reprocess: bool = False,
) -> str:
    """Ingest articles from configured RSS feeds.

    Processes all RSS feeds defined in sources.d/rss.yaml.

    Args:
        max_entries_per_feed: Maximum entries per feed (default: 10).
        after_date: Only fetch entries after this ISO date.
        force_reprocess: Re-process existing content.

    Returns:
        JSON with the number of items ingested.
    """
    from src.ingestion.orchestrator import ingest_rss as _ingest

    count = _ingest(
        max_entries_per_feed=max_entries_per_feed,
        after_date=_parse_date(after_date),
        force_reprocess=force_reprocess,
    )
    return _serialize({"items_ingested": count, "source": "rss"})


@mcp.tool()
def ingest_youtube(
    max_videos: int = 10,
    after_date: str | None = None,
    force_reprocess: bool = False,
    use_oauth: bool = True,
) -> str:
    """Ingest content from YouTube playlists, channels, and RSS feeds.

    Processes all YouTube sources (playlists via OAuth + RSS feeds).
    Supports Gemini native video extraction and transcript fallback.

    Args:
        max_videos: Maximum videos per source (default: 10).
        after_date: Only fetch videos after this ISO date.
        force_reprocess: Re-process existing content.
        use_oauth: Use OAuth for private playlists (default: True).

    Returns:
        JSON with the number of items ingested.
    """
    from src.ingestion.orchestrator import ingest_youtube as _ingest

    count = _ingest(
        max_videos=max_videos,
        after_date=_parse_date(after_date),
        force_reprocess=force_reprocess,
        use_oauth=use_oauth,
    )
    return _serialize({"items_ingested": count, "source": "youtube"})


@mcp.tool()
def ingest_podcast(
    max_entries_per_feed: int = 10,
    after_date: str | None = None,
    force_reprocess: bool = False,
) -> str:
    """Ingest episodes from configured podcast feeds.

    Uses 3-tier transcript strategy: feed text, linked transcript, or audio STT.

    Args:
        max_entries_per_feed: Maximum episodes per feed (default: 10).
        after_date: Only fetch episodes after this ISO date.
        force_reprocess: Re-process existing content.

    Returns:
        JSON with the number of items ingested.
    """
    from src.ingestion.orchestrator import ingest_podcast as _ingest

    count = _ingest(
        max_entries_per_feed=max_entries_per_feed,
        after_date=_parse_date(after_date),
        force_reprocess=force_reprocess,
    )
    return _serialize({"items_ingested": count, "source": "podcast"})


@mcp.tool()
def ingest_substack(
    max_entries_per_source: int = 10,
    after_date: str | None = None,
    force_reprocess: bool = False,
) -> str:
    """Ingest posts from Substack paid subscriptions.

    Processes Substack sources defined in sources.d/substack.yaml.

    Args:
        max_entries_per_source: Maximum posts per source (default: 10).
        after_date: Only fetch posts after this ISO date.
        force_reprocess: Re-process existing content.

    Returns:
        JSON with the number of items ingested.
    """
    from src.ingestion.orchestrator import ingest_substack as _ingest

    count = _ingest(
        max_entries_per_source=max_entries_per_source,
        after_date=_parse_date(after_date),
        force_reprocess=force_reprocess,
    )
    return _serialize({"items_ingested": count, "source": "substack"})


@mcp.tool()
def ingest_xsearch(
    prompt: str | None = None,
    max_threads: int | None = None,
    force_reprocess: bool = False,
) -> str:
    """Ingest X/Twitter content via Grok API search.

    Searches X for AI-relevant posts and threads using xAI's Grok API.

    Args:
        prompt: Custom search prompt. None = use configured default.
        max_threads: Maximum threads to ingest. None = use default.
        force_reprocess: Re-ingest existing threads.

    Returns:
        JSON with the number of items ingested.
    """
    from src.ingestion.orchestrator import ingest_xsearch as _ingest

    count = _ingest(
        prompt=prompt,
        max_threads=max_threads,
        force_reprocess=force_reprocess,
    )
    return _serialize({"items_ingested": count, "source": "xsearch"})


@mcp.tool()
def ingest_perplexity_search(
    prompt: str | None = None,
    max_results: int | None = None,
    force_reprocess: bool = False,
    recency_filter: str | None = None,
    context_size: str | None = None,
) -> str:
    """Ingest web content via Perplexity Sonar API search.

    AI-powered web search that discovers articles with citations.

    Args:
        prompt: Custom search prompt. None = use configured default.
        max_results: Maximum results. None = use default.
        force_reprocess: Re-ingest existing content.
        recency_filter: Time filter: 'hour', 'day', 'week', or 'month'.
        context_size: Context size: 'low', 'medium', or 'high'.

    Returns:
        JSON with the number of items ingested.
    """
    from src.ingestion.orchestrator import ingest_perplexity_search as _ingest

    count = _ingest(
        prompt=prompt,
        max_results=max_results,
        force_reprocess=force_reprocess,
        recency_filter=recency_filter,
        context_size=context_size,
    )
    return _serialize({"items_ingested": count, "source": "perplexity_search"})


@mcp.tool()
def ingest_url(
    url: str,
    title: str | None = None,
    tags: str | None = None,
    notes: str | None = None,
) -> str:
    """Ingest a single URL directly.

    Creates a content record and extracts content from the URL.
    Deduplicates by source URL.

    Args:
        url: The URL to ingest.
        title: Optional title override.
        tags: Comma-separated tags (e.g., 'ai,llm,research').
        notes: Optional user notes about the content.

    Returns:
        JSON with content_id, status ('queued' or 'exists'), and duplicate flag.
    """
    from src.ingestion.orchestrator import ingest_url as _ingest

    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    result = _ingest(url=url, title=title, tags=tag_list, notes=notes)
    return _serialize(result)


# ===========================================================================
# SUMMARIZATION TOOLS
# ===========================================================================


@mcp.tool()
def summarize_pending(
    source_types: str | None = None,
    limit: int | None = None,
    after_date: str | None = None,
    before_date: str | None = None,
    publication: str | None = None,
    search: str | None = None,
) -> str:
    """Summarize pending content using LLM.

    Processes unsummarized content items and generates structured summaries.

    Args:
        source_types: Comma-separated source filter (e.g., 'gmail,rss,youtube').
        limit: Maximum items to summarize.
        after_date: Only summarize content after this ISO date.
        before_date: Only summarize content before this ISO date.
        publication: Filter by publication name.
        search: Search filter on title.

    Returns:
        JSON with the count of items summarized.
    """
    from src.models.content import ContentSource
    from src.models.query import ContentQuery
    from src.processors.summarizer import ContentSummarizer

    query = ContentQuery(
        source_types=(
            [ContentSource(s.strip()) for s in source_types.split(",")]
            if source_types
            else None
        ),
        start_date=_parse_date(after_date),
        end_date=_parse_date(before_date),
        publications=[publication] if publication else None,
        search=search,
        limit=limit,
    )

    summarizer = ContentSummarizer()
    count = summarizer.summarize_pending_contents(query=query)
    return _serialize({"items_summarized": count})


# ===========================================================================
# DIGEST TOOLS
# ===========================================================================


@mcp.tool()
def create_digest(
    digest_type: str = "daily",
    period_start: str | None = None,
    period_end: str | None = None,
    source_types: str | None = None,
    include_historical_context: bool = True,
) -> str:
    """Create a daily or weekly digest from summarized content.

    Generates a structured digest with executive overview, strategic insights,
    technical developments, emerging trends, and actionable recommendations.

    Args:
        digest_type: 'daily' or 'weekly' (default: 'daily').
        period_start: Start of period (ISO date). Defaults to yesterday (daily) or last week (weekly).
        period_end: End of period (ISO date). Defaults to now.
        source_types: Comma-separated source filter (e.g., 'gmail,rss').
        include_historical_context: Include knowledge graph context (default: True).

    Returns:
        JSON with digest metadata including id, title, type, and content summary.
    """
    from src.cli.adapters import create_digest_sync
    from src.models.content import ContentSource
    from src.models.digest import DigestRequest, DigestType
    from src.models.query import ContentQuery

    dtype = DigestType(digest_type)
    now = datetime.now(UTC)

    if period_end:
        end = _parse_date(period_end) or now
    else:
        end = now

    if period_start:
        start = _parse_date(period_start) or (now - timedelta(days=1))
    else:
        start = now - (timedelta(days=1) if dtype == DigestType.DAILY else timedelta(weeks=1))

    content_query = None
    if source_types:
        content_query = ContentQuery(
            source_types=[ContentSource(s.strip()) for s in source_types.split(",")]
        )

    request = DigestRequest(
        digest_type=dtype,
        period_start=start,
        period_end=end,
        include_historical_context=include_historical_context,
        content_query=content_query,
    )

    result = create_digest_sync(request)
    if result is None:
        return _serialize({"error": "No content available for digest creation"})

    return _serialize({
        "digest_type": str(result.digest_type),
        "title": result.title,
        "period_start": str(result.period_start),
        "period_end": str(result.period_end),
        "content_count": result.newsletter_count,
        "executive_overview": result.executive_overview,
        "strategic_insights_count": len(result.strategic_insights),
        "technical_developments_count": len(result.technical_developments),
        "emerging_trends_count": len(result.emerging_trends),
        "model_used": result.model_used,
    })


@mcp.tool()
def list_digests(
    digest_type: str | None = None,
    status: str | None = None,
    limit: int = 10,
) -> str:
    """List existing digests with optional filtering.

    Args:
        digest_type: Filter by type: 'daily' or 'weekly'.
        status: Filter by status: 'COMPLETED', 'PENDING_REVIEW', 'APPROVED', etc.
        limit: Maximum results (default: 10).

    Returns:
        JSON array of digest summaries with id, title, type, status, and dates.
    """
    from src.models.digest import Digest, DigestStatus, DigestType
    from src.storage.database import get_db

    with get_db() as db:
        query = db.query(Digest).order_by(Digest.created_at.desc())

        if digest_type:
            query = query.filter(Digest.digest_type == DigestType(digest_type))
        if status:
            query = query.filter(Digest.status == DigestStatus(status))

        digests = query.limit(limit).all()

        return _serialize([
            {
                "id": d.id,
                "title": d.title,
                "digest_type": str(d.digest_type),
                "status": str(d.status),
                "period_start": str(d.period_start),
                "period_end": str(d.period_end),
                "content_count": d.newsletter_count,
                "created_at": str(d.created_at),
            }
            for d in digests
        ])


@mcp.tool()
def get_digest(digest_id: int) -> str:
    """Get full digest content by ID.

    Returns the complete digest including executive overview, all sections,
    and markdown content.

    Args:
        digest_id: The digest ID to retrieve.

    Returns:
        JSON with full digest content.
    """
    from src.cli.adapters import get_digest_sync

    result = get_digest_sync(digest_id)
    if result is None:
        return _serialize({"error": f"Digest {digest_id} not found"})
    return _serialize(result)


# ===========================================================================
# SEARCH TOOLS
# ===========================================================================


@mcp.tool()
def search_content(
    query: str,
    search_type: str = "hybrid",
    source_types: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    publications: str | None = None,
    limit: int = 20,
) -> str:
    """Search across all ingested content using hybrid BM25 + vector search.

    Combines keyword matching (BM25) with semantic similarity (vector embeddings)
    for comprehensive search results.

    Args:
        query: Search query text.
        search_type: Search method: 'hybrid' (default), 'bm25', or 'vector'.
        source_types: Comma-separated source filter (e.g., 'gmail,rss,youtube').
        date_from: Filter results after this ISO date.
        date_to: Filter results before this ISO date.
        publications: Comma-separated publication filter.
        limit: Maximum results (default: 20, max: 100).

    Returns:
        JSON with search results including title, score, source, and matching chunks.
    """
    import asyncio

    from src.models.search import SearchFilter, SearchQuery, SearchType
    from src.services.search import HybridSearchService
    from src.storage.database import get_db

    filters = SearchFilter(
        source_types=[s.strip() for s in source_types.split(",")] if source_types else None,
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
        publications=[p.strip() for p in publications.split(",")] if publications else None,
    )

    search_query = SearchQuery(
        query=query,
        type=SearchType(search_type),
        filters=filters if any([source_types, date_from, date_to, publications]) else None,
        limit=min(limit, 100),
    )

    with get_db() as db:
        service = HybridSearchService(session=db)
        response = asyncio.run(service.search(search_query))

    return _serialize(response)


# ===========================================================================
# PIPELINE TOOLS
# ===========================================================================


@mcp.tool()
def run_pipeline(digest_type: str = "daily") -> str:
    """Run the full ingestion -> summarization -> digest pipeline.

    Executes all three stages sequentially:
    1. Parallel ingestion from all configured sources
    2. Summarization of all pending content
    3. Digest creation for the period

    This is equivalent to running 'aca pipeline daily' or 'aca pipeline weekly'.

    Args:
        digest_type: 'daily' or 'weekly' (default: 'daily').

    Returns:
        JSON with results from each pipeline stage.
    """
    import asyncio

    from src.ingestion.orchestrator import (
        ingest_gmail,
        ingest_podcast,
        ingest_rss,
        ingest_substack,
        ingest_youtube,
    )
    from src.processors.summarizer import ContentSummarizer

    results: dict[str, Any] = {"pipeline_type": digest_type, "stages": {}}

    # Stage 1: Ingestion (sequential for simplicity in MCP context)
    ingestion_results: dict[str, int] = {}
    sources = {
        "gmail": lambda: ingest_gmail(),
        "rss": lambda: ingest_rss(),
        "youtube": lambda: ingest_youtube(),
        "podcast": lambda: ingest_podcast(),
        "substack": lambda: ingest_substack(),
    }

    for name, func in sources.items():
        try:
            count = func()
            ingestion_results[name] = count
        except Exception as e:
            ingestion_results[name] = 0
            results.setdefault("errors", {})[f"ingest_{name}"] = str(e)

    results["stages"]["ingestion"] = {
        "total_ingested": sum(ingestion_results.values()),
        "by_source": ingestion_results,
    }

    # Stage 2: Summarization
    try:
        summarizer = ContentSummarizer()
        summarized = summarizer.summarize_pending_contents()
        results["stages"]["summarization"] = {"items_summarized": summarized}
    except Exception as e:
        results["stages"]["summarization"] = {"error": str(e)}

    # Stage 3: Digest creation
    try:
        from src.cli.adapters import create_digest_sync
        from src.models.digest import DigestRequest, DigestType

        now = datetime.now(UTC)
        dtype = DigestType(digest_type)
        start = now - (timedelta(days=1) if dtype == DigestType.DAILY else timedelta(weeks=1))

        request = DigestRequest(
            digest_type=dtype,
            period_start=start,
            period_end=now,
        )
        digest = create_digest_sync(request)
        if digest:
            results["stages"]["digest"] = {
                "title": digest.title,
                "content_count": digest.newsletter_count,
            }
        else:
            results["stages"]["digest"] = {"error": "No content available"}
    except Exception as e:
        results["stages"]["digest"] = {"error": str(e)}

    return _serialize(results)


# ===========================================================================
# THEME ANALYSIS TOOLS
# ===========================================================================


@mcp.tool()
def analyze_themes(
    start_date: str | None = None,
    end_date: str | None = None,
    max_themes: int = 20,
    relevance_threshold: float = 0.3,
    include_historical_context: bool = True,
) -> str:
    """Analyze themes across ingested content.

    Identifies recurring themes, trends, and cross-cutting insights
    from content within the specified date range.

    Args:
        start_date: Analysis start date (ISO). Defaults to 7 days ago.
        end_date: Analysis end date (ISO). Defaults to now.
        max_themes: Maximum themes to return (default: 20).
        relevance_threshold: Minimum relevance score 0-1 (default: 0.3).
        include_historical_context: Include knowledge graph history (default: True).

    Returns:
        JSON with themes, each containing name, category, trend, relevance scores,
        and related content IDs.
    """
    from src.cli.adapters import analyze_themes_sync
    from src.models.theme import ThemeAnalysisRequest

    now = datetime.now(UTC)
    request = ThemeAnalysisRequest(
        start_date=_parse_date(start_date) or (now - timedelta(days=7)),
        end_date=_parse_date(end_date) or now,
        max_themes=max_themes,
        relevance_threshold=relevance_threshold,
    )

    result = analyze_themes_sync(request, include_historical=include_historical_context)
    if result is None:
        return _serialize({"error": "Theme analysis returned no results"})
    return _serialize(result)


# ===========================================================================
# PODCAST TOOLS
# ===========================================================================


@mcp.tool()
def generate_podcast_script(
    digest_id: int,
    length: str = "standard",
) -> str:
    """Generate a podcast script from a digest.

    Creates a two-host conversational podcast script from digest content.

    Args:
        digest_id: ID of the digest to convert to podcast.
        length: Target length: 'brief' (~5min), 'standard' (~15min), or 'extended' (~30min).

    Returns:
        JSON with script metadata including title, word count, duration, and sections.
    """
    from src.cli.adapters import generate_podcast_script_sync
    from src.models.podcast import PodcastLength, PodcastRequest

    request = PodcastRequest(
        digest_id=digest_id,
        length=PodcastLength(length),
    )

    result = generate_podcast_script_sync(request)
    if result is None:
        return _serialize({"error": f"Failed to generate podcast script for digest {digest_id}"})
    return _serialize(result)


# ===========================================================================
# REVIEW TOOLS
# ===========================================================================


@mcp.tool()
def list_pending_reviews() -> str:
    """List digests that are pending human review.

    Returns:
        JSON array of digests awaiting review with id, title, type, and creation date.
    """
    from src.cli.adapters import list_pending_reviews_sync

    results = list_pending_reviews_sync()
    if not results:
        return _serialize({"message": "No pending reviews", "reviews": []})
    return _serialize(results)


@mcp.tool()
def finalize_review(
    digest_id: int,
    action: str,
    reviewer: str = "mcp-agent",
    review_notes: str | None = None,
) -> str:
    """Finalize a digest review with approve, reject, or request revision.

    Args:
        digest_id: ID of the digest to review.
        action: Review action: 'approve', 'reject', or 'request_revision'.
        reviewer: Name of the reviewer (default: 'mcp-agent').
        review_notes: Optional notes explaining the review decision.

    Returns:
        JSON with the updated digest status.
    """
    from src.cli.adapters import finalize_review_sync

    result = finalize_review_sync(
        digest_id=digest_id,
        action=action,
        revision_history=None,
        reviewer=reviewer,
        review_notes=review_notes,
    )
    if result is None:
        return _serialize({"error": f"Digest {digest_id} not found"})
    return _serialize(result)


# ===========================================================================
# SOURCE MANAGEMENT TOOLS
# ===========================================================================


@mcp.tool()
def list_sources() -> str:
    """List all configured content sources.

    Returns all sources from sources.d/ configuration files, grouped by type.

    Returns:
        JSON with sources grouped by type (rss, gmail, youtube_playlist,
        youtube_rss, podcasts, websearch).
    """
    from src.config.sources import load_sources_config

    config = load_sources_config()
    sources: dict[str, list[dict[str, Any]]] = {}

    # Collect sources by type
    source_methods = {
        "gmail": "get_gmail_sources",
        "rss": "get_rss_sources",
        "youtube_playlist": "get_youtube_playlist_sources",
        "youtube_rss": "get_youtube_rss_sources",
        "podcasts": "get_podcast_sources",
        "websearch": "get_websearch_sources",
    }

    for source_type, method_name in source_methods.items():
        method = getattr(config, method_name, None)
        if method:
            try:
                items = method()
                sources[source_type] = [
                    {
                        "name": getattr(s, "name", None),
                        "enabled": getattr(s, "enabled", True),
                        "url": getattr(s, "url", None),
                        "id": getattr(s, "id", None),
                        "tags": getattr(s, "tags", []),
                    }
                    for s in items
                ]
            except Exception:
                sources[source_type] = []

    total = sum(len(v) for v in sources.values())
    return _serialize({"total_sources": total, "sources": sources})


# ===========================================================================
# CONTENT MANAGEMENT TOOLS
# ===========================================================================


@mcp.tool()
def list_content(
    source_types: str | None = None,
    status: str | None = None,
    publication: str | None = None,
    search: str | None = None,
    after_date: str | None = None,
    before_date: str | None = None,
    limit: int = 20,
    sort_by: str = "published_date",
    sort_order: str = "desc",
) -> str:
    """List ingested content items with filtering and sorting.

    Args:
        source_types: Comma-separated source filter (e.g., 'gmail,rss').
        status: Filter by status: 'pending', 'parsed', 'summarized', 'completed'.
        publication: Filter by publication name.
        search: Search filter on title.
        after_date: Filter content after this ISO date.
        before_date: Filter content before this ISO date.
        limit: Maximum results (default: 20).
        sort_by: Sort field: 'published_date', 'ingested_at', 'title', etc.
        sort_order: 'asc' or 'desc' (default: 'desc').

    Returns:
        JSON array of content items with id, title, source, status, and dates.
    """
    from src.models.content import Content, ContentSource, ContentStatus
    from src.storage.database import get_db

    with get_db() as db:
        query = db.query(Content)

        if source_types:
            types = [ContentSource(s.strip()) for s in source_types.split(",")]
            query = query.filter(Content.source_type.in_(types))
        if status:
            query = query.filter(Content.status == ContentStatus(status))
        if publication:
            query = query.filter(Content.publication.ilike(f"%{publication}%"))
        if search:
            query = query.filter(Content.title.ilike(f"%{search}%"))
        if after_date:
            dt = _parse_date(after_date)
            if dt:
                query = query.filter(Content.published_date >= dt)
        if before_date:
            dt = _parse_date(before_date)
            if dt:
                query = query.filter(Content.published_date <= dt)

        # Sorting
        sort_col = getattr(Content, sort_by, Content.published_date)
        query = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())

        items = query.limit(min(limit, 100)).all()

        return _serialize([
            {
                "id": c.id,
                "title": c.title,
                "source_type": str(c.source_type),
                "publication": c.publication,
                "status": str(c.status),
                "published_date": str(c.published_date) if c.published_date else None,
                "ingested_at": str(c.ingested_at) if c.ingested_at else None,
                "source_url": c.source_url,
            }
            for c in items
        ])


@mcp.tool()
def get_content(content_id: int) -> str:
    """Get full content item by ID including markdown content.

    Args:
        content_id: The content item ID.

    Returns:
        JSON with full content details including markdown body.
    """
    from src.models.content import Content
    from src.storage.database import get_db

    with get_db() as db:
        content = db.query(Content).filter(Content.id == content_id).first()
        if not content:
            return _serialize({"error": f"Content {content_id} not found"})

        return _serialize({
            "id": content.id,
            "title": content.title,
            "source_type": str(content.source_type),
            "publication": content.publication,
            "status": str(content.status),
            "published_date": str(content.published_date) if content.published_date else None,
            "source_url": content.source_url,
            "markdown_content": content.markdown_content,
            "summary": content.summary,
            "metadata": content.metadata_json,
        })


# ===========================================================================
# KNOWLEDGE GRAPH TOOLS
# ===========================================================================


@mcp.tool()
def search_knowledge_graph(query: str, limit: int = 10) -> str:
    """Search the knowledge graph for related concepts.

    Queries the Graphiti-powered knowledge graph for entities and relationships
    related to the search query.

    Args:
        query: Search query for concept discovery.
        limit: Maximum results (default: 10).

    Returns:
        JSON with related concepts, entities, and relationships.
    """
    from src.cli.adapters import search_graph_sync

    results = search_graph_sync(query, limit=limit)
    return _serialize(results)


# ===========================================================================
# Entry point
# ===========================================================================


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
