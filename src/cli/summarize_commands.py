"""CLI commands for content summarization.

In HTTP mode (default), commands call the backend API and stream SSE progress.
In direct mode (--direct flag, --sync flag, or API unreachable), commands call
services directly.

Usage:
    aca summarize pending --limit N
    aca summarize pending --source youtube,rss --after 2026-02-20 --dry-run
    aca summarize id <content-id>
    aca summarize list --limit N
"""

from __future__ import annotations

from typing import Annotated, Any

import httpx
import typer
from rich.console import Console
from rich.table import Table

from src.cli.output import is_direct_mode, is_json_mode, output_result

app = typer.Typer(help="Summarize ingested content.")

console = Console()


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------


def _summarize_via_api(params: dict[str, Any], label: str) -> None:
    """Call summarize via HTTP API with SSE progress tracking."""
    from src.cli.api_client import get_api_client
    from src.cli.progress import stream_job_progress

    client = get_api_client()
    response = client.summarize(**params)
    task_id = response.get("task_id", "")

    if not task_id:
        # Dry-run or immediate response without task_id
        if is_json_mode():
            output_result(response)
        else:
            queued = response.get("queued_count", 0)
            console.print(f"[green]Enqueued {queued} summarization job(s).[/green]")
        return

    result = stream_job_progress(
        client, task_id, label=label, stream_type="summarize", json_mode=is_json_mode()
    )

    if is_json_mode():
        output_result(result)
    else:
        status = result.get("status", "unknown")
        if status in ("completed", "complete"):
            processed = result.get("processed", result.get("queued_count", 0))
            console.print(f"[green]Summarized {processed} content item(s).[/green]")
        else:
            msg = result.get("message", "Unknown error")
            console.print(f"[red]Summarization failed: {msg}[/red]", style="bold")

    if result.get("status") in ("error", "failed"):
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# aca summarize pending
# ---------------------------------------------------------------------------


@app.command("pending")
def summarize_pending(
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum number of pending items to summarize (default: all).",
        ),
    ] = None,
    sync: Annotated[
        bool,
        typer.Option(
            "--sync",
            help="Run synchronously instead of enqueuing to job queue.",
        ),
    ] = False,
    source: Annotated[
        str | None,
        typer.Option(
            "--source",
            "-s",
            help="Comma-separated source types (gmail,rss,youtube,...)",
        ),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option(
            "--status",
            help="Comma-separated statuses (pending,parsed,...)",
        ),
    ] = None,
    after: Annotated[
        str | None,
        typer.Option(
            "--after",
            help="Content published after this date (YYYY-MM-DD)",
        ),
    ] = None,
    before: Annotated[
        str | None,
        typer.Option(
            "--before",
            help="Content published before this date (YYYY-MM-DD)",
        ),
    ] = None,
    publication: Annotated[
        str | None,
        typer.Option(
            "--publication",
            "-p",
            help="Filter by publication name",
        ),
    ] = None,
    search: Annotated[
        str | None,
        typer.Option(
            "--search",
            "-q",
            help="Search in title",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview matching content without executing",
        ),
    ] = False,
) -> None:
    """Summarize all pending content items.

    By default, calls the API to enqueue summarization jobs. Falls back to
    direct mode if the API is unreachable. Use --sync for sequential
    in-process summarization (always direct mode).

    Filter options (--source, --status, --after, --before, --publication, --search)
    narrow which content items are selected. Use --dry-run to preview without executing.
    """
    # --sync always runs direct (API doesn't support sync mode)
    if sync or is_direct_mode():
        return _summarize_pending_direct(
            limit=limit,
            sync=sync,
            source=source,
            status=status,
            after=after,
            before=before,
            publication=publication,
            search=search,
            dry_run=dry_run,
        )

    try:
        params: dict[str, Any] = {}
        if dry_run:
            params["dry_run"] = True
        has_filters = any([source, status, after, before, publication, search])
        if has_filters or limit:
            query_dict: dict[str, Any] = {}
            if source:
                query_dict["source_types"] = source.split(",")
            if status:
                query_dict["statuses"] = status.split(",")
            if after:
                query_dict["after"] = after
            if before:
                query_dict["before"] = before
            if publication:
                query_dict["publication"] = publication
            if search:
                query_dict["search"] = search
            if limit:
                query_dict["limit"] = limit
            params["query"] = query_dict
        _summarize_via_api(params, "Summarizing pending content")
    except httpx.ConnectError:
        if not is_json_mode():
            Console(stderr=True).print(
                "[yellow]Backend unavailable — summarizing directly...[/yellow]"
            )
        _summarize_pending_direct(
            limit=limit,
            sync=sync,
            source=source,
            status=status,
            after=after,
            before=before,
            publication=publication,
            search=search,
            dry_run=dry_run,
        )
    except typer.Exit:
        raise
    except Exception as e:
        if is_json_mode():
            output_result({"error": str(e)}, success=False)
        else:
            console.print(f"[red]Error summarizing pending content: {e}[/red]")
        raise typer.Exit(1)


def _summarize_pending_direct(
    *,
    limit: int | None,
    sync: bool,
    source: str | None,
    status: str | None,
    after: str | None,
    before: str | None,
    publication: str | None,
    search: str | None,
    dry_run: bool,
) -> None:
    """Direct mode: summarize pending content via local services."""
    import asyncio

    has_filters = any([source, status, after, before, publication, search])

    try:
        query = None
        if has_filters or dry_run:
            from src.cli.query_options import build_query_from_options
            from src.models.content import ContentStatus

            query = build_query_from_options(
                source=source,
                status=status,
                after=after,
                before=before,
                publication=publication,
                search=search,
                limit=limit,
                default_statuses=[ContentStatus.PENDING, ContentStatus.PARSED],
            )

        if dry_run:
            from src.cli.query_options import display_preview
            from src.services.content_query import ContentQueryService

            svc = ContentQueryService()
            preview = svc.preview(query)  # type: ignore[arg-type]
            if is_json_mode():
                output_result({"preview": preview.model_dump(mode="json")})
            else:
                display_preview(preview, action_name="summarize")
            return

        if sync:
            from src.processors.summarizer import ContentSummarizer

            summarizer = ContentSummarizer()
            if not is_json_mode():
                msg = "Summarizing pending content (sync mode)"
                if limit:
                    msg += f" (limit: {limit})"
                console.print(msg + "...")
            count = summarizer.summarize_pending_contents(limit=limit, query=query)
            if is_json_mode():
                output_result({"summarized_count": count, "limit": limit, "mode": "sync"})
            else:
                console.print(f"[green]Successfully summarized {count} content item(s).[/green]")
        else:
            from src.processors.summarizer import ContentSummarizer

            summarizer = ContentSummarizer()
            if not is_json_mode():
                msg = "Enqueuing pending content for summarization"
                if limit:
                    msg += f" (limit: {limit})"
                console.print(msg + "...")
            result = asyncio.run(summarizer.enqueue_pending_contents(limit=limit, query=query))
            enqueued: int = result["enqueued_count"]  # type: ignore[assignment]
            skipped: int = result["skipped_count"]  # type: ignore[assignment]
            if is_json_mode():
                output_result(
                    {
                        "enqueued_count": enqueued,
                        "skipped_count": skipped,
                        "job_ids": result["job_ids"],
                        "limit": limit,
                        "mode": "queue",
                    }
                )
            else:
                console.print(
                    f"[green]Enqueued {enqueued} summarization job(s) "
                    f"({skipped} already in queue).[/green]"
                )

    except typer.BadParameter:
        raise
    except Exception as e:
        if is_json_mode():
            output_result({"error": str(e)}, success=False)
        else:
            console.print(f"[red]Error summarizing pending content: {e}[/red]")
        raise typer.Exit(1)


@app.command("id")
def summarize_by_id(
    content_id: Annotated[
        int,
        typer.Argument(help="Content ID to summarize."),
    ],
    sync: Annotated[
        bool,
        typer.Option(
            "--sync",
            help="Run synchronously instead of enqueuing to job queue.",
        ),
    ] = False,
) -> None:
    """Summarize a specific content item by its ID.

    By default, calls the API to enqueue summarization. Falls back to direct
    mode if the API is unreachable. Use --sync for immediate in-process summarization.
    """
    if sync or is_direct_mode():
        return _summarize_by_id_direct(content_id, sync=sync)

    try:
        _summarize_via_api(
            {"content_ids": [content_id]},
            f"Summarizing content {content_id}",
        )
    except httpx.ConnectError:
        if not is_json_mode():
            Console(stderr=True).print(
                "[yellow]Backend unavailable — summarizing directly...[/yellow]"
            )
        _summarize_by_id_direct(content_id, sync=sync)
    except typer.Exit:
        raise
    except Exception as e:
        if is_json_mode():
            output_result({"error": str(e), "content_id": content_id}, success=False)
        else:
            console.print(f"[red]Error summarizing content {content_id}: {e}[/red]")
        raise typer.Exit(1)


def _summarize_by_id_direct(content_id: int, *, sync: bool = False) -> None:
    """Direct mode: summarize a specific content item."""
    import asyncio

    try:
        if sync:
            from src.processors.summarizer import ContentSummarizer

            summarizer = ContentSummarizer()
            if not is_json_mode():
                console.print(f"Summarizing content ID {content_id} (sync)...")
            success = summarizer.summarize_content(content_id)
            if success:
                if is_json_mode():
                    output_result({"content_id": content_id, "summarized": True, "mode": "sync"})
                else:
                    console.print(f"[green]Successfully summarized content {content_id}.[/green]")
            else:
                if is_json_mode():
                    output_result({"content_id": content_id, "summarized": False}, success=False)
                else:
                    console.print(f"[red]Failed to summarize content {content_id}.[/red]")
                raise typer.Exit(1)
        else:
            from src.queue.setup import enqueue_summarization_job

            if not is_json_mode():
                console.print(f"Enqueuing content ID {content_id} for summarization...")
            job_id = asyncio.run(enqueue_summarization_job(content_id))
            if job_id is not None:
                if is_json_mode():
                    output_result(
                        {
                            "content_id": content_id,
                            "job_id": job_id,
                            "enqueued": True,
                            "mode": "queue",
                        }
                    )
                else:
                    console.print(
                        f"[green]Enqueued summarization job {job_id} "
                        f"for content {content_id}.[/green]"
                    )
            else:
                if is_json_mode():
                    output_result(
                        {"content_id": content_id, "enqueued": False, "reason": "already_queued"}
                    )
                else:
                    console.print(
                        f"[yellow]Content {content_id} is already queued for summarization.[/yellow]"
                    )
    except typer.Exit:
        raise
    except Exception as e:
        if is_json_mode():
            output_result({"error": str(e), "content_id": content_id}, success=False)
        else:
            console.print(f"[red]Error summarizing content {content_id}: {e}[/red]")
        raise typer.Exit(1)


@app.command("list")
def list_summaries(
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum number of summaries to display.",
        ),
    ] = 20,
) -> None:
    """List recent summaries.

    Shows the most recent summaries ordered by creation date (newest first).
    """
    from src.cli.output import is_json_mode, output_result

    try:
        from src.models.summary import Summary
        from src.storage.database import get_db

        with get_db() as db:
            summaries = db.query(Summary).order_by(Summary.created_at.desc()).limit(limit).all()

        if is_json_mode():
            output_result(
                {
                    "count": len(summaries),
                    "summaries": [
                        {
                            "id": s.id,
                            "content_id": s.content_id,
                            "executive_summary": (
                                s.executive_summary[:120] + "..."
                                if s.executive_summary and len(s.executive_summary) > 120
                                else s.executive_summary
                            ),
                            "key_themes": s.key_themes,
                            "model_used": s.model_used,
                            "created_at": str(s.created_at),
                            "token_usage": s.token_usage,
                        }
                        for s in summaries
                    ],
                }
            )
        else:
            if not summaries:
                console.print("[yellow]No summaries found.[/yellow]")
                return

            table = Table(title=f"Recent Summaries (showing {len(summaries)})")
            table.add_column("ID", style="cyan", justify="right")
            table.add_column("Content ID", style="blue", justify="right")
            table.add_column("Summary", style="white", max_width=60)
            table.add_column("Themes", style="green", max_width=30)
            table.add_column("Model", style="magenta")
            table.add_column("Created", style="dim")

            for s in summaries:
                # Truncate executive summary for display
                summary_text = s.executive_summary or ""
                if len(summary_text) > 60:
                    summary_text = summary_text[:57] + "..."

                # Format themes
                themes = ", ".join(s.key_themes[:3]) if s.key_themes else "-"
                if s.key_themes and len(s.key_themes) > 3:
                    themes += f" (+{len(s.key_themes) - 3})"

                # Format date
                created = s.created_at.strftime("%Y-%m-%d %H:%M") if s.created_at else "-"

                table.add_row(
                    str(s.id),
                    str(s.content_id or "-"),
                    summary_text,
                    themes,
                    s.model_used or "-",
                    created,
                )

            console.print(table)

    except Exception as e:
        if is_json_mode():
            output_result({"error": str(e)}, success=False)
        else:
            console.print(f"[red]Error listing summaries: {e}[/red]")
        raise typer.Exit(1)
