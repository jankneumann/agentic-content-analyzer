"""CLI commands for Neon database branch management.

Usage:
    aca neon list                     # List all branches
    aca neon create <name>            # Create branch from main
    aca neon delete <name>            # Delete a branch
    aca neon connection <name>        # Print connection string
    aca neon clean                    # Delete stale agent branches
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import typer

from src.cli.output import is_json_mode, output_result

if TYPE_CHECKING:
    from src.storage.providers.neon_branch import NeonBranch, NeonBranchManager

app = typer.Typer(help="Neon database branch management for agent workflows.")


def _get_manager() -> NeonBranchManager:
    """Create a NeonBranchManager from current settings."""
    from src.config import settings
    from src.storage.providers.neon_branch import NeonBranchManager

    api_key = settings.neon_api_key
    project_id = settings.neon_project_id
    default_branch = settings.neon_default_branch

    if not api_key or not project_id:
        typer.echo(
            "Error: NEON_API_KEY and NEON_PROJECT_ID are required.\n"
            "Set them in .secrets.yaml, environment, or your profile.",
            err=True,
        )
        raise typer.Exit(1)

    return NeonBranchManager(
        api_key=api_key,
        project_id=project_id,
        default_branch=default_branch,
    )


@app.command("list")
def list_branches() -> None:
    """List all Neon branches in the configured project."""

    async def _list() -> list[NeonBranch]:
        manager = _get_manager()
        async with manager:
            return await manager.list_branches()

    branches = asyncio.run(_list())

    if is_json_mode():
        output_result(
            {
                "branches": [
                    {
                        "id": b.id,
                        "name": b.name,
                        "parent_id": b.parent_id,
                        "created_at": b.created_at.isoformat(),
                    }
                    for b in branches
                ]
            }
        )
        return

    if not branches:
        typer.echo("No branches found.")
        return

    typer.echo(f"{'Name':<40} {'ID':<20} {'Created':<20}")
    typer.echo("-" * 80)
    for b in branches:
        created = b.created_at.strftime("%Y-%m-%d %H:%M")
        typer.echo(f"{b.name:<40} {b.id:<20} {created:<20}")


@app.command("create")
def create_branch(
    name: str = typer.Argument(..., help="Branch name (e.g., claude/feature-xyz)"),
    parent: str = typer.Option("main", "--parent", "-p", help="Parent branch name"),
    force: bool = typer.Option(False, "--force", "-f", help="Delete existing branch and recreate"),
) -> None:
    """Create a new Neon database branch.

    Creates a copy-on-write branch from the parent (default: main).
    The branch gets its own read-write endpoint and connection string.

    Use --force to delete an existing branch with the same name and recreate it.
    """

    async def _create() -> NeonBranch:
        from src.storage.providers.neon_branch import NeonAPIError

        manager = _get_manager()
        async with manager:
            if force:
                try:
                    await manager.delete_branch(name)
                    if not is_json_mode():
                        typer.echo(f"Deleted existing branch: {name}")
                except NeonAPIError as e:
                    if e.status_code != 404:
                        raise
            return await manager.create_branch(name, parent=parent)

    branch = asyncio.run(_create())

    if is_json_mode():
        output_result(
            {
                "id": branch.id,
                "name": branch.name,
                "parent_id": branch.parent_id,
                "created_at": branch.created_at.isoformat(),
                "connection_string": branch.connection_string,
            }
        )
        return

    typer.echo(f"Created branch: {branch.name}")
    typer.echo(f"  ID: {branch.id}")
    if branch.connection_string:
        typer.echo(f"  Connection: {branch.connection_string}")
    typer.echo(
        f'\nTo use: export DATABASE_URL="{branch.connection_string or "<see Neon console>"}"'
    )


@app.command("delete")
def delete_branch(
    name: str = typer.Argument(..., help="Branch name to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
) -> None:
    """Delete a Neon database branch.

    This permanently destroys the branch and its data.
    """
    if not force:
        confirm = typer.confirm(f"Delete branch '{name}'? This cannot be undone")
        if not confirm:
            raise typer.Abort()

    async def _delete() -> None:
        manager = _get_manager()
        async with manager:
            await manager.delete_branch(name)

    asyncio.run(_delete())

    if is_json_mode():
        output_result({"deleted": name})
    else:
        typer.echo(f"Deleted branch: {name}")


@app.command("connection")
def connection_string(
    name: str = typer.Argument(..., help="Branch name"),
    pooled: bool = typer.Option(True, "--pooled/--direct", help="Pooled or direct connection"),
) -> None:
    """Print the connection string for a Neon branch.

    Use --direct for migrations (bypasses PgBouncer).
    """

    async def _get_conn() -> str:
        manager = _get_manager()
        async with manager:
            return await manager.get_connection_string(name, pooled=pooled)

    conn_str = asyncio.run(_get_conn())

    if is_json_mode():
        output_result({"branch": name, "pooled": pooled, "connection_string": conn_str})
    else:
        typer.echo(conn_str)


@app.command("clean")
def clean_branches(
    prefix: str = typer.Option(
        "claude/", "--prefix", help="Only delete branches matching this prefix"
    ),
    older_than: int = typer.Option(
        24, "--older-than", help="Only delete branches older than N hours"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be deleted"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
) -> None:
    """Clean up stale agent branches.

    Deletes branches matching --prefix that are older than --older-than hours.
    Useful for removing orphaned branches from crashed agent sessions.
    """

    async def _clean() -> list[str]:
        manager = _get_manager()
        cutoff = datetime.now(UTC) - timedelta(hours=older_than)

        async with manager:
            branches = await manager.list_branches()
            stale = [b for b in branches if b.name.startswith(prefix) and b.created_at < cutoff]

            if not stale:
                if not is_json_mode():
                    typer.echo("No stale branches found.")
                return []

            if not is_json_mode():
                typer.echo(f"Found {len(stale)} stale branch(es):")
                for b in stale:
                    age = datetime.now(UTC) - b.created_at
                    typer.echo(f"  {b.name} (age: {age.days}d {age.seconds // 3600}h)")

            if dry_run:
                if not is_json_mode():
                    typer.echo("\n(dry run — no branches deleted)")
                return [b.name for b in stale]

            if not force and not is_json_mode():
                confirm = typer.confirm(f"\nDelete {len(stale)} branch(es)?")
                if not confirm:
                    raise typer.Abort()

            deleted = []
            for b in stale:
                try:
                    await manager.delete_branch(b.name)
                    if not is_json_mode():
                        typer.echo(f"  Deleted: {b.name}")
                    deleted.append(b.name)
                except Exception as e:
                    typer.echo(f"  Failed to delete {b.name}: {e}", err=True)

            return deleted

    deleted = asyncio.run(_clean())

    if is_json_mode():
        output_result({"deleted": deleted, "count": len(deleted)})
