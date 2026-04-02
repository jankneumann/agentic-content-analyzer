"""Root CLI entrypoint for the aca command.

Usage:
    aca ingest gmail
    aca summarize pending
    aca create-digest daily
    aca pipeline daily
    aca review list
    aca analyze themes
    aca graph query
    aca podcast generate
    aca manage verify-setup
    aca profile list
    aca worker start
    aca jobs list

Or run as module:
    python -m src.cli
"""

from __future__ import annotations

import importlib.metadata
from typing import Annotated

import typer

from src.cli.agent_commands import app as agent_app
from src.cli.analyze_commands import app as analyze_app
from src.cli.digest_commands import app as digest_app
from src.cli.edit_commands import app as edit_app
from src.cli.evaluate_commands import app as evaluate_app
from src.cli.graph_commands import app as graph_app
from src.cli.ingest_commands import app as ingest_app
from src.cli.job_commands import app as job_app
from src.cli.manage_commands import app as manage_app
from src.cli.neon_commands import app as neon_app

# Import output utilities from the shared module (avoids circular imports)
from src.cli.output import (  # noqa: F401
    _set_direct_mode,
    _set_json_mode,
    is_direct_mode,
    is_json_mode,
    output_result,
)
from src.cli.pipeline_commands import app as pipeline_app
from src.cli.podcast_commands import app as podcast_app
from src.cli.profile_commands import app as profile_app
from src.cli.prompt_commands import app as prompts_app
from src.cli.review_commands import app as review_app
from src.cli.settings_commands import app as settings_app
from src.cli.summarize_commands import app as summarize_app
from src.cli.sync_commands import app as sync_app
from src.cli.worker_commands import app as worker_app

# Root Typer application
app = typer.Typer(
    name="aca",
    help="Agentic Content Aggregator — unified CLI for ingesting, summarizing, and delivering AI/Data newsletters.",
    no_args_is_help=True,
)

# Register all sub-command groups
app.add_typer(ingest_app, name="ingest")
app.add_typer(summarize_app, name="summarize")
app.add_typer(digest_app, name="create-digest")
app.add_typer(edit_app, name="edit")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(review_app, name="review")
app.add_typer(agent_app, name="agent")
app.add_typer(analyze_app, name="analyze")
app.add_typer(graph_app, name="graph")
app.add_typer(podcast_app, name="podcast")
app.add_typer(manage_app, name="manage")
app.add_typer(neon_app, name="neon")
app.add_typer(profile_app, name="profile")
app.add_typer(prompts_app, name="prompts")
app.add_typer(settings_app, name="settings")
app.add_typer(sync_app, name="sync")
app.add_typer(worker_app, name="worker")
app.add_typer(job_app, name="jobs")
app.add_typer(evaluate_app, name="evaluate")


def _version_callback(value: bool) -> None:
    if value:
        try:
            version = importlib.metadata.version("agentic-newsletter-aggregator")
        except importlib.metadata.PackageNotFoundError:
            version = "0.1.0-dev"
        typer.echo(f"aca {version}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Output in JSON format (machine-readable).",
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            "-d",
            help="Enable debug logging output.",
        ),
    ] = False,
    direct: Annotated[
        bool,
        typer.Option(
            "--direct",
            help="Run commands directly without backend API (offline mode).",
        ),
    ] = False,
) -> None:
    """Agentic Content Aggregator CLI.

    Ingest newsletters, summarize content, create digests, and manage
    the full content pipeline from a single command.
    """
    if json_output:
        _set_json_mode(True)

    if direct:
        _set_direct_mode(True)

    if debug:
        from src.config import settings

        settings.log_level = "DEBUG"
        settings.log_format = "json" if json_output else "text"

    from src.utils.logging import setup_logging

    setup_logging()
