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


@app.command("generate-secret")
def generate_secret() -> None:
    """Generate a cryptographically random secret key.

    Prints a 64-character URL-safe random key suitable for
    APP_SECRET_KEY or ADMIN_API_KEY.
    """
    import secrets as _secrets

    key = _secrets.token_urlsafe(48)
    if is_json_mode():
        output_result({"secret": key})
    else:
        typer.echo(key)


@app.command("backfill-chunks")
def backfill_chunks_cmd(
    batch_size: int = typer.Option(100, "--batch-size", "-b", help="Content records per batch"),
    delay: float = typer.Option(1.0, "--delay", "-d", help="Seconds between embedding batches"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Report what would be done without writing"
    ),
    embed_only: bool = typer.Option(False, "--embed-only", help="Only fill missing embeddings"),
    content_id: int | None = typer.Option(
        None, "--content-id", "-c", help="Process specific content ID"
    ),
) -> None:
    """Backfill document chunks and embeddings for existing content.

    Processes content records that have no associated chunks, generating
    chunks from markdown_content and embedding them for search indexing.
    """
    import asyncio

    from src.scripts.backfill_chunks import backfill_chunks

    result = asyncio.run(
        backfill_chunks(
            batch_size=batch_size,
            delay=delay,
            dry_run=dry_run,
            embed_only=embed_only,
            content_id=content_id,
        )
    )

    if is_json_mode():
        output_result(result)
    else:
        if result.get("skipped"):
            typer.echo(typer.style(f"Skipped: {result['reason']}", fg=typer.colors.YELLOW))
            return

        typer.echo("\nBackfill complete:")
        typer.echo(f"  Content processed: {result['content_processed']}")
        typer.echo(f"  Chunks created:    {result['chunks_created']}")
        typer.echo(f"  Embeddings:        {result['embeddings_generated']}")
        if result.get("errors"):
            typer.echo(typer.style(f"  Errors:            {result['errors']}", fg=typer.colors.RED))
        if result.get("skipped_count", 0):
            typer.echo(f"  Skipped:           {result['skipped']}")


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

    Verifies that the database, Neo4j, and LLM API are
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


@app.command("cleanup-notifications")
def cleanup_notifications_cmd(
    older_than: str = typer.Option(
        "90d", "--older-than", help="Delete events older than this duration (e.g. 30d, 7d)"
    ),
) -> None:
    """Delete old notification events.

    Duration format: <number>d for days (e.g. 30d, 90d, 7d).
    """
    # Parse duration
    match = re.match(r"^(\d+)d$", older_than)
    if not match:
        typer.echo(f"Error: Invalid duration format '{older_than}'. Use format like '30d'.")
        raise typer.Exit(1)

    days = int(match.group(1))
    if days < 1:
        typer.echo("Error: Duration must be at least 1 day.")
        raise typer.Exit(1)

    from src.services.notification_cleanup import cleanup_notifications

    count = cleanup_notifications(days)

    if is_json_mode():
        output_result({"deleted": count, "older_than_days": days})
    else:
        typer.echo(f"Deleted {count} notification events older than {days} days.")


@app.command("switch-embeddings")
def switch_embeddings_cmd(
    provider: str | None = typer.Option(
        None, "--provider", "-p", help="Target embedding provider (default: from settings)"
    ),
    model: str | None = typer.Option(
        None, "--model", "-m", help="Target embedding model (default: from settings)"
    ),
    batch_size: int = typer.Option(100, "--batch-size", "-b", help="Batch size for backfill"),
    delay: float = typer.Option(1.0, "--delay", "-d", help="Seconds between backfill batches"),
    skip_backfill: bool = typer.Option(
        False, "--skip-backfill", help="Only clear embeddings, don't re-embed"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Report what would be done without changes"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Switch embedding provider: clear embeddings, rebuild index, backfill.

    This command safely migrates from one embedding provider to another:
    1. Validates the target provider can be instantiated
    2. NULLs all existing embeddings and metadata
    3. Drops and recreates the HNSW index
    4. Optionally triggers a backfill with the new provider

    WARNING: This clears ALL existing embeddings. Vector search will be
    unavailable until backfill completes. BM25 search continues working.
    """
    import asyncio

    from src.config.settings import get_settings
    from src.scripts.switch_embeddings import switch_embeddings

    settings = get_settings()
    target_provider = provider or settings.embedding_provider
    target_model = model or settings.embedding_model

    if not dry_run and not yes:
        typer.echo(
            f"\nThis will clear ALL existing embeddings and switch to "
            f"{target_provider}/{target_model}."
        )
        typer.echo("Vector search will be unavailable until backfill completes.")
        typer.echo("BM25 keyword search will continue working.\n")
        if not typer.confirm("Proceed?"):
            raise typer.Exit(0)

    result = asyncio.run(
        switch_embeddings(
            provider=provider,
            model=model,
            batch_size=batch_size,
            delay=delay,
            skip_backfill=skip_backfill,
            dry_run=dry_run,
        )
    )

    if is_json_mode():
        output_result(result)
    else:
        if result.get("error"):
            typer.echo(typer.style(f"Error: {result['error']}", fg=typer.colors.RED))
            raise typer.Exit(1)

        if result.get("dry_run"):
            typer.echo("\n[DRY RUN] Switch summary:")
        else:
            typer.echo("\nSwitch complete:")

        typer.echo(f"  Provider:    {result['target_provider']}")
        typer.echo(f"  Model:       {result['target_model']}")
        typer.echo(f"  Dimensions:  {result['target_dimensions']}")
        typer.echo(f"  Existing:    {result['existing_embeddings']} embeddings")
        typer.echo(f"  Total:       {result['total_chunks']} chunks")

        if not result.get("dry_run"):
            cleared = result.get("embeddings_cleared", 0)
            typer.echo(f"  Cleared:     {cleared} embeddings")
            if result.get("backfill"):
                bf = result["backfill"]
                typer.echo(f"  Re-embedded: {bf.get('embeddings_generated', 0)} chunks")
                if bf.get("errors"):
                    typer.echo(typer.style(f"  Errors:      {bf['errors']}", fg=typer.colors.RED))
            elif result.get("skip_backfill"):
                typer.echo(
                    typer.style(
                        "  Backfill skipped. Run 'aca manage backfill-chunks --embed-only' "
                        "when ready.",
                        fg=typer.colors.YELLOW,
                    )
                )
