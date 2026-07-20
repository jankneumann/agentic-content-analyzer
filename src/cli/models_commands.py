"""CLI commands for model-registry freshness.

Usage:
    aca models discover [--provider google_ai]
    aca models refresh [--provider anthropic] [--apply]
    aca models propose-default --step youtube_processing --candidate gemini-3.1-flash-lite [--approve]

Safe by default: `refresh` previews diffs unless `--apply`; `propose-default`
stays pending unless `--approve` (a default swap is HIGH risk).

See openspec/changes/auto-update-model-registry/.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer

app = typer.Typer(
    name="models",
    help="Model registry — discovery, pricing refresh, and gated default promotion",
    no_args_is_help=True,
)


@app.command("discover")
def discover(
    provider: Annotated[
        list[str] | None,
        typer.Option("--provider", help="Limit to provider(s); repeatable. Default: all."),
    ] = None,
) -> None:
    """List models in provider catalogs that are not yet in the registry."""
    from src.services.model_registry_service import ModelRegistryService

    report = ModelRegistryService().discover_candidates(providers=provider)
    if report.candidates:
        typer.echo(f"Discovered {len(report.candidates)} candidate(s):")
        for c in report.candidates:
            typer.echo(f"  [{c.provider}] {c.model_id} ({c.source})")
    else:
        typer.echo("No new candidates found.")
    if report.providers_failed:
        typer.echo(f"Skipped/failed providers: {', '.join(report.providers_failed)}")
    for err in report.errors:
        typer.echo(f"  ! {err}")


@app.command("refresh")
def refresh(
    provider: Annotated[
        list[str] | None,
        typer.Option("--provider", help="Limit to provider(s); repeatable. Default: all."),
    ] = None,
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Apply pricing/spec diffs to models.yaml (default: preview)."),
    ] = False,
) -> None:
    """Preview (or --apply) pricing/spec diffs for existing registry models."""
    from src.services.model_registry_service import ModelRegistryService

    service = ModelRegistryService()
    report = asyncio.run(service.refresh_pricing(providers=provider, dry_run=not apply))
    typer.echo(
        f"Fetched: {', '.join(report.providers_fetched) or 'none'} | "
        f"failed: {', '.join(report.providers_failed) or 'none'}"
    )
    typer.echo(f"{len(report.diffs)} pricing diff(s), {len(report.new_models)} new model(s).")
    for d in report.diffs:
        typer.echo(f"  ~ {d.provider_key}.{d.field}: {d.current_value} -> {d.extracted_value}")
    for m in report.new_models:
        typer.echo(f"  + new: {m.model_id} ({m.provider_model_id})")
    typer.echo("Applied." if report.applied else "Dry-run (no changes written). Use --apply.")


@app.command("propose-default")
def propose_default(
    step: Annotated[str, typer.Option("--step", help="Pipeline step, e.g. youtube_processing")],
    candidate: Annotated[str, typer.Option("--candidate", help="Candidate model id")],
    approve: Annotated[
        bool,
        typer.Option("--approve", help="Apply the swap (HIGH risk; default: pending)."),
    ] = False,
) -> None:
    """Propose a candidate as a step default (gated; --approve to apply)."""
    from src.services.model_registry_service import ModelRegistryService

    result = ModelRegistryService().propose_default(step, candidate, approved=approve)
    typer.echo(
        f"step={result['step']} candidate={result['candidate']} "
        f"risk={result['risk']} status={result['status']}"
    )
    if result.get("reason"):
        typer.echo(f"  reason: {result['reason']}")
    if result["status"] == "pending_approval":
        typer.echo("  Re-run with --approve to apply (writes a settings_overrides row).")
