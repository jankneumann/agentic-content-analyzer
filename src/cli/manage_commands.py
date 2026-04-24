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
from src.cli.restore_commands import restore_from_cloud as _restore_from_cloud

app = typer.Typer(help="Setup and operational management commands.")

# Register restore-from-cloud subcommand (thin subprocess wrapper; see design D5).
# Implementation lives in `src/cli/restore_commands.py`.
app.command("restore-from-cloud")(_restore_from_cloud)


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

    # --- Graph DB check ---
    try:
        import asyncio

        from src.storage.graph_provider import GraphBackendUnavailableError
        from src.storage.graphiti_client import GraphitiClient

        asyncio.run(GraphitiClient.create())
        results.append({"service": "Graph DB", "status": "pass"})
    except GraphBackendUnavailableError as e:
        results.append({"service": "Graph DB", "status": "fail", "error": str(e)})
    except Exception as e:
        results.append({"service": "Graph DB", "status": "fail", "error": str(e)})

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


@app.command("extract-refs")
def extract_refs(
    after: str | None = typer.Option(
        None, "--after", help="ISO date: only process content after this date"
    ),
    before: str | None = typer.Option(
        None, "--before", help="ISO date: only process content before this date"
    ),
    source: str | None = typer.Option(
        None, "--source", help="Filter by source type (e.g., 'rss', 'substack')"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without storing"),
    batch_size: int = typer.Option(50, "--batch-size", "-b", help="Content items per batch"),
) -> None:
    """Extract references from existing content into content_references table."""
    from datetime import datetime as dt

    from src.models.content import Content
    from src.services.reference_extractor import ReferenceExtractor
    from src.storage.database import get_db

    extractor = ReferenceExtractor()
    total_stored = 0
    total_scanned = 0

    with get_db() as db:
        query = db.query(Content)
        if after:
            query = query.filter(Content.ingested_at >= dt.fromisoformat(after))
        if before:
            query = query.filter(Content.ingested_at <= dt.fromisoformat(before))
        if source:
            from sqlalchemy import String

            query = query.filter(Content.source_type.cast(String) == source)

        contents = query.all()
        total_content = len(contents)

        for i, content in enumerate(contents):
            refs = extractor.extract_from_content(content, db)
            total_scanned += 1

            if refs and not dry_run and content.id is not None:
                stored = extractor.store_references(content.id, refs, db)
                total_stored += stored
            elif refs:
                total_stored += len(refs)

            if not is_json_mode() and (i + 1) % batch_size == 0:
                typer.echo(
                    f"Processed {i + 1}/{total_content}, extracted {total_stored} references"
                )

    if is_json_mode():
        output_result(
            {
                "scanned": total_scanned,
                "references_found": total_stored,
                "dry_run": dry_run,
            }
        )
    elif dry_run:
        typer.echo(f"[DRY RUN] Scanned {total_scanned} items, found {total_stored} references")
    else:
        typer.echo(f"Extracted {total_stored} references from {total_scanned} content items")


@app.command("resolve-refs")
def resolve_refs(
    batch_size: int = typer.Option(
        100, "--batch-size", "-b", help="Number of references to process"
    ),
    auto_ingest: bool = typer.Option(
        False, "--auto-ingest", help="Trigger ingestion for unresolved structured IDs"
    ),
) -> None:
    """Resolve unresolved content references against the database."""
    from src.services.reference_resolver import ReferenceResolver
    from src.storage.database import get_db

    with get_db() as db:
        resolver = ReferenceResolver(db)
        resolved = resolver.resolve_batch(batch_size)

    if is_json_mode():
        output_result(
            {
                "resolved": resolved,
                "batch_size": batch_size,
                "auto_ingest": auto_ingest,
            }
        )
    else:
        typer.echo(f"Resolved {resolved} references (batch_size={batch_size})")

        if auto_ingest:
            typer.echo(
                "Auto-ingest: use 'aca manage extract-refs' + queue worker for automated ingestion"
            )


@app.command("backfill-tree-index")
def backfill_tree_index_cmd(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without changes"),
    content_id: int | None = typer.Option(None, "--content-id", help="Target specific content"),
    force: bool = typer.Option(False, "--force", help="Rebuild existing tree indexes"),
) -> None:
    """Build tree indexes for qualifying existing content.

    Scans content records for documents that qualify for tree indexing
    (token count > tree_index_min_tokens AND heading depth >= tree_index_min_heading_depth).
    Preserves existing flat chunks.
    """
    from src.config.settings import get_settings
    from src.services.chunking import _count_tokens, _detect_heading_depth
    from src.storage.database import get_db

    settings = get_settings()

    with get_db() as db:
        from src.models.content import Content

        if content_id:
            contents = db.query(Content).filter(Content.id == content_id).all()
        else:
            contents = db.query(Content).filter(Content.markdown_content.isnot(None)).all()

        qualifying = []
        for c in contents:
            if not c.markdown_content:
                continue
            tokens = _count_tokens(c.markdown_content)
            depth = _detect_heading_depth(c.markdown_content)
            if (
                tokens > settings.tree_index_min_tokens
                and depth >= settings.tree_index_min_heading_depth
            ):
                qualifying.append(c)

        if not qualifying:
            if not is_json_mode():
                typer.echo("No qualifying content found for tree indexing.")
            else:
                output_result({"qualifying": 0, "indexed": 0, "skipped": 0})
            return

        if dry_run:
            if not is_json_mode():
                typer.echo(f"Would index {len(qualifying)} content records:")
                for c in qualifying:
                    typer.echo(f"  - Content {c.id}: {c.title[:60] if c.title else 'Untitled'}")
            else:
                output_result(
                    {
                        "dry_run": True,
                        "qualifying": len(qualifying),
                        "content_ids": [c.id for c in qualifying],
                    }
                )
            return

        from src.services.indexing import build_tree_index

        indexed = 0
        skipped = 0
        for c in qualifying:
            try:
                assert c.id is not None
                count = build_tree_index(c.id, db, force=force)
                if count > 0:
                    indexed += 1
                    if not is_json_mode():
                        typer.echo(f"  Indexed content {c.id}: {count} tree chunks")
                else:
                    skipped += 1
                db.commit()
            except Exception as e:
                db.rollback()
                if not is_json_mode():
                    typer.echo(f"  Failed for content {c.id}: {e}", err=True)

        if is_json_mode():
            output_result({"qualifying": len(qualifying), "indexed": indexed, "skipped": skipped})
        else:
            typer.echo(
                f"Done: {indexed} indexed, {skipped} skipped out of {len(qualifying)} qualifying."
            )


@app.command("update-model-pricing")
def update_model_pricing_cmd(
    provider: list[str] | None = typer.Option(
        None, "--provider", "-p", help="Limit to specific providers (repeatable)"
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply", help="Preview changes (default) or apply to models.yaml"
    ),
    model: str = typer.Option(
        "claude-haiku-4-5", "--model", "-m", help="LLM model to use for extraction"
    ),
) -> None:
    """Extract model pricing from provider pages and update models.yaml.

    Fetches pricing pages from Anthropic, OpenAI, Google AI, and AWS Bedrock,
    uses an LLM to extract structured pricing data, and diffs it against the
    current settings/models.yaml.

    By default runs in --dry-run mode (preview only). Pass --apply to write.

    Examples:
        aca manage update-model-pricing                    # Preview all providers
        aca manage update-model-pricing -p anthropic       # Preview Anthropic only
        aca manage update-model-pricing --apply             # Apply changes
    """
    import asyncio

    from src.services.model_pricing_extractor import ModelPricingExtractor

    extractor = ModelPricingExtractor(extraction_model=model)
    report = asyncio.run(extractor.run(providers=provider, dry_run=dry_run))

    if is_json_mode():
        output_result(
            {
                "providers_fetched": report.providers_fetched,
                "providers_failed": report.providers_failed,
                "diffs": [
                    {
                        "key": d.provider_key,
                        "field": d.field,
                        "current": d.current_value,
                        "extracted": d.extracted_value,
                    }
                    for d in report.diffs
                ],
                "new_models": [
                    {
                        "model_id": m.model_id,
                        "provider_model_id": m.provider_model_id,
                        "cost_input": m.cost_per_mtok_input,
                        "cost_output": m.cost_per_mtok_output,
                        "notes": m.notes,
                    }
                    for m in report.new_models
                ],
                "errors": report.extraction_errors,
                "applied": report.applied,
            }
        )
        return

    # Human-readable output
    typer.echo()
    mode = (
        typer.style("DRY RUN", fg=typer.colors.YELLOW)
        if dry_run
        else typer.style("APPLY", fg=typer.colors.GREEN)
    )
    typer.echo(f"Model Pricing Extraction — {mode}")
    typer.echo("=" * 60)

    if report.providers_fetched:
        typer.echo(f"\nProviders fetched: {', '.join(report.providers_fetched)}")
    if report.providers_failed:
        typer.echo(
            typer.style(
                f"Providers failed: {', '.join(report.providers_failed)}",
                fg=typer.colors.RED,
            )
        )

    if report.diffs:
        typer.echo(f"\n--- Pricing changes detected ({len(report.diffs)}) ---")
        for d in report.diffs:
            typer.echo(
                f"  {d.provider_key}.{d.field}: "
                f"{typer.style(str(d.current_value), fg=typer.colors.RED)} → "
                f"{typer.style(str(d.extracted_value), fg=typer.colors.GREEN)}"
            )
    else:
        typer.echo(typer.style("\nNo pricing changes detected.", fg=typer.colors.GREEN))

    if report.new_models:
        typer.echo(f"\n--- New models found ({len(report.new_models)}) ---")
        for m in report.new_models:
            typer.echo(
                f"  {m.model_id}: ${m.cost_per_mtok_input:.2f}/${m.cost_per_mtok_output:.2f} "
                f"per Mtok — {m.notes}"
            )

    if report.extraction_errors:
        typer.echo(f"\n--- Errors ({len(report.extraction_errors)}) ---")
        for e in report.extraction_errors:
            typer.echo(typer.style(f"  {e}", fg=typer.colors.RED))

    if report.applied:
        typer.echo(
            typer.style("\n✓ Changes applied to settings/models.yaml", fg=typer.colors.GREEN)
        )
    elif report.has_changes and dry_run:
        typer.echo("\nRun with --apply to write changes to settings/models.yaml")


@app.command("list-models")
def list_models_cmd(
    family: str | None = typer.Option(
        None, "--family", "-f", help="Filter by model family (claude, gemini, gpt)"
    ),
) -> None:
    """List all models in the registry with their capabilities.

    Shows model ID, family, name, capability flags, and available providers.

    Examples:
        aca manage list-models                # All models
        aca manage list-models --family claude # Claude models only
        aca manage list-models --json          # JSON output
    """
    from src.services.model_registry_service import ModelRegistryService

    service = ModelRegistryService()
    models = service.list_models(family=family)

    if is_json_mode():
        output_result([m.model_dump() for m in models])
        return

    if not models:
        typer.echo("No models found.")
        return

    # Table output
    from rich.console import Console
    from rich.table import Table

    table = Table(title=f"Model Registry ({len(models)} models)")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Family", style="magenta")
    table.add_column("Name")
    table.add_column("Vision", justify="center")
    table.add_column("Video", justify="center")
    table.add_column("Audio", justify="center")
    table.add_column("Providers")
    table.add_column("$/MTok (in/out)", justify="right")

    for m in models:
        cost_str = ""
        if m.cost_per_mtok_input is not None:
            cost_str = f"${m.cost_per_mtok_input:.2f}/${m.cost_per_mtok_output:.2f}"

        table.add_row(
            m.id,
            m.family,
            m.name,
            "Y" if m.supports_vision else "",
            "Y" if m.supports_video else "",
            "Y" if m.supports_audio else "",
            ", ".join(m.providers),
            cost_str,
        )

    Console().print(table)


@app.command("model-info")
def model_info_cmd(
    model_id: str = typer.Argument(help="Model ID (e.g., claude-sonnet-4-5)"),
) -> None:
    """Show detailed model information with per-provider pricing.

    Examples:
        aca manage model-info claude-sonnet-4-5
        aca manage model-info gemini-2.5-flash --json
    """
    from src.services.model_registry_service import ModelRegistryService

    service = ModelRegistryService()
    detail = service.get_model(model_id)

    if not detail:
        typer.echo(typer.style(f"Model not found: {model_id}", fg=typer.colors.RED), err=True)
        raise typer.Exit(1)

    if is_json_mode():
        output_result(detail.model_dump())
        return

    # Header
    from rich.console import Console
    from rich.table import Table

    console = Console()

    console.print(f"\n[bold cyan]{detail.name}[/bold cyan] ({detail.id})")
    console.print(f"  Family: {detail.family}")
    caps = []
    if detail.supports_vision:
        caps.append("vision")
    if detail.supports_video:
        caps.append("video")
    if detail.supports_audio:
        caps.append("audio")
    console.print(f"  Capabilities: {', '.join(caps) if caps else 'text only'}")
    if detail.default_version:
        console.print(f"  Default version: {detail.default_version}")

    # Pricing table
    if detail.provider_pricing:
        console.print()
        table = Table(title="Provider Pricing")
        table.add_column("Provider", style="cyan")
        table.add_column("API Model ID", style="dim")
        table.add_column("Input $/MTok", justify="right", style="green")
        table.add_column("Output $/MTok", justify="right", style="green")
        table.add_column("Context", justify="right")
        table.add_column("Max Output", justify="right")
        table.add_column("Tier")

        for p in detail.provider_pricing:
            table.add_row(
                p.provider,
                p.provider_model_id,
                f"${p.cost_per_mtok_input:.2f}",
                f"${p.cost_per_mtok_output:.2f}",
                f"{p.context_window:,}",
                f"{p.max_output_tokens:,}",
                p.tier,
            )

        console.print(table)
    else:
        console.print("\n  No provider pricing configured.")
