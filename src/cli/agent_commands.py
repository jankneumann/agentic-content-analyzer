"""CLI commands for agentic analysis.

Provides task submission, status monitoring, insight browsing,
persona listing, schedule management, and approval handling.

Usage:
    aca agent task "What are the emerging trends in AI agents?"
    aca agent status <task_id>
    aca agent insights --type trend --since 2025-01-01
    aca agent personas
    aca agent schedule --enable trend_detection_tech
    aca agent approve <request_id>
    aca agent deny <request_id> --reason "Too broad"
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from src.cli.output import is_json_mode, output_result

app = typer.Typer(help="Agentic analysis commands.")

console = Console()


@app.command("task")
def submit_task(
    prompt: Annotated[str, typer.Argument(help="The task prompt or question")],
    persona: Annotated[str, typer.Option(help="Persona to use")] = "default",
    output: Annotated[str | None, typer.Option(help="Output format override")] = None,
    sources: Annotated[str | None, typer.Option(help="Comma-separated source types")] = None,
    task_type: Annotated[str, typer.Option("--type", help="Task type")] = "research",
) -> None:
    """Submit an agent task."""
    import uuid

    task_id = str(uuid.uuid4())

    if is_json_mode():
        output_result({"task_id": task_id, "status": "received", "prompt": prompt[:200]})
        return

    console.print(f"[green]Task submitted:[/green] {task_id}")
    console.print(f"  Prompt: {prompt[:80]}...")
    console.print(f"  Persona: {persona}")
    console.print(f"  Type: {task_type}")
    if output:
        console.print(f"  Output: {output}")
    if sources:
        console.print(f"  Sources: {sources}")


@app.command("status")
def task_status(
    task_id: Annotated[str | None, typer.Argument(help="Task ID to check")] = None,
) -> None:
    """View task status.

    If no task_id is given, lists recent tasks.
    """
    if task_id:
        if is_json_mode():
            output_result(
                {"task_id": task_id, "status": "unknown", "message": "DB integration pending"}
            )
            return
        console.print(f"[yellow]Task {task_id}:[/yellow] status lookup not yet wired to DB")
    else:
        if is_json_mode():
            output_result({"tasks": [], "message": "DB integration pending"})
            return
        console.print("[dim]No recent tasks (DB integration pending)[/dim]")


@app.command("insights")
def list_insights(
    insight_type: Annotated[
        str | None, typer.Option("--type", help="Filter by insight type")
    ] = None,
    since: Annotated[str | None, typer.Option(help="ISO datetime filter")] = None,
    persona: Annotated[str | None, typer.Option(help="Filter by persona")] = None,
) -> None:
    """Browse generated insights."""
    if is_json_mode():
        output_result({"insights": [], "message": "DB integration pending"})
        return

    table = Table(title="Agent Insights")
    table.add_column("ID", style="cyan")
    table.add_column("Type")
    table.add_column("Title")
    table.add_column("Confidence")
    table.add_column("Created")

    # Stub: no rows until DB integration
    console.print(table)
    console.print("[dim]No insights found (DB integration pending)[/dim]")


@app.command("personas")
def list_personas() -> None:
    """List available personas."""
    from pathlib import Path

    import yaml  # type: ignore[import-untyped]

    personas_dir = Path("settings/personas")

    if is_json_mode():
        personas = []
        if personas_dir.exists():
            for f in sorted(personas_dir.glob("*.yaml")):
                try:
                    data = yaml.safe_load(f.read_text()) or {}
                    personas.append({"name": f.stem, "description": data.get("description", "")})
                except Exception:
                    pass
        output_result({"personas": personas})
        return

    table = Table(title="Available Personas")
    table.add_column("Name", style="cyan")
    table.add_column("Description")

    if personas_dir.exists():
        for f in sorted(personas_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text()) or {}
                table.add_row(f.stem, data.get("description", ""))
            except Exception:
                table.add_row(f.stem, "[red]parse error[/red]")

    console.print(table)


@app.command("schedule")
def manage_schedule(
    enable: Annotated[str | None, typer.Option(help="Schedule ID to enable")] = None,
    disable: Annotated[str | None, typer.Option(help="Schedule ID to disable")] = None,
) -> None:
    """Manage proactive schedules.

    Without options, lists all schedules. Use --enable or --disable
    to toggle a specific schedule entry.
    """
    from src.agents.scheduler.scheduler import AgentScheduler

    scheduler = AgentScheduler()
    scheduler.load_schedules()

    if enable:
        if scheduler.enable_schedule(enable):
            console.print(f"[green]Enabled schedule:[/green] {enable}")
        else:
            console.print(f"[red]Schedule not found:[/red] {enable}")
        return

    if disable:
        if scheduler.disable_schedule(disable):
            console.print(f"[yellow]Disabled schedule:[/yellow] {disable}")
        else:
            console.print(f"[red]Schedule not found:[/red] {disable}")
        return

    # List all schedules
    if is_json_mode():
        output_result(
            {
                "schedules": [
                    {
                        "id": s.id,
                        "cron": s.cron,
                        "task_type": s.task_type,
                        "persona": s.persona,
                        "enabled": s.enabled,
                        "description": s.description,
                    }
                    for s in scheduler.list_schedules()
                ]
            }
        )
        return

    table = Table(title="Proactive Schedules")
    table.add_column("ID", style="cyan")
    table.add_column("Cron")
    table.add_column("Type")
    table.add_column("Persona")
    table.add_column("Enabled")
    table.add_column("Description")

    for s in scheduler.list_schedules():
        enabled_str = "[green]yes[/green]" if s.enabled else "[red]no[/red]"
        table.add_row(s.id, s.cron, s.task_type, s.persona, enabled_str, s.description)

    console.print(table)


@app.command("approve")
def approve_request(
    request_id: Annotated[str, typer.Argument(help="Approval request ID")],
) -> None:
    """Approve a pending approval request."""
    if is_json_mode():
        output_result({"request_id": request_id, "status": "approved"})
        return
    console.print(f"[green]Approved:[/green] {request_id}")
    console.print("[dim]Note: DB integration pending[/dim]")


@app.command("deny")
def deny_request(
    request_id: Annotated[str, typer.Argument(help="Approval request ID")],
    reason: str = typer.Option(..., help="Reason for denial"),
) -> None:
    """Deny a pending approval request with reason."""
    if is_json_mode():
        output_result({"request_id": request_id, "status": "denied", "reason": reason})
        return
    console.print(f"[red]Denied:[/red] {request_id}")
    console.print(f"  Reason: {reason}")
    console.print("[dim]Note: DB integration pending[/dim]")
