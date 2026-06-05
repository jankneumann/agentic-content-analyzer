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

# Module-level direct execution flag (bypass API, call services directly)
_direct_mode = False

# Module-level opt-in: run direct (in-process) against the REMOTE database.
# This is the deliberate escape hatch for heavy batch jobs (manage backfills,
# sync) where database_url has been pointed at the Railway proxy and the user
# accepts direct execution against prod data. It turns guard_remote_backend
# into a loud no-op instead of a refusal.
_remote_db = False


def _set_json_mode(enabled: bool) -> None:
    global _json_mode
    _json_mode = enabled


def is_json_mode() -> bool:
    return _json_mode


def _set_direct_mode(enabled: bool) -> None:
    global _direct_mode
    _direct_mode = enabled


def is_direct_mode() -> bool:
    return _direct_mode


def _set_remote_db(enabled: bool) -> None:
    global _remote_db
    _remote_db = enabled


def is_remote_db() -> bool:
    return _remote_db


# Hosts for which direct database access is the expected, correct behavior.
_LOCAL_HOSTS = frozenset({"", "localhost", "127.0.0.1", "0.0.0.0", "::1"})  # noqa: S104


def is_remote_backend() -> bool:
    """True when the active profile's API targets a non-localhost backend.

    Direct-mode commands talk to the LOCAL database. When the active profile
    points at a remote backend (e.g. railway-cli -> api.aca.rotkohl.ai),
    running a command directly would silently read/write LOCAL data while the
    user believes they are operating against prod — the "split-brain" failure.
    Commands consult this to route to HTTP or to refuse.

    Derived from the profile's ``api_base_url`` host, so it is correct for any
    remote profile without enumerating profile names.
    """
    from urllib.parse import urlparse

    from src.config.settings import get_settings

    host = (urlparse(get_settings().api_base_url).hostname or "").lower()
    return host not in _LOCAL_HOSTS


def guard_remote_backend(command: str, *, http_hint: str | None = None) -> None:
    """Refuse to run a direct-against-local-DB command under a remote profile.

    Call this at the direct-execution chokepoint of any command that touches
    the database directly. It is a no-op when the backend is local, so local
    development is unaffected. Under a remote profile it raises ``typer.Exit``
    with guidance, covering explicit ``--direct``, always-direct commands, and
    the ConnectError -> local-DB fallback uniformly.
    """
    if not is_remote_backend():
        return

    if is_remote_db():
        # Explicit opt-in (--remote-db): the user has pointed database_url at the
        # remote backend and accepts direct (in-process) execution against it.
        # Stay loud so it can never be mistaken for the silent split-brain path.
        typer.echo(
            f"Warning: `aca {command}` is running DIRECTLY against the REMOTE database "
            "(--remote-db). Confirm database_url targets the intended backend.",
            err=True,
        )
        return

    from src.config.settings import get_active_profile_name

    profile = get_active_profile_name() or "the active profile"
    lines = [
        f"Refusing to run `aca {command}` directly against the LOCAL database:",
        f"  profile '{profile}' targets a remote backend, so direct execution",
        "  would silently use local data instead of production.",
    ]
    if http_hint:
        lines.append(f"  Alternative: {http_hint}")
    lines.append(
        "  Or operate on local data with a local profile (unset PROFILE, or PROFILE=local)."
    )
    typer.echo("\n".join(lines), err=True)
    raise typer.Exit(1)


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
