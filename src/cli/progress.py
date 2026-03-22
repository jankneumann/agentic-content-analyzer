"""SSE progress display for CLI commands.

Consumes Server-Sent Events from the API and displays progress
using Rich spinners (human mode) or final JSON (JSON mode).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.cli.api_client import ApiClient

logger = logging.getLogger(__name__)


def stream_job_progress(
    client: ApiClient,
    task_id: str,
    label: str,
    *,
    stream_type: str = "ingest",
    json_mode: bool = False,
) -> dict:
    """Stream SSE events and display progress. Returns final event data.

    Args:
        client: ApiClient instance
        task_id: Job/task ID to track
        label: Human-readable label (e.g., "Gmail ingestion")
        stream_type: "ingest", "summarize", or "pipeline"
        json_mode: If True, suppress Rich output and only return final data

    Returns:
        Dict with final job status data from the terminal SSE event.
    """
    # Select the correct SSE stream method
    stream_methods = {
        "ingest": client.stream_ingest_status,
        "summarize": client.stream_summarize_status,
        "pipeline": lambda tid: client.stream_pipeline_status(int(tid)),
    }
    stream_fn = stream_methods.get(stream_type, client.stream_ingest_status)

    last_data: dict = {}

    if json_mode:
        # Silent mode — just consume events and return final
        for event in stream_fn(task_id):
            try:
                last_data = event.json()
            except (json.JSONDecodeError, ValueError):
                continue
            if _is_terminal(last_data):
                break
        return last_data

    # Rich mode — show spinner with progress updates
    from rich.console import Console

    console = Console(stderr=True)
    with console.status(f"[bold blue]{label}...", spinner="dots") as status:
        for event in stream_fn(task_id):
            try:
                last_data = event.json()
            except (json.JSONDecodeError, ValueError):
                continue

            progress = last_data.get("progress", 0)
            message = last_data.get("message", "")
            status_str = last_data.get("status", "")

            if message:
                status.update(f"[bold blue]{label}[/] [{progress}%] {message}")
            elif status_str:
                status.update(f"[bold blue]{label}[/] [{progress}%] {status_str}")

            if _is_terminal(last_data):
                break

    return last_data


def display_ingest_result(
    result: dict,
    source: str,
    *,
    json_mode: bool = False,
) -> None:
    """Display the final ingestion result.

    Args:
        result: Final SSE event data dict
        source: Source name (e.g., "gmail")
        json_mode: Output as JSON if True
    """
    if json_mode:
        from src.cli.output import output_result

        output_result(
            {
                "source": source,
                "status": result.get("status", "unknown"),
                "processed": result.get("processed", 0),
                "message": result.get("message", ""),
            }
        )
        return

    from rich.console import Console

    console = Console()
    status = result.get("status", "unknown")
    processed = result.get("processed", 0)
    message = result.get("message", "")

    if status in ("completed", "complete"):
        console.print(f"[green]Ingested {processed} items from {source}[/]")
        if message:
            console.print(f"  {message}")
    elif status == "error":
        error = result.get("error", message or "Unknown error")
        Console(stderr=True).print(f"[red]{source} ingestion failed:[/] {error}")
    else:
        console.print(f"[yellow]{source} ingestion {status}:[/] {message}")


def _is_terminal(data: dict) -> bool:
    """Check if SSE event data represents a terminal job state."""
    status = data.get("status", "")
    return status in ("completed", "complete", "error", "failed")
