"""Pipeline runner — extracted from CLI for shared API/CLI use.

Orchestrates the 3-stage pipeline: ingest → summarize → digest.
Can be called from the queue worker (via API) or directly from CLI.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from langfuse import observe, propagate_attributes

from src.utils.logging import get_logger

logger = get_logger(__name__)


@observe()
async def _run_ingestion(
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, int]:
    """Run all ingestion sources in parallel.

    Returns dict mapping source name to items ingested count.
    """
    from src.config import settings as app_settings
    from src.config.sources import WebSearchSource, load_sources_config
    from src.ingestion.orchestrator import (
        ingest_arxiv,
        ingest_gmail,
        ingest_perplexity_search,
        ingest_podcast,
        ingest_rss,
        ingest_scholar,
        ingest_substack,
        ingest_xsearch,
        ingest_youtube_playlist,
        ingest_youtube_rss,
    )

    sources: list[tuple[str, Callable[[], int]]] = [
        ("gmail", ingest_gmail),
        ("rss", ingest_rss),
        ("youtube-playlist", ingest_youtube_playlist),
        ("youtube-rss", ingest_youtube_rss),
        ("podcast", ingest_podcast),
        ("substack", ingest_substack),
    ]

    # Load sources configuration
    sources_config = None
    try:
        sources_config = load_sources_config(sources_dir=app_settings.sources_config_dir)
        websearch_sources: list[WebSearchSource] = sources_config.get_websearch_sources()  # type: ignore[assignment]
    except Exception as e:
        logger.warning(f"Failed to load sources config: {e}")
        websearch_sources = []

    for ws in websearch_sources:
        if ws.provider == "perplexity" and app_settings.perplexity_api_key:

            def _make_perplexity(src: WebSearchSource) -> Callable[[], int]:
                def _f() -> int:
                    return ingest_perplexity_search(  # type: ignore[no-any-return]
                        prompt=src.prompt,
                        max_results=src.max_results,
                        recency_filter=src.recency_filter,
                        context_size=src.context_size,
                    )

                return _f

            sources.append((f"websearch:{ws.name or 'perplexity'}", _make_perplexity(ws)))
        elif ws.provider == "grok" and app_settings.xai_api_key:

            def _make_grok(src: WebSearchSource) -> Callable[[], int]:
                def _f() -> int:
                    return ingest_xsearch(prompt=src.prompt, max_threads=src.max_threads)  # type: ignore[no-any-return]

                return _f

            sources.append((f"websearch:{ws.name or 'grok'}", _make_grok(ws)))

    # Add scholar sources from sources.d/scholar.yaml (if configured)
    # NOTE: get_scholar_sources() is added by wp-config; use getattr for forward-compat
    try:
        get_scholar = (
            getattr(sources_config, "get_scholar_sources", None) if sources_config else None
        )
        scholar_sources = get_scholar() if get_scholar else []
    except Exception:
        scholar_sources = []

    if scholar_sources:
        sources.append(("scholar", lambda: ingest_scholar()))

    # Add arXiv sources from sources.d/arxiv.yaml (if configured)
    try:
        get_arxiv = getattr(sources_config, "get_arxiv_sources", None) if sources_config else None
        arxiv_sources = get_arxiv() if get_arxiv else []
    except Exception:
        arxiv_sources = []

    if arxiv_sources:
        sources.append(("arxiv", lambda: ingest_arxiv()))

    if on_progress:
        on_progress({"stage": "ingestion", "message": f"Ingesting from {len(sources)} sources"})

    async def _run_one(name: str, func: Callable[[], int]) -> tuple[str, int | None, str | None]:
        try:
            count = await asyncio.to_thread(func)
            return (name, count, None)
        except Exception as e:
            logger.error(f"Ingestion failed for {name}: {e}")
            return (name, None, str(e))

    raw_results = await asyncio.gather(
        *[_run_one(name, func) for name, func in sources],
        return_exceptions=True,
    )

    results: dict[str, int] = {}
    errors: list[str] = []
    for r in raw_results:
        if isinstance(r, BaseException):
            errors.append(str(r))
        else:
            name, count, err = r
            if err:
                errors.append(f"{name}: {err}")
            else:
                results[name] = count or 0

    if not results and errors:
        raise RuntimeError("All ingestion sources failed: " + "; ".join(errors))

    return results


def _run_summarization() -> int:
    """Summarize all pending content. Returns count of summarized items."""
    from src.processors.summarizer import ContentSummarizer

    summarizer = ContentSummarizer()
    return summarizer.summarize_pending_contents()  # type: ignore[no-any-return]


def _run_digest(
    digest_type: str,
    period_start: datetime,
    period_end: datetime,
) -> dict[str, Any]:
    """Create a digest. Returns result metadata."""
    from src.cli.adapters import create_digest_sync
    from src.models.digest import DigestRequest, DigestType

    dtype = DigestType.DAILY if digest_type == "daily" else DigestType.WEEKLY
    request = DigestRequest(
        digest_type=dtype,
        period_start=period_start,
        period_end=period_end,
    )
    result = create_digest_sync(request)
    return {
        "title": result.title,
        "digest_type": digest_type,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "newsletter_count": result.newsletter_count,
    }


@observe()
async def run_pipeline(
    pipeline_type: str = "daily",
    date: str | None = None,
    sources: list[str] | None = None,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run the full pipeline: ingest → summarize → digest.

    Args:
        pipeline_type: "daily" or "weekly"
        date: Target date as YYYY-MM-DD (default: today/this week)
        sources: Optional list of source names to filter ingestion
        on_progress: Optional callback for progress updates

    Returns:
        Dict with pipeline result metadata including stage results.
    """
    # Parse target date
    if date:
        target = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=UTC)
    else:
        now = datetime.now(UTC)
        target = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if pipeline_type == "weekly":
        # Monday of the target week
        days_since_monday = target.weekday()
        period_start = target - timedelta(days=days_since_monday)
        period_end = period_start + timedelta(days=7)
    else:
        period_start = target
        period_end = target + timedelta(days=1)

    result: dict[str, Any] = {
        "pipeline_type": pipeline_type,
        "date": target.strftime("%Y-%m-%d"),
        "stages": {},
    }

    def _progress(data: dict[str, Any]) -> None:
        if on_progress:
            on_progress(data)

    # Propagate session context to all child observations (Langfuse)
    session_id = f"pipeline-{pipeline_type}-{target.strftime('%Y-%m-%d')}"
    with propagate_attributes(
        session_id=session_id,
        tags=[f"pipeline:{pipeline_type}"],
    ):
        return await _run_pipeline_stages(  # type: ignore[no-any-return]
            pipeline_type=pipeline_type,
            period_start=period_start,
            period_end=period_end,
            result=result,
            on_progress=_progress,
        )


@observe()
async def _run_pipeline_stages(
    *,
    pipeline_type: str,
    period_start: datetime,
    period_end: datetime,
    result: dict[str, Any],
    on_progress: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    """Execute pipeline stages within propagated session context."""
    # Stage 1: Ingestion
    on_progress({"stage": "ingestion", "status": "started"})
    try:
        ingestion_counts = await _run_ingestion(on_progress=on_progress)
        result["stages"]["ingestion"] = {"status": "completed", "counts": ingestion_counts}
        on_progress({"stage": "ingestion", "status": "completed", "counts": ingestion_counts})
    except Exception as e:
        result["stages"]["ingestion"] = {"status": "failed", "error": str(e)}
        on_progress({"stage": "ingestion", "status": "failed", "error": str(e)})
        raise

    # Stage 2: Summarization
    on_progress({"stage": "summarization", "status": "started"})
    try:
        summarized = await asyncio.to_thread(_run_summarization)
        result["stages"]["summarization"] = {"status": "completed", "count": summarized}
        on_progress({"stage": "summarization", "status": "completed", "count": summarized})
    except Exception as e:
        result["stages"]["summarization"] = {"status": "failed", "error": str(e)}
        on_progress({"stage": "summarization", "status": "failed", "error": str(e)})
        raise

    # Stage 3: Digest Creation
    on_progress({"stage": "digest", "status": "started"})
    try:
        digest_info = await asyncio.to_thread(_run_digest, pipeline_type, period_start, period_end)
        result["stages"]["digest"] = {"status": "completed", **digest_info}
        on_progress({"stage": "digest", "status": "completed", **digest_info})
    except Exception as e:
        result["stages"]["digest"] = {"status": "failed", "error": str(e)}
        on_progress({"stage": "digest", "status": "failed", "error": str(e)})
        raise

    return result
