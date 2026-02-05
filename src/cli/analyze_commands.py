"""CLI commands for theme analysis.

Usage:
    aca analyze themes
    aca analyze themes --start 2025-01-01 --end 2025-01-07
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from src.cli.output import is_json_mode, output_result

app = typer.Typer(help="Analyze themes across content.")


@app.command("themes")
def themes(
    start: Annotated[
        str | None,
        typer.Option(
            "--start",
            help="Start date (YYYY-MM-DD). Defaults to 7 days ago.",
        ),
    ] = None,
    end: Annotated[
        str | None,
        typer.Option(
            "--end",
            help="End date (YYYY-MM-DD). Defaults to today.",
        ),
    ] = None,
    max_themes: Annotated[
        int,
        typer.Option(
            "--max-themes",
            help="Maximum number of themes to return.",
        ),
    ] = 15,
    relevance_threshold: Annotated[
        float,
        typer.Option(
            "--threshold",
            help="Minimum relevance score (0-1).",
        ),
    ] = 0.3,
) -> None:
    """Analyze themes in content within a date range.

    Identifies recurring themes, trends, and patterns across ingested
    content items. Defaults to the last 7 days if no dates are specified.
    """
    console = Console()

    # Parse dates with defaults
    try:
        if end is not None:
            end_date = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=UTC)
        else:
            end_date = datetime.now(UTC).replace(hour=23, minute=59, second=59)

        if start is not None:
            start_date = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=UTC)
        else:
            start_date = end_date - timedelta(days=7)
    except ValueError as e:
        console.print(f"[red]Error:[/red] Invalid date format: {e}")
        console.print("Use YYYY-MM-DD format (e.g., 2025-01-15).")
        raise typer.Exit(1)

    if start_date > end_date:
        console.print("[red]Error:[/red] Start date must be before end date.")
        raise typer.Exit(1)

    console.print(
        f"Analyzing themes from [bold]{start_date.strftime('%Y-%m-%d')}[/bold] "
        f"to [bold]{end_date.strftime('%Y-%m-%d')}[/bold]..."
    )

    try:
        from src.cli.adapters import analyze_themes_sync
        from src.models.theme import ThemeAnalysisRequest

        request = ThemeAnalysisRequest(
            start_date=start_date,
            end_date=end_date,
            max_themes=max_themes,
            relevance_threshold=relevance_threshold,
        )
        result = analyze_themes_sync(request)
    except Exception as e:
        console.print(f"[red]Error:[/red] Theme analysis failed: {e}")
        raise typer.Exit(1)

    if not result.themes:
        console.print("[yellow]No themes found in the specified date range.[/yellow]")
        if is_json_mode():
            output_result({"themes": [], "total": 0})
        raise typer.Exit(0)

    # JSON output mode
    if is_json_mode():
        themes_data = [
            {
                "name": theme.name,
                "description": theme.description,
                "category": theme.category.value,
                "trend": theme.trend.value,
                "content_count": len(theme.newsletter_ids),
                "relevance_score": theme.relevance_score,
            }
            for theme in result.themes
        ]
        json.dump(
            {
                "themes": themes_data,
                "total": result.total_themes,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "content_analyzed": result.newsletter_count,
            },
            sys.stdout,
            default=str,
        )
        sys.stdout.write("\n")
        raise typer.Exit(0)

    # Rich table output
    console.print()
    console.print(
        f"Found [bold]{result.total_themes}[/bold] themes "
        f"across [bold]{result.newsletter_count}[/bold] content items."
    )
    console.print()

    table = Table(title="Theme Analysis Results")
    table.add_column("Theme", style="bold cyan", no_wrap=False, max_width=30)
    table.add_column("Category", style="magenta")
    table.add_column("Trend", style="green")
    table.add_column("Content Count", justify="right", style="yellow")

    for theme in result.themes:
        # Format trend with visual indicator
        trend_display = _format_trend(theme.trend.value)

        table.add_row(
            theme.name,
            theme.category.value.replace("_", " ").title(),
            trend_display,
            str(len(theme.newsletter_ids)),
        )

    console.print(table)

    # Show top theme if available
    if result.top_theme:
        console.print()
        console.print(f"Top theme: [bold]{result.top_theme}[/bold]")

    # Show cross-theme insights if available
    if result.cross_theme_insights:
        console.print()
        console.print("[bold]Cross-theme insights:[/bold]")
        for insight in result.cross_theme_insights:
            console.print(f"  - {insight}")


def _format_trend(trend: str) -> str:
    """Format a trend value with a visual indicator."""
    indicators = {
        "emerging": "[bright_green]Emerging[/bright_green]",
        "growing": "[green]Growing[/green]",
        "established": "[blue]Established[/blue]",
        "declining": "[red]Declining[/red]",
        "one_off": "[dim]One-off[/dim]",
    }
    return indicators.get(trend, trend)
