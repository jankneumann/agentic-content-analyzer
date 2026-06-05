"""``aca deploy`` — operations against the deployed Railway service.

Currently provides ``sync-secrets``, which pushes allowlisted secrets from the
local ``.secrets.yaml`` (or env overrides) to a Railway service/environment.

Safety model (mirrors ``aca curate`` / ``substack-sync``):
  - **Allowlist-gated**: only keys declared in ``settings/deploy/railway_secrets.yaml``
    for the target service are eligible.
  - **Dry-run by default**: writes happen only with ``--apply``.
  - **Additive**: variables are created/updated, never deleted.
  - **Redacted**: secret values are always masked in output.
"""

from __future__ import annotations

from typing import Annotated

import typer

from src.cli.output import is_json_mode, output_result
from src.cli.railway import get_variables, linked_target, set_variables

app = typer.Typer(
    name="deploy",
    help="Operations against the deployed Railway service.",
    no_args_is_help=True,
)


@app.callback()
def _deploy() -> None:
    """Operations against the deployed Railway service.

    A no-op callback that forces Typer to treat ``deploy`` as a command group
    (a single-command Typer otherwise collapses and would reject the
    ``sync-secrets`` subcommand name).
    """


def mask(value: str) -> str:
    """Mask a secret for display: first 3 + last 4 chars, dots when too short."""
    if not value:
        return ""
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:3]}…{value[-4:]}"


@app.command("sync-secrets")
def sync_secrets(
    service: Annotated[
        str,
        typer.Option(
            "--service",
            "-s",
            help="Railway service name (must exist in railway_secrets.yaml).",
        ),
    ],
    environment: Annotated[
        str | None,
        typer.Option(
            "--env",
            "--environment",
            help="Railway environment. Required with --apply.",
        ),
    ] = None,
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Write changes. Without this flag, dry-run only."),
    ] = False,
    only: Annotated[
        list[str] | None,
        typer.Option("--only", help="Limit to specific local key(s). Repeatable."),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip the confirmation prompt when applying."),
    ] = False,
) -> None:
    """Sync allowlisted local secrets to a Railway service (dry-run by default)."""
    from src.config.deploy_secrets import DeploySecretsError, SecretMapping, load_mapping
    from src.config.secrets import resolve_secret

    try:
        mapping = load_mapping()
    except DeploySecretsError as e:
        typer.echo(f"Error loading railway_secrets.yaml: {e}", err=True)
        raise typer.Exit(1) from e

    if service not in mapping:
        known = ", ".join(sorted(mapping)) or "(none)"
        typer.echo(
            f"Service '{service}' not found in railway_secrets.yaml. Known services: {known}",
            err=True,
        )
        raise typer.Exit(1)

    if apply and not environment:
        typer.echo(
            "--apply requires an explicit --env (refusing to write to an implicit environment).",
            err=True,
        )
        raise typer.Exit(1)

    svc = mapping[service]
    only_set = set(only) if only else None

    # Resolve local values (env > .secrets.yaml). Missing values are skipped,
    # never pushed.
    pending: list[tuple[SecretMapping, str]] = []
    skipped: list[str] = []
    for sm in svc.secrets:
        if only_set is not None and sm.local not in only_set:
            continue
        value = resolve_secret(sm.local)
        if not value:
            skipped.append(sm.local)
            continue
        pending.append((sm, value))

    # Classify against the live Railway variables.
    remote = get_variables(service=service, environment=environment)
    new: list[tuple[SecretMapping, str]] = []
    changed: list[tuple[SecretMapping, str]] = []
    unchanged: list[tuple[SecretMapping, str]] = []
    for sm, value in pending:
        current = remote.get(sm.railway)
        if current is None:
            new.append((sm, value))
        elif current != value:
            changed.append((sm, value))
        else:
            unchanged.append((sm, value))

    managed_targets = {sm.railway for sm in svc.secrets}
    unmanaged = sorted(k for k in remote if k not in managed_targets)
    to_write = new + changed

    if not is_json_mode():
        _render_diff(service, environment, new, changed, unchanged, skipped, unmanaged)

    applied = False
    if apply and to_write:
        if not is_json_mode() and not yes:
            typer.confirm(
                f"Write {len(to_write)} variable(s) to {service}/{environment}?",
                abort=True,
            )
        set_variables(
            {sm.railway: value for sm, value in to_write},
            service=service,
            environment=environment,
        )
        applied = True
        if not is_json_mode():
            typer.echo(
                f"\nApplied: {len(new)} created, {len(changed)} updated on {service}/{environment}."
            )
    elif apply and not to_write:
        if not is_json_mode():
            typer.echo("\nNothing to apply — all managed secrets are already up to date.")
    elif not is_json_mode():
        typer.echo(
            f"\nDry-run — {len(to_write)} change(s) would be written. Re-run with --apply to write."
        )

    if is_json_mode():
        output_result(
            {
                "service": service,
                "environment": environment,
                "new": [_entry(sm, v) for sm, v in new],
                "changed": [_entry(sm, v) for sm, v in changed],
                "unchanged": [{"local": sm.local, "railway": sm.railway} for sm, _ in unchanged],
                "skipped": skipped,
                "unmanaged": unmanaged,
                "applied": applied,
            }
        )


def _entry(sm: object, value: str) -> dict[str, str]:
    return {"local": sm.local, "railway": sm.railway, "masked": mask(value)}  # type: ignore[attr-defined]


def _render_diff(
    service: str,
    environment: str | None,
    new: list,
    changed: list,
    unchanged: list,
    skipped: list[str],
    unmanaged: list[str],
) -> None:
    """Print a human-readable, redacted diff of the planned sync."""
    target = linked_target() or "(railway not linked or CLI unavailable)"
    env_label = environment or "(default)"
    typer.echo(f"\nRailway secret sync — service '{service}', environment '{env_label}'")
    typer.echo(f"  Linked target: {target}\n")

    for sm, value in new:
        typer.echo(f"  + {sm.railway:<24} [new]        → {mask(value)}")
    for sm, value in changed:
        typer.echo(f"  ~ {sm.railway:<24} [changed]    → {mask(value)}")
    for sm, _ in unchanged:
        typer.echo(f"  = {sm.railway:<24} [unchanged]")
    for local in skipped:
        typer.echo(f"  ? {local:<24} [skipped — no local value]")
    if unmanaged:
        typer.echo(f"\n  Unmanaged on Railway (left untouched): {', '.join(unmanaged)}")
