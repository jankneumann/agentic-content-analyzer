"""CLI commands for digest review and revision.

Usage:
    aca review list
    aca review view <digest-id>
    aca review revise <digest-id>
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import typer

from src.cli.adapters import (
    finalize_review_sync,
    get_digest_sync,
    list_pending_reviews_sync,
    process_revision_turn_sync,
    start_revision_session_sync,
)
from src.cli.output import is_json_mode, output_result

app = typer.Typer(help="Review and revise digests.")


def _format_digest_summary(digest: Any) -> dict[str, Any]:
    """Format a digest object into a summary dictionary for display.

    Args:
        digest: Digest ORM object.

    Returns:
        Dictionary with key digest fields.
    """
    return {
        "id": digest.id,
        "type": str(digest.digest_type),
        "title": digest.title,
        "status": str(digest.status),
        "period_start": digest.period_start.strftime("%Y-%m-%d") if digest.period_start else None,
        "period_end": digest.period_end.strftime("%Y-%m-%d") if digest.period_end else None,
        "newsletter_count": digest.newsletter_count,
        "revision_count": digest.revision_count,
        "created_at": digest.created_at.strftime("%Y-%m-%d %H:%M") if digest.created_at else None,
    }


def _display_digest_content(digest: Any) -> None:
    """Display full digest content using Rich formatting.

    Args:
        digest: Digest ORM object with full content fields.
    """
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel

    console = Console()

    # Header panel
    header_lines = [
        f"**Type:** {digest.digest_type}",
        f"**Status:** {digest.status}",
        f"**Period:** {digest.period_start.strftime('%Y-%m-%d')} to {digest.period_end.strftime('%Y-%m-%d')}",
        f"**Content Count:** {digest.newsletter_count}",
        f"**Revisions:** {digest.revision_count}",
        f"**Model:** {digest.model_used}",
    ]
    if digest.reviewed_by:
        header_lines.append(f"**Reviewed By:** {digest.reviewed_by}")
    if digest.reviewed_at:
        header_lines.append(f"**Reviewed At:** {digest.reviewed_at.strftime('%Y-%m-%d %H:%M')}")

    console.print(
        Panel(
            Markdown("\n".join(header_lines)),
            title=f"[bold]Digest #{digest.id}: {digest.title}[/bold]",
            border_style="blue",
        )
    )

    # If markdown_content is available, display it directly
    if digest.markdown_content:
        console.print()
        console.print(Markdown(digest.markdown_content))
        return

    # Otherwise, render structured fields

    # Executive Overview
    console.print()
    console.print("[bold]Executive Overview[/bold]")
    console.print(Markdown(digest.executive_overview))

    # Strategic Insights
    if digest.strategic_insights:
        console.print()
        console.print("[bold]Strategic Insights[/bold]")
        for idx, insight in enumerate(digest.strategic_insights, 1):
            if isinstance(insight, dict):
                title = insight.get("title", "Untitled")
                summary = insight.get("summary", "")
                console.print(f"\n  {idx}. [bold]{title}[/bold]")
                console.print(f"     {summary}")
            else:
                console.print(f"  {idx}. {insight}")

    # Technical Developments
    if digest.technical_developments:
        console.print()
        console.print("[bold]Technical Developments[/bold]")
        for idx, dev in enumerate(digest.technical_developments, 1):
            if isinstance(dev, dict):
                title = dev.get("title", "Untitled")
                summary = dev.get("summary", "")
                console.print(f"\n  {idx}. [bold]{title}[/bold]")
                console.print(f"     {summary}")
            else:
                console.print(f"  {idx}. {dev}")

    # Emerging Trends
    if digest.emerging_trends:
        console.print()
        console.print("[bold]Emerging Trends[/bold]")
        for idx, trend in enumerate(digest.emerging_trends, 1):
            if isinstance(trend, dict):
                title = trend.get("title", "Untitled")
                summary = trend.get("summary", "")
                console.print(f"\n  {idx}. [bold]{title}[/bold]")
                console.print(f"     {summary}")
            else:
                console.print(f"  {idx}. {trend}")

    # Actionable Recommendations
    if digest.actionable_recommendations:
        console.print()
        console.print("[bold]Actionable Recommendations[/bold]")
        if isinstance(digest.actionable_recommendations, dict):
            for role, actions in digest.actionable_recommendations.items():
                console.print(f"\n  [bold]{role}:[/bold]")
                if isinstance(actions, list):
                    for action in actions:
                        console.print(f"    - {action}")
                else:
                    console.print(f"    {actions}")


@app.command("list")
def list_reviews() -> None:
    """List all digests pending review.

    Shows digests with status PENDING_REVIEW, ordered by creation date
    (newest first). Displays ID, type, title, period, and creation date.
    """
    try:
        digests = list_pending_reviews_sync()
    except Exception as e:
        typer.echo(f"Error listing pending reviews: {e}")
        raise typer.Exit(1)

    if not digests:
        typer.echo("No digests pending review.")
        if is_json_mode():
            output_result({"digests": [], "count": 0})
        return

    if is_json_mode():
        output_result(
            {
                "digests": [_format_digest_summary(d) for d in digests],
                "count": len(digests),
            }
        )
        return

    # Rich table display
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="Digests Pending Review")

    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Title", style="white", max_width=50)
    table.add_column("Period", style="green")
    table.add_column("Items", justify="right")
    table.add_column("Revisions", justify="right")
    table.add_column("Created", style="dim")

    for digest in digests:
        period = ""
        if digest.period_start and digest.period_end:
            period = (
                f"{digest.period_start.strftime('%Y-%m-%d')} to "
                f"{digest.period_end.strftime('%Y-%m-%d')}"
            )

        created = ""
        if digest.created_at:
            created = digest.created_at.strftime("%Y-%m-%d %H:%M")

        table.add_row(
            str(digest.id),
            str(digest.digest_type),
            digest.title or "(no title)",
            period,
            str(digest.newsletter_count),
            str(digest.revision_count),
            created,
        )

    console.print(table)
    typer.echo(f"\n{len(digests)} digest(s) pending review.")


@app.command("view")
def view(
    digest_id: Annotated[
        int,
        typer.Argument(help="ID of the digest to view."),
    ],
) -> None:
    """View full content of a digest.

    Displays the complete digest including executive overview, strategic
    insights, technical developments, emerging trends, and actionable
    recommendations.
    """
    try:
        digest = get_digest_sync(digest_id)
    except Exception as e:
        typer.echo(f"Error loading digest: {e}")
        raise typer.Exit(1)

    if not digest:
        typer.echo(f"Error: Digest {digest_id} not found.")
        raise typer.Exit(1)

    if is_json_mode():
        output_result(_format_digest_summary(digest))
        return

    _display_digest_content(digest)


@app.command("revise")
def revise(
    digest_id: Annotated[
        int,
        typer.Argument(help="ID of the digest to revise interactively."),
    ],
) -> None:
    """Start an interactive revision REPL for a digest.

    Loads the digest, displays its content, then enters a revision loop where
    you can request changes. The AI will revise the digest based on your
    instructions. Type "done" or press Ctrl-D to finish and approve.

    Example:
        aca review revise 42
        revision> Make the executive overview more concise
        revision> Add more detail to the first strategic insight
        revision> done
    """
    # Load digest
    try:
        digest = get_digest_sync(digest_id)
    except Exception as e:
        typer.echo(f"Error loading digest: {e}")
        raise typer.Exit(1)

    if not digest:
        typer.echo(f"Error: Digest {digest_id} not found.")
        raise typer.Exit(1)

    # Display current digest content
    typer.echo(f"Loaded digest #{digest_id}: {digest.title}")
    typer.echo("-" * 60)
    _display_digest_content(digest)
    typer.echo("-" * 60)

    # Start revision session
    session_id = str(uuid.uuid4())
    try:
        context = start_revision_session_sync(digest_id, session_id, "cli-user")
    except ValueError as e:
        typer.echo(f"Error: {e}")
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error starting revision session: {e}")
        raise typer.Exit(1)

    typer.echo(f"\nRevision session started (session: {session_id[:8]}...).")
    typer.echo('Type your revision requests. Enter "done" or press Ctrl-D to finish.\n')

    # Conversation history for multi-turn context
    history: list[dict[str, Any]] = []
    turn_count = 0

    # REPL loop
    while True:
        try:
            user_input = input("revision> ")
        except (EOFError, KeyboardInterrupt):
            # Ctrl-D or Ctrl-C exits the REPL
            typer.echo("")
            break

        # Strip and check for exit command
        user_input = user_input.strip()
        if not user_input:
            continue
        if user_input.lower() == "done":
            break

        # Process revision turn
        turn_count += 1
        try:
            result = process_revision_turn_sync(context, user_input, history, session_id)
        except Exception as e:
            typer.echo(f"Error processing revision: {e}")
            typer.echo("You can try again or type 'done' to finish.\n")
            continue

        # Update conversation history with this turn
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": result.explanation})

        # Display result
        from rich.console import Console
        from rich.panel import Panel

        console = Console()

        console.print()
        console.print(
            Panel(
                f"[bold]Section modified:[/bold] {result.section_modified}\n\n"
                f"[bold]Explanation:[/bold] {result.explanation}\n\n"
                f"[bold]Confidence:[/bold] {result.confidence_score:.0%}",
                title=f"[bold green]Revision #{turn_count}[/bold green]",
                border_style="green",
            )
        )

        # Show revised content preview
        if result.revised_content:
            if isinstance(result.revised_content, str):
                from rich.markdown import Markdown

                console.print()
                console.print("[bold]Revised content:[/bold]")
                console.print(Markdown(result.revised_content))
            else:
                console.print()
                console.print("[bold]Revised content:[/bold]")
                console.print(result.revised_content)

        console.print()

    # Finalize review - approve on exit
    typer.echo("Finalizing review...")
    try:
        finalize_review_sync(
            digest_id=digest_id,
            action="approve",
            revision_history=None,
            reviewer="cli-user",
        )
        typer.echo(
            f"Review finalized: digest #{digest_id} approved ({turn_count} revision(s) applied)."
        )
    except Exception as e:
        typer.echo(f"Error finalizing review: {e}")
        raise typer.Exit(1)

    if is_json_mode():
        output_result(
            {
                "digest_id": digest_id,
                "action": "approve",
                "revision_turns": turn_count,
                "session_id": session_id,
            }
        )
