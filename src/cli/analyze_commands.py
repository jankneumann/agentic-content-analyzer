"""CLI commands for theme analysis.

In HTTP mode (default), commands call the backend API via httpx and poll
for results. In direct mode (--direct flag or API unreachable), commands
call adapter functions directly (legacy inline behavior).

Usage:
    aca analyze themes
    aca analyze themes --start 2025-01-01 --end 2025-01-07
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
import typer
from rich.console import Console
from rich.table import Table

from src.cli.output import is_direct_mode, is_json_mode, output_result

app = typer.Typer(help="Analyze themes across content.")


# ---------------------------------------------------------------------------
# Direct-mode helper
# ---------------------------------------------------------------------------


def _analyze_themes_direct(
    start_date: datetime,
    end_date: datetime,
    max_themes: int,
    relevance_threshold: float,
    console: Console,
) -> None:
    """Run theme analysis via direct service calls (legacy path)."""
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
                "content_count": len(theme.content_ids),
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
                "content_analyzed": result.content_count,
            },
            sys.stdout,
            default=str,
        )
        sys.stdout.write("\n")
        raise typer.Exit(0)

    # Rich table output
    _display_theme_results(result, start_date, end_date, console)


def _display_theme_results(
    result: object,
    start_date: datetime,
    end_date: datetime,
    console: Console,
) -> None:
    """Display theme analysis results in Rich table format.

    Works with both direct-mode ThemeAnalysisResult objects and API dicts.
    """
    # Handle both ORM result objects and API response dicts
    if isinstance(result, dict):
        themes = result.get("themes", [])
        total_themes = result.get("total_themes", len(themes))
        content_count = result.get("content_count", 0)
        top_theme = result.get("top_theme")
        cross_theme_insights = result.get("cross_theme_insights", [])
    else:
        themes = result.themes  # type: ignore[attr-defined]
        total_themes = result.total_themes  # type: ignore[attr-defined]
        content_count = result.content_count  # type: ignore[attr-defined]
        top_theme = result.top_theme  # type: ignore[attr-defined]
        cross_theme_insights = result.cross_theme_insights  # type: ignore[attr-defined]

    console.print()
    console.print(
        f"Found [bold]{total_themes}[/bold] themes "
        f"across [bold]{content_count}[/bold] content items."
    )
    console.print()

    table = Table(title="Theme Analysis Results")
    table.add_column("Theme", style="bold cyan", no_wrap=False, max_width=30)
    table.add_column("Category", style="magenta")
    table.add_column("Trend", style="green")
    table.add_column("Content Count", justify="right", style="yellow")

    for theme in themes:
        if isinstance(theme, dict):
            name = theme.get("name", "")
            category = theme.get("category", "").replace("_", " ").title()
            trend_val = theme.get("trend", "")
            content_ids = theme.get("content_ids", [])
            content_count_val = theme.get("content_count", len(content_ids))
        else:
            name = theme.name
            category = theme.category.value.replace("_", " ").title()
            trend_val = theme.trend.value
            content_count_val = len(theme.content_ids)

        trend_display = _format_trend(str(trend_val))

        table.add_row(
            name,
            category,
            trend_display,
            str(content_count_val),
        )

    console.print(table)

    # Show top theme if available
    if top_theme:
        console.print()
        console.print(f"Top theme: [bold]{top_theme}[/bold]")

    # Show cross-theme insights if available
    if cross_theme_insights:
        console.print()
        console.print("[bold]Cross-theme insights:[/bold]")
        for insight in cross_theme_insights:
            console.print(f"  - {insight}")


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


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

    if not is_json_mode():
        console.print(
            f"Analyzing themes from [bold]{start_date.strftime('%Y-%m-%d')}[/bold] "
            f"to [bold]{end_date.strftime('%Y-%m-%d')}[/bold]..."
        )

    if is_direct_mode():
        _analyze_themes_direct(start_date, end_date, max_themes, relevance_threshold, console)
        return

    # HTTP path
    try:
        from src.cli.api_client import get_api_client

        client = get_api_client()
        result = client.analyze_themes(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            max_themes=max_themes,
            relevance_threshold=relevance_threshold,
        )
    except httpx.ConnectError:
        if not is_json_mode():
            Console(stderr=True).print(
                "[yellow]Backend unavailable — running theme analysis directly...[/yellow]"
            )
        _analyze_themes_direct(start_date, end_date, max_themes, relevance_threshold, console)
        return
    except (RuntimeError, TimeoutError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Handle API response
    themes_list = result.get("themes", [])
    if not themes_list:
        console.print("[yellow]No themes found in the specified date range.[/yellow]")
        if is_json_mode():
            output_result({"themes": [], "total": 0})
        raise typer.Exit(0)

    # JSON output mode
    if is_json_mode():
        themes_data = [
            {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "category": t.get("category", ""),
                "trend": t.get("trend", ""),
                "content_count": len(t.get("content_ids", [])),
                "relevance_score": t.get("relevance_score", 0),
            }
            for t in themes_list
        ]
        json.dump(
            {
                "themes": themes_data,
                "total": result.get("total_themes", len(themes_list)),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "content_analyzed": result.get("content_count", 0),
            },
            sys.stdout,
            default=str,
        )
        sys.stdout.write("\n")
        raise typer.Exit(0)

    # Rich table output
    _display_theme_results(result, start_date, end_date, console)


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
