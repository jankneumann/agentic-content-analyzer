"""Runnable GX-10 backup, restore, and checkpoint entrypoint."""

from .runtime import main, run_synthetic_checkpoint

__all__ = ["main", "run_synthetic_checkpoint"]
