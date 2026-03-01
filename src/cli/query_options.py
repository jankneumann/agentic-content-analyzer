"""Shared CLI query options for content filtering.

Provides reusable query filter options and a helper function to translate
CLI flags into a ContentQuery model. Used by summarize and digest commands.
"""

from datetime import UTC, datetime

import typer

from src.models.content import ContentSource, ContentStatus
from src.models.query import ContentQuery, ContentQueryPreview


def build_query_from_options(
    source: str | None,
    status: str | None,
    after: str | None,
    before: str | None,
    publication: str | None,
    search: str | None,
    limit: int | None = None,
    default_statuses: list[ContentStatus] | None = None,
) -> ContentQuery:
    """Translate CLI options to ContentQuery.

    Validation errors (invalid enum values, bad date format) raise
    typer.BadParameter with descriptive messages listing valid values.

    Args:
        source: Comma-separated source type values
        status: Comma-separated status values
        after: Start date in YYYY-MM-DD format
        before: End date in YYYY-MM-DD format
        publication: Publication name search (ILIKE)
        search: Title search (ILIKE)
        limit: Maximum results
        default_statuses: Statuses to apply when --status not provided

    Returns:
        ContentQuery with parsed filter values
    """
    source_types = None
    if source:
        try:
            source_types = [ContentSource(s.strip()) for s in source.split(",") if s.strip()]
        except ValueError as e:
            valid = ", ".join(s.value for s in ContentSource)
            raise typer.BadParameter(f"Invalid source: {e}. Valid: {valid}")
        if not source_types:
            raise typer.BadParameter(
                f"Empty source value. Valid: {', '.join(s.value for s in ContentSource)}"
            )

    statuses = default_statuses
    if status:
        try:
            statuses = [ContentStatus(s.strip()) for s in status.split(",") if s.strip()]
        except ValueError as e:
            valid = ", ".join(s.value for s in ContentStatus)
            raise typer.BadParameter(f"Invalid status: {e}. Valid: {valid}")
        if not statuses:
            raise typer.BadParameter(
                f"Empty status value. Valid: {', '.join(s.value for s in ContentStatus)}"
            )

    start_date = None
    if after:
        try:
            start_date = datetime.strptime(after, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            raise typer.BadParameter(f"Invalid date format '{after}'. Use YYYY-MM-DD.")

    end_date = None
    if before:
        try:
            end_date = datetime.strptime(before, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            raise typer.BadParameter(f"Invalid date format '{before}'. Use YYYY-MM-DD.")

    return ContentQuery(
        source_types=source_types,
        statuses=statuses,
        start_date=start_date,
        end_date=end_date,
        publication_search=publication,
        search=search,
        limit=limit,
    )


def display_preview(preview: ContentQueryPreview, action_name: str = "process") -> None:
    """Display a ContentQueryPreview as a Rich table.

    Args:
        preview: The preview to display
        action_name: Name of the action (e.g., "summarize", "include in digest")
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()

    if preview.total_count == 0:
        console.print("\n[yellow]No content matches the specified filters.[/yellow]")
        return

    console.print("\n[bold]Content Query Preview[/bold]")
    console.print(f"  Matching items: [cyan]{preview.total_count}[/cyan]")

    earliest_raw = preview.date_range.get("earliest")
    latest_raw = preview.date_range.get("latest")
    if earliest_raw and latest_raw:
        console.print(f"  Date range: {earliest_raw[:10]} → {latest_raw[:10]}")

    if preview.by_source:
        console.print("\n  [bold]By Source:[/bold]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        for src, cnt in preview.by_source.items():
            table.add_row(f"    {src}", str(cnt))
        console.print(table)

    if preview.by_status:
        console.print("  [bold]By Status:[/bold]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        for st, cnt in preview.by_status.items():
            table.add_row(f"    {st}", str(cnt))
        console.print(table)

    if preview.sample_titles:
        shown = len(preview.sample_titles)
        header = "  [bold]Sample Titles[/bold]"
        if preview.total_count > shown:
            header += f" (showing {shown} of {preview.total_count})"
        console.print(header + ":")
        for i, title in enumerate(preview.sample_titles, 1):
            console.print(f"    {i}. {title}")

    console.print(f"\nRun without --dry-run to {action_name} these {preview.total_count} items.")
