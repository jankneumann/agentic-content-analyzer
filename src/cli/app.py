"""Root CLI entrypoint for the aca command.

Usage:
    aca ingest gmail
    aca summarize run
    aca digest create
    aca pipeline run
    aca review list
    aca theme create
    aca graph query
    aca podcast-script create
    aca manage verify-setup
    aca profile list
    aca worker start
    aca operations list

Or run as module:
    python -m src.cli
"""

from __future__ import annotations

import importlib.metadata
from typing import Annotated, ClassVar

import typer

# typer 0.20 vendors click as `typer._click`, so TyperGroup.get_command is
# annotated against typer._click.core.Command/Context there while older typer
# lines annotate against click's. CanonicalCommandGroup.get_command below
# overrides that method, so it has to name whichever flavour the installed
# typer was built against -- naming the wrong one is an [override] error, which
# is what kept the typer cap pinned below 0.20.
try:  # typer >= 0.20
    from typer._click.core import Command, Context
except ImportError:  # pragma: no cover - typer < 0.20 uses click directly
    from click.core import Command, Context  # type: ignore[assignment]

from typer.core import TyperGroup

from src.cli.agent_commands import app as agent_app
from src.cli.auth_commands import app as auth_app
from src.cli.backup_commands import app as backup_app
from src.cli.batch_commands import app as batch_app
from src.cli.curate_commands import app as curate_app
from src.cli.deploy_commands import app as deploy_app
from src.cli.edit_commands import app as edit_app
from src.cli.evaluate_commands import app as evaluate_app
from src.cli.filter_commands import app as filter_app
from src.cli.graph_commands import app as graph_app
from src.cli.kb_commands import app as kb_app
from src.cli.manage_commands import app as manage_app
from src.cli.models_commands import app as models_app
from src.cli.neon_commands import app as neon_app

# Import output utilities from the shared module (avoids circular imports)
from src.cli.output import (  # noqa: F401
    _set_direct_mode,
    _set_json_mode,
    _set_remote_db,
    is_direct_mode,
    is_json_mode,
    is_remote_db,
    output_result,
)
from src.cli.profile_commands import app as profile_app
from src.cli.prompt_commands import app as prompts_app
from src.cli.review_commands import app as review_app
from src.cli.settings_commands import app as settings_app
from src.cli.source_commands import app as sources_app
from src.cli.sync_commands import app as sync_app
from src.cli.worker_commands import app as worker_app
from src.cli.workflow_commands import (
    WorkflowCliState,
    audio_digest_app,
    capabilities,
    configured_sources,
    default_client_factory,
    digest_app,
    ingest_app,
    operations_app,
    pipeline_app,
    podcast_audio_app,
    podcast_script_app,
    summarize_app,
    theme_app,
)
from src.clients.operational_observability import install_cli_telemetry


class CanonicalCommandGroup(TyperGroup):
    """Add migration guidance while keeping removed aliases unregistered."""

    _REPLACEMENTS: ClassVar[dict[str, str]] = {
        "analyze": "theme create",
        "create-digest": "digest create",
        "jobs": "operations",
        "podcast": "podcast-script create",
    }

    def get_command(self, ctx: Context, cmd_name: str) -> Command | None:
        command = super().get_command(ctx, cmd_name)
        if command is None and cmd_name in self._REPLACEMENTS:
            ctx.fail(
                f"No such command '{cmd_name}'. Use 'aca {self._REPLACEMENTS[cmd_name]}' instead."
            )
        return command


# Root Typer application
app = typer.Typer(
    name="aca",
    cls=CanonicalCommandGroup,
    help="Agentic Content Aggregator — unified CLI for ingesting, summarizing, and delivering AI/Data newsletters.",
    no_args_is_help=True,
)

# Register all sub-command groups
app.add_typer(ingest_app, name="ingest")
app.add_typer(filter_app, name="filter")
app.add_typer(summarize_app, name="summarize")
app.add_typer(digest_app, name="digest")
app.add_typer(edit_app, name="edit")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(review_app, name="review")
app.add_typer(agent_app, name="agent")
app.add_typer(theme_app, name="theme")
app.add_typer(graph_app, name="graph")
app.add_typer(podcast_script_app, name="podcast-script")
app.add_typer(podcast_audio_app, name="podcast-audio")
app.add_typer(audio_digest_app, name="audio-digest")
app.add_typer(operations_app, name="operations")
app.add_typer(manage_app, name="manage")
app.add_typer(neon_app, name="neon")
app.add_typer(profile_app, name="profile")
app.add_typer(prompts_app, name="prompts")
app.add_typer(settings_app, name="settings")
app.add_typer(sources_app, name="sources")
app.add_typer(sync_app, name="sync")
app.add_typer(worker_app, name="worker")
app.add_typer(evaluate_app, name="evaluate")
app.add_typer(batch_app, name="batch")
app.add_typer(models_app, name="models")
app.add_typer(kb_app, name="kb")
app.add_typer(auth_app, name="auth")
app.add_typer(curate_app, name="curate")
app.add_typer(deploy_app, name="deploy")
app.add_typer(backup_app, name="backup")
app.command("capabilities")(capabilities)
app.command("configured-sources")(configured_sources)


def _version_callback(value: bool) -> None:
    if value:
        try:
            version = importlib.metadata.version("agentic-content-analyzer")
        except importlib.metadata.PackageNotFoundError:
            version = "0.1.0-dev"
        typer.echo(f"aca {version}")
        raise typer.Exit()


@app.callback()
def main_callback(
    ctx: typer.Context,
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
            help="Run supported administrative commands without the backend API.",
        ),
    ] = False,
    remote_db: Annotated[
        bool,
        typer.Option(
            "--remote-db",
            help=(
                "Opt in to running direct (in-process) against the REMOTE database "
                "for heavy batch jobs (manage backfills, sync). Implies --direct and "
                "bypasses the split-brain guard with a warning. Requires database_url "
                "to point at the remote backend."
            ),
        ),
    ] = False,
) -> None:
    """Agentic Content Aggregator CLI.

    Ingest newsletters, summarize content, create digests, and manage
    the full content pipeline from a single command.
    """
    _set_json_mode(json_output)
    ctx.obj = WorkflowCliState(
        json_output=json_output,
        client_factory=default_client_factory,
    )

    # Reset legacy administrative-command modes on every invocation. Canonical
    # workflow commands ignore direct mode and always use durable HTTP submission.
    _set_remote_db(remote_db)
    _set_direct_mode(direct or remote_db)

    if debug:
        from src.config import settings

        settings.log_level = "DEBUG"
        settings.log_format = "json" if json_output else "text"

    from src.utils.logging import setup_logging

    setup_logging()
    install_cli_telemetry(ctx)
