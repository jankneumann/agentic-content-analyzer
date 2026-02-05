"""CLI commands for content summarization.

Usage:
    aca summarize pending --limit N
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
) -> None:
    """Summarize all pending content items.

    Finds content with PENDING or PARSED status and runs summarization.
    """
    from src.cli.output import is_json_mode, output_result

    try:
        from src.processors.summarizer import ContentSummarizer

        summarizer = ContentSummarizer()

        if not is_json_mode():
            msg = "Summarizing pending content"
            if limit:
                msg += f" (limit: {limit})"
            msg += "..."
            console.print(msg)

        count = summarizer.summarize_pending_contents(limit=limit)

        if is_json_mode():
            output_result({"summarized_count": count, "limit": limit})
        else:
            console.print(f"[green]Successfully summarized {count} content item(s).[/green]")

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
) -> None:
    """Summarize a specific content item by its ID."""
    from src.cli.output import is_json_mode, output_result

    try:
        from src.processors.summarizer import ContentSummarizer

        summarizer = ContentSummarizer()

        if not is_json_mode():
            console.print(f"Summarizing content ID {content_id}...")

        success = summarizer.summarize_content(content_id)

        if success:
            if is_json_mode():
                output_result({"content_id": content_id, "summarized": True})
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
