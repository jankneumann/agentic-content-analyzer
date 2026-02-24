"""CLI commands for content ingestion.

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
from typing import Annotated

import typer

from src.cli.output import is_json_mode, output_result

app = typer.Typer(help="Ingest content from various sources.", no_args_is_help=True)


def _days_to_after_date(days: int | None) -> datetime | None:
    """Convert a --days integer to an after_date datetime, or None."""
    if days is None:
        return None
    return datetime.now(UTC) - timedelta(days=days)


# ---------------------------------------------------------------------------
# aca ingest gmail
# ---------------------------------------------------------------------------


@app.command("gmail")
def gmail(
    query: Annotated[
        str,
        typer.Option("--query", "-q", help="Gmail search query."),
    ] = "label:newsletters-ai",
    max: Annotated[
        int,
        typer.Option("--max", "-m", help="Maximum number of emails to fetch."),
    ] = 10,
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
    from rich.console import Console

    console = Console()
    after_date = _days_to_after_date(days)

    try:
        from src.ingestion.orchestrator import ingest_gmail

        count = ingest_gmail(
            query=query,
            max_results=max,
            after_date=after_date,
            force_reprocess=force,
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


# ---------------------------------------------------------------------------
# aca ingest rss
# ---------------------------------------------------------------------------


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
    from rich.console import Console

    from src.ingestion.rss import IngestionResult

    console = Console()
    after_date = _days_to_after_date(days)

    # Capture the full IngestionResult via on_result callback
    # so the CLI can display redirect/failure details.
    captured_result: IngestionResult | None = None

    def _capture_result(r: IngestionResult) -> None:
        nonlocal captured_result
        captured_result = r

    try:
        from src.ingestion.orchestrator import ingest_rss

        count = ingest_rss(
            max_entries_per_feed=max,
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
            # Show redirected sources — user should update their config
            if captured_result.redirected_sources:
                console.print(
                    f"\n[yellow]Warning:[/yellow] {len(captured_result.redirected_sources)} "
                    f"source(s) redirected to new URLs:"
                )
                for r in captured_result.redirected_sources:
                    label = r.name or r.url
                    console.print(f"  [yellow]{label}[/yellow]")
                    console.print(f"    {r.url} -> {r.redirected_to}")

            # Show failed sources — user should investigate or disable
            if captured_result.failed_sources:
                console.print(
                    f"\n[red]Error:[/red] {len(captured_result.failed_sources)} source(s) failed:"
                )
                for r in captured_result.failed_sources:
                    label = r.name or r.url
                    console.print(f"  [red]{label}[/red] ({r.error_type})")
                    console.print(f"    {r.error}")


# ---------------------------------------------------------------------------
# aca ingest substack
# ---------------------------------------------------------------------------


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
    from rich.console import Console

    console = Console()
    after_date = _days_to_after_date(days)

    try:
        from src.ingestion.orchestrator import ingest_substack

        count = ingest_substack(
            max_entries_per_source=max,
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
    """Sync Substack subscriptions: paid → substack.yaml, free → rss.yaml."""
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
            f"  Paid → substack.yaml: {result.substack_added} added, "
            f"{result.substack_existing} existing\n"
            f"  Free → rss.yaml: {result.rss_added} added, "
            f"{result.rss_existing} already present{removed_msg}"
        )


# ---------------------------------------------------------------------------
# aca ingest youtube
# ---------------------------------------------------------------------------


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
    from rich.console import Console

    console = Console()
    after_date = _days_to_after_date(days)
    use_oauth = not public_only

    try:
        from src.ingestion.orchestrator import ingest_youtube_playlist

        total = ingest_youtube_playlist(
            max_videos=max,
            after_date=after_date,
            force_reprocess=force,
            use_oauth=use_oauth,
        )
    except Exception as exc:
        if is_json_mode():
            output_result({"error": str(exc), "source": "youtube-playlist"}, success=False)
        else:
            console.print(f"[red]YouTube playlist ingestion failed:[/red] {exc}")
        raise typer.Exit(1)

    if is_json_mode():
        output_result({"source": "youtube-playlist", "ingested": total})
    else:
        console.print(
            f"[green]YouTube playlist ingestion complete.[/green] {total} item(s) ingested."
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
    from rich.console import Console

    console = Console()
    after_date = _days_to_after_date(days)

    try:
        from src.ingestion.orchestrator import ingest_youtube_rss

        total = ingest_youtube_rss(
            max_videos=max,
            after_date=after_date,
            force_reprocess=force,
        )
    except Exception as exc:
        if is_json_mode():
            output_result({"error": str(exc), "source": "youtube-rss"}, success=False)
        else:
            console.print(f"[red]YouTube RSS ingestion failed:[/red] {exc}")
        raise typer.Exit(1)

    if is_json_mode():
        output_result({"source": "youtube-rss", "ingested": total})
    else:
        console.print(f"[green]YouTube RSS ingestion complete.[/green] {total} item(s) ingested.")


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
    from rich.console import Console

    console = Console()
    after_date = _days_to_after_date(days)
    use_oauth = not public_only

    try:
        from src.ingestion.orchestrator import ingest_youtube

        total = ingest_youtube(
            max_videos=max,
            after_date=after_date,
            force_reprocess=force,
            use_oauth=use_oauth,
        )
    except Exception as exc:
        if is_json_mode():
            output_result({"error": str(exc), "source": "youtube"}, success=False)
        else:
            console.print(f"[red]YouTube ingestion failed:[/red] {exc}")
        raise typer.Exit(1)

    if is_json_mode():
        output_result({"source": "youtube", "ingested": total})
    else:
        console.print(f"[green]YouTube ingestion complete.[/green] {total} item(s) ingested.")


# ---------------------------------------------------------------------------
# aca ingest podcast
# ---------------------------------------------------------------------------


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
    from rich.console import Console

    console = Console()
    after_date = _days_to_after_date(days)

    try:
        # When --no-transcribe is passed, override per-source transcribe setting
        # by providing explicit sources with transcribe toggled off.
        # This requires calling the service directly (orchestrator doesn't
        # handle custom source overrides).
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
                max_entries_per_feed=max,
                after_date=after_date,
                force_reprocess=force,
            )
        else:
            from src.ingestion.orchestrator import ingest_podcast

            count = ingest_podcast(
                max_entries_per_feed=max,
                after_date=after_date,
                force_reprocess=force,
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


# ---------------------------------------------------------------------------
# aca ingest xsearch
# ---------------------------------------------------------------------------


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
    from rich.console import Console

    console = Console()

    try:
        from src.ingestion.orchestrator import ingest_xsearch

        count = ingest_xsearch(
            prompt=prompt,
            max_threads=max_threads,
            force_reprocess=force,
        )
    except Exception as exc:
        if is_json_mode():
            output_result({"error": str(exc), "source": "xsearch"}, success=False)
        else:
            console.print(f"[red]X search ingestion failed:[/red] {exc}")
        raise typer.Exit(1)

    if is_json_mode():
        output_result({"source": "xsearch", "ingested": count})
    else:
        console.print(f"[green]X search ingestion complete.[/green] {count} item(s) ingested.")


# ---------------------------------------------------------------------------
# aca ingest files
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
    """Ingest one or more local files into the content pipeline."""
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

            content = ingest_file_sync(
                file_path=file_path,
                publication=publication,
                title=title,
            )
            results.append(
                {
                    "path": str(file_path),
                    "content_id": content.id,
                    "title": content.title,
                }
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
