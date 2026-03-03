"""CLI commands for content summarization.

Usage:
    aca summarize pending --limit N
    aca summarize pending --source youtube,rss --after 2026-02-20 --dry-run
    aca summarize id <content-id>
    aca summarize list --limit N
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Summarize ingested content.")

console = Console()


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

    By default, enqueues summarization jobs to the queue for concurrent
    processing by the embedded worker (or standalone aca worker).
    Use --sync for sequential in-process summarization.

    Filter options (--source, --status, --after, --before, --publication, --search)
    narrow which content items are selected. Use --dry-run to preview without executing.
    """
    import asyncio

    from src.cli.output import is_json_mode, output_result

    has_filters = any([source, status, after, before, publication, search])

    try:
        # Build ContentQuery when filters are provided
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

        # Handle dry-run: preview only
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
                msg += "..."
                console.print(msg)

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
                msg += "..."
                console.print(msg)

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
                if enqueued > 0:
                    console.print(
                        "[dim]Jobs will be processed by the embedded worker "
                        "(WORKER_CONCURRENCY controls parallelism).[/dim]"
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

    By default, enqueues a summarization job to the queue.
    Use --sync for immediate in-process summarization.
    """
    import asyncio

    from src.cli.output import is_json_mode, output_result

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
                    output_result(
                        {"content_id": content_id, "summarized": False},
                        success=False,
                    )
                else:
                    console.print(
                        f"[red]Failed to summarize content {content_id}. "
                        f"Check that the ID exists and has not already been summarized.[/red]"
                    )
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
                        f"[yellow]Content {content_id} is already queued "
                        f"for summarization.[/yellow]"
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
