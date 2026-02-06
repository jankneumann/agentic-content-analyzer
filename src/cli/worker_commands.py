"""CLI commands for job queue workers.

Usage:
    aca worker start
    aca worker start --concurrency 10
"""

from __future__ import annotations

import asyncio
import os
import signal
from typing import Annotated

import typer

from src.cli.output import is_json_mode, output_result
from src.utils.logging import get_logger

app = typer.Typer(help="Job queue worker commands.")

logger = get_logger(__name__)

# Concurrency limits
DEFAULT_CONCURRENCY = 5
MAX_CONCURRENCY = 20


def _get_default_concurrency() -> int:
    """Get default concurrency from environment or use default.

    Returns:
        Concurrency value from WORKER_CONCURRENCY env var or DEFAULT_CONCURRENCY
    """
    env_value = os.environ.get("WORKER_CONCURRENCY")
    if env_value:
        try:
            value = int(env_value)
            if 1 <= value <= MAX_CONCURRENCY:
                return value
            logger.warning(
                f"WORKER_CONCURRENCY={value} out of range (1-{MAX_CONCURRENCY}), "
                f"using default {DEFAULT_CONCURRENCY}"
            )
        except ValueError:
            logger.warning(
                f"Invalid WORKER_CONCURRENCY='{env_value}', using default {DEFAULT_CONCURRENCY}"
            )
    return DEFAULT_CONCURRENCY


async def _run_worker(concurrency: int) -> None:
    """Run the queue worker with graceful shutdown handling.

    Args:
        concurrency: Maximum number of concurrent tasks
    """
    from datetime import timedelta

    from src.queue.setup import close_queue, get_queue
    from src.tasks.content import register_content_tasks

    # Track shutdown state
    shutdown_event = asyncio.Event()

    def signal_handler(signum: int, frame: object) -> None:
        """Handle SIGTERM/SIGINT for graceful shutdown."""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name}, initiating graceful shutdown...")
        shutdown_event.set()

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Initialize queue
        pgq = await get_queue()

        # Register task handlers
        register_content_tasks(pgq)

        logger.info(f"Worker ready - concurrency={concurrency}, listening for jobs...")

        if not is_json_mode():
            typer.echo(
                typer.style(
                    f"Worker started with concurrency={concurrency}",
                    fg=typer.colors.GREEN,
                )
            )
            typer.echo("Press Ctrl+C to stop gracefully")
        else:
            output_result(
                {
                    "status": "ready",
                    "concurrency": concurrency,
                    "message": "Worker started and listening for jobs",
                }
            )

        # Run the worker loop
        # PGQueuer handles signal-based shutdown internally when running
        await pgq.run(
            dequeue_timeout=timedelta(seconds=30),
            batch_size=10,
            max_concurrent_tasks=concurrency,
        )

    except asyncio.CancelledError:
        logger.info("Worker cancelled, shutting down...")
    except Exception as e:
        logger.error(f"Worker error: {e}")
        raise
    finally:
        # Clean up queue connection
        await close_queue()
        logger.info("Worker shutdown complete")

        if not is_json_mode():
            typer.echo(typer.style("Worker stopped", fg=typer.colors.YELLOW))


@app.command("start")
def start(
    concurrency: Annotated[
        int | None,
        typer.Option(
            "--concurrency",
            "-c",
            help=f"Maximum concurrent tasks (1-{MAX_CONCURRENCY}). "
            f"Default from WORKER_CONCURRENCY env var or {DEFAULT_CONCURRENCY}.",
            min=1,
            max=MAX_CONCURRENCY,
        ),
    ] = None,
) -> None:
    """Start the job queue worker.

    The worker processes background jobs from the PostgreSQL-based queue,
    including URL content extraction, summarization, and newsletter scanning.

    Graceful shutdown is supported via SIGTERM or Ctrl+C. The worker will
    stop claiming new jobs and wait for in-progress jobs to complete.

    Examples:
        aca worker start                    # Use default concurrency
        aca worker start --concurrency 10   # Process up to 10 jobs at once
        WORKER_CONCURRENCY=8 aca worker start  # Set via environment
    """
    # Resolve concurrency value
    if concurrency is None:
        concurrency = _get_default_concurrency()

    # Validate concurrency range (typer handles min/max but we double-check)
    if concurrency < 1 or concurrency > MAX_CONCURRENCY:
        typer.echo(
            typer.style(
                f"Concurrency must be between 1 and {MAX_CONCURRENCY}",
                fg=typer.colors.RED,
            )
        )
        raise typer.Exit(1)

    logger.info(f"Starting worker with concurrency={concurrency}")

    try:
        asyncio.run(_run_worker(concurrency))
    except KeyboardInterrupt:
        # Handle keyboard interrupt gracefully
        if not is_json_mode():
            typer.echo("\nReceived interrupt, worker stopped")
    except Exception as e:
        typer.echo(typer.style(f"Worker failed: {e}", fg=typer.colors.RED))
        raise typer.Exit(1)
