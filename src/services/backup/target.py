"""The backup target: key layout, encryption, upload, read-back, listing.

One code path for Cloudflare R2, AWS S3, and MinIO. They differ only in the values
of the `backup_s3_*` settings, so there is no provider branch in this module and
adding one would be a bug.

`rclone` is configured entirely through the environment (`RCLONE_CONFIG_*`) rather
than a config file or `--s3-access-key-id` flags. Both alternatives put the secret
somewhere another local user can read it — argv via /proc, a config file via the
filesystem — and the environment of a process is readable only by its owner.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.services.backup.executor import CommandResult, Stage, run_command
from src.services.backup.models import RetentionTier

#: rclone remote name. Local to the invocation; never persisted to a config file.
REMOTE = "backup"

#: Encrypted artifacts carry this suffix so an unencrypted object on the target is
#: visibly anomalous rather than merely undocumented.
ENCRYPTED_SUFFIX = ".age"

CANARY_NAME = "canary.txt"
CANARY_PLAINTEXT = "aca-backup-canary"


class BackupTargetNotConfiguredError(RuntimeError):
    """The target is missing a setting the run cannot proceed without."""


@dataclass(frozen=True)
class TargetConfig:
    endpoint: str | None
    bucket: str
    region: str
    prefix: str
    access_key_id: str | None
    secret_access_key: str | None

    @classmethod
    def from_settings(cls, settings: Any) -> TargetConfig:
        bucket = getattr(settings, "backup_s3_bucket", None)
        if not bucket:
            raise BackupTargetNotConfiguredError(
                "BACKUP_S3_BUCKET is not set. The backup target must be configured "
                "explicitly; there is no default destination."
            )
        return cls(
            endpoint=_plain(getattr(settings, "backup_s3_endpoint", None)),
            bucket=str(bucket),
            region=str(getattr(settings, "backup_s3_region", None) or "auto"),
            prefix=str(getattr(settings, "backup_s3_prefix", None) or "aca").strip("/"),
            access_key_id=_plain(getattr(settings, "backup_s3_access_key_id", None)),
            secret_access_key=_plain(getattr(settings, "backup_s3_secret_access_key", None)),
        )

    def rclone_env(self) -> dict[str, str]:
        """Credentials and endpoint, by environment only — never argv, never a file."""
        env = {
            f"RCLONE_CONFIG_{REMOTE.upper()}_TYPE": "s3",
            f"RCLONE_CONFIG_{REMOTE.upper()}_PROVIDER": "Other",
            f"RCLONE_CONFIG_{REMOTE.upper()}_REGION": self.region,
            # Never let rclone reach for ~/.aws or an instance profile: an
            # unconfigured backup must fail loudly, not quietly write somewhere else.
            f"RCLONE_CONFIG_{REMOTE.upper()}_ENV_AUTH": "false",
        }
        if self.endpoint:
            env[f"RCLONE_CONFIG_{REMOTE.upper()}_ENDPOINT"] = self.endpoint
        if self.access_key_id:
            env[f"RCLONE_CONFIG_{REMOTE.upper()}_ACCESS_KEY_ID"] = self.access_key_id
        if self.secret_access_key:
            env[f"RCLONE_CONFIG_{REMOTE.upper()}_SECRET_ACCESS_KEY"] = self.secret_access_key
        return env

    def remote_path(self, key: str) -> str:
        return f"{REMOTE}:{self.bucket}/{key}"


def _plain(value: object) -> str | None:
    if value is None:
        return None
    if hasattr(value, "get_secret_value"):
        return str(value.get_secret_value())  # type: ignore[attr-defined]
    text = str(value)
    return text or None


def run_stamp(moment: datetime) -> str:
    """Compact ISO-8601 UTC stamp, safe in an object key."""
    return moment.strftime("%Y-%m-%dT%H%M%SZ")


def artifact_key(
    prefix: str,
    tier: RetentionTier,
    stamp: str,
    artifact_name: str,
) -> str:
    """`<prefix>/<tier>/<stamp>/<name>.age`.

    The tier is a KEY SEGMENT, not a tag: lifecycle rules expire by age under a
    prefix, and R2 supports no tag filters, so tiering by tag would collapse to
    "keep everything N days, then nothing" (design A5).
    """
    return f"{prefix}/{tier}/{stamp}/{artifact_name}{ENCRYPTED_SUFFIX}"


def manifest_key(prefix: str, environment: str) -> str:
    """The well-known, ENVIRONMENT-SCOPED manifest key.

    The environment segment is not cosmetic. With a fixed key under a prefix that
    defaults to a shared constant, a staging run overwrites the production
    freshness signal — production backups could stop entirely while /ready reported
    ok (design A6.3). The reader independently checks the environment recorded
    inside the document, so a mis-set prefix cannot fake it either.
    """
    return f"{prefix}/manifests/{environment}/latest.json"


def canary_key(prefix: str, environment: str) -> str:
    return f"{prefix}/manifests/{environment}/{CANARY_NAME}{ENCRYPTED_SUFFIX}"


def encrypt_stage(recipient: str) -> Stage:
    """`age` encryption, in the pipe, before anything leaves the host.

    The recipient is a PUBLIC key, so it is safe in argv — unlike every other
    secret this package handles.
    """
    return Stage(
        name="age",
        argv=("age", "--encrypt", "--recipient", recipient),
    )


def upload_stage(config: TargetConfig, key: str) -> Stage:
    """`rclone rcat` — streams stdin straight to the object, no local staging."""
    return Stage(
        name="rclone",
        argv=("rclone", "rcat", config.remote_path(key)),
        env=config.rclone_env(),
    )


def stored_size(config: TargetConfig, key: str) -> int | None:
    """Read the stored object's size back from the target.

    Necessary because a successful upload of a TRUNCATED stream is still a
    successful upload. Comparing this against the bytes the pipeline actually
    streamed is what turns "rclone exited 0" into evidence (design A6.1).
    """
    result = run_command(
        ["rclone", "size", "--json", config.remote_path(key)],
        env=config.rclone_env(),
    )
    if not result.ok:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    size = payload.get("bytes")
    return int(size) if isinstance(size, int) else None


def put_text(config: TargetConfig, key: str, body: str) -> CommandResult:
    """Upload a small text object (the manifest) from memory."""
    return run_command(
        ["rclone", "rcat", config.remote_path(key)],
        env=config.rclone_env(),
        stdin_text=body,
    )


def list_objects(config: TargetConfig, *, sub_prefix: str | None = None) -> list[dict[str, Any]]:
    """List objects under the configured prefix. READ ONLY, by construction.

    `lsjson` has no destructive mode; there is no code path in this package that
    can delete from the target, which is what makes "no unattended deletion" a
    property of the code rather than a promise in a document.
    """
    path = config.prefix if sub_prefix is None else f"{config.prefix}/{sub_prefix.strip('/')}"
    result = run_command(
        ["rclone", "lsjson", "--recursive", config.remote_path(path)],
        env=config.rclone_env(),
    )
    if not result.ok:
        return []
    try:
        entries = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def decrypt_command(identity_path: str, remote_key: str) -> tuple[list[str], Mapping[str, str]]:
    """argv for decrypting one object to stdout, for `verify` and for restore."""
    return (
        ["age", "--decrypt", "--identity", identity_path, remote_key],
        {},
    )
