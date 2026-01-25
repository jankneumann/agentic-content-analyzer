"""Background task definitions for PGQueuer.

This module contains all task entrypoints that can be processed
by the queue worker.
"""

from src.tasks.content import register_content_tasks

__all__ = [
    "register_content_tasks",
]
