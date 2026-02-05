"""CLI commands for digest creation.

Usage:
    aca create-digest daily --date YYYY-MM-DD
    aca create-digest weekly --week YYYY-MM-DD
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(help="Create daily or weekly digests.")

console = Console()


def _parse_date(date_str: str) -> datetime:
    """Parse a YYYY-MM-DD date string into a timezone-aware datetime.

    Args:
        date_str: Date in YYYY-MM-DD format.

    Returns:
        A UTC-aware datetime at midnight of the given date.

    Raises:
        typer.BadParameter: If the date string is not valid.
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        raise typer.BadParameter(f"Invalid date format: '{date_str}'. Expected YYYY-MM-DD.")


def _monday_of_week(dt: datetime) -> datetime:
    """Return the Monday (start of ISO week) for the week containing the given date.

    Args:
        dt: A datetime within the target week.

    Returns:
        Datetime set to Monday 00:00:00 UTC of that week.
    """
    # weekday(): Monday=0, Sunday=6
    return dt - timedelta(days=dt.weekday())


@app.command("daily")
def create_daily_digest(
    date: Annotated[
        str | None,
        typer.Option(
            "--date",
            "-d",
            help="Date for the digest in YYYY-MM-DD format (default: today).",
        ),
    ] = None,
) -> None:
    """Create a daily digest for the specified date.

    Aggregates all summarized content from the given day into a single digest.
    If no date is provided, defaults to today.
    """
    from src.cli.adapters import create_digest_sync
    from src.cli.output import is_json_mode, output_result
    from src.models.digest import DigestRequest, DigestType

    try:
        if date is not None:
            period_start = _parse_date(date)
        else:
            now = datetime.now(UTC)
            period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        period_end = period_start + timedelta(days=1)

        if not is_json_mode():
            console.print(
                f"Creating daily digest for [cyan]{period_start.strftime('%Y-%m-%d')}[/cyan]..."
            )

        request = DigestRequest(
            digest_type=DigestType.DAILY,
            period_start=period_start,
            period_end=period_end,
        )

        result = create_digest_sync(request)

        if is_json_mode():
            output_result(
                {
                    "digest_type": "daily",
                    "period_start": str(period_start),
                    "period_end": str(period_end),
                    "title": result.title,
                    "newsletter_count": result.newsletter_count,
                    "model_used": result.model_used,
                    "strategic_insights_count": len(result.strategic_insights),
                    "technical_developments_count": len(result.technical_developments),
                    "emerging_trends_count": len(result.emerging_trends),
                }
            )
        else:
            console.print("\n[green]Daily digest created successfully![/green]")
            console.print(f"  Title: [bold]{result.title}[/bold]")
            console.print(f"  Period: {period_start.strftime('%Y-%m-%d')}")
            console.print(f"  Sources: {result.newsletter_count}")
            console.print(f"  Strategic insights: {len(result.strategic_insights)}")
            console.print(f"  Technical developments: {len(result.technical_developments)}")
            console.print(f"  Emerging trends: {len(result.emerging_trends)}")
            console.print(f"  Model: {result.model_used}")

    except typer.BadParameter:
        raise
    except Exception as e:
        if is_json_mode():
            output_result({"error": str(e), "digest_type": "daily"}, success=False)
        else:
            console.print(f"[red]Error creating daily digest: {e}[/red]")
        raise typer.Exit(1)


@app.command("weekly")
def create_weekly_digest(
    week: Annotated[
        str | None,
        typer.Option(
            "--week",
            "-w",
            help=(
                "Any date within the target week in YYYY-MM-DD format. "
                "The digest will cover Monday through Sunday of that week. "
                "Default: current week."
            ),
        ),
    ] = None,
) -> None:
    """Create a weekly digest for the week containing the specified date.

    The week is defined as Monday 00:00 UTC through the following Monday 00:00 UTC.
    If no date is provided, defaults to the current week.
    """
    from src.cli.adapters import create_digest_sync
    from src.cli.output import is_json_mode, output_result
    from src.models.digest import DigestRequest, DigestType

    try:
        if week is not None:
            reference_date = _parse_date(week)
        else:
            reference_date = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

        period_start = _monday_of_week(reference_date)
        period_end = period_start + timedelta(days=7)

        if not is_json_mode():
            console.print(
                f"Creating weekly digest for "
                f"[cyan]{period_start.strftime('%Y-%m-%d')}[/cyan] to "
                f"[cyan]{(period_end - timedelta(days=1)).strftime('%Y-%m-%d')}[/cyan]..."
            )

        request = DigestRequest(
            digest_type=DigestType.WEEKLY,
            period_start=period_start,
            period_end=period_end,
        )

        result = create_digest_sync(request)

        if is_json_mode():
            output_result(
                {
                    "digest_type": "weekly",
                    "period_start": str(period_start),
                    "period_end": str(period_end),
                    "title": result.title,
                    "newsletter_count": result.newsletter_count,
                    "model_used": result.model_used,
                    "strategic_insights_count": len(result.strategic_insights),
                    "technical_developments_count": len(result.technical_developments),
                    "emerging_trends_count": len(result.emerging_trends),
                }
            )
        else:
            console.print("\n[green]Weekly digest created successfully![/green]")
            console.print(f"  Title: [bold]{result.title}[/bold]")
            console.print(
                f"  Period: {period_start.strftime('%Y-%m-%d')} to "
                f"{(period_end - timedelta(days=1)).strftime('%Y-%m-%d')}"
            )
            console.print(f"  Sources: {result.newsletter_count}")
            console.print(f"  Strategic insights: {len(result.strategic_insights)}")
            console.print(f"  Technical developments: {len(result.technical_developments)}")
            console.print(f"  Emerging trends: {len(result.emerging_trends)}")
            console.print(f"  Model: {result.model_used}")

    except typer.BadParameter:
        raise
    except Exception as e:
        if is_json_mode():
            output_result({"error": str(e), "digest_type": "weekly"}, success=False)
        else:
            console.print(f"[red]Error creating weekly digest: {e}[/red]")
        raise typer.Exit(1)
