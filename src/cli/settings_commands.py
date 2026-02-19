"""CLI commands for settings management.

Usage:
    aca settings list
    aca settings list --prefix model
    aca settings get <key>
    aca settings set <key> <value>
    aca settings reset <key>
"""

from __future__ import annotations

from typing import Annotated

import typer

from src.cli.output import is_json_mode, output_result

app = typer.Typer(
    name="settings",
    help="Manage application settings overrides.",
    no_args_is_help=True,
)


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


@app.command("get")
def get_setting(
    key: Annotated[str, typer.Argument(help="Settings key (e.g., 'model.summarization')")],
) -> None:
    """Get the value of a specific settings override."""
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


@app.command("reset")
def reset_setting(
    key: Annotated[str, typer.Argument(help="Settings key to reset")],
) -> None:
    """Reset a settings override to its default value."""
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
