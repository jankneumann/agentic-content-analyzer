"""CLI command for restoring a cloud backup into a Postgres database.

Design reference: `openspec/changes/cloud-db-source-of-truth/design.md` D5, as
amended by `add-gx10-backup-scheme`.

This module is a thin subprocess orchestrator — it calls `rclone`, `age` and
`pg_restore` via `subprocess.run`. It does NOT reimplement database restore logic
in Python. Nonzero exit codes from subprocesses propagate to the CLI caller.

What changed for gx-10, and why:

* **Endpoint-agnostic.** The target is resolved from the provider-neutral
  `backup_s3_*` settings, so R2, AWS S3 and MinIO all take the same code path.
  The command previously spoke `mc` to a MinIO endpoint only.
* **Discovery no longer depends on a filename prefix.** It matched a literal
  `railway-` in the dump filename, which no artifact this project now writes
  carries. Artifacts are found by the configured prefix and the timestamp
  convention instead.
* **Encrypted artifacts are decrypted on the way in**, because the backup path
  encrypts on the way out and a restore that cannot decrypt is not a restore.

Three credential-safety fixes land here too, unavoidably, because this rewrite
edits exactly those lines:

1. Credentials were passed as `mc alias set <endpoint> <user> <password>` — argv,
   which is world-readable in /proc for the life of the process.
2. The success payload echoed `target_db` with its password in clear, so a JSON
   log of a successful restore leaked the database password.
3. The live-database guard compared URLs with `str.strip()` equality, so a
   trailing slash, a `?sslmode=require`, or a default port written explicitly
   defeated it — and the thing it guards is `pg_restore --clean --if-exists`
   against production.

Usage::

    aca manage restore-from-cloud
    aca manage restore-from-cloud --backup-date 2026-04-20
    aca manage restore-from-cloud --target-db postgresql://localhost/my_local
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlsplit

import typer

from src.cli.output import is_json_mode, output_result
from src.clients.operational_observability import operational_stage
from src.config.settings import get_settings

app = typer.Typer(help="Cloud backup restoration commands.")

#: Artifact keys are `<prefix>/<tier>/<ISO-8601 stamp>/<name>`; the date is the
#: first ten characters of the stamp segment. Nothing here depends on the file
#: NAME, so a `postgres.dump.age` written by `aca backup run` and a legacy
#: `railway-....dump` are both discoverable.
_ARTIFACT_KEY_RE = re.compile(
    r"(?P<key>[\w./-]*?(?P<date>\d{4}-\d{2}-\d{2})T\d{6}Z/[\w.-]+\.dump(?:\.age)?)$"
)

#: Ports that mean "the default", so `host/db` and `host:5432/db` compare equal.
_DEFAULT_PG_PORT = 5432


def _error(msg: str, *, code: int = 1) -> None:
    """Emit an error and exit non-zero. Errors go to stderr even in --json mode."""
    if is_json_mode():
        output_result({"success": False, "error": msg}, success=False)
    else:
        typer.echo(typer.style(f"Error: {msg}", fg=typer.colors.RED), err=True)
    raise typer.Exit(code)


def mask_text(text: str, *urls: str) -> str:
    """Redact any password from `urls` wherever it appears in `text`.

    Subprocess stderr is quoted back to the operator because a restore failure is
    useless without it. This makes quoting it safe regardless of what the tool
    chose to echo.
    """
    redacted = text
    for url in urls:
        try:
            password = urlsplit(url).password
        except ValueError:
            continue
        for secret in {password, unquote(password)} if password else set():
            if secret:
                redacted = redacted.replace(secret, "***")
    return redacted


def split_database_credentials(url: str) -> tuple[str, dict[str, str]]:
    """Split a Postgres URL into an argv-safe URL and the env that carries the password.

    `pg_restore --dbname <url>` puts the whole URL in argv, and argv is world
    readable in /proc for the life of the process — the very leak this module's
    `mc alias set` fix removed, reproduced one subprocess later. libpq reads
    `PGPASSWORD` from the environment, which is readable only by the process owner,
    so the password travels there and the URL that reaches argv carries none.

    Returns the URL unchanged with an empty env when there is no password to move.
    """
    parts = urlsplit(url)
    if not parts.password:
        return url, {}
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    userinfo = f"{parts.username}@" if parts.username else ""
    stripped = f"{parts.scheme}://{userinfo}{host}{parts.path}" + (
        f"?{parts.query}" if parts.query else ""
    )
    return stripped, {"PGPASSWORD": unquote(parts.password)}


def mask_database_url(url: str) -> str:
    """Replace the password in a Postgres URL with a fixed mask.

    Applied to every emitted `target_db`. Reporting the URL back is genuinely
    useful — it is how an operator confirms the restore went where they meant —
    but the password is no part of that confirmation.
    """
    parts = urlsplit(url)
    if not parts.password:
        return url
    userinfo = f"{parts.username}:***" if parts.username else "***"
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return f"{parts.scheme}://{userinfo}@{host}{parts.path}" + (
        f"?{parts.query}" if parts.query else ""
    )


@dataclass(frozen=True)
class DatabaseIdentity:
    """The parts of a Postgres URL that determine WHICH database it addresses.

    Credentials, SSL mode, application name and search path are all absent: two
    URLs differing only in those address the same database, and a guard that
    treats them as different databases does not guard anything.
    """

    host: str
    port: int
    database: str

    @classmethod
    def parse(cls, url: str | None) -> DatabaseIdentity | None:
        if not url:
            return None
        try:
            parts = urlsplit(str(url).strip())
        except ValueError:
            return None
        host = (parts.hostname or "").lower().rstrip(".")
        if not host:
            return None
        database = unquote(parts.path).strip("/")
        if not database:
            return None
        return cls(host=host, port=parts.port or _DEFAULT_PG_PORT, database=database)


def _addresses_same_database(left: str | None, right: str | None) -> bool:
    """True when both URLs address the same database, however they are written.

    The original comparison was `str(a).strip() == str(b).strip()`. Every one of
    these defeated it while still pointing at production: a trailing slash, an
    explicit `:5432`, an added `?sslmode=require`, a differently-cased host, a
    percent-encoded password. The guarded operation is
    `pg_restore --clean --if-exists`, which drops objects in the target.
    """
    parsed_left = DatabaseIdentity.parse(left)
    parsed_right = DatabaseIdentity.parse(right)
    if parsed_left is None or parsed_right is None:
        return False
    return parsed_left == parsed_right


def _resolve_target_db(
    target_db: str | None,
    settings_obj: Any,
    *,
    allow_remote: bool = False,
) -> str:
    """Resolve the target database URL — defends against restoring over production.

    Default resolution order (safe):
      1. Explicit --target-db value (operator is responsible).
      2. settings.database_url (local scratch / development target).

    ``railway_database_url`` is the source-of-truth production URL. Falling back
    to it as the restore target would let ``aca manage restore-from-cloud --yes``
    silently run ``pg_restore --clean --if-exists`` against production — the exact
    opposite of what sync-down is supposed to do. We refuse this unless the
    operator passes ``--allow-remote-target`` as an explicit opt-in.
    """
    railway_url = getattr(settings_obj, "railway_database_url", None)
    local_url = getattr(settings_obj, "database_url", None)
    refusal_hint = "Pass --allow-remote-target if this is really what you want."

    if target_db:
        # Explicit override — but guard against accidentally pasting the prod URL,
        # in any of the many forms that address the same database.
        if not allow_remote and _addresses_same_database(target_db, railway_url):
            _error(
                "Refusing to restore over the Railway cloud database (--target-db "
                f"addresses the same database as RAILWAY_DATABASE_URL). {refusal_hint}"
            )
        return target_db

    # No explicit target — default STRICTLY to local DATABASE_URL, never railway.
    if not local_url:
        if railway_url and not allow_remote:
            _error(
                "No local DATABASE_URL configured, and falling back to RAILWAY_DATABASE_URL "
                "is refused (would overwrite production). Pass --target-db or set DATABASE_URL."
            )
        if allow_remote and railway_url:
            return str(railway_url)
        _error(
            "No target database configured. Pass --target-db or set DATABASE_URL in your profile."
        )

    # Even when DATABASE_URL is set, refuse if it addresses the same database as
    # RAILWAY_DATABASE_URL — that means a profile has pointed the "local" DB at
    # the cloud source-of-truth.
    if not allow_remote and _addresses_same_database(local_url, railway_url):
        _error(
            "Refusing to restore: DATABASE_URL addresses the same database as "
            f"RAILWAY_DATABASE_URL, which would overwrite production. {refusal_hint}"
        )
    return str(local_url)


def _parse_backup_listing(stdout: str, prefix: str) -> list[tuple[str, str]]:
    """Parse `rclone lsjson` output into (date, key) pairs.

    Discovery is by the configured prefix and the timestamp convention, never by a
    `railway-` filename prefix — no artifact this project writes carries one.
    """
    try:
        entries = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    found: list[tuple[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("Path") or "")
        match = _ARTIFACT_KEY_RE.search(f"{prefix}/{path}" if prefix else path)
        if match:
            found.append((match.group("date"), match.group("key")))
    return found


def _run_restore_phase(
    phase: str,
    argv: list[str],
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run one real restore subprocess inside masked phase and outcome spans."""
    with operational_stage(
        f"restore.{phase}",
        stage="restore",
        attributes={"restore.phase": phase},
    ):
        result = subprocess.run(argv, **kwargs)
        with operational_stage(
            f"restore.{phase}.outcome",
            stage="restore",
            attributes={
                "restore.phase": phase,
                "operation.outcome": (
                    "succeeded" if result.returncode == 0 else "permanent_failure"
                ),
            },
        ):
            pass
        return result


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
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt.",
    ),
    allow_remote_target: bool = typer.Option(
        False,
        "--allow-remote-target",
        help="DANGEROUS: allow the target DB to be the Railway production URL. "
        "Default is to refuse — sync-down should restore to a LOCAL scratch DB.",
    ),
) -> None:
    """Restore a backup dump from the configured backup target into Postgres.

    A thin wrapper around `rclone` + `age` + `pg_restore`. Fails fast on any
    subprocess error; does NOT retry. See docs/BACKUP_RESTORE.md for the full
    workflow and prerequisites.
    """
    from src.services.backup.target import (
        BackupTargetNotConfiguredError,
        TargetConfig,
    )

    settings_obj = get_settings()

    # --- 1. Resolve the backup target ----------------------------------------
    try:
        config = TargetConfig.from_settings(settings_obj)
    except BackupTargetNotConfiguredError as exc:
        _error(
            f"{exc} Set BACKUP_S3_BUCKET (and BACKUP_S3_ENDPOINT for R2/MinIO); "
            "the legacy RAILWAY_MINIO_* names still map forward."
        )
        return  # unreachable — _error raises

    if not config.access_key_id or not config.secret_access_key:
        _error(
            "Backup target credentials are not configured. Set "
            "BACKUP_S3_ACCESS_KEY_ID and BACKUP_S3_SECRET_ACCESS_KEY."
        )
        return

    target_url = _resolve_target_db(target_db, settings_obj, allow_remote=allow_remote_target)
    # Every credential travels by environment. rclone reads RCLONE_CONFIG_*; a
    # `--s3-secret-access-key` flag would put it in argv instead.
    rclone_env = config.rclone_env()

    # --- 2. Confirm (skip in --json / --yes) ---------------------------------
    if not yes and not is_json_mode():
        typer.echo(
            f"About to restore a backup into {mask_database_url(target_url)}.\n"
            "This will run `pg_restore --clean --if-exists` against the target DB."
        )
        if not typer.confirm("Proceed?"):
            raise typer.Exit(0)

    # --- 3. List backups -----------------------------------------------------
    ls_result = subprocess.run(
        ["rclone", "lsjson", "--recursive", config.remote_path(config.prefix)],  # noqa: S607
        capture_output=True,
        text=True,
        env=rclone_env,
        check=False,
    )
    if ls_result.returncode != 0:
        _error(
            f"rclone lsjson failed (exit {ls_result.returncode}): "
            f"{ls_result.stderr.strip() or ls_result.stdout.strip()}"
        )
        return

    available = _parse_backup_listing(ls_result.stdout, config.prefix)
    if not available:
        _error(f"No backup dumps found under {config.bucket}/{config.prefix}.")
        return

    # --- 4. Resolve the artifact --------------------------------------------
    if backup_date:
        matches = [(d, k) for (d, k) in available if d == backup_date]
        if not matches:
            _error(
                f"No backup found for date {backup_date}. "
                f"Available dates: {sorted({d for d, _ in available})}"
            )
            return
        artifact_key = sorted(matches)[-1][1]
    else:
        artifact_key = sorted(available)[-1][1]

    encrypted = artifact_key.endswith(".age")
    local_name = artifact_key.rsplit("/", 1)[-1]
    staged_path = f"{dump_dir.rstrip('/')}/{local_name}"
    restore_path = staged_path.removesuffix(".age")

    # --- 5. Download ---------------------------------------------------------
    cp_result = _run_restore_phase(
        "download",
        ["rclone", "copyto", config.remote_path(artifact_key), staged_path],
        capture_output=True,
        text=True,
        env=rclone_env,
        check=False,
    )
    if cp_result.returncode != 0:
        _error(
            f"rclone copyto failed (exit {cp_result.returncode}): "
            f"{cp_result.stderr.strip() or cp_result.stdout.strip()}"
        )
        return

    # --- 6. Decrypt ----------------------------------------------------------
    if encrypted:
        identity = getattr(settings_obj, "backup_age_identity_path", None)
        if not identity:
            _error(
                "This artifact is age-encrypted but BACKUP_AGE_IDENTITY_PATH is not "
                "set, so it cannot be decrypted. Recover the escrowed identity key "
                "first — see docs/BACKUP_RESTORE.md."
            )
            return
        age_result = _run_restore_phase(
            "decrypt",
            [
                "age",
                "--decrypt",
                "--identity",
                str(identity),
                "--output",
                restore_path,
                staged_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if age_result.returncode != 0:
            _error(
                f"age decryption failed (exit {age_result.returncode}). The identity "
                "at BACKUP_AGE_IDENTITY_PATH does not open this artifact."
            )
            return

    # --- 7. pg_restore -------------------------------------------------------
    # --clean --if-exists DROPS objects in the target. Retained deliberately: a
    # restore into a database holding stale objects produces a silently mixed
    # state, which is worse than a loud one. The guards above are what make it
    # safe, not its absence.
    # The password is moved out of argv and into PGPASSWORD. `--clean --if-exists`
    # is retained deliberately (see above); what changes here is only WHERE the
    # credential travels.
    argv_url, pg_env = split_database_credentials(target_url)
    pg_result = _run_restore_phase(
        "apply",
        [
            "pg_restore",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "--format=custom",
            "--dbname",
            argv_url,
            restore_path,
        ],
        capture_output=True,
        text=True,
        env={**os.environ, **pg_env} if pg_env else None,
        check=False,
    )
    if pg_result.returncode != 0:
        # pg_restore echoes the connection string it was given on failure. That
        # string no longer carries a password, but it is masked anyway rather than
        # relying on that remaining true.
        detail = pg_result.stderr.strip() or pg_result.stdout.strip()
        _error(f"pg_restore failed (exit {pg_result.returncode}): {mask_text(detail, target_url)}")
        return

    # --- 8. Summary ----------------------------------------------------------
    summary: dict[str, Any] = {
        "success": True,
        "dump_file": local_name,
        "source": artifact_key,
        "local_path": restore_path,
        "decrypted": encrypted,
        # Masked: a JSON log of a successful restore previously carried the
        # target database password in clear.
        "target_db": mask_database_url(target_url),
    }

    if is_json_mode():
        output_result(summary)
    else:
        typer.echo(
            typer.style(
                f"Restored {local_name} into {mask_database_url(target_url)}.",
                fg=typer.colors.GREEN,
            )
        )
        typer.echo(f"  Local dump staged at: {restore_path}")
        typer.echo("  (Delete manually if no longer needed.)")
