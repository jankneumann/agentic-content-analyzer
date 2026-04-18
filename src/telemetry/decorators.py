"""Safe Langfuse decorator re-exports.

Provides @observe and propagate_attributes() with graceful degradation
when the langfuse package is not installed. Import from here instead of
directly from langfuse to prevent ImportError in modules that use
decorators at the top level.

Usage:
    from src.telemetry.decorators import observe, propagate_attributes

    @observe()
    def my_function():
        ...

    with propagate_attributes(session_id="abc"):
        ...
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

try:
    from langfuse import observe, propagate_attributes
except ImportError:

    def observe(**kwargs: Any) -> Any:  # type: ignore[misc]
        """No-op @observe() decorator when langfuse is not installed."""

        def decorator(func: Any) -> Any:
            return func

        return decorator

    @contextmanager
    def propagate_attributes(**kwargs: Any) -> Any:  # type: ignore[misc]
        """No-op propagate_attributes() context manager when langfuse is not installed."""
        yield


__all__ = ["observe", "propagate_attributes"]
