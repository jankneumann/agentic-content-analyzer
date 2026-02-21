"""Embedded worker entry point.

Runs the same queue runtime used by `aca worker start` so local and deployed
workers share concurrency, dequeue, and shutdown semantics.
"""

import asyncio
import os
import signal
import sys

from src.queue.worker import register_all_handlers, run_worker
from src.telemetry import setup_telemetry, shutdown_telemetry
from src.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_CONCURRENCY = 5
MAX_CONCURRENCY = 20


def _get_runtime_concurrency() -> int:
    raw = os.environ.get("WORKER_CONCURRENCY")
    if not raw:
        return DEFAULT_CONCURRENCY
    try:
        value = int(raw)
    except ValueError:
        logger.warning(f"Invalid WORKER_CONCURRENCY='{raw}', using {DEFAULT_CONCURRENCY}")
        return DEFAULT_CONCURRENCY
    if 1 <= value <= MAX_CONCURRENCY:
        return value
    logger.warning(
        f"WORKER_CONCURRENCY={value} out of range (1-{MAX_CONCURRENCY}), using {DEFAULT_CONCURRENCY}"
    )
    return DEFAULT_CONCURRENCY


def _handle_shutdown(signum: int, frame: object) -> None:
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")


async def main() -> None:
    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    setup_telemetry(app=None)
    concurrency = _get_runtime_concurrency()

    logger.info(f"Starting embedded queue worker (concurrency={concurrency})")
    try:
        from src.queue.setup import ensure_queue_schema_compatible

        await ensure_queue_schema_compatible()
        register_all_handlers()
        await run_worker(concurrency=concurrency)
    except asyncio.CancelledError:
        logger.info("Worker cancelled")
    except Exception as e:
        logger.error(f"Worker error: {e}")
        raise
    finally:
        shutdown_telemetry()
        logger.info("Worker shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
        sys.exit(0)
