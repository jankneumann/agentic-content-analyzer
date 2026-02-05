"""Shared output utilities for CLI commands.

This module is intentionally separate from app.py to avoid circular imports.
Command modules can safely import from here without triggering circular
dependency chains (app.py imports command modules which import from app.py).
"""

from __future__ import annotations

import json
import sys

import typer

# Module-level JSON output flag
_json_mode = False


def _set_json_mode(enabled: bool) -> None:
    global _json_mode
    _json_mode = enabled


def is_json_mode() -> bool:
    return _json_mode


def output_result(data: dict | list | str, success: bool = True) -> None:
    """Output result in either Rich or JSON format depending on mode."""
    if is_json_mode():
        if isinstance(data, str):
            json.dump({"message": data, "success": success}, sys.stdout)
        else:
            json.dump(data, sys.stdout, default=str)
        sys.stdout.write("\n")
    else:
        if isinstance(data, str):
            typer.echo(data)
        else:
            from rich import print as rprint

            rprint(data)
