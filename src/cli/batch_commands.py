"""CLI ops commands for Gemini batch execution.

Only ``aca batch status`` is public. Maintenance is an internal leader-elected
worker activity, not a free-form CLI or queue mutation.
"""

from __future__ import annotations

import typer

from src.cli.output import guard_remote_backend, is_json_mode, output_result

app = typer.Typer(
    name="batch",
    help="Gemini batch execution status",
    no_args_is_help=True,
)


@app.command("status")
def status() -> None:
    """Show batch job/request counts by state (read-only)."""
    guard_remote_backend("batch status")
    from sqlalchemy import func

    from src.models.batch import BatchJob, BatchRequest as BatchRequestRow
    from src.storage.database import get_db

    with get_db() as db:
        jobs = dict(db.query(BatchJob.state, func.count()).group_by(BatchJob.state).all())
        requests = dict(
            db.query(BatchRequestRow.status, func.count()).group_by(BatchRequestRow.status).all()
        )
        recent_rows = db.query(BatchJob).order_by(BatchJob.created_at.desc()).limit(10).all()

    recent_jobs = [
        {
            "id": row.id,
            "provider_job_name": row.provider_job_name,
            "model_step": row.model_step,
            "model_id": row.model_id,
            "state": row.state,
            "request_count": row.request_count,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "error": row.error,
        }
        for row in recent_rows
    ]
    result = {"jobs": jobs, "requests": requests, "recent_jobs": recent_jobs}
    if is_json_mode():
        output_result(result)
        return

    typer.echo("\nBatch jobs by state:")
    if jobs:
        for state, count in sorted(jobs.items()):
            typer.echo(f"  {state:<14}{count:>6}")
    else:
        typer.echo("  (none)")
    typer.echo("\nRecent batch jobs:")
    if recent_jobs:
        for job in recent_jobs:
            typer.echo(
                f"  {job['state']:<12} {job['model_step']:<24} "
                f"{job['request_count']:>5} request(s)  {job['id']}"
            )
    else:
        typer.echo("  (none)")
    typer.echo("\nBatch requests by status:")
    if requests:
        for st, count in sorted(requests.items()):
            typer.echo(f"  {st:<14}{count:>6}")
    else:
        typer.echo("  (none)")
