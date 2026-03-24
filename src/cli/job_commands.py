"""CLI commands for job queue management.

In HTTP mode (default), commands call the backend API via httpx.
In direct mode (--direct flag or API unreachable), commands call
queue functions directly (legacy inline behavior).

Usage:
    aca jobs list
    aca jobs show <job-id>
    aca jobs retry <job-id>
    aca jobs retry --failed
    aca jobs cleanup --older-than 30d
    aca jobs history [--since 1d] [--type summarize] [--status completed]
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import httpx
import typer

from src.cli.adapters import run_async
from src.cli.output import is_direct_mode, is_json_mode, output_result
from src.models.jobs import TYPE_ALIASES, JobHistoryItem, JobListItem, JobRecord, JobStatus

app = typer.Typer(help="Manage background jobs in the queue.")


def _truncate(text: str | None, max_len: int = 40) -> str:
    """Truncate text with ellipsis for table display.

    Args:
        text: Text to truncate (None-safe)
        max_len: Maximum length before truncation

    Returns:
        Truncated text with ellipsis if needed
    """
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _format_datetime(dt: datetime | None) -> str:
    """Format datetime for display.

    Args:
        dt: Datetime to format (None-safe)

    Returns:
        Formatted datetime string or empty string
    """
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")


def _format_job_summary(job: JobListItem | JobRecord) -> dict[str, Any]:
    """Format a job into a summary dictionary for JSON output.

    Args:
        job: Job model instance

    Returns:
        Dictionary with key job fields
    """
    result: dict[str, Any] = {
        "id": job.id,
        "entrypoint": job.entrypoint,
        "status": job.status.value,
        "progress": job.progress if hasattr(job, "progress") else 0,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }
    if job.error:
        result["error"] = job.error
    if hasattr(job, "retry_count"):
        result["retry_count"] = job.retry_count
    if hasattr(job, "started_at") and job.started_at:
        result["started_at"] = job.started_at.isoformat()
    if hasattr(job, "completed_at") and job.completed_at:
        result["completed_at"] = job.completed_at.isoformat()
    return result


def _get_status_color(status: JobStatus) -> str:
    """Get Rich color for job status.

    Args:
        status: Job status enum

    Returns:
        Rich color name
    """
    colors = {
        JobStatus.QUEUED: "yellow",
        JobStatus.IN_PROGRESS: "blue",
        JobStatus.COMPLETED: "green",
        JobStatus.FAILED: "red",
    }
    return colors.get(status, "white")


def _parse_duration(duration_str: str) -> int:
    """Parse duration string like '30d', '7d' into days.

    Args:
        duration_str: Duration string (e.g., '30d', '7d', '14d')

    Returns:
        Number of days

    Raises:
        typer.BadParameter: If format is invalid
    """
    match = re.match(r"^(\d+)d$", duration_str.strip().lower())
    if not match:
        raise typer.BadParameter(
            f"Invalid duration format: '{duration_str}'. Use format like '30d' for 30 days."
        )
    return int(match.group(1))


# ---------------------------------------------------------------------------
# aca jobs list
# ---------------------------------------------------------------------------


def _list_jobs_direct(status: str | None, entrypoint: str | None, limit: int, offset: int) -> None:
    """Direct job listing (legacy inline path)."""
    from src.queue.setup import list_jobs as queue_list_jobs

    # Parse and validate status filter
    status_filter: JobStatus | None = None
    if status:
        try:
            status_filter = JobStatus(status.lower())
        except ValueError:
            valid = ", ".join(s.value for s in JobStatus)
            typer.echo(f"Error: Invalid status '{status}'. Valid options: {valid}")
            raise typer.Exit(1)

    try:
        jobs, total = run_async(
            queue_list_jobs(
                status=status_filter,
                entrypoint=entrypoint,
                limit=limit,
                offset=offset,
            )
        )
    except Exception as e:
        typer.echo(f"Error listing jobs: {e}")
        raise typer.Exit(1)

    if not jobs:
        if is_json_mode():
            output_result({"jobs": [], "total": 0, "offset": offset, "limit": limit})
        else:
            typer.echo("No jobs found matching the criteria.")
        return

    if is_json_mode():
        output_result(
            {
                "jobs": [_format_job_summary(j) for j in jobs],
                "total": total,
                "offset": offset,
                "limit": limit,
            }
        )
        return

    # Rich table display
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title=f"Jobs ({len(jobs)} of {total} shown)")

    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Entrypoint", style="white", max_width=25)
    table.add_column("Status", style="bold")
    table.add_column("Progress", justify="right")
    table.add_column("Error", style="red", max_width=30)
    table.add_column("Created", style="dim")

    for job in jobs:
        status_color = _get_status_color(job.status)
        status_display = f"[{status_color}]{job.status.value}[/{status_color}]"

        progress_display = f"{job.progress}%" if job.progress > 0 else "-"

        table.add_row(
            str(job.id),
            _truncate(job.entrypoint, 25),
            status_display,
            progress_display,
            _truncate(job.error, 30),
            _format_datetime(job.created_at),
        )

    console.print(table)

    # Pagination info
    showing_end = min(offset + limit, total)
    console.print(f"\nShowing {offset + 1}-{showing_end} of {total} jobs.")
    if total > offset + limit:
        console.print(f"[dim]Use --offset {offset + limit} to see more.[/dim]")


@app.command("list")
def list_jobs(
    status: Annotated[
        str | None,
        typer.Option(
            "--status",
            "-s",
            help="Filter by status: queued, in_progress, completed, failed",
        ),
    ] = None,
    entrypoint: Annotated[
        str | None,
        typer.Option(
            "--entrypoint",
            "-e",
            help="Filter by task entrypoint (e.g., 'summarize_content')",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            help="Maximum number of jobs to display (max 100)",
        ),
    ] = 20,
    offset: Annotated[
        int,
        typer.Option(
            "--offset",
            help="Pagination offset",
        ),
    ] = 0,
) -> None:
    """List jobs in the queue with optional filters.

    Shows job ID, entrypoint, status, progress, and creation time.
    Use --status to filter by job state, --entrypoint to filter by task type.

    Examples:
        aca jobs list
        aca jobs list --status failed
        aca jobs list --entrypoint summarize_content
        aca jobs list --limit 50 --offset 100
    """
    if is_direct_mode():
        return _list_jobs_direct(status, entrypoint, limit, offset)

    try:
        from src.cli.api_client import get_api_client

        client = get_api_client()
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if entrypoint:
            params["entrypoint"] = entrypoint
        response = client.list_jobs(**params)
    except httpx.ConnectError:
        if not is_json_mode():
            from rich.console import Console

            Console(stderr=True).print(
                "[yellow]Backend unavailable — listing jobs directly...[/yellow]"
            )
        _list_jobs_direct(status, entrypoint, limit, offset)
        return

    if is_json_mode():
        output_result(response)
        return

    # Parse API response
    jobs_data = response.get("jobs", [])
    total = response.get("total", len(jobs_data))

    if not jobs_data:
        typer.echo("No jobs found matching the criteria.")
        return

    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title=f"Jobs ({len(jobs_data)} of {total} shown)")

    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Entrypoint", style="white", max_width=25)
    table.add_column("Status", style="bold")
    table.add_column("Progress", justify="right")
    table.add_column("Error", style="red", max_width=30)
    table.add_column("Created", style="dim")

    for job in jobs_data:
        status_val = job.get("status", "")
        # Map status string to color
        color_map = {
            "queued": "yellow",
            "in_progress": "blue",
            "completed": "green",
            "failed": "red",
        }
        status_color = color_map.get(status_val, "white")
        status_display = f"[{status_color}]{status_val}[/{status_color}]"

        progress = job.get("progress", 0)
        progress_display = f"{progress}%" if progress > 0 else "-"

        table.add_row(
            str(job.get("id", "")),
            _truncate(job.get("entrypoint", ""), 25),
            status_display,
            progress_display,
            _truncate(job.get("error"), 30),
            job.get("created_at", ""),
        )

    console.print(table)

    # Pagination info
    showing_end = min(offset + limit, total)
    console.print(f"\nShowing {offset + 1}-{showing_end} of {total} jobs.")
    if total > offset + limit:
        console.print(f"[dim]Use --offset {offset + limit} to see more.[/dim]")


# ---------------------------------------------------------------------------
# aca jobs history (direct-only — uses queue internals not exposed via API)
# ---------------------------------------------------------------------------


def _format_history_item(item: JobHistoryItem) -> dict[str, Any]:
    """Format a history item for JSON output."""
    result: dict[str, Any] = {
        "id": item.id,
        "entrypoint": item.entrypoint,
        "task_label": item.task_label,
        "status": item.status.value,
        "content_id": item.content_id,
        "description": item.description,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
    if item.error:
        result["error"] = item.error
    if item.started_at:
        result["started_at"] = item.started_at.isoformat()
    if item.completed_at:
        result["completed_at"] = item.completed_at.isoformat()
    return result


@app.command("history")
def history(
    since: Annotated[
        str | None,
        typer.Option(
            "--since",
            "-S",
            help="Time filter: 1d, 7d, 30d, or ISO datetime",
        ),
    ] = None,
    last: Annotated[
        int | None,
        typer.Option(
            "--last",
            "-n",
            help="Show last N entries (overrides --since)",
        ),
    ] = None,
    task_type: Annotated[
        str | None,
        typer.Option(
            "--type",
            "-t",
            help="Filter by task type: summarize, batch, extract, process, ingest",
        ),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option(
            "--status",
            help="Filter by status: queued, in_progress, completed, failed",
        ),
    ] = None,
) -> None:
    """Show task execution history with human-readable context.

    Displays an enriched view of job history including task labels,
    content descriptions, and timing information.

    Always runs directly (uses queue internals not exposed via API).

    Examples:
        aca jobs history
        aca jobs history --since 1d
        aca jobs history --last 10
        aca jobs history --type summarize --status completed
        aca jobs history --since 7d --type ingest
    """
    from src.queue.setup import list_job_history

    # Parse time filter
    since_dt: datetime | None = None
    if since:
        match = re.match(r"^(\d+)d$", since.strip().lower())
        if match:
            since_dt = datetime.now(UTC) - timedelta(days=int(match.group(1)))
        else:
            try:
                since_dt = datetime.fromisoformat(since)
            except ValueError:
                typer.echo(
                    f"Error: Invalid --since format: '{since}'. "
                    "Use shorthand (1d, 7d, 30d) or ISO datetime."
                )
                raise typer.Exit(1)

    # Resolve task type alias
    entrypoint: str | None = None
    if task_type:
        entrypoint = TYPE_ALIASES.get(task_type.lower())
        if not entrypoint:
            valid = ", ".join(TYPE_ALIASES.keys())
            typer.echo(f"Error: Unknown --type '{task_type}'. Valid options: {valid}")
            raise typer.Exit(1)

    # Parse status
    status_filter: JobStatus | None = None
    if status:
        try:
            status_filter = JobStatus(status.lower())
        except ValueError:
            valid = ", ".join(s.value for s in JobStatus)
            typer.echo(f"Error: Invalid status '{status}'. Valid options: {valid}")
            raise typer.Exit(1)

    limit = last if last else 20

    try:
        items, total = run_async(
            list_job_history(
                since=since_dt,
                status=status_filter,
                entrypoint=entrypoint,
                limit=limit,
                offset=0,
            )
        )
    except Exception as e:
        typer.echo(f"Error fetching job history: {e}")
        raise typer.Exit(1)

    if not items:
        if is_json_mode():
            output_result({"jobs": [], "total": 0, "offset": 0, "limit": limit})
        else:
            typer.echo("No jobs found matching the criteria.")
        return

    if is_json_mode():
        output_result(
            {
                "jobs": [_format_history_item(i) for i in items],
                "total": total,
                "offset": 0,
                "limit": limit,
            }
        )
        return

    # Rich table display
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title=f"Task History ({len(items)} of {total} shown)")

    table.add_column("Date/Time", style="dim", no_wrap=True)
    table.add_column("Task", style="white", max_width=20)
    table.add_column("Content ID", justify="right", style="cyan")
    table.add_column("Job ID", justify="right", style="cyan")
    table.add_column("Description", max_width=40)
    table.add_column("Status", style="bold")

    for item in items:
        status_color = _get_status_color(item.status)
        status_display = f"[{status_color}]{item.status.value}[/{status_color}]"

        table.add_row(
            _format_datetime(item.created_at),
            item.task_label,
            str(item.content_id) if item.content_id else "-",
            str(item.id),
            _truncate(item.description, 40),
            status_display,
        )

    console.print(table)

    if total > len(items):
        console.print(f"\n[dim]Showing {len(items)} of {total} total entries.[/dim]")


# ---------------------------------------------------------------------------
# aca jobs show
# ---------------------------------------------------------------------------


def _show_job_direct(job_id: int) -> None:
    """Direct job detail display (legacy inline path)."""
    from src.queue.setup import get_job_status

    try:
        job = run_async(get_job_status(job_id))
    except Exception as e:
        typer.echo(f"Error fetching job: {e}")
        raise typer.Exit(1)

    if not job:
        typer.echo(f"Error: Job {job_id} not found.")
        raise typer.Exit(1)

    if is_json_mode():
        output_result(_format_job_summary(job))
        return

    # Rich panel display
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    # Status with color
    status_color = _get_status_color(job.status)

    # Build details table
    details = Table.grid(padding=(0, 2))
    details.add_column(style="bold")
    details.add_column()

    details.add_row("ID:", str(job.id))
    details.add_row("Entrypoint:", job.entrypoint)
    details.add_row("Status:", f"[{status_color}]{job.status.value}[/{status_color}]")
    details.add_row("Priority:", str(job.priority))
    details.add_row("Retry Count:", str(job.retry_count))
    details.add_row("Progress:", f"{job.progress}%")
    if job.progress_message:
        details.add_row("Message:", job.progress_message)

    details.add_row("", "")  # Spacer
    details.add_row("Created:", _format_datetime(job.created_at))
    if job.started_at:
        details.add_row("Started:", _format_datetime(job.started_at))
    if job.completed_at:
        details.add_row("Completed:", _format_datetime(job.completed_at))

    if job.error:
        details.add_row("", "")  # Spacer
        details.add_row("Error:", f"[red]{job.error}[/red]")

    console.print(
        Panel(
            details,
            title=f"[bold]Job #{job.id}[/bold]",
            border_style="blue",
        )
    )

    # Show payload if non-empty (excluding progress fields)
    payload_display = {k: v for k, v in job.payload.items() if k not in ("progress", "message")}
    if payload_display:
        console.print()
        console.print("[bold]Payload:[/bold]")
        import json

        console.print(json.dumps(payload_display, indent=2, default=str))


@app.command("show")
def show_job(
    job_id: Annotated[
        int,
        typer.Argument(help="ID of the job to view"),
    ],
) -> None:
    """Show detailed information about a specific job.

    Displays all job metadata including payload, priority, retry count,
    and timestamps.

    Example:
        aca jobs show 123
    """
    if is_direct_mode():
        return _show_job_direct(job_id)

    try:
        from src.cli.api_client import get_api_client

        client = get_api_client()
        response = client.get_job(job_id)
    except httpx.ConnectError:
        if not is_json_mode():
            from rich.console import Console

            Console(stderr=True).print(
                "[yellow]Backend unavailable — fetching job directly...[/yellow]"
            )
        _show_job_direct(job_id)
        return

    if is_json_mode():
        output_result(response)
        return

    # Rich panel display from API response
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    status_val = response.get("status", "")
    color_map = {
        "queued": "yellow",
        "in_progress": "blue",
        "completed": "green",
        "failed": "red",
    }
    status_color = color_map.get(status_val, "white")

    # Build details table
    details = Table.grid(padding=(0, 2))
    details.add_column(style="bold")
    details.add_column()

    details.add_row("ID:", str(response.get("id", "")))
    details.add_row("Entrypoint:", response.get("entrypoint", ""))
    details.add_row("Status:", f"[{status_color}]{status_val}[/{status_color}]")
    details.add_row("Priority:", str(response.get("priority", 0)))
    details.add_row("Retry Count:", str(response.get("retry_count", 0)))
    progress = response.get("progress", 0)
    details.add_row("Progress:", f"{progress}%")
    progress_message = response.get("progress_message")
    if progress_message:
        details.add_row("Message:", progress_message)

    details.add_row("", "")  # Spacer
    details.add_row("Created:", response.get("created_at", ""))
    started_at = response.get("started_at")
    if started_at:
        details.add_row("Started:", started_at)
    completed_at = response.get("completed_at")
    if completed_at:
        details.add_row("Completed:", completed_at)

    error = response.get("error")
    if error:
        details.add_row("", "")  # Spacer
        details.add_row("Error:", f"[red]{error}[/red]")

    console.print(
        Panel(
            details,
            title=f"[bold]Job #{response.get('id', job_id)}[/bold]",
            border_style="blue",
        )
    )

    # Show payload if present
    payload = response.get("payload", {})
    payload_display = {k: v for k, v in payload.items() if k not in ("progress", "message")}
    if payload_display:
        console.print()
        console.print("[bold]Payload:[/bold]")
        import json

        console.print(json.dumps(payload_display, indent=2, default=str))


# ---------------------------------------------------------------------------
# aca jobs retry
# ---------------------------------------------------------------------------


def _retry_job_direct(job_id: int | None, failed: bool) -> None:
    """Direct job retry (legacy inline path)."""
    from src.queue.setup import list_jobs as queue_list_jobs, retry_failed_job

    if failed:
        # Bulk retry all failed jobs
        try:
            jobs, _total = run_async(queue_list_jobs(status=JobStatus.FAILED, limit=100))
        except Exception as e:
            typer.echo(f"Error listing failed jobs: {e}")
            raise typer.Exit(1)

        if not jobs:
            if is_json_mode():
                output_result({"retried_count": 0, "message": "No failed jobs to retry"})
            else:
                typer.echo("No failed jobs to retry.")
            return

        retried_count = 0
        failed_retries: list[dict[str, Any]] = []

        for job in jobs:
            try:
                result = run_async(retry_failed_job(job.id))
                if result:
                    retried_count += 1
                else:
                    failed_retries.append({"id": job.id, "error": "Not retryable"})
            except Exception as e:
                failed_retries.append({"id": job.id, "error": str(e)})

        if is_json_mode():
            output_result(
                {
                    "retried_count": retried_count,
                    "failed_count": len(failed_retries),
                    "failures": failed_retries,
                }
            )
        else:
            typer.echo(
                typer.style(
                    f"Retried {retried_count} failed job(s).",
                    fg=typer.colors.GREEN,
                )
            )
            if failed_retries:
                typer.echo(
                    typer.style(
                        f"Failed to retry {len(failed_retries)} job(s).",
                        fg=typer.colors.YELLOW,
                    )
                )
    else:
        # Single job retry
        assert job_id is not None
        try:
            result = run_async(retry_failed_job(job_id))
        except Exception as e:
            typer.echo(f"Error retrying job: {e}")
            raise typer.Exit(1)

        if not result:
            typer.echo(f"Error: Job {job_id} not found or is not in failed status.")
            raise typer.Exit(1)

        if is_json_mode():
            output_result(_format_job_summary(result))
        else:
            typer.echo(
                typer.style(
                    f"Job {job_id} re-enqueued for processing (retry #{result.retry_count}).",
                    fg=typer.colors.GREEN,
                )
            )


@app.command("retry")
def retry_job(
    job_id: Annotated[
        int | None,
        typer.Argument(help="ID of the failed job to retry"),
    ] = None,
    failed: Annotated[
        bool,
        typer.Option(
            "--failed",
            "-f",
            help="Retry all failed jobs (bulk operation)",
        ),
    ] = False,
) -> None:
    """Retry a failed job or all failed jobs.

    Re-enqueues the job(s) for processing. Only jobs with status 'failed'
    can be retried.

    Examples:
        aca jobs retry 123
        aca jobs retry --failed
    """
    if not job_id and not failed:
        typer.echo("Error: Provide a job ID or use --failed for bulk retry.")
        raise typer.Exit(1)

    if job_id and failed:
        typer.echo("Error: Cannot use both job ID and --failed together.")
        raise typer.Exit(1)

    if is_direct_mode():
        return _retry_job_direct(job_id, failed)

    # HTTP mode: single job retry only (bulk --failed uses direct path)
    if failed:
        # Bulk retry not exposed via single API call — use direct path
        if not is_json_mode():
            from rich.console import Console

            Console(stderr=True).print("[yellow]Bulk retry uses direct mode...[/yellow]")
        return _retry_job_direct(job_id, failed)

    assert job_id is not None
    try:
        from src.cli.api_client import get_api_client

        client = get_api_client()
        response = client.retry_job(job_id)
    except httpx.ConnectError:
        if not is_json_mode():
            from rich.console import Console

            Console(stderr=True).print(
                "[yellow]Backend unavailable — retrying job directly...[/yellow]"
            )
        _retry_job_direct(job_id, failed)
        return

    if is_json_mode():
        output_result(response)
    else:
        retry_count = response.get("retry_count", "?")
        typer.echo(
            typer.style(
                f"Job {job_id} re-enqueued for processing (retry #{retry_count}).",
                fg=typer.colors.GREEN,
            )
        )


# ---------------------------------------------------------------------------
# aca jobs cleanup (direct-only — uses queue internals not exposed via API)
# ---------------------------------------------------------------------------


@app.command("cleanup")
def cleanup_jobs(
    older_than: Annotated[
        str,
        typer.Option(
            "--older-than",
            "-o",
            help="Delete completed jobs older than this duration (e.g., '30d' for 30 days)",
        ),
    ] = "30d",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            help="Show what would be deleted without actually deleting",
        ),
    ] = False,
) -> None:
    """Clean up old completed jobs from the queue.

    Only deletes jobs with status 'completed'. Never deletes queued,
    in_progress, or failed jobs.

    Always runs directly (uses queue internals not exposed via API).

    Examples:
        aca jobs cleanup --older-than 30d
        aca jobs cleanup --older-than 7d --dry-run
    """
    from src.queue.setup import cleanup_old_jobs, list_jobs as queue_list_jobs

    try:
        days = _parse_duration(older_than)
    except typer.BadParameter as e:
        typer.echo(f"Error: {e}")
        raise typer.Exit(1)

    if dry_run:
        # Count completed jobs that would be deleted
        try:
            jobs, total = run_async(queue_list_jobs(status=JobStatus.COMPLETED, limit=100))
        except Exception as e:
            typer.echo(f"Error listing jobs: {e}")
            raise typer.Exit(1)

        # Count jobs older than threshold
        cutoff = datetime.now(UTC) - timedelta(days=days)
        old_jobs = [j for j in jobs if j.created_at and j.created_at < cutoff]

        if is_json_mode():
            output_result(
                {
                    "dry_run": True,
                    "older_than_days": days,
                    "would_delete_count": len(old_jobs),
                    "total_completed": total,
                }
            )
        else:
            typer.echo(
                f"[Dry run] Would delete {len(old_jobs)} completed job(s) older than {days} days."
            )
            typer.echo(f"Total completed jobs in queue: {total}")
            typer.echo("\nRun without --dry-run to actually delete.")
        return

    try:
        deleted_count = run_async(cleanup_old_jobs(older_than_days=days))
    except Exception as e:
        typer.echo(f"Error cleaning up jobs: {e}")
        raise typer.Exit(1)

    if is_json_mode():
        output_result(
            {
                "deleted_count": deleted_count,
                "older_than_days": days,
            }
        )
    else:
        typer.echo(
            typer.style(
                f"Cleaned up {deleted_count} completed job(s) older than {days} days.",
                fg=typer.colors.GREEN,
            )
        )
