"""Queue module for durable background task processing.

This module provides a PostgreSQL-based task queue using PGQueuer,
integrated with the DatabaseProvider abstraction for provider-agnostic
queue connections.
"""

from src.queue.setup import (
    get_queue,
    get_queue_queries,
    init_queue_schema,
)

__all__ = [
    "get_queue",
    "get_queue_queries",
    "init_queue_schema",
]
