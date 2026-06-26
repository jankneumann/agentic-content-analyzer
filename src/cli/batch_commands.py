"""CLI ops commands for Gemini batch execution.

Usage:
    aca batch status          # read: job/request counts by state
    aca batch flush           # manual trigger: submit ripe pending groups
    aca batch poll            # manual trigger: poll jobs + run sync fallback

``status`` is read-only. ``flush``/``poll`` run the same idempotent sweeps the
queue workers run — exposed here for operators to force a cycle without waiting
for the interval driver. They are no-ops when there's nothing to do.
"""

from __future__ import annotations

import typer

from src.cli.output import guard_remote_backend, is_json_mode, output_result

app = typer.Typer(
    name="batch",
    help="Gemini batch execution — status and manual submit/poll triggers",
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


@app.command("flush")
def flush() -> None:
    """Submit ripe pending request groups now (manual trigger)."""
    guard_remote_backend("batch flush")
    import asyncio

    from src.config.models import get_model_config
    from src.services.batch.workers import run_batch_submit
    from src.services.llm_router import LLMRouter
    from src.storage.database import get_db

    model_config = get_model_config()
    cfg = model_config.batch_config
    router = LLMRouter(model_config)

    with get_db() as db:
        summary = asyncio.run(
            run_batch_submit(
                db,
                router,
                flush_max_requests=cfg["flush_max_requests"],
                flush_max_wait_minutes=cfg["flush_max_wait_minutes"],
            )
        )

    result = {
        "jobs_created": summary.jobs_created,
        "requests_submitted": summary.requests_submitted,
        "groups_held": summary.groups_held,
    }
    if is_json_mode():
        output_result(result)
        return
    typer.echo(
        f"Flushed: {summary.jobs_created} job(s), "
        f"{summary.requests_submitted} request(s) submitted, "
        f"{summary.groups_held} group(s) held under threshold."
    )


@app.command("poll")
def poll() -> None:
    """Poll open jobs, reconcile results, and run synchronous fallback."""
    guard_remote_backend("batch poll")
    import asyncio

    from src.config.models import get_model_config
    from src.services.batch.workers import run_batch_poll, run_sync_fallback
    from src.services.llm_router import LLMRouter
    from src.storage.database import get_db

    model_config = get_model_config()
    router = LLMRouter(model_config)

    with get_db() as db:
        poll_summary = asyncio.run(run_batch_poll(db, router))
        fallback_summary = asyncio.run(run_sync_fallback(db, router))

    result = {
        "jobs_polled": poll_summary.jobs_polled,
        "requests_reconciled": poll_summary.requests_reconciled,
        "requests_fallback": poll_summary.requests_fallback,
        "jobs_still_running": poll_summary.jobs_still_running,
        "fallback_recovered": fallback_summary.requests_recovered,
        "fallback_failed": fallback_summary.requests_failed,
    }
    if is_json_mode():
        output_result(result)
        return
    typer.echo(
        f"Polled {poll_summary.jobs_polled} job(s): "
        f"{poll_summary.requests_reconciled} reconciled, "
        f"{poll_summary.requests_fallback} to fallback, "
        f"{poll_summary.jobs_still_running} still running. "
        f"Fallback recovered {fallback_summary.requests_recovered}, "
        f"failed {fallback_summary.requests_failed}."
    )
