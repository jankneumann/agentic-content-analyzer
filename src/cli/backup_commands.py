"""`aca backup` — scheduled off-site backup, verification, and listing.

This is the single entry point for the systemd timer, for a manual run, and for
the round-trip integration test. That is deliberate: when the scheduled path and
the tested path are the same command, "the backup works" is a claim the test suite
can actually make about the thing that runs at 03:00.

Output obeys the CLI JSON contract — exactly one JSON document on stdout, every
diagnostic on stderr — and carries no credential in either mode. There is no
delete subcommand and no delete flag: retention is enforced by backup-target
lifecycle rules, so this command literally cannot remove an object.
"""

from __future__ import annotations

from typing import Any

import typer

from src.cli.output import is_json_mode, output_result

app = typer.Typer(help="Off-site backup: run, verify prerequisites, list artifacts.")


def _fail(message: str, *, payload: dict[str, Any] | None = None, code: int = 1) -> None:
    """Emit a failure. Errors go to stderr even in JSON mode."""
    if is_json_mode():
        output_result({"success": False, "error": message, **(payload or {})}, success=False)
    else:
        typer.echo(typer.style(f"Error: {message}", fg=typer.colors.RED), err=True)
    raise typer.Exit(code)


def _engine(now: Any = None) -> Any:
    from src.config.settings import get_settings
    from src.services.backup.engine import BackupEngine

    return BackupEngine(get_settings(), now=now)


@app.command("run")
def run() -> None:
    """Capture every configured store to the backup target.

    Exits non-zero if ANY store failed. A store that failed must never be able to
    leave a green exit status behind — that is exactly how the backup this
    replaces stayed broken and invisible for as long as it did.
    """
    from src.services.backup.engine import BackupPreflightError
    from src.services.backup.target import BackupTargetNotConfiguredError

    try:
        result = _engine().run()
    except BackupPreflightError as exc:
        _fail(
            f"Backup prerequisites are not met: {exc}",
            payload={"preflight": {"missing": exc.report.describe()}},
        )
        return
    except BackupTargetNotConfiguredError as exc:
        _fail(str(exc))
        return

    payload = {
        "success": result.exit_code == 0,
        "environment": result.environment,
        "retention_tier": str(result.retention_tier),
        "overall_outcome": result.overall_outcome,
        "manifest_written": result.succeeded,
        "stores": [store.to_manifest_entry() for store in result.stores],
    }

    if is_json_mode():
        output_result(payload, success=result.exit_code == 0)
    else:
        for store in result.stores:
            colour = {
                "succeeded": typer.colors.GREEN,
                "skipped": typer.colors.YELLOW,
                "failed": typer.colors.RED,
            }[str(store.outcome)]
            detail = store.reason or f"{store.bytes} bytes"
            typer.echo(
                f"  {typer.style(str(store.outcome).upper(), fg=colour)}"
                f"  {store.store}: {detail}"
            )
        if not result.succeeded:
            typer.echo(
                typer.style(
                    "Manifest NOT written — the previous manifest is left in place so a "
                    "broken backup cannot look fresh.",
                    fg=typer.colors.RED,
                ),
                err=True,
            )

    if result.exit_code != 0:
        raise typer.Exit(result.exit_code)


@app.command("verify")
def verify() -> None:
    """Check prerequisites and prove the canary still decrypts.

    Answers "could I actually restore from this?", which is a different question
    from "did a job run". A missing binary is named individually rather than
    reported as a generic failure.
    """
    from src.services.backup.target import BackupTargetNotConfiguredError

    try:
        result = _engine().verify()
    except BackupTargetNotConfiguredError as exc:
        _fail(str(exc))
        return

    payload = {
        "success": result.ok,
        "missing_binaries": list(result.preflight.missing_binaries),
        "missing_settings": list(result.preflight.missing_settings),
        "canary_present": result.canary_present,
        "canary_decrypted": result.canary_decrypted,
        "manifest_present": result.manifest_present,
        "detail": result.detail,
    }

    if is_json_mode():
        output_result(payload, success=result.ok)
    else:
        for binary in result.preflight.missing_binaries:
            typer.echo(typer.style(f"  MISSING BINARY  {binary}", fg=typer.colors.RED), err=True)
        for setting in result.preflight.missing_settings:
            typer.echo(typer.style(f"  MISSING SETTING {setting}", fg=typer.colors.RED), err=True)
        if result.detail:
            typer.echo(typer.style(f"  {result.detail}", fg=typer.colors.YELLOW), err=True)
        if result.ok:
            typer.echo(typer.style("Backup prerequisites verified.", fg=typer.colors.GREEN))

    if not result.ok:
        raise typer.Exit(1)


@app.command("list")
def list_backups() -> None:
    """List backup artifacts under the configured prefix. Read-only."""
    from src.services.backup.target import BackupTargetNotConfiguredError

    try:
        entries = _engine().list_backups()
    except BackupTargetNotConfiguredError as exc:
        _fail(str(exc))
        return

    if is_json_mode():
        output_result({"success": True, "count": len(entries), "backups": entries})
        return

    if not entries:
        typer.echo("No backup artifacts found under the configured prefix.")
        return
    for entry in entries:
        typer.echo(f"  {entry['modified_at']}  {entry['size']:>12}  {entry['key']}")
