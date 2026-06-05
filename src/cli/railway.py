"""Shared helpers around the Railway CLI (``railway``).

Thin wrappers over ``railway variables`` / ``railway status`` used by both
``aca auth`` (OAuth-token push) and ``aca deploy sync-secrets``. Keeping the
subprocess plumbing and error messaging in one place avoids the duplication
that previously lived only in ``auth_commands.py``.

All write paths require either ``railway link`` to have been run in the current
directory OR ``RAILWAY_TOKEN`` to be set in the environment, and the ``railway``
CLI itself to be installed.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import typer

_INSTALL_HINT = (
    "railway CLI not found in PATH. Install with:\n"
    "  brew install railway     (macOS)\n"
    "  npm install -g @railway/cli\n"
    "Or see https://docs.railway.com/guides/cli"
)


def ensure_railway_cli() -> None:
    """Exit with install guidance when the ``railway`` CLI is unavailable."""
    if not shutil.which("railway"):
        typer.echo(_INSTALL_HINT, err=True)
        raise typer.Exit(1)


def _target_flags(service: str | None, environment: str | None) -> list[str]:
    flags: list[str] = []
    if service:
        flags.extend(["--service", service])
    if environment:
        flags.extend(["--environment", environment])
    return flags


def set_variable(key: str, value: str, service: str | None = None) -> None:
    """Set a single Railway variable via ``railway variables --set KEY=VALUE``.

    The value is never echoed back — env vars set via this path are often
    multi-kilobyte secret blobs that would flood the terminal.
    """
    ensure_railway_cli()

    cmd = ["railway", "variables", "--set", f"{key}={value}"]
    if service:
        cmd.extend(["--service", service])

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        typer.echo(
            f"`railway variables --set {key}=...` failed (exit {e.returncode}):\n"
            f"  stderr: {e.stderr.strip() or '(empty)'}\n"
            "Make sure you've run `railway link` in this directory or set RAILWAY_TOKEN.",
            err=True,
        )
        raise typer.Exit(1) from e

    target = f" on service {service}" if service else ""
    typer.echo(f"Railway env var {key} set{target}.")


def set_variables(
    pairs: dict[str, str],
    service: str | None = None,
    environment: str | None = None,
) -> None:
    """Set multiple Railway variables in one ``railway variables`` invocation.

    Batching ``--set`` flags into a single call minimizes the number of
    redeploys Railway triggers. Values are never echoed.
    """
    if not pairs:
        return
    ensure_railway_cli()

    cmd = ["railway", "variables"]
    for key, value in pairs.items():
        cmd.extend(["--set", f"{key}={value}"])
    cmd.extend(_target_flags(service, environment))

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        keys = ", ".join(pairs)
        typer.echo(
            f"`railway variables --set` failed for [{keys}] (exit {e.returncode}):\n"
            f"  stderr: {e.stderr.strip() or '(empty)'}\n"
            "Make sure you've run `railway link` in this directory or set RAILWAY_TOKEN.",
            err=True,
        )
        raise typer.Exit(1) from e


def get_variables(
    service: str | None = None,
    environment: str | None = None,
    *,
    timeout: int = 30,
) -> dict[str, str]:
    """Return current Railway variables as a ``{name: value}`` dict.

    Best-effort: returns an empty dict when the CLI is missing, not linked, the
    command fails, or the output can't be parsed. ``railway variables --json``
    emits a flat name→value object.
    """
    if not shutil.which("railway"):
        return {}

    cmd = ["railway", "variables", "--json", *_target_flags(service, environment)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except (subprocess.TimeoutExpired, OSError):
        return {}
    if result.returncode != 0 or not result.stdout.strip():
        return {}

    try:
        data = json.loads(result.stdout)
    except (ValueError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if v is not None}


def linked_target() -> str | None:
    """Return ``"project / environment"`` for the linked Railway target.

    Reads ``railway status --json``. Returns None when the CLI is missing, not
    linked, or the output can't be parsed. Best-effort — never raises.
    """
    if not shutil.which("railway"):
        return None
    try:
        result = subprocess.run(
            ["railway", "status", "--json"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        data = json.loads(result.stdout)
    except (ValueError, TypeError):
        return None

    def _name(value: object) -> str | None:
        if isinstance(value, dict):
            name = value.get("name")
            return str(name) if name else None
        return str(value) if value else None

    project = _name(data.get("name")) or _name(data.get("project"))
    environment = _name(data.get("environment"))
    parts = [p for p in (project, environment) if p]
    return " / ".join(parts) if parts else None
