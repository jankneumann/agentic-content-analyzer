"""CLI commands for settings management.

In HTTP mode (default), commands call the backend API via httpx.
In direct mode (--direct flag or API unreachable), commands call
services directly (legacy inline behavior).

Usage:
    aca settings list
    aca settings list --prefix model
    aca settings get <key>
    aca settings set <key> <value>
    aca settings reset <key>
"""

from __future__ import annotations

from typing import Annotated

import httpx
import typer

from src.cli.output import is_direct_mode, is_json_mode, output_result

app = typer.Typer(
    name="settings",
    help="Manage application settings overrides.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Direct-mode implementations
# ---------------------------------------------------------------------------


def _list_settings_direct(prefix: str) -> None:
    """List settings overrides directly via DB."""
    from src.services.settings_service import SettingsService
    from src.storage.database import get_db

    with get_db() as db:
        service = SettingsService(db)
        overrides = service.list_by_prefix(prefix)

    if is_json_mode():
        output_result({"overrides": overrides, "count": len(overrides)})
        return

    if not overrides:
        typer.echo("No settings overrides found.")
        return

    typer.echo()
    typer.echo(typer.style("  Settings Overrides", bold=True))
    typer.echo()

    for o in overrides:
        key_display = typer.style(o["key"], fg=typer.colors.CYAN)
        version_display = typer.style(f"v{o['version']}", fg=typer.colors.YELLOW)
        typer.echo(f"  {key_display}  =  {o['value']}  ({version_display})")
        if o.get("description"):
            typer.echo(f"    {typer.style(o['description'], dim=True)}")

    typer.echo()
    typer.echo(f"  Total: {len(overrides)} override(s)")


def _get_setting_direct(key: str) -> None:
    """Get a setting override directly via DB."""
    from src.services.settings_service import SettingsService
    from src.storage.database import get_db

    with get_db() as db:
        service = SettingsService(db)
        override = service.get_override(key)

    if is_json_mode():
        if override:
            output_result(
                {
                    "key": override.key,
                    "value": override.value,
                    "version": override.version,
                    "description": override.description,
                }
            )
        else:
            output_result({"key": key, "value": None, "message": "No override set"})
        return

    if override:
        typer.echo(f"  Key:         {override.key}")
        typer.echo(f"  Value:       {override.value}")
        typer.echo(f"  Version:     {override.version}")
        if override.description:
            typer.echo(f"  Description: {override.description}")
    else:
        typer.echo(f"  No override set for '{key}'")


def _set_setting_direct(key: str, value: str, description: str | None) -> None:
    """Set a setting override directly via DB."""
    from src.services.settings_service import SettingsService
    from src.storage.database import get_db

    with get_db() as db:
        service = SettingsService(db)
        service.set(key, value, description=description)
        override = service.get_override(key)

    if is_json_mode():
        output_result(
            {
                "key": key,
                "value": value,
                "version": override.version if override else 1,
            }
        )
        return

    version = override.version if override else 1
    typer.echo(f"  Set {key} = {value} (v{version})")


def _reset_setting_direct(key: str) -> None:
    """Reset a setting override directly via DB."""
    from src.services.settings_service import SettingsService
    from src.storage.database import get_db

    with get_db() as db:
        service = SettingsService(db)
        deleted = service.delete(key)

    if is_json_mode():
        output_result({"key": key, "deleted": deleted})
        return

    if deleted:
        typer.echo(f"  Reset '{key}' to default")
    else:
        typer.echo(f"  No override found for '{key}'")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("list")
def list_settings(
    prefix: Annotated[
        str,
        typer.Option("--prefix", "-p", help="Filter by key prefix (e.g., 'model', 'voice')"),
    ] = "",
) -> None:
    """List all settings overrides.

    Shows all database-persisted settings overrides, optionally
    filtered by key prefix.
    """
    if is_direct_mode():
        return _list_settings_direct(prefix)

    try:
        from src.cli.api_client import get_api_client

        client = get_api_client()
        params = {}
        if prefix:
            params["prefix"] = prefix
        data = client.list_settings(**params)

        if is_json_mode():
            output_result(data)
            return

        overrides = data.get("overrides", [])
        if not overrides:
            typer.echo("No settings overrides found.")
            return

        typer.echo()
        typer.echo(typer.style("  Settings Overrides", bold=True))
        typer.echo()

        for o in overrides:
            key_display = typer.style(o["key"], fg=typer.colors.CYAN)
            version_display = typer.style(f"v{o['version']}", fg=typer.colors.YELLOW)
            typer.echo(f"  {key_display}  =  {o['value']}  ({version_display})")
            if o.get("description"):
                typer.echo(f"    {typer.style(o['description'], dim=True)}")

        typer.echo()
        typer.echo(f"  Total: {len(overrides)} override(s)")
    except httpx.ConnectError:
        if not is_json_mode():
            typer.echo("Backend unavailable -- running directly...", err=True)
        _list_settings_direct(prefix)


@app.command("get")
def get_setting(
    key: Annotated[str, typer.Argument(help="Settings key (e.g., 'model.summarization')")],
) -> None:
    """Get the value of a specific settings override."""
    if is_direct_mode():
        return _get_setting_direct(key)

    try:
        from src.cli.api_client import get_api_client

        client = get_api_client()
        data = client.get_setting(key)

        if is_json_mode():
            output_result(data)
            return

        typer.echo(f"  Key:         {data['key']}")
        typer.echo(f"  Value:       {data['value']}")
        typer.echo(f"  Version:     {data['version']}")
        if data.get("description"):
            typer.echo(f"  Description: {data['description']}")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            if is_json_mode():
                output_result({"key": key, "value": None, "message": "No override set"})
            else:
                typer.echo(f"  No override set for '{key}'")
        else:
            raise
    except httpx.ConnectError:
        if not is_json_mode():
            typer.echo("Backend unavailable -- running directly...", err=True)
        _get_setting_direct(key)


@app.command("set")
def set_setting(
    key: Annotated[str, typer.Argument(help="Settings key (e.g., 'model.summarization')")],
    value: Annotated[str, typer.Argument(help="Value to set")],
    description: Annotated[
        str | None,
        typer.Option("--description", "-d", help="Description of the change"),
    ] = None,
) -> None:
    """Set a settings override value."""
    if is_direct_mode():
        return _set_setting_direct(key, value, description)

    try:
        from src.cli.api_client import get_api_client

        client = get_api_client()
        data = client.set_setting(key, value)

        if is_json_mode():
            output_result(data)
            return

        version = data.get("version", 1)
        typer.echo(f"  Set {key} = {value} (v{version})")
    except httpx.ConnectError:
        if not is_json_mode():
            typer.echo("Backend unavailable -- running directly...", err=True)
        _set_setting_direct(key, value, description)


@app.command("reset")
def reset_setting(
    key: Annotated[str, typer.Argument(help="Settings key to reset")],
) -> None:
    """Reset a settings override to its default value."""
    if is_direct_mode():
        return _reset_setting_direct(key)

    try:
        from src.cli.api_client import get_api_client

        client = get_api_client()
        client.delete_setting(key)

        if is_json_mode():
            output_result({"key": key, "deleted": True})
            return

        typer.echo(f"  Reset '{key}' to default")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            if is_json_mode():
                output_result({"key": key, "deleted": False})
            else:
                typer.echo(f"  No override found for '{key}'")
        else:
            raise
    except httpx.ConnectError:
        if not is_json_mode():
            typer.echo("Backend unavailable -- running directly...", err=True)
        _reset_setting_direct(key)
