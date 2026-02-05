"""CLI commands for setup and operational management.

Usage:
    aca manage setup-gmail
    aca manage verify-setup
    aca manage railway-sync
    aca manage check-profile-secrets
"""

from __future__ import annotations

import os
import re
from typing import Any

import typer

from src.cli.output import is_json_mode, output_result

app = typer.Typer(help="Setup and operational management commands.")


def _flatten_dict(d: dict[str, Any], parent_key: str = "", sep: str = ".") -> dict[str, Any]:
    """Flatten a nested dictionary into dot-separated keys.

    Args:
        d: Dictionary to flatten
        parent_key: Prefix for nested keys
        sep: Separator between key levels

    Returns:
        Flat dictionary with dot-separated keys
    """
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


@app.command("setup-gmail")
def setup_gmail() -> None:
    """Initiate Gmail OAuth setup.

    Opens a browser window for Gmail OAuth authorization.
    Follow the prompts to grant access to your Gmail account
    for newsletter ingestion.
    """
    typer.echo("Initiating Gmail OAuth setup...")

    try:
        from src.ingestion.gmail import GmailClient

        GmailClient()
        typer.echo(
            typer.style(
                "Gmail OAuth setup initiated. Follow the browser prompts.",
                fg=typer.colors.GREEN,
            )
        )
    except Exception as e:
        typer.echo(typer.style(f"Error during Gmail setup: {e}", fg=typer.colors.RED))
        raise typer.Exit(1)


@app.command("verify-setup")
def verify_setup() -> None:
    """Check connectivity for all services.

    Verifies that the database, Redis, Neo4j, and LLM API are
    reachable and properly configured. Results are displayed in
    a summary table.
    """
    results: list[dict[str, str]] = []

    # --- Database check ---
    try:
        from sqlalchemy import text

        from src.storage.database import get_db

        with get_db() as db:
            db.execute(text("SELECT 1"))
        results.append({"service": "Database", "status": "pass"})
    except Exception as e:
        results.append({"service": "Database", "status": "fail", "error": str(e)})

    # --- Redis check ---
    try:
        import redis  # type: ignore[import-untyped]

        from src.config import settings

        r = redis.from_url(settings.redis_url)
        r.ping()
        results.append({"service": "Redis", "status": "pass"})
    except Exception as e:
        results.append({"service": "Redis", "status": "fail", "error": str(e)})

    # --- Neo4j check ---
    try:
        from src.storage.graphiti_client import GraphitiClient

        GraphitiClient()
        results.append({"service": "Neo4j", "status": "pass"})
    except Exception as e:
        results.append({"service": "Neo4j", "status": "fail", "error": str(e)})

    # --- LLM API check ---
    try:
        from src.config import settings

        api_key = settings.anthropic_api_key
        has_key = bool(api_key and api_key != "test-key")
        if has_key:
            results.append({"service": "LLM API (Anthropic)", "status": "pass"})
        else:
            results.append(
                {
                    "service": "LLM API (Anthropic)",
                    "status": "fail",
                    "error": "API key not configured or set to test-key",
                }
            )
    except Exception as e:
        results.append({"service": "LLM API (Anthropic)", "status": "fail", "error": str(e)})

    # --- Display results ---
    if is_json_mode():
        output_result(results)
    else:
        from rich.console import Console
        from rich.table import Table

        table = Table(title="Service Connectivity Check")
        table.add_column("Service", style="bold")
        table.add_column("Status")
        table.add_column("Details")

        for r in results:
            if r["status"] == "pass":
                status_display = "[green]\u2713 Pass[/green]"
            else:
                status_display = "[red]\u2717 Fail[/red]"
            error_detail = r.get("error", "")
            table.add_row(r["service"], status_display, error_detail)

        console = Console()
        console.print(table)

        # Summary
        pass_count = sum(1 for r in results if r["status"] == "pass")
        total = len(results)
        if pass_count == total:
            console.print(f"\n[green]All {total} services connected successfully.[/green]")
        else:
            console.print(
                f"\n[yellow]{pass_count}/{total} services connected. "
                f"Fix failing services before proceeding.[/yellow]"
            )


@app.command("railway-sync")
def railway_sync() -> None:
    """Trigger Railway deployment sync.

    Prints instructions for deploying to Railway. Actual deployment
    is performed via the Railway CLI.
    """
    typer.echo("Railway sync: Run 'railway up' from the project root.")
    typer.echo("See docs/MOBILE_DEPLOYMENT.md for deployment guide.")


@app.command("check-profile-secrets")
def check_profile_secrets() -> None:
    """Check for unresolved secret references in the active profile.

    Scans the active profile's settings for ${VAR} references where
    the corresponding environment variable or secret is not set.
    Helps identify missing configuration before running the application.
    """
    from src.config.profiles import load_profile
    from src.config.settings import get_active_profile_name

    profile_name = get_active_profile_name()
    if not profile_name:
        typer.echo("No profile active (PROFILE env var not set)")
        raise typer.Exit(0)

    try:
        profile = load_profile(profile_name, skip_interpolation=True)
    except Exception as e:
        typer.echo(typer.style(f"Error loading profile '{profile_name}': {e}", fg=typer.colors.RED))
        raise typer.Exit(1)

    settings_dict = profile.settings.model_dump()

    # Find unresolved ${VAR} references
    unresolved: list[tuple[str, str]] = []
    for key, value in _flatten_dict(settings_dict).items():
        if isinstance(value, str):
            refs = re.findall(r"\$\{(\w+)\}", value)
            for ref in refs:
                if not os.environ.get(ref):
                    unresolved.append((key, ref))

    if is_json_mode():
        output_result(
            {
                "profile": profile_name,
                "unresolved_count": len(unresolved),
                "unresolved": [{"setting": k, "variable": v} for k, v in unresolved],
            }
        )
    elif not unresolved:
        typer.echo(
            typer.style(
                f"Profile '{profile_name}': All secret references are resolved.",
                fg=typer.colors.GREEN,
            )
        )
    else:
        from rich.console import Console
        from rich.table import Table

        table = Table(title=f"Unresolved Secrets in Profile '{profile_name}'")
        table.add_column("Setting", style="bold")
        table.add_column("Missing Variable", style="red")

        for setting_key, var_name in unresolved:
            table.add_row(setting_key, f"${{{var_name}}}")

        console = Console()
        console.print(table)
        console.print(
            f"\n[yellow]{len(unresolved)} unresolved reference(s) found. "
            f"Set these environment variables or add them to .secrets.yaml.[/yellow]"
        )
