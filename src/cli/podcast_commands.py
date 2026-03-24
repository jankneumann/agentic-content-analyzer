"""CLI commands for podcast generation.

In HTTP mode (default), commands call the backend API via httpx.
In direct mode (--direct flag or API unreachable), commands call
services directly (legacy inline behavior).

Usage:
    aca podcast generate --digest-id <id>
    aca podcast list-scripts --limit N
"""

from __future__ import annotations

from typing import Annotated, Any

import httpx
import typer

from src.cli.output import is_direct_mode, is_json_mode, output_result

app = typer.Typer(help="Generate and manage podcast scripts.")


# ---------------------------------------------------------------------------
# aca podcast generate
# ---------------------------------------------------------------------------


def _generate_direct(digest_id: int, length: str) -> None:
    """Direct podcast generation (legacy inline path)."""
    from src.models.podcast import PodcastLength, PodcastRequest

    # Validate length
    valid_lengths = [member.value for member in PodcastLength]
    if length not in valid_lengths:
        if is_json_mode():
            output_result(
                {
                    "error": f"Invalid length '{length}'. Must be one of: {', '.join(valid_lengths)}",
                    "source": "podcast",
                },
                success=False,
            )
        else:
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

    if not is_json_mode():
        typer.echo(f"Generating podcast script for digest {digest_id} (length: {length})...")

    try:
        from src.cli.adapters import generate_podcast_script_sync

        script_record = generate_podcast_script_sync(request)
    except Exception as e:
        if is_json_mode():
            output_result({"error": str(e), "source": "podcast"}, success=False)
        else:
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
    if is_direct_mode():
        return _generate_direct(digest_id, length)

    try:
        from src.cli.api_client import get_api_client

        client = get_api_client()
        params: dict[str, Any] = {"digest_id": digest_id}
        if length != "standard":
            params["length"] = length
        response = client.generate_podcast(**params)
    except httpx.ConnectError:
        if not is_json_mode():
            from rich.console import Console

            Console(stderr=True).print(
                "[yellow]Backend unavailable — generating podcast script directly...[/yellow]"
            )
        _generate_direct(digest_id, length)
        return

    if is_json_mode():
        output_result(response)
    else:
        typer.echo()
        typer.echo(typer.style("Podcast script generated successfully!", fg=typer.colors.GREEN))
        typer.echo(f"  ID:         {response.get('id', 'N/A')}")
        typer.echo(f"  Digest:     {response.get('digest_id', digest_id)}")
        typer.echo(f"  Title:      {response.get('title', 'N/A')}")
        typer.echo(f"  Length:     {response.get('length', length)}")
        typer.echo(f"  Word count: {response.get('word_count', 'N/A')}")
        status = response.get("status")
        if status:
            typer.echo(f"  Status:     {status}")


# ---------------------------------------------------------------------------
# aca podcast list-scripts
# ---------------------------------------------------------------------------


def _list_scripts_direct(limit: int, status: str | None, digest_id: int | None) -> None:
    """Direct podcast script listing (legacy inline path)."""
    try:
        from src.models.podcast import PodcastScriptRecord
        from src.storage.database import get_db

        with get_db() as db:
            query = db.query(PodcastScriptRecord)
            if status:
                query = query.filter(PodcastScriptRecord.status == status)
            if digest_id is not None:
                query = query.filter(PodcastScriptRecord.digest_id == digest_id)
            scripts = query.order_by(PodcastScriptRecord.created_at.desc()).limit(limit).all()
    except Exception as e:
        if is_json_mode():
            output_result({"error": str(e), "source": "podcast-scripts"}, success=False)
        else:
            typer.echo(typer.style(f"Error querying podcast scripts: {e}", fg=typer.colors.RED))
        raise typer.Exit(1)

    if not scripts:
        if is_json_mode():
            output_result({"scripts": [], "total": 0})
        else:
            typer.echo("No podcast scripts found.")
        return

    if is_json_mode():
        output_result(
            {
                "scripts": [
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
                ],
                "total": len(scripts),
            }
        )
    else:
        from rich.console import Console
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

        console = Console()
        console.print(table)


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
    status: Annotated[
        str | None,
        typer.Option(
            "--status",
            "-s",
            help="Filter by status (e.g., 'completed', 'pending').",
        ),
    ] = None,
    digest_id: Annotated[
        int | None,
        typer.Option(
            "--digest-id",
            "-d",
            help="Filter by digest ID.",
        ),
    ] = None,
) -> None:
    """List recent podcast scripts.

    Shows podcast scripts ordered by creation date (newest first).
    """
    if is_direct_mode():
        return _list_scripts_direct(limit, status, digest_id)

    try:
        from src.cli.api_client import get_api_client

        client = get_api_client()
        params: dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        if digest_id is not None:
            params["digest_id"] = digest_id
        response = client.list_scripts(**params)
    except httpx.ConnectError:
        if not is_json_mode():
            from rich.console import Console

            Console(stderr=True).print(
                "[yellow]Backend unavailable — listing scripts directly...[/yellow]"
            )
        _list_scripts_direct(limit, status, digest_id)
        return

    if is_json_mode():
        output_result(response)
        return

    # Parse API response
    scripts = response.get("scripts", response.get("items", []))
    if not scripts:
        typer.echo("No podcast scripts found.")
        return

    from rich.console import Console
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
        status_val = s.get("status", "")
        status_style = ""
        if status_val == "completed":
            status_style = "green"
        elif status_val == "failed":
            status_style = "red"
        elif "pending" in status_val or "generating" in status_val:
            status_style = "yellow"

        table.add_row(
            str(s.get("id", "")),
            str(s.get("digest_id", "")),
            s.get("title") or "(untitled)",
            s.get("length", ""),
            str(s.get("word_count", "-")) if s.get("word_count") else "-",
            f"[{status_style}]{status_val}[/{status_style}]" if status_style else status_val,
            s.get("created_at", "-"),
        )

    console = Console()
    console.print(table)
