"""CLI commands for knowledge graph operations.

Usage:
    aca graph extract-entities --content-id 123
    aca graph query --query "RAG architecture"
"""

from __future__ import annotations

import json
import sys
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from src.cli.output import is_json_mode, output_result

app = typer.Typer(help="Manage the knowledge graph.")


@app.command("extract-entities")
def extract_entities(
    content_id: Annotated[
        int,
        typer.Option(
            "--content-id",
            help="ID of the content item to extract entities from.",
        ),
    ],
) -> None:
    """Extract entities from a content item into the knowledge graph.

    Reads the specified content item from the database and processes it
    through the Graphiti client to extract entities, relationships, and
    concepts into the Neo4j knowledge graph.
    """
    console = Console()
    console.print(f"Extracting entities from content [bold]{content_id}[/bold]...")

    try:
        from src.cli.adapters import run_async
        from src.models.content import Content
        from src.models.summary import Summary
        from src.storage.database import get_db
        from src.storage.graph_provider import GraphBackendUnavailableError
        from src.storage.graphiti_client import GraphitiClient

        # Load content and its summary from database
        with get_db() as db:
            content = db.query(Content).filter(Content.id == content_id).first()
            if not content:
                console.print(f"[red]Error:[/red] Content with ID {content_id} not found.")
                raise typer.Exit(1)

            # Get the most recent summary for this content
            summary = (
                db.query(Summary)
                .filter(Summary.content_id == content_id)
                .order_by(Summary.id.desc())
                .first()
            )
            if not summary:
                console.print(
                    f"[red]Error:[/red] No summary found for content ID {content_id}. "
                    "Run summarization first."
                )
                raise typer.Exit(1)

            content_title = content.title

            # Extract entities via GraphitiClient

            async def _extract() -> None:
                client = await GraphitiClient.create()
                try:
                    await client.add_content_summary(content, summary)
                finally:
                    client.close()

            run_async(_extract())

        if is_json_mode():
            output_result(
                {
                    "status": "success",
                    "content_id": content_id,
                    "title": content_title,
                    "message": f"Entities extracted from '{content_title}'",
                }
            )
        else:
            console.print(f"[green]Successfully extracted entities from:[/green] {content_title}")

    except GraphBackendUnavailableError as e:
        console.print(f"[red]Error:[/red] Graph backend is unavailable: {e}")
        raise typer.Exit(1)
    except ConnectionError as e:
        console.print(f"[red]Error:[/red] Graph database is unavailable: {e}")
        raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        error_msg = str(e).lower()
        if "connection" in error_msg or "neo4j" in error_msg or "refused" in error_msg:
            console.print("[red]Error:[/red] Graph database is unavailable.")
        else:
            console.print(f"[red]Error:[/red] Entity extraction failed: {e}")
        raise typer.Exit(1)


@app.command("query")
def query(
    query_text: Annotated[
        str,
        typer.Option(
            "--query",
            "-q",
            help="Text query to search the knowledge graph.",
        ),
    ],
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum number of results to return.",
        ),
    ] = 10,
) -> None:
    """Query the knowledge graph for entities and relationships.

    Performs a semantic search across the knowledge graph to find
    entities, relationships, and facts related to the query text.
    """
    console = Console()
    console.print(f"Querying knowledge graph for: [bold]{query_text}[/bold]...")

    try:
        from src.cli.adapters import search_graph_sync

        results = search_graph_sync(query_text, limit=limit)
    except ConnectionError as e:
        console.print(f"[red]Error:[/red] Graph database is unavailable: {e}")
        raise typer.Exit(1)
    except Exception as e:
        error_msg = str(e).lower()
        if "connection" in error_msg or "neo4j" in error_msg or "refused" in error_msg:
            console.print("[red]Error:[/red] Graph database is unavailable.")
        else:
            console.print(f"[red]Error:[/red] Graph query failed: {e}")
        raise typer.Exit(1)

    if not results:
        console.print("[yellow]No results found for the given query.[/yellow]")
        if is_json_mode():
            output_result({"results": [], "total": 0, "query": query_text})
        raise typer.Exit(0)

    # JSON output mode
    if is_json_mode():
        # Serialize results, handling any non-serializable types
        json.dump(
            {
                "results": results,
                "total": len(results),
                "query": query_text,
            },
            sys.stdout,
            default=str,
        )
        sys.stdout.write("\n")
        raise typer.Exit(0)

    # Rich table output
    console.print()
    console.print(f"Found [bold]{len(results)}[/bold] results.")
    console.print()

    table = Table(title=f"Knowledge Graph Results: '{query_text}'")
    table.add_column("#", style="dim", justify="right", width=4)
    table.add_column("Name / Fact", style="bold cyan", no_wrap=False, max_width=40)
    table.add_column("Type", style="magenta", max_width=15)
    table.add_column("Details", style="white", no_wrap=False, max_width=50)

    for idx, result in enumerate(results, start=1):
        # Handle both dict and object-style results
        if isinstance(result, dict):
            name = result.get("name", result.get("fact", str(result)))
            result_type = result.get("type", result.get("source", "unknown"))
            details = result.get("content", result.get("description", ""))
        else:
            # Handle Graphiti result objects with attribute access
            name = getattr(result, "name", getattr(result, "fact", str(result)))
            result_type = getattr(result, "type", getattr(result, "source", "unknown"))
            details = getattr(result, "content", getattr(result, "description", ""))

        # Truncate long details for display
        details_str = str(details) if details else ""
        if len(details_str) > 100:
            details_str = details_str[:97] + "..."

        table.add_row(
            str(idx),
            str(name),
            str(result_type),
            details_str,
        )

    console.print(table)
