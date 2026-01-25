"""PGQueuer worker entry point.

This module runs the background job processor that consumes tasks
from the PostgreSQL queue and executes them.

Usage:
    python -m src.worker

The worker uses direct database connections (not pooled) for:
- Reliable LISTEN/NOTIFY for job notifications
- Long-lived connections that don't exhaust pooler limits
- Isolation from web application connection pool
"""

import asyncio
import signal
import sys

from src.queue.setup import close_queue, get_queue
from src.tasks.content import register_content_tasks
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Flag for graceful shutdown
_shutdown_requested = False


def _handle_shutdown(signum: int, frame: object) -> None:
    """Handle shutdown signals gracefully."""
    global _shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    _shutdown_requested = True


async def main() -> None:
    """Main worker entry point.

    Sets up signal handlers, initializes the queue connection,
    registers task handlers, and runs the worker loop.
    """
    global _shutdown_requested

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    logger.info("Starting PGQueuer worker...")

    try:
        # Get PGQueuer instance (uses provider abstraction for connection)
        pgq = await get_queue()

        # Register all task handlers
        register_content_tasks(pgq)

        logger.info("Worker started, listening for jobs...")
        logger.info("Press Ctrl+C to stop")

        # Run the worker (blocks until shutdown)
        # PGQueuer uses LISTEN/NOTIFY for efficient job polling
        await pgq.run()

    except asyncio.CancelledError:
        logger.info("Worker cancelled")
    except Exception as e:
        logger.error(f"Worker error: {e}")
        raise
    finally:
        # Clean up
        await close_queue()
        logger.info("Worker shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
        sys.exit(0)
