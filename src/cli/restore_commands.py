"""CLI command for restoring a Railway MinIO backup to a local Postgres.

Design reference: `openspec/changes/cloud-db-source-of-truth/design.md` D5.

This module is a thin subprocess orchestrator — it calls `mc` (MinIO client)
and `pg_restore` via `subprocess.run`. It does NOT reimplement database
restore logic in Python. Nonzero exit codes from subprocesses propagate
to the CLI caller.

Usage::

    aca manage restore-from-cloud
    aca manage restore-from-cloud --backup-date 2026-04-20
    aca manage restore-from-cloud --target-db postgresql://localhost/my_local
"""

from __future__ import annotations

import re
import subprocess
from typing import Any

import typer

from src.cli.output import is_json_mode, output_result
from src.config.settings import get_settings

app = typer.Typer(help="Cloud backup restoration commands.")

# Regex to extract date from `railway-YYYY-MM-DD-HHMM.dump` filenames produced
# by the Railway backup pg_cron job (see docs/SETUP.md "Automated Backups").
_DUMP_FILENAME_RE = re.compile(r"(railway-(\d{4}-\d{2}-\d{2})[-\w]*\.dump)")


def _error(msg: str, *, code: int = 1) -> None:
    """Emit an error and exit non-zero. Errors go to stderr even in --json mode."""
    if is_json_mode():
        output_result({"success": False, "error": msg}, success=False)
    else:
        typer.echo(typer.style(f"Error: {msg}", fg=typer.colors.RED), err=True)
    raise typer.Exit(code)


def _parse_mc_ls_output(stdout: str) -> list[tuple[str, str]]:
    """Parse `mc ls` output into a list of (date, filename) tuples.

    Expected line format::

        [2026-04-20 03:00:00 UTC]  50MiB railway-2026-04-20-0300.dump
    """
    matches: list[tuple[str, str]] = []
    for line in stdout.splitlines():
        m = _DUMP_FILENAME_RE.search(line)
        if m:
            filename, date = m.group(1), m.group(2)
            matches.append((date, filename))
    return matches


def _resolve_target_db(target_db: str | None, settings_obj: Any) -> str:
    """Resolve the target database URL from --target-db or settings."""
    if target_db:
        return target_db
    # Prefer railway_database_url only if explicitly set; otherwise database_url.
    url = settings_obj.railway_database_url or settings_obj.database_url
    if not url:
        _error(
            "No target database configured. Pass --target-db or set DATABASE_URL in your profile."
        )
    return str(url)


@app.command("restore-from-cloud")
def restore_from_cloud(
    backup_date: str | None = typer.Option(
        None,
        "--backup-date",
        help="Date (YYYY-MM-DD) of backup to restore. Defaults to the latest available.",
    ),
    target_db: str | None = typer.Option(
        None,
        "--target-db",
        help="Target DB URL for pg_restore. Defaults to DATABASE_URL from the active profile.",
    ),
    dump_dir: str = typer.Option(
        "/tmp",  # noqa: S108 — user-overridable staging dir; operator-initiated CLI, not multi-tenant service
        "--dump-dir",
        help="Local directory to stage the downloaded dump file.",
    ),
    alias_name: str = typer.Option(
        "aca-backups",
        "--alias",
        help="mc alias name to use (created/overwritten).",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt.",
    ),
) -> None:
    """Restore a Railway MinIO backup dump into a local Postgres database.

    This is a thin wrapper around `mc cp` + `pg_restore`. Fails fast on any
    subprocess error; does NOT retry. See docs/SYNC_DOWN.md for the full
    workflow and prerequisites (mc CLI, pg_restore, safe target DB).
    """
    settings_obj = get_settings()

    # --- 1. Validate MinIO configuration -------------------------------------
    minio_endpoint = settings_obj.railway_minio_endpoint
    minio_user = settings_obj.minio_root_user
    minio_password = settings_obj.minio_root_password
    bucket = settings_obj.railway_backup_bucket or "backups"

    if not minio_endpoint or not minio_user or not minio_password:
        _error(
            "MinIO credentials not configured. "
            "Set RAILWAY_MINIO_ENDPOINT, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD "
            "(typically via the railway-cli profile)."
        )
        return  # unreachable — _error raises

    target_url = _resolve_target_db(target_db, settings_obj)

    # --- 2. Confirm (skip in --json / --yes) ---------------------------------
    if not yes and not is_json_mode():
        typer.echo(
            f"About to restore a Railway backup into {target_url}.\n"
            "This will run `pg_restore --clean --if-exists` against the target DB."
        )
        if not typer.confirm("Proceed?"):
            raise typer.Exit(0)

    # --- 3. Configure mc alias -----------------------------------------------
    alias_result = subprocess.run(
        [  # noqa: S607 — `mc` resolved from operator PATH (thin wrapper; design D5)
            "mc",
            "alias",
            "set",
            alias_name,
            minio_endpoint,
            minio_user,
            minio_password,
        ],
        capture_output=True,
        text=True,
    )
    if alias_result.returncode != 0:
        _error(
            f"mc alias set failed (exit {alias_result.returncode}): "
            f"{alias_result.stderr.strip() or alias_result.stdout.strip()}"
        )
        return

    # --- 4. List backups -----------------------------------------------------
    ls_result = subprocess.run(
        ["mc", "ls", f"{alias_name}/{bucket}/"],  # noqa: S607 — `mc` on PATH
        capture_output=True,
        text=True,
    )
    if ls_result.returncode != 0:
        _error(
            f"mc ls failed (exit {ls_result.returncode}): "
            f"{ls_result.stderr.strip() or ls_result.stdout.strip()}"
        )
        return

    available = _parse_mc_ls_output(ls_result.stdout)
    if not available:
        _error(f"No backup dumps found in {alias_name}/{bucket}/.")
        return

    # --- 5. Resolve dump filename -------------------------------------------
    if backup_date:
        matches = [(d, f) for (d, f) in available if d == backup_date]
        if not matches:
            _error(
                f"No backup found for date {backup_date}. "
                f"Available dates: {sorted({d for d, _ in available})}"
            )
            return
        # Take most recent within the same day (lex sort on filename is fine
        # since the filename embeds HHMM).
        dump_filename = sorted(matches, key=lambda t: t[1])[-1][1]
    else:
        # Latest overall — sort by date then filename.
        dump_filename = sorted(available, key=lambda t: (t[0], t[1]))[-1][1]

    # --- 6. Download dump ----------------------------------------------------
    remote_path = f"{alias_name}/{bucket}/{dump_filename}"
    local_path = f"{dump_dir.rstrip('/')}/{dump_filename}"

    cp_result = subprocess.run(
        ["mc", "cp", remote_path, local_path],  # noqa: S607 — `mc` on PATH
        capture_output=True,
        text=True,
    )
    if cp_result.returncode != 0:
        _error(
            f"mc cp failed (exit {cp_result.returncode}): "
            f"{cp_result.stderr.strip() or cp_result.stdout.strip()}"
        )
        return

    # --- 7. pg_restore -------------------------------------------------------
    pg_result = subprocess.run(
        [  # noqa: S607 — `pg_restore` resolved from operator PATH
            "pg_restore",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "--format=custom",
            "--dbname",
            target_url,
            local_path,
        ],
        capture_output=True,
        text=True,
    )
    if pg_result.returncode != 0:
        _error(
            f"pg_restore failed (exit {pg_result.returncode}): "
            f"{pg_result.stderr.strip() or pg_result.stdout.strip()}"
        )
        return

    # --- 8. Summary ----------------------------------------------------------
    summary: dict[str, Any] = {
        "success": True,
        "dump_file": dump_filename,
        "source": remote_path,
        "local_path": local_path,
        "target_db": target_url,
    }

    if is_json_mode():
        output_result(summary)
    else:
        typer.echo(
            typer.style(
                f"Restored {dump_filename} into {target_url}.",
                fg=typer.colors.GREEN,
            )
        )
        typer.echo(f"  Local dump staged at: {local_path}")
        typer.echo("  (Delete manually if no longer needed.)")
