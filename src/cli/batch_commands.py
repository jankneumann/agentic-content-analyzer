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

    result = {"jobs": jobs, "requests": requests}
    if is_json_mode():
        output_result(result)
        return

    typer.echo("\nBatch jobs by state:")
    if jobs:
        for state, count in sorted(jobs.items()):
            typer.echo(f"  {state:<14}{count:>6}")
    else:
        typer.echo("  (none)")
    typer.echo("\nBatch requests by status:")
    if requests:
        for st, count in sorted(requests.items()):
            typer.echo(f"  {st:<14}{count:>6}")
    else:
        typer.echo("  (none)")
