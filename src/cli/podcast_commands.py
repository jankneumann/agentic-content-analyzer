"""CLI commands for podcast generation.

Usage:
    aca podcast generate --digest-id <id>
    aca podcast list-scripts --limit N
"""

from __future__ import annotations

from typing import Annotated

import typer

from src.cli.output import is_json_mode, output_result

app = typer.Typer(help="Generate and manage podcast scripts.")


@app.command("generate")
def generate(
    digest_id: Annotated[
        int,
        typer.Option(
            "--digest-id",
            "-d",
            help="ID of the digest to generate a podcast script from.",
        ),
    ],
    length: Annotated[
        str,
        typer.Option(
            "--length",
            "-l",
            help="Podcast length: 'brief', 'standard', or 'extended'.",
        ),
    ] = "standard",
) -> None:
    """Generate a podcast script from a digest.

    Creates a two-host dialogue script suitable for TTS audio generation.
    The script goes through a review workflow before audio can be produced.
    """
    from src.models.podcast import PodcastLength, PodcastRequest

    # Validate length
    valid_lengths = [member.value for member in PodcastLength]
    if length not in valid_lengths:
        typer.echo(
            typer.style(
                f"Error: Invalid length '{length}'. Must be one of: {', '.join(valid_lengths)}",
                fg=typer.colors.RED,
            )
        )
        raise typer.Exit(1)

    request = PodcastRequest(
        digest_id=digest_id,
        length=PodcastLength(length),
    )

    typer.echo(f"Generating podcast script for digest {digest_id} (length: {length})...")

    try:
        from src.cli.adapters import generate_podcast_script_sync

        script_record = generate_podcast_script_sync(request)
    except Exception as e:
        typer.echo(typer.style(f"Error generating podcast script: {e}", fg=typer.colors.RED))
        raise typer.Exit(1)

    if is_json_mode():
        output_result(
            {
                "id": script_record.id,
                "digest_id": digest_id,
                "title": script_record.title,
                "length": script_record.length,
                "word_count": script_record.word_count,
                "status": getattr(script_record, "status", None),
            }
        )
    else:
        typer.echo()
        typer.echo(typer.style("Podcast script generated successfully!", fg=typer.colors.GREEN))
        typer.echo(f"  ID:         {script_record.id}")
        typer.echo(f"  Title:      {script_record.title}")
        typer.echo(f"  Length:     {script_record.length}")
        typer.echo(f"  Word count: {script_record.word_count}")
        status = getattr(script_record, "status", None)
        if status:
            typer.echo(f"  Status:     {status}")


@app.command("list-scripts")
def list_scripts(
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum number of scripts to display.",
        ),
    ] = 10,
) -> None:
    """List recent podcast scripts.

    Shows podcast scripts ordered by creation date (newest first).
    """
    try:
        from src.models.podcast import PodcastScriptRecord
        from src.storage.database import get_db

        with get_db() as db:
            scripts = (
                db.query(PodcastScriptRecord)
                .order_by(PodcastScriptRecord.created_at.desc())
                .limit(limit)
                .all()
            )
    except Exception as e:
        typer.echo(typer.style(f"Error querying podcast scripts: {e}", fg=typer.colors.RED))
        raise typer.Exit(1)

    if not scripts:
        output_result("No podcast scripts found.")
        return

    if is_json_mode():
        output_result(
            [
                {
                    "id": s.id,
                    "digest_id": s.digest_id,
                    "title": s.title,
                    "length": s.length,
                    "word_count": s.word_count,
                    "status": s.status,
                    "created_at": str(s.created_at) if s.created_at else None,
                }
                for s in scripts
            ]
        )
    else:
        from rich.table import Table

        table = Table(title=f"Podcast Scripts (latest {limit})")
        table.add_column("ID", style="cyan", justify="right")
        table.add_column("Digest", justify="right")
        table.add_column("Title", style="bold")
        table.add_column("Length")
        table.add_column("Words", justify="right")
        table.add_column("Status")
        table.add_column("Created")

        for s in scripts:
            status_style = ""
            status_val = s.status or ""
            if status_val == "completed":
                status_style = "green"
            elif status_val == "failed":
                status_style = "red"
            elif "pending" in status_val or "generating" in status_val:
                status_style = "yellow"

            table.add_row(
                str(s.id),
                str(s.digest_id),
                s.title or "(untitled)",
                s.length or "",
                str(s.word_count) if s.word_count else "-",
                f"[{status_style}]{status_val}[/{status_style}]" if status_style else status_val,
                str(s.created_at.strftime("%Y-%m-%d %H:%M")) if s.created_at else "-",
            )

        from rich.console import Console

        console = Console()
        console.print(table)
