"""`aca telemetry` — housekeeping for the trace store.

Open-source Langfuse has no scheduled deletion: automated retention is an
enterprise feature, so a self-hosted stack keeps every trace forever. The
worker prunes on a timer; this is the same code with a hand on it, which is
what makes the scheduled path testable without waiting a day for a tick.

Output obeys the CLI JSON contract: one JSON document on stdout, every
diagnostic on stderr.
"""

from __future__ import annotations

import asyncio
from typing import Any

import typer

from src.cli.output import is_json_mode, output_result

app = typer.Typer(help="Telemetry store housekeeping: prune expired traces.")


def _fail(message: str, *, code: int = 1) -> None:
    if is_json_mode():
        output_result({"success": False, "error": message}, success=False)
    else:
        typer.echo(typer.style(f"Error: {message}", fg=typer.colors.RED), err=True)
    raise typer.Exit(code)


@app.command("prune-traces")
def prune_traces(
    older_than_days: int = typer.Option(
        None,
        "--older-than-days",
        help="Delete traces older than this. Defaults to the configured retention window.",
    ),
    batch_size: int = typer.Option(
        None,
        "--batch-size",
        help="Traces per delete request. Large batches time out in ClickHouse.",
    ),
    max_deletes: int = typer.Option(
        None,
        "--max-deletes",
        help="Stop after this many traces. The next run continues where this one stopped.",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Actually delete. Without it this only counts what would go.",
    ),
) -> None:
    """Delete expired Langfuse traces over the public API.

    Dry run by default. Deletion is irreversible and clears the ClickHouse rows
    together with their object-storage blobs, so the destructive direction is
    the one you have to ask for.
    """

    from src.config.settings import get_settings
    from src.services.langfuse_retention import (
        LangfuseRetentionClient,
        LangfuseRetentionError,
        prune_expired_traces,
    )

    settings = get_settings()
    public_key = settings.langfuse_public_key
    secret_key = settings.langfuse_secret_key
    base_url = settings.langfuse_base_url
    if not (public_key and secret_key and base_url):
        _fail("Langfuse credentials are not configured for this profile")
        return

    days = older_than_days or settings.langfuse_trace_retention_days
    size = batch_size or settings.langfuse_trace_retention_batch_size
    cap = max_deletes or settings.langfuse_trace_retention_max_deletes_per_run

    async def _run() -> Any:
        async with LangfuseRetentionClient(
            base_url=base_url,
            public_key=public_key,
            secret_key=secret_key,
        ) as client:
            return await prune_expired_traces(
                client,
                retention_days=days,
                batch_size=size,
                max_deletes=cap,
                dry_run=not apply,
            )

    try:
        result = asyncio.run(_run())
    except LangfuseRetentionError as exc:
        _fail(str(exc))
        return
    except ValueError as exc:
        _fail(str(exc))
        return

    payload = {
        "success": True,
        "applied": apply,
        "retention_days": days,
        "cutoff": result.cutoff.isoformat(),
        "trace_count": result.deleted_count,
        "batch_count": result.batch_count,
        "capped": result.capped,
    }

    if is_json_mode():
        output_result(payload, success=True)
        return

    verb = "Deleted" if apply else "Would delete"
    typer.echo(f"{verb} {result.deleted_count} traces older than {days} days")
    typer.echo(f"  cutoff: {result.cutoff.isoformat()}")
    if result.capped:
        typer.echo(
            typer.style(
                f"  stopped at the {cap} cap; run again to continue",
                fg=typer.colors.YELLOW,
            ),
            err=True,
        )
    if not apply:
        typer.echo(
            typer.style("  dry run — pass --apply to delete", fg=typer.colors.YELLOW),
            err=True,
        )
    if apply:
        typer.echo(
            "  deletion is asynchronous; traces stay visible until the Langfuse "
            "worker drains the queue",
            err=True,
        )
