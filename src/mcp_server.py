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
import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP


def _strict_http_mode() -> bool:
    """Whether the MCP server was started with --strict-http semantics."""
    return os.environ.get("ACA_MCP_STRICT_HTTP", "").lower() in ("1", "true", "yes", "on")


def _get_api_client() -> Any | None:
    """Return a shared ApiClient when HTTP mode is configured, else None.

    HTTP mode is enabled when BOTH ``ACA_API_BASE_URL`` and ``ACA_ADMIN_KEY``
    env vars are set. Partial config (only one set) falls back to in-process
    mode and emits a warning to stderr — NOT to the tool response — so the
    MCP JSON-RPC stdout channel stays clean.

    When ``ACA_MCP_STRICT_HTTP`` is set and the config is missing or
    incomplete, this still returns None; the caller is expected to surface
    an error rather than silently proceed to in-process mode.
    """
    base_url = os.environ.get("ACA_API_BASE_URL", "").strip()
    admin_key = os.environ.get("ACA_ADMIN_KEY", "").strip()
    if base_url and admin_key:
        from src.cli.api_client import ApiClient

        return ApiClient(base_url=base_url, admin_key=admin_key)
    if base_url or admin_key:
        missing = "ACA_ADMIN_KEY" if base_url else "ACA_API_BASE_URL"
        print(
            f"aca-mcp: partial HTTP config — {missing} not set; falling back to in-process mode.",
            file=sys.stderr,
        )
    return None


def _strict_http_error(tool: str, reason: str) -> str:
    """Shape a uniform error response when --strict-http rejects a call."""
    return _serialize({"error": "strict_http_unavailable", "tool": tool, "detail": reason})


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
def ingest_arxiv(
    max_results: int = 20,
    days: int | None = None,
    force_reprocess: bool = False,
    no_pdf: bool = False,
) -> str:
    """Ingest papers from configured arXiv sources.

    Searches arXiv for papers matching categories and keywords defined
    in sources.d/arxiv.yaml. Downloads and extracts full PDF text via
    Docling parser. No API key required.

    Args:
        max_results: Maximum papers per source (default 20).
        days: Only ingest papers from the last N days (client-side filter).
        force_reprocess: Force re-ingest existing papers.
        no_pdf: Skip PDF download, use abstract-only content.

    Returns:
        JSON with items_ingested count and source name.
    """
    from datetime import UTC, datetime, timedelta

    from src.ingestion.orchestrator import ingest_arxiv as _ingest

    after_date = None
    if days is not None:
        after_date = datetime.now(UTC) - timedelta(days=days)

    count = _ingest(
        max_results=max_results,
        after_date=after_date,
        force_reprocess=force_reprocess,
        no_pdf=no_pdf,
    )
    return _serialize({"items_ingested": count, "source": "arxiv"})


@mcp.tool()
def ingest_huggingface_papers(
    max_papers: int = 30,
    days: int | None = None,
    force_reprocess: bool = False,
) -> str:
    """Ingest daily papers from HuggingFace Papers (https://huggingface.co/papers).

    Fetches the community-curated daily papers listing, extracts paper
    metadata (title, authors, abstract) and arXiv links. Cross-deduplicates
    with existing arXiv source records.

    Args:
        max_papers: Maximum papers to ingest (default 30).
        days: Only ingest papers from the last N days (client-side filter).
        force_reprocess: Force re-ingest existing papers.

    Returns:
        JSON with items_ingested count and source name.
    """
    from datetime import UTC, datetime, timedelta

    from src.ingestion.orchestrator import ingest_huggingface_papers as _ingest

    after_date = None
    if days is not None:
        after_date = datetime.now(UTC) - timedelta(days=days)

    count = _ingest(
        max_papers=max_papers,
        after_date=after_date,
        force_reprocess=force_reprocess,
    )
    return _serialize({"items_ingested": count, "source": "huggingface_papers"})


@mcp.tool()
def ingest_arxiv_paper(
    identifier: str,
    no_pdf: bool = False,
    force_reprocess: bool = False,
) -> str:
    """Ingest a single arXiv paper by ID, URL, or DOI.

    Accepts arXiv IDs (2301.12345), URLs (https://arxiv.org/abs/...),
    or DOIs (10.48550/arXiv.2301.12345). Downloads and extracts full
    PDF text by default.

    Args:
        identifier: arXiv ID, URL, or DOI.
        no_pdf: Skip PDF download, use abstract-only.
        force_reprocess: Force re-ingest if paper already exists.

    Returns:
        JSON with ingestion result including arxiv_id and status.
    """
    from src.ingestion.orchestrator import ingest_arxiv_paper as _ingest

    count = _ingest(
        identifier=identifier,
        pdf_extraction=not no_pdf,
        force_reprocess=force_reprocess,
    )
    return _serialize(
        {
            "identifier": identifier,
            "items_ingested": count,
            "source": "arxiv-paper",
        }
    )


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
            [ContentSource(s.strip()) for s in source_types.split(",")] if source_types else None
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

    return _serialize(
        {
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
        }
    )


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

        return _serialize(
            [
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
            ]
        )


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

        return _serialize(
            [
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
            ]
        )


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

        return _serialize(
            {
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
            }
        )


# ===========================================================================
# KNOWLEDGE GRAPH TOOLS
# ===========================================================================


@mcp.tool()
def search_knowledge_graph(query: str, limit: int = 10) -> str:
    """Search the knowledge graph (OpenAPI-aligned shape).

    Returns ``{entities: [{id, name, type, score}], relationships:
    [{source_id, target_id, type, score}]}`` per
    ``contracts/openapi/v1.yaml#/components/schemas/GraphQueryResponse``.

    HTTP mode: POST /api/v1/graph/query. In-process fallback adapts the
    existing Graphiti-powered search into the same shape.
    """
    client = _get_api_client()
    if client is not None:
        try:
            return _serialize(client.graph_query(query=query, limit=limit))
        finally:
            client.close()
    if _strict_http_mode():
        return _strict_http_error(
            "search_knowledge_graph",
            "ACA_MCP_STRICT_HTTP is set but ACA_API_BASE_URL/ACA_ADMIN_KEY are missing",
        )

    # In-process path — adapt the existing graph search into the OpenAPI shape.
    from src.cli.adapters import search_graph_sync

    raw = search_graph_sync(query, limit=limit) or []
    entities: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        if "source_node_uuid" in row or "target_node_uuid" in row:
            relationships.append(
                {
                    "source_id": str(row.get("source_node_uuid", "")),
                    "target_id": str(row.get("target_node_uuid", "")),
                    "type": str(row.get("name") or row.get("type") or ""),
                    "score": float(row.get("score", 0.0) or 0.0),
                }
            )
        else:
            entities.append(
                {
                    "id": str(row.get("uuid") or row.get("id") or ""),
                    "name": str(row.get("name", "")),
                    "type": str(row.get("type") or row.get("labels", "Entity") or "Entity"),
                    "score": float(row.get("score", 0.0) or 0.0),
                }
            )
    return _serialize({"entities": entities, "relationships": relationships})


# ===========================================================================
# CONTENT EDITING TOOLS
# ===========================================================================


@mcp.tool()
def update_content(
    content_id: int,
    title: str | None = None,
    markdown_content: str | None = None,
    author: str | None = None,
    publication: str | None = None,
    status: str | None = None,
) -> str:
    """Update a content item's fields.

    Supports partial updates — only specified fields are changed.
    If markdown_content is updated, the content hash is automatically recalculated.

    Args:
        content_id: The content item ID to update.
        title: New title.
        markdown_content: New markdown body.
        author: New author name.
        publication: New publication name.
        status: New status ('pending', 'parsed', 'completed', 'failed').

    Returns:
        JSON with the updated content item.
    """
    from src.models.content import ContentStatus, ContentUpdate
    from src.services.content_service import ContentService
    from src.storage.database import get_db

    update_data: dict[str, Any] = {}
    if title is not None:
        update_data["title"] = title
    if markdown_content is not None:
        update_data["markdown_content"] = markdown_content
    if author is not None:
        update_data["author"] = author
    if publication is not None:
        update_data["publication"] = publication
    if status is not None:
        update_data["status"] = ContentStatus(status)

    if not update_data:
        return _serialize({"error": "No fields to update"})

    data = ContentUpdate(**update_data)

    with get_db() as db:
        service = ContentService(db)
        result = service.update(content_id, data)
        if result is None:
            return _serialize({"error": f"Content {content_id} not found"})
        return _serialize(
            {
                "id": result.id,
                "title": result.title,
                "status": str(result.status),
                "updated_fields": list(update_data.keys()),
            }
        )


@mcp.tool()
def get_summary(content_id: int) -> str:
    """Get the structured summary for a content item.

    Returns the full summary including executive summary, key themes,
    strategic insights, technical details, and actionable items.

    Args:
        content_id: The content item ID whose summary to retrieve.

    Returns:
        JSON with summary fields or error if not found.
    """
    from src.models.summary import Summary
    from src.storage.database import get_db

    with get_db() as db:
        summary = db.query(Summary).filter(Summary.content_id == content_id).first()
        if not summary:
            return _serialize({"error": f"No summary found for content {content_id}"})

        return _serialize(
            {
                "id": summary.id,
                "content_id": summary.content_id,
                "executive_summary": summary.executive_summary,
                "key_themes": summary.key_themes,
                "strategic_insights": summary.strategic_insights,
                "technical_details": summary.technical_details,
                "actionable_items": summary.actionable_items,
                "notable_quotes": summary.notable_quotes,
                "relevant_links": summary.relevant_links,
                "relevance_scores": summary.relevance_scores,
                "markdown_content": summary.markdown_content,
                "model_used": summary.model_used,
                "created_at": str(summary.created_at) if summary.created_at else None,
            }
        )


@mcp.tool()
def update_summary(
    content_id: int,
    executive_summary: str | None = None,
    key_themes: str | None = None,
    strategic_insights: str | None = None,
    technical_details: str | None = None,
    actionable_items: str | None = None,
    markdown_content: str | None = None,
) -> str:
    """Update a content item's summary.

    Supports partial updates. List fields accept JSON-encoded arrays.

    Args:
        content_id: The content item ID whose summary to update.
        executive_summary: New executive summary text.
        key_themes: JSON array of theme strings (e.g., '["RAG", "Fine-tuning"]').
        strategic_insights: JSON array of insight strings.
        technical_details: JSON array of technical detail strings.
        actionable_items: JSON array of action item strings.
        markdown_content: New full markdown representation.

    Returns:
        JSON with the updated summary.
    """
    from src.models.summary import Summary
    from src.storage.database import get_db

    with get_db() as db:
        summary = db.query(Summary).filter(Summary.content_id == content_id).first()
        if not summary:
            return _serialize({"error": f"No summary found for content {content_id}"})

        updated_fields = []
        if executive_summary is not None:
            summary.executive_summary = executive_summary
            updated_fields.append("executive_summary")
        if key_themes is not None:
            summary.key_themes = json.loads(key_themes)
            updated_fields.append("key_themes")
        if strategic_insights is not None:
            summary.strategic_insights = json.loads(strategic_insights)
            updated_fields.append("strategic_insights")
        if technical_details is not None:
            summary.technical_details = json.loads(technical_details)
            updated_fields.append("technical_details")
        if actionable_items is not None:
            summary.actionable_items = json.loads(actionable_items)
            updated_fields.append("actionable_items")
        if markdown_content is not None:
            summary.markdown_content = markdown_content
            updated_fields.append("markdown_content")

        if not updated_fields:
            return _serialize({"error": "No fields to update"})

        db.commit()
        db.refresh(summary)

        return _serialize(
            {
                "id": summary.id,
                "content_id": summary.content_id,
                "updated_fields": updated_fields,
            }
        )


@mcp.tool()
def resummarize_content(
    content_id: int,
    feedback: str | None = None,
) -> str:
    """Re-summarize a content item, optionally with revision feedback.

    If feedback is provided, the existing summary's executive_summary is
    prepended with the feedback as context for the LLM to improve upon.
    Without feedback, generates a fresh summary from the original content.

    Args:
        content_id: The content item ID to re-summarize.
        feedback: Optional natural language feedback for the LLM
                  (e.g., 'Focus more on the RAG architecture details').

    Returns:
        JSON with the new summary metadata.
    """
    from src.models.content import Content, ContentStatus
    from src.models.summary import Summary
    from src.processors.summarizer import ContentSummarizer
    from src.storage.database import get_db

    # If feedback is provided, embed it into content metadata so
    # the summarizer can use it as guidance
    if feedback:
        with get_db() as db:
            content = db.query(Content).filter(Content.id == content_id).first()
            if not content:
                return _serialize({"error": f"Content {content_id} not found"})

            # Store feedback in metadata for the summarizer prompt
            meta = content.metadata_json or {}
            meta["revision_feedback"] = feedback
            content.metadata_json = meta

            # Reset status to allow re-summarization
            content.status = ContentStatus.PARSED
            # Remove existing summary so a fresh one is generated
            db.query(Summary).filter(Summary.content_id == content_id).delete()
            db.commit()

    # Run the summarizer
    summarizer = ContentSummarizer()
    success = summarizer.summarize_content(content_id)

    if not success:
        return _serialize({"error": f"Summarization failed for content {content_id}"})

    # Return the new summary
    with get_db() as db:
        summary = db.query(Summary).filter(Summary.content_id == content_id).first()
        if not summary:
            return _serialize({"error": "Summary not found after re-summarization"})

        return _serialize(
            {
                "id": summary.id,
                "content_id": summary.content_id,
                "executive_summary": summary.executive_summary,
                "key_themes": summary.key_themes,
                "model_used": summary.model_used,
                "created_at": str(summary.created_at) if summary.created_at else None,
                "had_feedback": feedback is not None,
            }
        )


# ===========================================================================
# DIGEST EDITING TOOLS
# ===========================================================================


@mcp.tool()
def get_digest_markdown(digest_id: int) -> str:
    """Get digest as full markdown document.

    Returns the markdown representation of the digest, suitable for
    editing in an external editor and pushing back.

    Args:
        digest_id: The digest ID.

    Returns:
        JSON with markdown_content and section structure.
    """
    from src.models.digest import Digest
    from src.storage.database import get_db

    with get_db() as db:
        digest = db.query(Digest).filter(Digest.id == digest_id).first()
        if not digest:
            return _serialize({"error": f"Digest {digest_id} not found"})

        return _serialize(
            {
                "id": digest.id,
                "title": digest.title,
                "digest_type": str(digest.digest_type),
                "status": str(digest.status),
                "markdown_content": digest.markdown_content,
                "executive_overview": digest.executive_overview,
                "strategic_insights": digest.strategic_insights,
                "technical_developments": digest.technical_developments,
                "emerging_trends": digest.emerging_trends,
                "actionable_recommendations": digest.actionable_recommendations,
                "theme_tags": digest.theme_tags,
                "revision_count": digest.revision_count,
            }
        )


@mcp.tool()
def update_digest(
    digest_id: int,
    title: str | None = None,
    executive_overview: str | None = None,
    markdown_content: str | None = None,
    strategic_insights: str | None = None,
    technical_developments: str | None = None,
    emerging_trends: str | None = None,
    actionable_recommendations: str | None = None,
) -> str:
    """Directly update digest fields.

    Supports partial updates. JSON section fields accept JSON-encoded values.
    Valid sections: title, executive_overview, strategic_insights,
    technical_developments, emerging_trends, actionable_recommendations.

    Args:
        digest_id: The digest ID to update.
        title: New digest title.
        executive_overview: New executive overview text.
        markdown_content: New full markdown content.
        strategic_insights: JSON array of DigestSection objects.
        technical_developments: JSON array of DigestSection objects.
        emerging_trends: JSON array of DigestSection objects.
        actionable_recommendations: JSON dict mapping roles to action lists.

    Returns:
        JSON with the updated digest metadata.
    """
    from src.models.digest import Digest
    from src.storage.database import get_db

    with get_db() as db:
        digest = db.query(Digest).filter(Digest.id == digest_id).first()
        if not digest:
            return _serialize({"error": f"Digest {digest_id} not found"})

        updated_fields = []
        if title is not None:
            digest.title = title
            updated_fields.append("title")
        if executive_overview is not None:
            digest.executive_overview = executive_overview
            updated_fields.append("executive_overview")
        if markdown_content is not None:
            digest.markdown_content = markdown_content
            updated_fields.append("markdown_content")
        if strategic_insights is not None:
            digest.strategic_insights = json.loads(strategic_insights)
            updated_fields.append("strategic_insights")
        if technical_developments is not None:
            digest.technical_developments = json.loads(technical_developments)
            updated_fields.append("technical_developments")
        if emerging_trends is not None:
            digest.emerging_trends = json.loads(emerging_trends)
            updated_fields.append("emerging_trends")
        if actionable_recommendations is not None:
            digest.actionable_recommendations = json.loads(actionable_recommendations)
            updated_fields.append("actionable_recommendations")

        if not updated_fields:
            return _serialize({"error": "No fields to update"})

        digest.revision_count += 1
        db.commit()
        db.refresh(digest)

        return _serialize(
            {
                "id": digest.id,
                "title": digest.title,
                "status": str(digest.status),
                "revision_count": digest.revision_count,
                "updated_fields": updated_fields,
            }
        )


@mcp.tool()
def revise_digest_section(
    digest_id: int,
    section: str,
    feedback: str,
) -> str:
    """AI-assisted revision of a digest section.

    Sends natural language feedback to the LLM, which revises the specified
    section accordingly. This mirrors the interactive revision workflow
    in the review UI.

    Valid sections: title, executive_overview, strategic_insights,
    technical_developments, emerging_trends, actionable_recommendations.

    Args:
        digest_id: The digest ID to revise.
        section: Section name to revise.
        feedback: Natural language feedback describing desired changes
                  (e.g., 'Make this more concise and focus on RAG developments').

    Returns:
        JSON with the revised section content and metadata.
    """
    import asyncio

    from src.services.review_service import ReviewService

    service = ReviewService()

    # Start a revision session
    session_id = f"mcp-{digest_id}-{int(datetime.now(UTC).timestamp())}"

    try:
        context = asyncio.run(service.start_revision_session(digest_id, session_id, "mcp-agent"))
    except Exception as e:
        return _serialize({"error": str(e)})

    # Process the revision turn
    prompt = f"Please revise the '{section}' section. Feedback: {feedback}"
    try:
        result = asyncio.run(service.process_revision_turn(context, prompt, [], session_id))
    except Exception as e:
        return _serialize({"error": f"Revision failed: {e}"})

    # Apply the revision
    if result and result.get("revised_content"):
        try:
            asyncio.run(service.apply_revision(digest_id, section, result["revised_content"]))
        except Exception as e:
            return _serialize({"error": f"Failed to apply revision: {e}"})

    return _serialize(
        {
            "digest_id": digest_id,
            "section": section,
            "status": "revised",
            "revision_result": result,
        }
    )


# ===========================================================================
# PODCAST SCRIPT EDITING TOOLS
# ===========================================================================


@mcp.tool()
def get_podcast_script(script_id: int) -> str:
    """Get a podcast script with review-friendly formatting.

    Returns all sections with dialogue turns, word counts, and metadata.

    Args:
        script_id: The podcast script ID.

    Returns:
        JSON with formatted script sections, dialogue, and metadata.
    """
    from src.services.script_review_service import ScriptReviewService

    service = ScriptReviewService()
    try:
        result = service.get_script_for_review(script_id)
        return _serialize(result)
    except ValueError as e:
        return _serialize({"error": str(e)})


@mcp.tool()
def update_podcast_section(
    script_id: int,
    section_index: int,
    dialogue: str,
) -> str:
    """Directly replace a podcast script section's dialogue.

    Replaces the dialogue turns in a specific section with new content.

    Args:
        script_id: The podcast script ID.
        section_index: Zero-based index of the section to update.
        dialogue: JSON array of DialogueTurn objects, each with:
                  'speaker' ('alex' or 'sam'), 'text', optional 'emphasis'
                  and 'pause_after'.
                  Example: '[{"speaker":"alex","text":"Hello!"},{"speaker":"sam","text":"Hi!"}]'

    Returns:
        JSON with the updated script metadata.
    """
    import asyncio

    from src.models.podcast import DialogueTurn, ScriptRevisionRequest
    from src.services.script_review_service import ScriptReviewService

    turns_data = json.loads(dialogue)
    replacement = [DialogueTurn(**t) for t in turns_data]

    request = ScriptRevisionRequest(
        script_id=script_id,
        section_index=section_index,
        feedback="Direct replacement via MCP",
        replacement_dialogue=replacement,
    )

    service = ScriptReviewService()
    try:
        result = asyncio.run(service.revise_section(request))
        return _serialize(
            {
                "script_id": result.id,
                "status": result.status,
                "revision_count": result.revision_count,
                "section_updated": section_index,
            }
        )
    except Exception as e:
        return _serialize({"error": str(e)})


@mcp.tool()
def revise_podcast_section(
    script_id: int,
    section_index: int,
    feedback: str,
) -> str:
    """AI-assisted revision of a podcast script section.

    Sends natural language feedback to the LLM, which revises the
    section's dialogue accordingly.

    Args:
        script_id: The podcast script ID.
        section_index: Zero-based index of the section to revise.
        feedback: Natural language feedback describing desired changes
                  (e.g., 'Make the intro more engaging and add a hook').

    Returns:
        JSON with the updated script metadata.
    """
    import asyncio

    from src.models.podcast import ScriptRevisionRequest
    from src.services.script_review_service import ScriptReviewService

    request = ScriptRevisionRequest(
        script_id=script_id,
        section_index=section_index,
        feedback=feedback,
    )

    service = ScriptReviewService()
    try:
        result = asyncio.run(service.revise_section(request))
        return _serialize(
            {
                "script_id": result.id,
                "status": result.status,
                "revision_count": result.revision_count,
                "section_revised": section_index,
            }
        )
    except Exception as e:
        return _serialize({"error": str(e)})


@mcp.tool()
def review_podcast_script(
    script_id: int,
    action: str,
    reviewer: str = "mcp-agent",
    section_feedback: str | None = None,
    general_notes: str | None = None,
) -> str:
    """Submit a review for a podcast script.

    Args:
        script_id: The podcast script ID.
        action: Review action: 'approve', 'request_revision', or 'reject'.
        reviewer: Reviewer name (default: 'mcp-agent').
        section_feedback: JSON dict mapping section indices to feedback strings.
                          Example: '{"0": "Make intro shorter", "2": "Add more technical depth"}'
        general_notes: Overall review notes.

    Returns:
        JSON with the updated script status.
    """
    import asyncio

    from src.models.podcast import ScriptReviewAction, ScriptReviewRequest
    from src.services.script_review_service import ScriptReviewService

    feedback_dict: dict[int, str] = {}
    if section_feedback:
        raw = json.loads(section_feedback)
        feedback_dict = {int(k): v for k, v in raw.items()}

    request = ScriptReviewRequest(
        script_id=script_id,
        action=ScriptReviewAction(action),
        reviewer=reviewer,
        section_feedback=feedback_dict,
        general_notes=general_notes,
    )

    service = ScriptReviewService()
    try:
        result = asyncio.run(service.submit_review(request))
        return _serialize(
            {
                "script_id": result.id,
                "status": result.status,
                "revision_count": result.revision_count,
                "reviewed_by": result.reviewed_by,
            }
        )
    except Exception as e:
        return _serialize({"error": str(e)})


# ===========================================================================
# CONTENT REFERENCE TOOLS
# ===========================================================================


@mcp.tool()
def get_content_references(
    content_id: int,
    direction: str = "outgoing",
) -> str:
    """Get references for a content item.

    Retrieves citation and reference relationships for a specific content record.
    Outgoing = what this content cites; incoming = what cites this content.

    Args:
        content_id: Content record ID.
        direction: 'outgoing' (what this cites) or 'incoming' (what cites this).

    Returns:
        JSON with references list, count, and direction.
    """
    from src.models.content_reference import ContentReference, ResolutionStatus
    from src.storage.database import get_db

    with get_db() as db:
        if direction == "incoming":
            refs = (
                db.query(ContentReference)
                .filter(
                    ContentReference.target_content_id == content_id,
                    ContentReference.resolution_status == ResolutionStatus.RESOLVED,
                )
                .all()
            )
        else:
            refs = (
                db.query(ContentReference)
                .filter(ContentReference.source_content_id == content_id)
                .all()
            )

        result = []
        for ref in refs:
            result.append(
                {
                    "id": ref.id,
                    "reference_type": ref.reference_type,
                    "external_id": ref.external_id,
                    "external_id_type": ref.external_id_type,
                    "external_url": ref.external_url,
                    "resolution_status": ref.resolution_status,
                    "target_content_id": ref.target_content_id,
                    "confidence": ref.confidence,
                }
            )

    return _serialize({"references": result, "count": len(result), "direction": direction})


@mcp.tool()
def extract_references(
    after: str | None = None,
    before: str | None = None,
    source: str | None = None,
    dry_run: bool = False,
    batch_size: int = 50,
) -> str:
    """Extract references from existing content (OpenAPI-aligned shape).

    Returns ``{references_extracted, content_processed, has_more,
    next_cursor?, per_content?}`` per
    ``contracts/openapi/v1.yaml#/components/schemas/ReferencesExtractResponse``.
    ``has_more`` is always present; ``next_cursor`` is present only when
    ``has_more=true``; ``per_content`` is an optional enriched array.

    HTTP mode: POST /api/v1/references/extract (accepts ``since``/``until``
    XOR ``content_ids``). In-process fallback mirrors the same shape.
    """
    client = _get_api_client()
    if client is not None:
        try:
            body: dict[str, Any] = {"batch_size": batch_size}
            if after is not None:
                body["since"] = after
            if before is not None:
                body["until"] = before
            # The HTTP endpoint does not accept "source" / "dry_run" filters — those
            # are in-process-only conveniences. If the caller asked for them, fall
            # through to in-process mode below rather than silently discarding.
            if source is None and not dry_run:
                return _serialize(client.references_extract(**body))
        finally:
            client.close()
    if _strict_http_mode():
        return _strict_http_error(
            "extract_references",
            "ACA_MCP_STRICT_HTTP is set but ACA_API_BASE_URL/ACA_ADMIN_KEY are missing (or source/dry_run filter used)",
        )

    # In-process path — shape-match HTTP response.
    from datetime import datetime as dt

    from sqlalchemy import text as sa_text

    from src.models.content import Content
    from src.services.reference_extractor import ReferenceExtractor
    from src.storage.database import get_db

    extractor = ReferenceExtractor()
    total_stored = 0
    total_scanned = 0
    per_content: list[dict[str, int]] = []
    overflow_ingested_at: datetime | None = None

    with get_db() as db:
        query = db.query(Content).order_by(Content.ingested_at.asc())
        if after:
            query = query.filter(Content.ingested_at >= dt.fromisoformat(after))
        if before:
            query = query.filter(Content.ingested_at <= dt.fromisoformat(before))
        if source:
            query = query.filter(Content.source_type.cast(sa_text("text")) == source)

        # Fetch batch_size + 1 to detect has_more cheaply.
        contents = query.limit(batch_size + 1).all()
        has_more = len(contents) > batch_size
        if has_more:
            # IR-004 fix: next_cursor is the FIRST UNPROCESSED row's timestamp
            # (match the HTTP route semantics at
            # src/api/routes/reference_routes.py:121-125). Using the last
            # processed row would re-process that item when the client passes
            # the cursor back as `since`.
            overflow_ingested_at = contents[batch_size].ingested_at
            contents = contents[:batch_size]

        for content in contents:
            refs = extractor.extract_from_content(content, db)
            total_scanned += 1
            per_content.append(
                {"content_id": content.id or 0, "references_found": len(refs) if refs else 0}
            )
            if refs and not dry_run and content.id is not None:
                stored = extractor.store_references(content.id, refs, db)
                total_stored += stored
            elif refs:
                total_stored += len(refs)

    response: dict[str, Any] = {
        "references_extracted": total_stored,
        "content_processed": total_scanned,
        "has_more": has_more,
        "per_content": per_content,
    }
    if has_more and overflow_ingested_at is not None:
        response["next_cursor"] = overflow_ingested_at.isoformat()
    return _serialize(response)


@mcp.tool()
def resolve_references(
    batch_size: int = 100,
) -> str:
    """Resolve unresolved content references (OpenAPI-aligned shape).

    Returns ``{resolved_count, still_unresolved_count, has_more}`` per
    ``contracts/openapi/v1.yaml#/components/schemas/ReferencesResolveResponse``.

    HTTP mode: POST /api/v1/references/resolve. In-process fallback mirrors
    the same shape, counting remaining unresolved rows post-batch.
    """
    client = _get_api_client()
    if client is not None:
        try:
            return _serialize(client.references_resolve(batch_size=batch_size))
        finally:
            client.close()
    if _strict_http_mode():
        return _strict_http_error(
            "resolve_references",
            "ACA_MCP_STRICT_HTTP is set but ACA_API_BASE_URL/ACA_ADMIN_KEY are missing",
        )

    # In-process path.
    from src.models.content_reference import ContentReference
    from src.services.reference_resolver import ReferenceResolver
    from src.storage.database import get_db

    with get_db() as db:
        resolver = ReferenceResolver(db)
        resolved = resolver.resolve_batch(batch_size)
        still_unresolved = (
            db.query(ContentReference)
            .filter(ContentReference.resolution_status == "unresolved")
            .count()
        )
    return _serialize(
        {
            "resolved_count": int(resolved),
            "still_unresolved_count": int(still_unresolved),
            "has_more": still_unresolved > 0,
        }
    )


@mcp.tool()
def ingest_reference(
    reference_id: int,
) -> str:
    """Ingest content for a specific unresolved reference (ad-hoc).

    Operates independently of reference_auto_ingest_enabled setting --
    requires explicit invocation per reference. The setting gates only
    unattended background auto-ingestion, not deliberate per-reference requests.

    Args:
        reference_id: content_references row ID.

    Returns:
        JSON with ingestion result and resolution status.
    """
    import asyncio

    from src.config.settings import get_settings
    from src.models.content_reference import ContentReference, ResolutionStatus
    from src.services.reference_auto_ingest import AutoIngestTrigger
    from src.storage.database import get_db

    with get_db() as db:
        ref = db.get(ContentReference, reference_id)
        if not ref:
            return _serialize({"error": f"Reference {reference_id} not found"})

        if ref.resolution_status == ResolutionStatus.RESOLVED:
            return _serialize(
                {
                    "status": "already_resolved",
                    "target_content_id": ref.target_content_id,
                }
            )

        if not ref.external_id or not ref.external_id_type:
            return _serialize({"error": "Reference has no structured ID for ingestion"})

        settings = get_settings()
        trigger = AutoIngestTrigger(
            db=db,
            enabled=True,  # Always enabled for ad-hoc (independent of setting)
            max_depth=settings.reference_auto_ingest_max_depth,
        )

        try:
            content = asyncio.run(trigger.maybe_ingest(ref))
        except RuntimeError:
            # Already in async context
            loop = asyncio.get_event_loop()
            content = loop.run_until_complete(trigger.maybe_ingest(ref))

        if content:
            return _serialize(
                {
                    "status": "ingested",
                    "content_id": content.id if hasattr(content, "id") else None,
                }
            )
        else:
            return _serialize({"status": "ingestion_failed"})


# ===========================================================================
# MODEL REGISTRY TOOLS
# ===========================================================================


@mcp.tool()
def list_models(family: str | None = None) -> str:
    """List all models in the registry with capabilities and pricing.

    Returns model ID, name, family, capability flags, available providers,
    and default pricing for each model.

    Args:
        family: Optional filter by model family (e.g., "claude", "gemini", "gpt").

    Returns:
        JSON array of model summaries.
    """
    from src.services.model_registry_service import ModelRegistryService

    service = ModelRegistryService()
    models = service.list_models(family=family)
    return _serialize([m.model_dump() for m in models])


@mcp.tool()
def get_model_pricing(model_id: str) -> str:
    """Get detailed pricing for a specific model across all providers.

    Returns the model's capabilities and a pricing breakdown showing
    cost per million tokens, context window, and max output for each provider.

    Args:
        model_id: Family-based model ID (e.g., "claude-sonnet-4-5", "gemini-2.5-flash").

    Returns:
        JSON with model details and per-provider pricing, or error if not found.
    """
    from src.services.model_registry_service import ModelRegistryService

    service = ModelRegistryService()
    detail = service.get_model(model_id)
    if not detail:
        return _serialize({"error": f"Model not found: {model_id}"})
    return _serialize(detail.model_dump())


@mcp.tool()
def refresh_model_pricing(
    providers: str | None = None,
    dry_run: bool = True,
) -> str:
    """Extract latest pricing from provider pages and compare with the registry.

    Fetches pricing pages from Anthropic, OpenAI, Google AI, and/or AWS Bedrock,
    uses LLM-based extraction to parse pricing tables, and diffs against the
    current settings/models.yaml.

    Args:
        providers: Comma-separated provider names to check (e.g., "anthropic,openai").
                   None = check all configured providers.
        dry_run: If True (default), only report differences without modifying files.
                 Set to False to apply changes to models.yaml.

    Returns:
        JSON report with diffs, new models found, and any errors.
    """
    import asyncio

    from src.services.model_registry_service import ModelRegistryService

    service = ModelRegistryService()
    provider_list = [p.strip() for p in providers.split(",")] if providers else None
    report = asyncio.run(service.refresh_pricing(providers=provider_list, dry_run=dry_run))
    return _serialize(report.model_dump())


# ===========================================================================
# Auth middleware for HTTP transports
# ===========================================================================


class AdminKeyAuthMiddleware:
    """ASGI middleware that enforces X-Admin-Key authentication.

    Reuses the project's existing ADMIN_API_KEY setting for consistency
    with the REST API auth model. Skips auth in development mode when
    no keys are configured (same behavior as AuthMiddleware).
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        from src.config import get_settings

        settings = get_settings()

        # Dev mode without keys configured: allow all (matches REST API behavior)
        keys_configured = settings.app_secret_key or settings.admin_api_key
        if settings.is_development and not keys_configured:
            await self.app(scope, receive, send)
            return

        # Extract headers
        headers = dict(scope.get("headers", []))
        admin_key = headers.get(b"x-admin-key", b"").decode()

        # Check X-Admin-Key
        if admin_key and settings.admin_api_key:
            import secrets as _secrets

            if _secrets.compare_digest(admin_key, settings.admin_api_key):
                await self.app(scope, receive, send)
                return

        # Check session cookie (JWT)
        if settings.app_secret_key:
            cookie_header = headers.get(b"cookie", b"").decode()
            session_token = _extract_cookie(cookie_header, "session")
            if session_token:
                payload = _verify_jwt_token(session_token, settings.app_secret_key)
                if payload is not None:
                    await self.app(scope, receive, send)
                    return

        # Reject
        if scope["type"] == "http":
            response_body = json.dumps(
                {"error": "Authentication required. Provide X-Admin-Key header."}
            ).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        [b"content-type", b"application/json"],
                        [b"content-length", str(len(response_body)).encode()],
                    ],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": response_body,
                }
            )
        else:
            # WebSocket: close with 4401
            await send({"type": "websocket.close", "code": 4401})


def _extract_cookie(cookie_header: str, name: str) -> str | None:
    """Extract a cookie value from a Cookie header string."""
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith(f"{name}="):
            return part[len(name) + 1 :]
    return None


def _verify_jwt_token(token: str, app_secret_key: str) -> dict | None:
    """Verify a JWT session token using the same logic as auth_routes."""
    try:
        import hmac

        import jwt

        signing_key = hmac.new(app_secret_key.encode(), b"jwt-signing-key", "sha256").digest()
        return jwt.decode(
            token,
            signing_key,
            algorithms=["HS256"],
            issuer="newsletter-aggregator",
        )
    except Exception:
        return None


# ===========================================================================
# OBSIDIAN SYNC TOOLS
# ===========================================================================


@mcp.tool()
def sync_obsidian(
    vault_path: str,
    since: str | None = None,
    include_entities: bool = True,
    include_themes: bool = True,
    clean: bool = False,
    max_entities: int = 10000,
) -> str:
    """Export knowledge base to an Obsidian-compatible markdown vault.

    Creates markdown files with YAML frontmatter, wikilinks, and theme
    Maps of Content. Uses incremental sync to only write new or changed items.

    Args:
        vault_path: Path to the Obsidian vault directory.
        since: Only export content after this ISO date (e.g., '2026-03-01').
        include_entities: Include Neo4j entity export (default: True).
        include_themes: Include theme MOC generation (default: True).
        clean: Remove stale managed files no longer in the database.
        max_entities: Maximum entities to export from Neo4j (default: 10000).

    Returns:
        JSON with counts per content type (created/updated/skipped).
    """
    from src.sync.obsidian_exporter import ExportOptions, ObsidianExporter, validate_vault_path

    try:
        resolved_path = validate_vault_path(vault_path)
    except ValueError as e:
        return _serialize({"error": str(e)})

    since_dt = _parse_date(since)

    options = ExportOptions(
        since=since_dt,
        include_entities=include_entities,
        include_themes=include_themes,
        clean=clean,
        max_entities=max_entities,
    )

    from src.config.settings import get_settings

    settings = get_settings()

    from sqlalchemy import create_engine

    engine = create_engine(settings.get_effective_database_url())

    neo4j_driver = None
    if include_entities:
        try:
            from neo4j import GraphDatabase

            uri = settings.get_effective_neo4j_uri()
            user = settings.get_effective_neo4j_user()
            password = settings.get_effective_neo4j_password()
            neo4j_driver = GraphDatabase.driver(uri, auth=(user, password))
        except Exception:
            options.include_entities = False

    try:
        exporter = ObsidianExporter(
            engine=engine,
            vault_path=resolved_path,
            neo4j_driver=neo4j_driver,
            options=options,
        )
        summary = exporter.export_all()
        return _serialize(summary.to_dict())
    except Exception as e:
        return _serialize({"error": str(e)})
    finally:
        engine.dispose()
        if neo4j_driver:
            neo4j_driver.close()


# ===========================================================================
# KNOWLEDGE BASE TOOLS
# ===========================================================================


@mcp.tool()
def search_knowledge_base(query: str, limit: int = 10) -> str:
    """Search compiled KB topics (OpenAPI-aligned shape).

    Returns ``{topics: [{slug, title, score, excerpt, last_compiled_at}], total_count}``
    per ``contracts/openapi/v1.yaml#/components/schemas/KBSearchResponse``.

    In HTTP mode (ACA_API_BASE_URL + ACA_ADMIN_KEY set), calls GET
    /api/v1/kb/search. Otherwise falls back to an in-process query that
    emits the same shape.
    """
    client = _get_api_client()
    if client is not None:
        try:
            return _serialize(client.kb_search(query=query, limit=limit))
        finally:
            client.close()
    if _strict_http_mode():
        return _strict_http_error(
            "search_knowledge_base",
            "ACA_MCP_STRICT_HTTP is set but ACA_API_BASE_URL/ACA_ADMIN_KEY are missing",
        )

    # In-process path — mirror the HTTP route's ranking + filtering exactly.
    # IR-006 fix: HTTP and in-process MUST emit the same shape for the same data.
    # - total_count is the FULL ranked match count (may exceed limit)
    # - last_compiled_at is required; topics whose last_compiled_at AND
    #   updated_at AND created_at are all null are DROPPED (not fabricated)
    # - excerpt/score derived the same way as the HTTP handler
    from src.api.routes.kb_search_routes import (
        _extract_excerpt,
        _resolve_last_compiled_at,
        _score_topic,
    )
    from src.models.topic import Topic, TopicStatus
    from src.storage.database import get_db

    needle = query.strip()
    needle_like = f"%{needle}%"
    with get_db() as db:
        candidates = (
            db.query(Topic)
            .filter(Topic.status.notin_([TopicStatus.ARCHIVED, TopicStatus.MERGED]))
            .filter(
                (Topic.name.ilike(needle_like))
                | (Topic.slug.ilike(needle_like))
                | (Topic.summary.ilike(needle_like))
                | (Topic.article_md.ilike(needle_like)),
            )
            .all()
        )
        ranked: list[tuple[float, Any]] = []
        for topic in candidates:
            score = _score_topic(topic, needle)
            if score <= 0.0:
                continue
            ranked.append((score, topic))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        total = len(ranked)

        topics: list[dict[str, Any]] = []
        for score, topic in ranked[:limit]:
            last_compiled = _resolve_last_compiled_at(topic)
            if last_compiled is None:
                continue  # match HTTP: skip rows missing all timestamp fallbacks
            topics.append(
                {
                    "slug": topic.slug,
                    "title": topic.name,
                    "score": round(score, 6),
                    "excerpt": _extract_excerpt(topic, needle),
                    "last_compiled_at": last_compiled.isoformat()
                    if hasattr(last_compiled, "isoformat")
                    else str(last_compiled),
                }
            )
        return _serialize({"topics": topics, "total_count": total})


@mcp.tool()
def get_topic(slug: str) -> str:
    """Get full topic details including the compiled article.

    Args:
        slug: The topic slug.

    Returns:
        JSON with topic metadata and the compiled article markdown.
    """
    from src.models.topic import Topic
    from src.storage.database import get_db

    with get_db() as db:
        topic = db.query(Topic).filter_by(slug=slug).first()
        if topic is None:
            return _serialize({"error": f"Topic not found: {slug}"})
        return _serialize(
            {
                "id": topic.id,
                "slug": topic.slug,
                "name": topic.name,
                "category": topic.category,
                "status": str(topic.status) if topic.status is not None else None,
                "summary": topic.summary,
                "article_md": topic.article_md,
                "article_version": topic.article_version,
                "trend": topic.trend,
                "relevance_score": float(topic.relevance_score or 0.0),
                "mention_count": int(topic.mention_count or 0),
                "source_content_ids": list(topic.source_content_ids or []),
                "related_topic_ids": list(topic.related_topic_ids or []),
                "last_compiled_at": str(topic.last_compiled_at) if topic.last_compiled_at else None,
            }
        )


@mcp.tool()
def update_topic(
    slug: str,
    summary: str | None = None,
    article_md: str | None = None,
) -> str:
    """Update a topic's summary and/or article markdown.

    Updating ``article_md`` increments the topic's ``article_version``.

    Args:
        slug: The topic slug.
        summary: Optional new 1-2 sentence summary.
        article_md: Optional new full article markdown.

    Returns:
        JSON with the updated topic or an error.
    """
    from src.models.topic import Topic
    from src.storage.database import get_db

    with get_db() as db:
        topic = db.query(Topic).filter_by(slug=slug).first()
        if topic is None:
            return _serialize({"error": f"Topic not found: {slug}"})
        if summary is not None:
            topic.summary = summary
        if article_md is not None:
            topic.article_md = article_md
            topic.article_version = (topic.article_version or 0) + 1
        db.commit()
        db.refresh(topic)
        return _serialize(
            {
                "slug": topic.slug,
                "name": topic.name,
                "article_version": topic.article_version,
                "summary": topic.summary,
                "article_md": topic.article_md,
            }
        )


@mcp.tool()
def add_topic_note(
    slug: str,
    content: str,
    note_type: str = "observation",
    author: str = "agent",
) -> str:
    """Attach a note to a topic.

    Args:
        slug: The topic slug.
        content: Note body.
        note_type: 'observation' (default), 'question', 'correction', or 'insight'.
        author: Who created the note (default: 'agent').

    Returns:
        JSON with the created note.
    """
    from src.services.knowledge_base import KnowledgeBaseService
    from src.storage.database import get_db

    with get_db() as db:
        service = KnowledgeBaseService(db)
        try:
            note = service.add_note(
                topic_slug=slug,
                content=content,
                note_type=note_type,
                author=author,
            )
        except ValueError as exc:
            return _serialize({"error": str(exc)})
        return _serialize(
            {
                "id": note.id,
                "topic_id": note.topic_id,
                "note_type": str(note.note_type) if note.note_type is not None else None,
                "content": note.content,
                "author": note.author,
                "created_at": str(note.created_at) if note.created_at else None,
            }
        )


@mcp.tool()
def get_kb_index(index_type: str = "master") -> str:
    """Return a cached KB index as markdown.

    Args:
        index_type: 'master' (default), 'recency', 'category_<name>', or 'trend_<name>'.

    Returns:
        JSON with ``index_type``, ``content``, and ``generated_at``.
    """
    from src.models.topic import KBIndex
    from src.storage.database import get_db

    with get_db() as db:
        row = db.query(KBIndex).filter_by(index_type=index_type).first()
        if row is None:
            return _serialize(
                {
                    "index_type": index_type,
                    "content": "",
                    "generated_at": None,
                }
            )
        return _serialize(
            {
                "index_type": row.index_type,
                "content": row.content,
                "generated_at": str(row.generated_at) if row.generated_at else None,
            }
        )


@mcp.tool()
def compile_knowledge_base() -> str:
    """Run an incremental KB compilation.

    Returns:
        JSON with the compile summary (topics found/compiled/skipped/failed).
    """
    import asyncio

    from src.services.knowledge_base import (
        KBCompileLockError,
        KnowledgeBaseService,
    )
    from src.storage.database import get_db

    async def _run() -> dict:
        with get_db() as db:
            service = KnowledgeBaseService(db)
            try:
                summary = await service.compile()
            except KBCompileLockError as exc:
                return {"error": str(exc)}
            return summary.to_dict()

    try:
        result = asyncio.run(_run())
    except RuntimeError as exc:
        # Called from an already-running loop (e.g., SSE transport)
        return _serialize({"error": f"KB compile requires a fresh loop: {exc}"})
    return _serialize(result)


# ===========================================================================
# Entry point
# ===========================================================================


def _validate_strict_http_config_or_exit() -> None:
    """Enforce --strict-http / ACA_MCP_STRICT_HTTP at startup.

    Per specs/mcp-http-client/spec.md §"Strict HTTP mode rejects unconfigured
    tools": if strict mode is on, the server MUST log an error to stderr at
    startup when ACA_API_BASE_URL/ACA_ADMIN_KEY are incomplete, and subsequent
    tool invocations MUST return an error rather than silently fall back
    in-process. This function emits the stderr error and exits with code 2;
    the per-tool strict error payload is still produced if the operator
    somehow bypasses this check.
    """
    if not _strict_http_mode():
        return
    base_url = os.environ.get("ACA_API_BASE_URL", "").strip()
    admin_key = os.environ.get("ACA_ADMIN_KEY", "").strip()
    if base_url and admin_key:
        return
    missing = []
    if not base_url:
        missing.append("ACA_API_BASE_URL")
    if not admin_key:
        missing.append("ACA_ADMIN_KEY")
    print(
        "aca-mcp: --strict-http is enabled but required HTTP config is missing: "
        f"{', '.join(missing)}. Refusing to start — either supply the missing env "
        "vars or disable ACA_MCP_STRICT_HTTP.",
        file=sys.stderr,
    )
    sys.exit(2)


def main() -> None:
    """Run the MCP server.

    Supports three transports:
        stdio (default):  For Claude Desktop, Cursor, etc.
        sse:              For remote/web clients with auth
        streamable-http:  For newer MCP clients with auth

    CLI flags:
        --strict-http:  Refuse to fall back to in-process mode on any of the
                        refactored KB/graph/references tools. If HTTP config
                        (ACA_API_BASE_URL + ACA_ADMIN_KEY) is incomplete, the
                        server logs an error to stderr and exits 2. Can also
                        be enabled via the ACA_MCP_STRICT_HTTP env var.

    Environment variables:
        MCP_TRANSPORT:        Transport type (stdio, sse, streamable-http)
        MCP_PORT:             Port for HTTP transports (default: 8100)
        MCP_HOST:             Host for HTTP transports (default: 0.0.0.0)
        ADMIN_API_KEY:        Required for HTTP transports (auth via X-Admin-Key header)
        ACA_API_BASE_URL:     Required in strict-http mode for KB/graph/refs tools
        ACA_ADMIN_KEY:        Required in strict-http mode for KB/graph/refs tools
        ACA_MCP_STRICT_HTTP:  Equivalent to --strict-http.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="aca-mcp", add_help=True)
    parser.add_argument(
        "--strict-http",
        action="store_true",
        help="Refuse in-process fallback; require ACA_API_BASE_URL and ACA_ADMIN_KEY.",
    )
    args, _ = parser.parse_known_args()
    if args.strict_http:
        os.environ["ACA_MCP_STRICT_HTTP"] = "1"
    _validate_strict_http_config_or_exit()

    transport = os.environ.get("MCP_TRANSPORT", "stdio")

    if transport == "stdio":
        mcp.run()
        return

    import uvicorn

    host = os.environ.get("MCP_HOST", "0.0.0.0")  # noqa: S104
    port = int(os.environ.get("MCP_PORT", "8100"))

    if transport == "sse":
        starlette_app = mcp.sse_app()
    elif transport == "streamable-http":
        starlette_app = mcp.streamable_http_app()
    else:
        raise ValueError(f"Unknown transport: {transport}. Use stdio, sse, or streamable-http.")

    # Wrap with auth middleware for HTTP transports
    starlette_app.add_middleware(AdminKeyAuthMiddleware)

    uvicorn.run(starlette_app, host=host, port=port)


if __name__ == "__main__":
    main()
