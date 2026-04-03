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

import asyncio
import uuid
from datetime import datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from src.cli.output import is_json_mode, output_result
from src.services.agent_service import AgentInsightService, AgentTaskService, ApprovalService
from src.storage.database import get_db

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
    params: dict = {}
    if output:
        params["output_format"] = output
    if sources:
        params["sources"] = sources.split(",")

    with get_db() as db:
        task = AgentTaskService(db).create_task(
            prompt=prompt,
            task_type=task_type,
            persona=persona,
            source="user",
            params=params if params else None,
        )
        db.commit()
        task_id = str(task.id)

    # Enqueue for async execution
    try:
        from src.queue.setup import enqueue_queue_job

        asyncio.run(
            enqueue_queue_job(
                "execute_agent_task",
                {"task_id": task_id, "prompt": prompt, "persona": persona},
            )
        )
    except Exception:
        # Queue may not be available; task is still persisted
        pass

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
    with get_db() as db:
        svc = AgentTaskService(db)

        if task_id:
            try:
                tid = uuid.UUID(task_id)
            except ValueError:
                if is_json_mode():
                    output_result({"error": "Invalid task ID format"}, success=False)
                else:
                    console.print(f"[red]Invalid task ID:[/red] {task_id}")
                raise typer.Exit(code=1)

            task = svc.get_task(tid)
            if task is None:
                if is_json_mode():
                    output_result({"error": "Task not found"}, success=False)
                else:
                    console.print(f"[red]Task not found:[/red] {task_id}")
                raise typer.Exit(code=1)

            if is_json_mode():
                output_result(
                    {
                        "task_id": str(task.id),
                        "status": task.status,
                        "task_type": task.task_type,
                        "persona": task.persona_name,
                        "prompt": task.prompt,
                        "result": task.result,
                        "error": task.error_message,
                        "created_at": str(task.created_at) if task.created_at else None,
                        "started_at": str(task.started_at) if task.started_at else None,
                        "completed_at": str(task.completed_at) if task.completed_at else None,
                    }
                )
                return

            status_color = {
                "completed": "green",
                "failed": "red",
                "blocked": "yellow",
            }.get(task.status, "cyan")
            console.print(f"[bold]Task {task.id}[/bold]")
            console.print(f"  Status: [{status_color}]{task.status}[/{status_color}]")
            console.print(f"  Type: {task.task_type}")
            console.print(f"  Persona: {task.persona_name}")
            console.print(f"  Prompt: {task.prompt[:120]}")
            if task.error_message:
                console.print(f"  [red]Error:[/red] {task.error_message}")
            if task.result:
                console.print(f"  Result: {task.result}")
            console.print(f"  Created: {task.created_at}")
            if task.started_at:
                console.print(f"  Started: {task.started_at}")
            if task.completed_at:
                console.print(f"  Completed: {task.completed_at}")
        else:
            tasks, total = svc.list_tasks(limit=10)

            if is_json_mode():
                output_result(
                    {
                        "tasks": [
                            {
                                "task_id": str(t.id),
                                "status": t.status,
                                "task_type": t.task_type,
                                "persona": t.persona_name,
                                "prompt": t.prompt[:100],
                                "created_at": str(t.created_at) if t.created_at else None,
                            }
                            for t in tasks
                        ],
                        "total": total,
                    }
                )
                return

            table = Table(title=f"Recent Tasks ({total} total)")
            table.add_column("ID", style="cyan", max_width=36)
            table.add_column("Status")
            table.add_column("Type")
            table.add_column("Persona")
            table.add_column("Prompt", max_width=50)
            table.add_column("Created")

            for t in tasks:
                status_color = {
                    "completed": "green",
                    "failed": "red",
                    "blocked": "yellow",
                }.get(t.status, "white")
                table.add_row(
                    str(t.id)[:8] + "...",
                    f"[{status_color}]{t.status}[/{status_color}]",
                    t.task_type,
                    t.persona_name,
                    t.prompt[:50],
                    str(t.created_at)[:19] if t.created_at else "",
                )

            console.print(table)


@app.command("insights")
def list_insights(
    insight_type: Annotated[
        str | None, typer.Option("--type", help="Filter by insight type")
    ] = None,
    since: Annotated[str | None, typer.Option(help="ISO datetime filter")] = None,
    persona: Annotated[str | None, typer.Option(help="Filter by persona")] = None,
) -> None:
    """Browse generated insights."""
    since_dt: datetime | None = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            if is_json_mode():
                output_result({"error": f"Invalid datetime format: {since}"}, success=False)
            else:
                console.print(f"[red]Invalid datetime format:[/red] {since}")
            raise typer.Exit(code=1)

    with get_db() as db:
        insights, total = AgentInsightService(db).list_insights(
            insight_type=insight_type,
            since=since_dt,
            persona=persona,
        )

    if is_json_mode():
        output_result(
            {
                "insights": [
                    {
                        "id": str(i.id),
                        "type": i.insight_type,
                        "title": i.title,
                        "confidence": i.confidence,
                        "tags": i.tags,
                        "created_at": str(i.created_at) if i.created_at else None,
                    }
                    for i in insights
                ],
                "total": total,
            }
        )
        return

    table = Table(title=f"Agent Insights ({total} total)")
    table.add_column("ID", style="cyan")
    table.add_column("Type")
    table.add_column("Title")
    table.add_column("Confidence")
    table.add_column("Created")

    for i in insights:
        table.add_row(
            str(i.id)[:8] + "...",
            i.insight_type,
            i.title,
            f"{i.confidence:.2f}",
            str(i.created_at)[:19] if i.created_at else "",
        )

    console.print(table)


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
    try:
        rid = uuid.UUID(request_id)
    except ValueError:
        if is_json_mode():
            output_result({"error": "Invalid request ID format"}, success=False)
        else:
            console.print(f"[red]Invalid request ID:[/red] {request_id}")
        raise typer.Exit(code=1)

    with get_db() as db:
        req = ApprovalService(db).decide_request(rid, approved=True)
        db.commit()

    if req is None:
        if is_json_mode():
            output_result({"error": "Approval request not found"}, success=False)
        else:
            console.print(f"[red]Approval request not found:[/red] {request_id}")
        raise typer.Exit(code=1)

    if is_json_mode():
        output_result(
            {
                "request_id": str(req.id),
                "status": req.status,
                "action": req.action,
                "decided_at": str(req.decided_at) if req.decided_at else None,
            }
        )
        return

    console.print(f"[green]Approved:[/green] {req.id}")
    console.print(f"  Action: {req.action}")
    console.print(f"  Status: {req.status}")


@app.command("deny")
def deny_request(
    request_id: Annotated[str, typer.Argument(help="Approval request ID")],
    reason: str = typer.Option(..., help="Reason for denial"),
) -> None:
    """Deny a pending approval request with reason."""
    try:
        rid = uuid.UUID(request_id)
    except ValueError:
        if is_json_mode():
            output_result({"error": "Invalid request ID format"}, success=False)
        else:
            console.print(f"[red]Invalid request ID:[/red] {request_id}")
        raise typer.Exit(code=1)

    with get_db() as db:
        req = ApprovalService(db).decide_request(rid, approved=False, reason=reason)
        db.commit()

    if req is None:
        if is_json_mode():
            output_result({"error": "Approval request not found"}, success=False)
        else:
            console.print(f"[red]Approval request not found:[/red] {request_id}")
        raise typer.Exit(code=1)

    if is_json_mode():
        output_result(
            {
                "request_id": str(req.id),
                "status": req.status,
                "action": req.action,
                "reason": req.decision_reason,
                "decided_at": str(req.decided_at) if req.decided_at else None,
            }
        )
        return

    console.print(f"[red]Denied:[/red] {req.id}")
    console.print(f"  Action: {req.action}")
    console.print(f"  Reason: {reason}")
    console.print(f"  Status: {req.status}")
