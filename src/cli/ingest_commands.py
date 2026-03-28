"""CLI commands for content ingestion.

In HTTP mode (default), commands call the backend API via httpx and stream
SSE progress. In direct mode (--direct flag or API unreachable), commands
call orchestrator functions directly (legacy inline behavior).

Usage:
    aca ingest gmail
    aca ingest rss
    aca ingest substack
    aca ingest substack-sync
    aca ingest youtube
    aca ingest podcast
    aca ingest files <path...>
    aca ingest url <url>
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer

from src.cli.output import is_direct_mode, is_json_mode, output_result

app = typer.Typer(help="Ingest content from various sources.", no_args_is_help=True)


def _days_to_after_date(days: int | None) -> datetime | None:
    """Convert a --days integer to an after_date datetime, or None."""
    if days is None:
        return None
    return datetime.now(UTC) - timedelta(days=days)


# ---------------------------------------------------------------------------
# Shared HTTP ingestion helper
# ---------------------------------------------------------------------------


def _ingest_via_api(source: str, params: dict[str, Any], label: str) -> None:
    """Ingest via the backend API with SSE progress streaming.

    Calls POST /api/v1/contents/ingest, then streams progress until completion.
    Falls back to direct mode on connection error.
    """
    from src.cli.api_client import get_api_client
    from src.cli.progress import display_ingest_result, stream_job_progress

    client = get_api_client()
    try:
        response = client.ingest(source=source, **params)
    except httpx.ConnectError:
        if not is_json_mode():
            from rich.console import Console

            Console(stderr=True).print(
                f"[yellow]Backend unavailable — running {source} ingestion directly...[/yellow]"
            )
        raise  # Let caller handle fallback

    task_id = response.get("task_id", "")
    result = stream_job_progress(
        client, task_id, label=label, stream_type="ingest", json_mode=is_json_mode()
    )
    display_ingest_result(result, source=source, json_mode=is_json_mode())

    # Exit with error if job failed
    if result.get("status") in ("error", "failed"):
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# aca ingest gmail
# ---------------------------------------------------------------------------


def _gmail_direct(query: str, max_results: int, after_date: datetime | None, force: bool) -> None:
    """Direct Gmail ingestion (legacy inline path)."""
    from rich.console import Console

    console = Console()
    try:
        from src.ingestion.orchestrator import ingest_gmail

        count = ingest_gmail(
            query=query, max_results=max_results, after_date=after_date, force_reprocess=force
        )
    except Exception as exc:
        if is_json_mode():
            output_result({"error": str(exc), "source": "gmail"}, success=False)
        else:
            console.print(f"[red]Gmail ingestion failed:[/red] {exc}")
        raise typer.Exit(1)

    if is_json_mode():
        output_result({"source": "gmail", "ingested": count})
    else:
        console.print(f"[green]Gmail ingestion complete.[/green] {count} item(s) ingested.")


@app.command("gmail")
def gmail(
    query: Annotated[
        str,
        typer.Option("--query", "-q", help="Gmail search query."),
    ] = "label:newsletters-ai",
    max: Annotated[
        int | None,
        typer.Option("--max", "-m", help="Maximum number of emails to fetch."),
    ] = None,
    days: Annotated[
        int | None,
        typer.Option("--days", "-d", help="Only fetch emails from the last N days."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force reprocess existing content."),
    ] = False,
) -> None:
    """Ingest newsletters from Gmail."""
    after_date = _days_to_after_date(days)

    if is_direct_mode():
        return _gmail_direct(query, max or 10, after_date, force)

    try:
        params: dict[str, Any] = {"query": query, "force_reprocess": force}
        if max is not None:
            params["max_results"] = max
        if days is not None:
            params["days_back"] = days
        _ingest_via_api("gmail", params, "Gmail ingestion")
    except httpx.ConnectError:
        _gmail_direct(query, max or 10, after_date, force)


# ---------------------------------------------------------------------------
# aca ingest rss
# ---------------------------------------------------------------------------


def _rss_direct(max_results: int, after_date: datetime | None, force: bool) -> None:
    """Direct RSS ingestion (legacy inline path)."""
    from rich.console import Console

    from src.ingestion.rss import IngestionResult

    console = Console()
    captured_result: IngestionResult | None = None

    def _capture_result(r: IngestionResult) -> None:
        nonlocal captured_result
        captured_result = r

    try:
        from src.ingestion.orchestrator import ingest_rss

        count = ingest_rss(
            max_entries_per_feed=max_results,
            after_date=after_date,
            force_reprocess=force,
            on_result=_capture_result,
        )
    except Exception as exc:
        if is_json_mode():
            output_result({"error": str(exc), "source": "rss"}, success=False)
        else:
            console.print(f"[red]RSS ingestion failed:[/red] {exc}")
        raise typer.Exit(1)

    if is_json_mode():
        result_data: dict = {"source": "rss", "ingested": count}
        if captured_result:
            result_data["failed_sources"] = [
                {"url": r.url, "name": r.name, "error": r.error, "error_type": r.error_type}
                for r in captured_result.failed_sources
            ]
            result_data["redirected_sources"] = [
                {"url": r.url, "name": r.name, "redirected_to": r.redirected_to}
                for r in captured_result.redirected_sources
            ]
        output_result(result_data)
    else:
        console.print(f"[green]RSS ingestion complete.[/green] {count} item(s) ingested.")
        if captured_result:
            if captured_result.redirected_sources:
                console.print(
                    f"\n[yellow]Warning:[/yellow] {len(captured_result.redirected_sources)} "
                    f"source(s) redirected to new URLs:"
                )
                for r in captured_result.redirected_sources:
                    label = r.name or r.url
                    console.print(f"  [yellow]{label}[/yellow]")
                    console.print(f"    {r.url} -> {r.redirected_to}")
            if captured_result.failed_sources:
                console.print(
                    f"\n[red]Error:[/red] {len(captured_result.failed_sources)} source(s) failed:"
                )
                for r in captured_result.failed_sources:
                    label = r.name or r.url
                    console.print(f"  [red]{label}[/red] ({r.error_type})")
                    console.print(f"    {r.error}")


@app.command("rss")
def rss(
    max: Annotated[
        int,
        typer.Option("--max", "-m", help="Maximum entries per feed."),
    ] = 10,
    days: Annotated[
        int | None,
        typer.Option("--days", "-d", help="Only fetch entries from the last N days."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force reprocess existing content."),
    ] = False,
) -> None:
    """Ingest articles from configured RSS feeds."""
    after_date = _days_to_after_date(days)

    if is_direct_mode():
        return _rss_direct(max, after_date, force)

    try:
        params: dict[str, Any] = {"max_results": max, "force_reprocess": force}
        if days is not None:
            params["days_back"] = days
        _ingest_via_api("rss", params, "RSS ingestion")
    except httpx.ConnectError:
        _rss_direct(max, after_date, force)


# ---------------------------------------------------------------------------
# aca ingest blog
# ---------------------------------------------------------------------------


def _blog_direct(max_results: int, after_date: datetime | None, force: bool) -> None:
    """Direct blog ingestion."""
    from src.ingestion.orchestrator import ingest_blog

    count = ingest_blog(
        max_entries_per_source=max_results,
        after_date=after_date,
        force_reprocess=force,
    )
    output_result({"source": "blog", "ingested": count})


@app.command("blog")
def blog(
    max: Annotated[
        int,
        typer.Option("--max", "-m", help="Maximum posts per blog source."),
    ] = 10,
    days: Annotated[
        int | None,
        typer.Option("--days", "-d", help="Only fetch posts from the last N days."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force reprocess existing content."),
    ] = False,
) -> None:
    """Ingest posts from configured blog sources."""
    after_date = _days_to_after_date(days)

    if is_direct_mode():
        return _blog_direct(max, after_date, force)

    try:
        params: dict[str, Any] = {"max_results": max, "force_reprocess": force}
        if days is not None:
            params["days_back"] = days
        _ingest_via_api("blog", params, "Blog ingestion")
    except httpx.ConnectError:
        _blog_direct(max, after_date, force)


# ---------------------------------------------------------------------------
# aca ingest substack
# ---------------------------------------------------------------------------


def _substack_direct(
    max_results: int, after_date: datetime | None, force: bool, session_cookie: str | None
) -> None:
    """Direct Substack ingestion."""
    from rich.console import Console

    console = Console()
    try:
        from src.ingestion.orchestrator import ingest_substack

        count = ingest_substack(
            max_entries_per_source=max_results,
            after_date=after_date,
            force_reprocess=force,
            session_cookie=session_cookie,
        )
    except Exception as exc:
        if is_json_mode():
            output_result({"error": str(exc), "source": "substack"}, success=False)
        else:
            console.print(f"[red]Substack ingestion failed:[/red] {exc}")
        raise typer.Exit(1)

    if is_json_mode():
        output_result({"source": "substack", "ingested": count})
    else:
        console.print(f"[green]Substack ingestion complete.[/green] {count} item(s) ingested.")


@app.command("substack")
def substack(
    max: Annotated[
        int,
        typer.Option("--max", "-m", help="Maximum posts per Substack source."),
    ] = 10,
    days: Annotated[
        int | None,
        typer.Option("--days", "-d", help="Only fetch posts from the last N days."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force reprocess existing content."),
    ] = False,
    session_cookie: Annotated[
        str | None,
        typer.Option("--session-cookie", help="Override SUBSTACK_SESSION_COOKIE value."),
    ] = None,
) -> None:
    """Ingest posts from Substack sources configured in sources.d/substack.yaml."""
    after_date = _days_to_after_date(days)

    if is_direct_mode():
        return _substack_direct(max, after_date, force, session_cookie)

    try:
        params: dict[str, Any] = {"max_results": max, "force_reprocess": force}
        if days is not None:
            params["days_back"] = days
        if session_cookie:
            params["session_cookie"] = session_cookie
        _ingest_via_api("substack", params, "Substack ingestion")
    except httpx.ConnectError:
        _substack_direct(max, after_date, force, session_cookie)


# ---------------------------------------------------------------------------
# aca ingest substack-sync (always direct — writes config files)
# ---------------------------------------------------------------------------


@app.command("substack-sync")
def substack_sync(
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Path to write substack.yaml (default: sources.d/substack.yaml).",
        ),
    ] = None,
    session_cookie: Annotated[
        str | None,
        typer.Option("--session-cookie", help="Override SUBSTACK_SESSION_COOKIE value."),
    ] = None,
) -> None:
    """Sync Substack subscriptions: paid -> substack.yaml, free -> rss.yaml.

    Always runs directly (writes local config files, not a job queue operation).
    """
    from rich.console import Console

    console = Console()

    try:
        from src.ingestion.substack import sync_substack_sources

        result = sync_substack_sources(output_path=output, session_cookie=session_cookie)
    except Exception as exc:
        if is_json_mode():
            output_result({"error": str(exc), "source": "substack-sync"}, success=False)
        else:
            console.print(f"[red]Substack sync failed:[/red] {exc}")
        raise typer.Exit(1)

    if is_json_mode():
        output_result(
            {
                "source": "substack-sync",
                "substack_added": result.substack_added,
                "substack_existing": result.substack_existing,
                "rss_added": result.rss_added,
                "rss_existing": result.rss_existing,
                "rss_removed": result.rss_removed,
            }
        )
    else:
        removed_msg = ""
        if result.rss_removed:
            removed_msg = f", {result.rss_removed} removed (now in substack.yaml)"
        console.print(
            f"[green]Substack sync complete.[/green]\n"
            f"  Paid -> substack.yaml: {result.substack_added} added, "
            f"{result.substack_existing} existing\n"
            f"  Free -> rss.yaml: {result.rss_added} added, "
            f"{result.rss_existing} already present{removed_msg}"
        )


# ---------------------------------------------------------------------------
# aca ingest youtube
# ---------------------------------------------------------------------------


def _youtube_direct(
    source_name: str,
    func_name: str,
    max_videos: int,
    after_date: datetime | None,
    force: bool,
    use_oauth: bool = True,
) -> None:
    """Direct YouTube ingestion (shared for all youtube variants)."""
    from rich.console import Console

    console = Console()
    # Human-readable label with proper capitalization
    labels: dict[str, str] = {
        "youtube": "YouTube",
        "youtube-playlist": "YouTube playlist",
        "youtube-rss": "YouTube RSS",
    }
    label = labels.get(source_name, source_name)

    try:
        import importlib

        mod = importlib.import_module("src.ingestion.orchestrator")
        ingest_func = getattr(mod, func_name)

        kwargs: dict[str, Any] = {
            "max_videos": max_videos,
            "after_date": after_date,
            "force_reprocess": force,
        }
        if func_name in ("ingest_youtube", "ingest_youtube_playlist"):
            kwargs["use_oauth"] = use_oauth

        total = ingest_func(**kwargs)
    except Exception as exc:
        if is_json_mode():
            output_result({"error": str(exc), "source": source_name}, success=False)
        else:
            console.print(f"[red]{label} ingestion failed:[/red] {exc}")
        raise typer.Exit(1)

    if is_json_mode():
        output_result({"source": source_name, "ingested": total})
    else:
        console.print(f"[green]{label} ingestion complete.[/green] {total} item(s) ingested.")


@app.command("youtube-playlist")
def youtube_playlist(
    max: Annotated[
        int,
        typer.Option("--max", "-m", help="Maximum videos per playlist/channel."),
    ] = 10,
    days: Annotated[
        int | None,
        typer.Option("--days", "-d", help="Only fetch videos from the last N days."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force reprocess existing content."),
    ] = False,
    public_only: Annotated[
        bool,
        typer.Option("--public-only", help="Skip OAuth, use API key only (public content)."),
    ] = False,
) -> None:
    """Ingest content from YouTube playlists and channels."""
    after_date = _days_to_after_date(days)

    if is_direct_mode():
        return _youtube_direct(
            "youtube-playlist", "ingest_youtube_playlist", max, after_date, force, not public_only
        )

    try:
        params: dict[str, Any] = {"max_results": max, "force_reprocess": force}
        if days is not None:
            params["days_back"] = days
        if public_only:
            params["public_only"] = True
        _ingest_via_api("youtube-playlist", params, "YouTube playlist ingestion")
    except httpx.ConnectError:
        _youtube_direct(
            "youtube-playlist", "ingest_youtube_playlist", max, after_date, force, not public_only
        )


@app.command("youtube-rss")
def youtube_rss(
    max: Annotated[
        int,
        typer.Option("--max", "-m", help="Maximum videos per RSS feed."),
    ] = 10,
    days: Annotated[
        int | None,
        typer.Option("--days", "-d", help="Only fetch videos from the last N days."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force reprocess existing content."),
    ] = False,
) -> None:
    """Ingest content from YouTube RSS feeds."""
    after_date = _days_to_after_date(days)

    if is_direct_mode():
        return _youtube_direct("youtube-rss", "ingest_youtube_rss", max, after_date, force)

    try:
        params: dict[str, Any] = {"max_results": max, "force_reprocess": force}
        if days is not None:
            params["days_back"] = days
        _ingest_via_api("youtube-rss", params, "YouTube RSS ingestion")
    except httpx.ConnectError:
        _youtube_direct("youtube-rss", "ingest_youtube_rss", max, after_date, force)


@app.command("youtube")
def youtube(
    max: Annotated[
        int,
        typer.Option("--max", "-m", help="Maximum videos per playlist/channel/feed."),
    ] = 10,
    days: Annotated[
        int | None,
        typer.Option("--days", "-d", help="Only fetch videos from the last N days."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force reprocess existing content."),
    ] = False,
    public_only: Annotated[
        bool,
        typer.Option("--public-only", help="Skip OAuth, use API key only (public content)."),
    ] = False,
) -> None:
    """Ingest from all YouTube sources (playlists, channels, and RSS feeds)."""
    after_date = _days_to_after_date(days)

    if is_direct_mode():
        return _youtube_direct("youtube", "ingest_youtube", max, after_date, force, not public_only)

    try:
        params: dict[str, Any] = {"max_results": max, "force_reprocess": force}
        if days is not None:
            params["days_back"] = days
        if public_only:
            params["public_only"] = True
        _ingest_via_api("youtube", params, "YouTube ingestion")
    except httpx.ConnectError:
        _youtube_direct("youtube", "ingest_youtube", max, after_date, force, not public_only)


# ---------------------------------------------------------------------------
# aca ingest podcast
# ---------------------------------------------------------------------------


def _podcast_direct(
    max_results: int, after_date: datetime | None, force: bool, transcribe: bool
) -> None:
    """Direct podcast ingestion."""
    from rich.console import Console

    console = Console()
    try:
        if not transcribe:
            from src.config import settings
            from src.ingestion.podcast import PodcastContentIngestionService

            service = PodcastContentIngestionService()
            sources_config = settings.get_sources_config()
            sources = sources_config.get_podcast_sources()
            for source in sources:
                source.transcribe = False
            count = service.ingest_all_feeds(
                sources=sources,
                max_entries_per_feed=max_results,
                after_date=after_date,
                force_reprocess=force,
            )
        else:
            from src.ingestion.orchestrator import ingest_podcast

            count = ingest_podcast(
                max_entries_per_feed=max_results, after_date=after_date, force_reprocess=force
            )
    except Exception as exc:
        if is_json_mode():
            output_result({"error": str(exc), "source": "podcast"}, success=False)
        else:
            console.print(f"[red]Podcast ingestion failed:[/red] {exc}")
        raise typer.Exit(1)

    if is_json_mode():
        output_result({"source": "podcast", "ingested": count})
    else:
        console.print(f"[green]Podcast ingestion complete.[/green] {count} episode(s) ingested.")


@app.command("podcast")
def podcast(
    max: Annotated[
        int,
        typer.Option("--max", "-m", help="Maximum episodes per feed."),
    ] = 10,
    days: Annotated[
        int | None,
        typer.Option("--days", "-d", help="Only fetch episodes from the last N days."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force reprocess existing content."),
    ] = False,
    transcribe: Annotated[
        bool,
        typer.Option(
            "--transcribe/--no-transcribe", help="Enable/disable audio transcription (Tier 3)."
        ),
    ] = True,
) -> None:
    """Ingest episodes from configured podcast feeds."""
    after_date = _days_to_after_date(days)

    if is_direct_mode():
        return _podcast_direct(max, after_date, force, transcribe)

    try:
        params: dict[str, Any] = {"max_results": max, "force_reprocess": force}
        if days is not None:
            params["days_back"] = days
        if not transcribe:
            params["transcribe"] = False
        _ingest_via_api("podcast", params, "Podcast ingestion")
    except httpx.ConnectError:
        _podcast_direct(max, after_date, force, transcribe)


# ---------------------------------------------------------------------------
# aca ingest xsearch
# ---------------------------------------------------------------------------


def _xsearch_direct(prompt: str | None, max_threads: int | None, force: bool) -> None:
    """Direct X search ingestion."""
    from dataclasses import asdict

    from rich.console import Console

    from src.ingestion.xsearch import XSearchResult

    console = Console()
    xsearch_result: XSearchResult | None = None

    def _capture_result(result: XSearchResult) -> None:
        nonlocal xsearch_result
        xsearch_result = result

    try:
        from src.ingestion.orchestrator import ingest_xsearch

        count = ingest_xsearch(
            prompt=prompt, max_threads=max_threads, force_reprocess=force, on_result=_capture_result
        )
    except Exception as exc:
        if is_json_mode():
            output_result({"error": str(exc), "source": "xsearch"}, success=False)
        else:
            console.print(f"[red]X search ingestion failed:[/red] {exc}")
        raise typer.Exit(1)

    if is_json_mode():
        data: dict = {"source": "xsearch", "ingested": count}
        if xsearch_result is not None:
            data.update(asdict(xsearch_result))
        output_result(data)
    else:
        console.print(f"[green]X search ingestion complete.[/green] {count} item(s) ingested.")
        if xsearch_result is not None:
            details = []
            if xsearch_result.threads_found:
                details.append(f"{xsearch_result.threads_found} thread(s) found")
            if xsearch_result.items_skipped:
                details.append(f"{xsearch_result.items_skipped} skipped (duplicates)")
            if xsearch_result.tool_calls_made:
                details.append(f"{xsearch_result.tool_calls_made} Grok tool call(s)")
            if xsearch_result.errors:
                details.append(f"{len(xsearch_result.errors)} error(s)")
            if details:
                console.print(f"  [dim]{' | '.join(details)}[/dim]")


@app.command("xsearch")
def xsearch(
    prompt: Annotated[
        str | None,
        typer.Option("--prompt", "-p", help="Custom search prompt (overrides configured default)."),
    ] = None,
    max_threads: Annotated[
        int | None,
        typer.Option("--max-threads", "-m", help="Maximum threads to ingest."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force reprocess existing content."),
    ] = False,
) -> None:
    """Search X via Grok API and ingest AI-relevant posts/threads."""
    if is_direct_mode():
        return _xsearch_direct(prompt, max_threads, force)

    try:
        params: dict[str, Any] = {"force_reprocess": force}
        if prompt is not None:
            params["prompt"] = prompt
        if max_threads is not None:
            params["max_threads"] = max_threads
        _ingest_via_api("xsearch", params, "X search ingestion")
    except httpx.ConnectError:
        _xsearch_direct(prompt, max_threads, force)


# ---------------------------------------------------------------------------
# aca ingest perplexity-search
# ---------------------------------------------------------------------------


def _perplexity_direct(
    prompt: str | None,
    max_results: int | None,
    force: bool,
    recency: str | None,
    context_size: str | None,
) -> None:
    """Direct Perplexity search ingestion."""
    from dataclasses import asdict

    from rich.console import Console

    from src.ingestion.perplexity_search import PerplexitySearchResult

    console = Console()
    search_result: PerplexitySearchResult | None = None

    def _capture_result(result: PerplexitySearchResult) -> None:
        nonlocal search_result
        search_result = result

    try:
        from src.ingestion.orchestrator import ingest_perplexity_search

        count = ingest_perplexity_search(
            prompt=prompt,
            max_results=max_results,
            force_reprocess=force,
            recency_filter=recency,
            context_size=context_size,
            on_result=_capture_result,
        )
    except Exception as exc:
        if is_json_mode():
            output_result({"error": str(exc), "source": "perplexity"}, success=False)
        else:
            console.print(f"[red]Perplexity search ingestion failed:[/red] {exc}")
        raise typer.Exit(1)

    if is_json_mode():
        data: dict = {"source": "perplexity", "ingested": count}
        if search_result is not None:
            data.update(asdict(search_result))
        output_result(data)
    else:
        console.print(
            f"[green]Perplexity search ingestion complete.[/green] {count} item(s) ingested."
        )
        if search_result is not None:
            details = []
            if search_result.queries_made:
                details.append(f"{search_result.queries_made} query(ies) made")
            if search_result.citations_found:
                details.append(f"{search_result.citations_found} citation(s) found")
            if search_result.items_skipped:
                details.append(f"{search_result.items_skipped} skipped (duplicates)")
            if search_result.errors:
                details.append(f"{len(search_result.errors)} error(s)")
            if details:
                console.print(f"  [dim]{' | '.join(details)}[/dim]")


@app.command("perplexity-search")
def perplexity_search(
    prompt: Annotated[
        str | None,
        typer.Option("--prompt", "-p", help="Custom search prompt (overrides configured default)."),
    ] = None,
    max_results: Annotated[
        int | None,
        typer.Option("--max-results", "-m", help="Maximum results to ingest."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force reprocess existing content."),
    ] = False,
    recency: Annotated[
        str | None,
        typer.Option("--recency", help="Recency filter (hour/day/week/month)."),
    ] = None,
    context_size: Annotated[
        str | None,
        typer.Option("--context-size", help="Search context size (low/medium/high)."),
    ] = None,
) -> None:
    """Search the web via Perplexity Sonar API and ingest AI-relevant articles."""
    if is_direct_mode():
        return _perplexity_direct(prompt, max_results, force, recency, context_size)

    try:
        params: dict[str, Any] = {"force_reprocess": force}
        if prompt is not None:
            params["prompt"] = prompt
        if max_results is not None:
            params["max_results"] = max_results
        if recency is not None:
            params["recency_filter"] = recency
        if context_size is not None:
            params["context_size"] = context_size
        _ingest_via_api("perplexity", params, "Perplexity search ingestion")
    except httpx.ConnectError:
        _perplexity_direct(prompt, max_results, force, recency, context_size)


# ---------------------------------------------------------------------------
# aca ingest files (always direct — requires local file access)
# ---------------------------------------------------------------------------


@app.command("files")
def files(
    paths: Annotated[
        list[Path],
        typer.Argument(help="File path(s) to ingest."),
    ],
    publication: Annotated[
        str | None,
        typer.Option("--publication", "-p", help="Publisher or source name."),
    ] = None,
    title: Annotated[
        str | None,
        typer.Option("--title", "-t", help="Title override (only for single file)."),
    ] = None,
) -> None:
    """Ingest one or more local files into the content pipeline.

    Always runs directly (requires local file system access).
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()

    if title and len(paths) > 1:
        console.print("[yellow]Warning:[/yellow] --title is ignored when ingesting multiple files.")
        title = None

    results: list[dict] = []
    errors: list[dict] = []

    for file_path in paths:
        if not file_path.exists():
            err = {"path": str(file_path), "error": "File not found"}
            errors.append(err)
            if not is_json_mode():
                console.print(f"[red]File not found:[/red] {file_path}")
            continue

        try:
            from src.cli.adapters import ingest_file_sync

            content = ingest_file_sync(file_path=file_path, publication=publication, title=title)
            results.append(
                {"path": str(file_path), "content_id": content.id, "title": content.title}
            )
        except Exception as exc:
            err = {"path": str(file_path), "error": str(exc)}
            errors.append(err)
            if not is_json_mode():
                console.print(f"[red]Failed to ingest {file_path}:[/red] {exc}")

    if is_json_mode():
        output_result(
            {
                "source": "files",
                "ingested": len(results),
                "failed": len(errors),
                "results": results,
                "errors": errors,
            }
        )
    else:
        if results:
            table = Table(title="Ingested Files")
            table.add_column("Path", style="cyan")
            table.add_column("ID", style="green")
            table.add_column("Title")
            for r in results:
                table.add_row(r["path"], str(r["content_id"]), r["title"])
            console.print(table)

        total = len(results)
        failed = len(errors)
        console.print(
            f"[green]File ingestion complete.[/green] {total} file(s) ingested, {failed} failed."
        )

    if errors and not results:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# aca ingest url
# ---------------------------------------------------------------------------


def _url_direct(
    target_url: str, title: str | None, tags: list[str] | None, notes: str | None
) -> None:
    """Direct URL ingestion."""
    from rich.console import Console

    console = Console()
    try:
        from src.ingestion.orchestrator import ingest_url

        result = ingest_url(url=target_url, title=title, tags=tags, notes=notes)
    except Exception as exc:
        if is_json_mode():
            output_result({"error": str(exc), "source": "url"}, success=False)
        else:
            console.print(f"[red]URL ingestion failed:[/red] {exc}")
        raise typer.Exit(1)

    if is_json_mode():
        output_result(
            {
                "source": "url",
                "content_id": result.content_id,
                "status": result.status,
                "duplicate": result.duplicate,
            }
        )
    else:
        if result.duplicate:
            console.print(f"[yellow]URL already exists.[/yellow] Content ID: {result.content_id}")
        else:
            console.print(
                f"[green]URL ingested.[/green] Content ID: {result.content_id} (extraction queued)"
            )


@app.command("url")
def url(
    target_url: Annotated[
        str,
        typer.Argument(help="URL to ingest."),
    ],
    title: Annotated[
        str | None,
        typer.Option("--title", "-t", help="Title override for the content."),
    ] = None,
    tags: Annotated[
        list[str] | None,
        typer.Option("--tag", help="Tag(s) to attach (repeatable)."),
    ] = None,
    notes: Annotated[
        str | None,
        typer.Option("--notes", "-n", help="Notes to attach to the content."),
    ] = None,
) -> None:
    """Ingest a single URL into the content pipeline."""
    if is_direct_mode():
        return _url_direct(target_url, title, tags, notes)

    try:
        params: dict[str, Any] = {"url": target_url}
        if title is not None:
            params["title"] = title
        if tags is not None:
            params["tags"] = tags
        if notes is not None:
            params["notes"] = notes
        _ingest_via_api("url", params, "URL ingestion")
    except httpx.ConnectError:
        _url_direct(target_url, title, tags, notes)


# ---------------------------------------------------------------------------
# aca ingest scholar
# ---------------------------------------------------------------------------


def _scholar_direct(max_entries: int) -> None:
    """Direct scholar ingestion."""
    from rich.console import Console

    console = Console()
    try:
        from src.ingestion.orchestrator import ingest_scholar

        count = ingest_scholar(max_entries=max_entries)
    except Exception as exc:
        if is_json_mode():
            output_result({"error": str(exc), "source": "scholar"}, success=False)
        else:
            console.print(f"[red]Scholar ingestion failed:[/red] {exc}")
        raise typer.Exit(1)

    if is_json_mode():
        output_result({"source": "scholar", "items_ingested": count})
    else:
        console.print(f"[green]Scholar ingestion complete.[/green] {count} paper(s) ingested.")


@app.command("scholar")
def scholar(
    max_entries: Annotated[
        int,
        typer.Option("--max", "-m", help="Maximum papers per source."),
    ] = 20,
) -> None:
    """Ingest academic papers from configured scholar sources."""
    if is_direct_mode():
        return _scholar_direct(max_entries)

    try:
        params: dict[str, Any] = {"max_entries": max_entries}
        _ingest_via_api("scholar", params, "Scholar ingestion")
    except httpx.ConnectError:
        _scholar_direct(max_entries)


# ---------------------------------------------------------------------------
# aca ingest scholar-paper
# ---------------------------------------------------------------------------


def _scholar_paper_direct(identifier: str, with_refs: bool) -> None:
    """Direct scholar paper ingestion."""
    from rich.console import Console

    console = Console()
    try:
        from src.ingestion.orchestrator import ingest_scholar_paper

        count = ingest_scholar_paper(identifier=identifier, with_refs=with_refs)
    except Exception as exc:
        if is_json_mode():
            output_result({"error": str(exc), "source": "scholar-paper"}, success=False)
        else:
            console.print(f"[red]Scholar paper ingestion failed:[/red] {exc}")
        raise typer.Exit(1)

    if is_json_mode():
        output_result(
            {
                "source": "scholar-paper",
                "identifier": identifier,
                "items_ingested": count,
                "with_refs": with_refs,
            }
        )
    else:
        if count > 0:
            msg = f"[green]Paper ingested.[/green] Identifier: {identifier}"
            if with_refs:
                msg += " (with references)"
            console.print(msg)
        else:
            console.print("[yellow]Paper not ingested[/yellow] (already exists or not found).")


@app.command("scholar-paper")
def scholar_paper(
    identifier: Annotated[
        str,
        typer.Argument(help="Paper identifier: DOI, arXiv ID, S2 paper ID, or URL."),
    ],
    with_refs: Annotated[
        bool,
        typer.Option("--with-refs", help="Also ingest referenced papers."),
    ] = False,
) -> None:
    """Ingest a single academic paper by identifier (DOI, arXiv ID, S2 ID, or URL)."""
    if is_direct_mode():
        return _scholar_paper_direct(identifier, with_refs)

    try:
        params: dict[str, Any] = {"identifier": identifier, "with_refs": with_refs}
        _ingest_via_api("scholar-paper", params, "Scholar paper ingestion")
    except httpx.ConnectError:
        _scholar_paper_direct(identifier, with_refs)


# ---------------------------------------------------------------------------
# aca ingest scholar-refs
# ---------------------------------------------------------------------------


def _scholar_refs_direct(
    after: str | None,
    before: str | None,
    source: list[str] | None,
    dry_run: bool,
    limit: int | None,
) -> None:
    """Direct scholar reference extraction."""
    from rich.console import Console

    console = Console()

    after_dt: datetime | None = None
    before_dt: datetime | None = None
    if after:
        after_dt = datetime.strptime(after, "%Y-%m-%d").replace(tzinfo=UTC)
    if before:
        before_dt = datetime.strptime(before, "%Y-%m-%d").replace(tzinfo=UTC)

    try:
        from src.ingestion.orchestrator import ingest_scholar_refs

        count = ingest_scholar_refs(
            after=after_dt,
            before=before_dt,
            source_types=source,
            dry_run=dry_run,
            limit=limit,
        )
    except Exception as exc:
        if is_json_mode():
            output_result({"error": str(exc), "source": "scholar-refs"}, success=False)
        else:
            console.print(f"[red]Scholar reference extraction failed:[/red] {exc}")
        raise typer.Exit(1)

    if is_json_mode():
        output_result(
            {
                "source": "scholar-refs",
                "papers_ingested": count,
                "dry_run": dry_run,
            }
        )
    else:
        if dry_run:
            console.print(f"[yellow]Dry run:[/yellow] {count} paper(s) would be ingested.")
        else:
            console.print(
                f"[green]Reference extraction complete.[/green] {count} paper(s) ingested."
            )


@app.command("scholar-refs")
def scholar_refs(
    after: Annotated[
        str | None,
        typer.Option("--after", help="Only scan content after this date (YYYY-MM-DD)."),
    ] = None,
    before: Annotated[
        str | None,
        typer.Option("--before", help="Only scan content before this date (YYYY-MM-DD)."),
    ] = None,
    source: Annotated[
        list[str] | None,
        typer.Option("--source", "-s", help="Filter by source type (repeatable)."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview without ingesting."),
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option("--limit", "-l", help="Maximum references to ingest."),
    ] = None,
) -> None:
    """Extract and ingest academic paper references from existing content."""
    if is_direct_mode():
        return _scholar_refs_direct(after, before, source, dry_run, limit)

    try:
        params: dict[str, Any] = {"dry_run": dry_run}
        if after is not None:
            params["after"] = after
        if before is not None:
            params["before"] = before
        if source is not None:
            params["source_types"] = source
        if limit is not None:
            params["limit"] = limit
        _ingest_via_api("scholar-refs", params, "Scholar reference extraction")
    except httpx.ConnectError:
        _scholar_refs_direct(after, before, source, dry_run, limit)
