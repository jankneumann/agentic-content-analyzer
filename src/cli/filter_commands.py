"""CLI commands for the ingestion filter.

Commands:
    aca filter explain <content-id>   Show stored per-tier decision for a row.
    aca filter rerun --persona ...    Re-evaluate rows for a persona.
    aca filter stats                  Aggregate counts by decision / tier.

These commands operate directly on the database (no HTTP mode) because the
filter is a local-pipeline concept — there's no user-facing session to route
through the backend.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

import typer

app = typer.Typer(help="Inspect and re-run the ingestion filter.", no_args_is_help=True)


@app.command("explain")
def explain(
    content_id: Annotated[int, typer.Argument(help="Content row id.")],
) -> None:
    """Print the stored filter decision for a content row."""
    from src.models.content import Content
    from src.storage.database import get_db

    with get_db() as db:
        row = db.get(Content, content_id)
        if row is None:
            typer.echo(f"content id={content_id} not found")
            raise typer.Exit(code=1)
        typer.echo(f"content_id:       {row.id}")
        typer.echo(f"source_type:      {row.source_type}")
        typer.echo(f"status:           {row.status}")
        typer.echo(f"filter_decision:  {row.filter_decision}")
        typer.echo(f"filter_score:     {row.filter_score}")
        typer.echo(f"filter_tier:      {row.filter_tier}")
        typer.echo(f"filter_reason:    {row.filter_reason}")
        typer.echo(f"priority_bucket:  {row.priority_bucket}")
        typer.echo(f"filtered_at:      {row.filtered_at}")


@app.command("rerun")
def rerun(
    persona: Annotated[str, typer.Option("--persona", help="Persona id to re-evaluate for.")],
    since: Annotated[
        datetime | None,
        typer.Option(
            "--since",
            help="Only re-evaluate rows ingested at/after this UTC datetime (ISO 8601).",
        ),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Print stats but do not update rows.")
    ] = False,
) -> None:
    """Re-run the filter over previously-ingested rows for a persona."""
    from src.ingestion.filter_hook import apply_filter_to_recent

    effective_since = since or datetime.fromtimestamp(0)
    stats = apply_filter_to_recent(
        since=effective_since, persona_id=persona, dry_run=dry_run
    )
    typer.echo(f"rerun: {stats.as_dict()}")


@app.command("stats")
def stats() -> None:
    """Print aggregate counts of filter decisions across the Content table."""
    from sqlalchemy import func

    from src.models.content import Content
    from src.storage.database import get_db

    with get_db() as db:
        rows = (
            db.query(
                Content.filter_decision,
                Content.filter_tier,
                func.count(Content.id),
            )
            .group_by(Content.filter_decision, Content.filter_tier)
            .all()
        )
        if not rows:
            typer.echo("no filter decisions recorded")
            return
        typer.echo(f"{'decision':<10} {'tier':<12} count")
        typer.echo("-" * 32)
        for decision, tier, count in rows:
            typer.echo(f"{decision or '(null)':<10} {tier or '(null)':<12} {count}")
