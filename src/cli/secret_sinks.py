"""Secret sinks: where CLI credential commands push a freshly minted secret.

``aca auth gmail|youtube --to <sink>`` (and later browser-session capture
commands) hand a ``{KEY: value}`` mapping to one of these sinks:

* ``railway``      — ``railway variables --set`` on the linked project
                     (the behaviour of the deprecated ``--deploy`` flag).
* ``bao``          — OpenBao KV v2 **server-side PATCH** on the existing
                     ``BAO_MOUNT_PATH``/``BAO_SECRET_PATH`` (default
                     ``secret/newsletter``), recording ``<KEY>_SAVED_AT``.
* ``secrets-file`` — in-place upsert of ``.secrets.yaml`` (``SECRETS_FILE``),
                     preserving every other key and, where possible, comments.

Security contract shared by every sink: values are never logged, echoed, put in
argv (except the Railway CLI, which only accepts ``--set KEY=VALUE``) or placed
in exception messages. Only key names and the target are ever printed.

Why a raw PATCH instead of ``hvac``'s ``kv.v2.patch()``: hvac implements
``patch`` client-side as ``read_secret_version`` + ``create_or_update_secret``
with CAS. That needs ``read`` capability (the workstation AppRole deliberately
lacks it) and is a full-document write. The HTTP ``PATCH`` with
``application/merge-patch+json`` is applied atomically by the server, needs
only the ``patch`` capability, and returns 404 when the secret does not exist —
which this sink surfaces as an error instead of creating the path.
"""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import typer
import yaml

from src.cli import railway as railway_cli
from src.config.secrets import get_secrets_path, saved_at_key

__all__ = [
    "BaoSink",
    "RailwaySink",
    "SecretSink",
    "SecretSinkError",
    "SecretsFileSink",
    "SinkName",
    "build_sink",
    "echo_railway_target_notice",
]

_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


class SinkName(StrEnum):
    """CLI-facing names accepted by ``--to``."""

    RAILWAY = "railway"
    BAO = "bao"
    SECRETS_FILE = "secrets-file"


class SecretSinkError(Exception):
    """A sink could not accept a write. Messages never contain secret values."""


@runtime_checkable
class SecretSink(Protocol):
    """Destination for one or more secrets written in a single operation."""

    name: SinkName

    @property
    def target(self) -> str:
        """Human description of the destination (no values)."""
        ...

    @property
    def next_step_hint(self) -> str:
        """What the operator should do after a successful write."""
        ...

    def check(self) -> None:
        """Fail fast (before any interactive login) if the sink is unusable."""
        ...

    def write(self, values: Mapping[str, str]) -> list[str]:
        """Write every ``KEY -> value`` pair; return the key names written."""
        ...


def _validated(values: Mapping[str, str]) -> dict[str, str]:
    if not values:
        raise SecretSinkError("No secrets to write")
    out: dict[str, str] = {}
    for key, value in values.items():
        if not isinstance(key, str) or not _KEY_RE.match(key):
            raise SecretSinkError(
                f"Invalid secret name {key!r}: expected UPPER_SNAKE_CASE (e.g. X_AUTH_TOKEN)"
            )
        if not isinstance(value, str):
            raise SecretSinkError(f"Value for {key} must be a string")
        out[key] = value
    return out


# ---------------------------------------------------------------------------
# Railway
# ---------------------------------------------------------------------------


def echo_railway_target_notice(service: str | None, linked: str | None) -> None:
    """Surface the two independent sources of truth before pushing to Railway.

    The push writes to whatever Railway project ``railway link`` points at,
    which is *independent* of the active profile's ``api_base_url``. Showing
    both prevents pushing OAuth tokens to the wrong project/service.
    """
    from src.config.settings import get_active_profile_name, get_settings

    profile = get_active_profile_name() or "(none)"
    api_base_url = get_settings().api_base_url
    linked_desc = linked or "(unknown — railway not linked or CLI unavailable)"
    target_service = service or "(default service)"

    typer.echo(
        "\nDeploy target — please confirm before secrets are pushed:\n"
        f"  Active profile : {profile}  (api_base_url: {api_base_url})\n"
        f"  Railway link   : {linked_desc}\n"
        f"  Railway service: {target_service}\n"
        "  NOTE: --to railway pushes to the *linked Railway project* above, which is\n"
        "  independent of the profile's api_base_url. Make sure they match.\n"
    )


class RailwaySink:
    """Push secrets as Railway service variables via the ``railway`` CLI."""

    name = SinkName.RAILWAY

    def __init__(self, service: str | None = None) -> None:
        self.service = service

    @property
    def target(self) -> str:
        return f"Railway service {self.service or '(default service)'}"

    @property
    def next_step_hint(self) -> str:
        return (
            "Restart the Railway service to pick up the new env vars "
            "(railway redeploys automatically on env-var change in most cases)."
        )

    def check(self) -> None:
        railway_cli.ensure_railway_cli()
        echo_railway_target_notice(self.service, railway_cli.linked_target())

    def write(self, values: Mapping[str, str]) -> list[str]:
        pairs = _validated(values)
        # One `railway variables` call per write: a multi-key write (e.g. the
        # X cookie pair) lands in a single redeploy instead of a torn pair.
        railway_cli.set_variables(pairs, service=self.service)
        suffix = f" on service {self.service}" if self.service else ""
        for key in pairs:
            typer.echo(f"Railway env var {key} set{suffix}.")
        return list(pairs)


# ---------------------------------------------------------------------------
# OpenBao
# ---------------------------------------------------------------------------

_BAO_ERROR_HINTS: dict[str, str] = {
    "InvalidPath": (
        "does not exist. This sink only PATCHes an existing KV v2 secret and never "
        "creates it (creating would need a full write). Seed the path first with "
        "`python scripts/bao_seed_newsletter.py`, then re-run."
    ),
    "Forbidden": "denied the write: the token/AppRole needs the 'patch' capability on it.",
    "Unauthorized": "rejected the credentials: check BAO_ROLE_ID/BAO_SECRET_ID or BAO_TOKEN.",
    "UnsupportedOperation": (
        "does not support PATCH: the mount must be KV version 2 on OpenBao/Vault >= 1.9."
    ),
}


def _default_bao_client() -> Any:
    """Build and authenticate an hvac client from ``BAO_*`` env vars."""
    addr = os.environ.get("BAO_ADDR")
    if not addr:
        raise SecretSinkError(
            "BAO_ADDR is not set. Export BAO_ADDR plus BAO_ROLE_ID/BAO_SECRET_ID "
            "(AppRole) or BAO_TOKEN before using --to bao."
        )
    from src.config import bao_secrets

    if bao_secrets.hvac is None:
        raise SecretSinkError(
            "The OpenBao client library is not installed. Install it with: pip install '.[vault]'"
        )
    if not (
        (os.environ.get("BAO_ROLE_ID") and os.environ.get("BAO_SECRET_ID"))
        or os.environ.get("BAO_TOKEN")
    ):
        raise SecretSinkError(
            "No OpenBao credentials: set BAO_ROLE_ID+BAO_SECRET_ID (AppRole) or BAO_TOKEN."
        )
    try:
        client = bao_secrets.hvac.Client(url=addr, timeout=10)
        client, _ttl = bao_secrets._authenticate_client(client)
        authenticated = bool(client.is_authenticated())
    except Exception as exc:
        raise SecretSinkError(
            f"OpenBao authentication at {addr} failed ({type(exc).__name__})"
        ) from exc
    if not authenticated:
        raise SecretSinkError(f"OpenBao authentication at {addr} failed")
    return client


def _utc_now() -> datetime:
    return datetime.now(UTC)


class BaoSink:
    """PATCH secrets into the existing OpenBao KV v2 secret the worker reads.

    Each written key ``K`` gets a sibling ``K_SAVED_AT`` (ISO-8601 UTC) in the
    same atomic PATCH. Every other key at the path is untouched.
    """

    name = SinkName.BAO

    def __init__(
        self,
        *,
        client: Any | None = None,
        client_factory: Callable[[], Any] | None = None,
        mount_path: str | None = None,
        secret_path: str | None = None,
        clock: Callable[[], datetime] = _utc_now,
        # Receives the one value-free success line; None silences it (the API
        # server reports through its response and logger instead).
        echo: Callable[[str], None] | None = typer.echo,
    ) -> None:
        self._client = client
        self._client_factory = client_factory
        self.mount_path = (mount_path or os.environ.get("BAO_MOUNT_PATH") or "secret").strip("/")
        self.secret_path = (secret_path or os.environ.get("BAO_SECRET_PATH") or "newsletter").strip(
            "/"
        )
        self._clock = clock
        self._echo = echo

    @property
    def target(self) -> str:
        return f"OpenBao {self.mount_path}/{self.secret_path}"

    @property
    def next_step_hint(self) -> str:
        return "Restart workers to use the new value (settings load OpenBao once at startup)."

    def _get_client(self) -> Any:
        if self._client is None:
            factory = self._client_factory or _default_bao_client
            self._client = factory()
        return self._client

    def check(self) -> None:
        # Authenticate only. The workstation role cannot read the path, so no
        # existence probe here; a missing path surfaces as a 404 on write.
        self._get_client()

    def write(self, values: Mapping[str, str]) -> list[str]:
        secrets = _validated(values)
        saved_at = self._clock().astimezone(UTC).isoformat(timespec="seconds")
        payload = dict(secrets)
        for key in secrets:
            if not key.endswith("_SAVED_AT"):
                payload[saved_at_key(key)] = saved_at

        client = self._get_client()
        url = f"/v1/{self.mount_path}/data/{self.secret_path}"
        try:
            client.adapter.request(
                "PATCH",
                url,
                headers={"Content-Type": "application/merge-patch+json"},
                json={"data": payload},
            )
        except Exception as exc:
            hint = _BAO_ERROR_HINTS.get(type(exc).__name__)
            if hint is not None:
                message = f"{self.target} {hint}"
            else:
                message = f"PATCH to {self.target} failed ({type(exc).__name__})"
            raise SecretSinkError(message) from exc

        if self._echo is not None:
            self._echo(f"{self.target}: patched {', '.join(secrets)} (saved_at {saved_at}).")
        return list(secrets)


# ---------------------------------------------------------------------------
# .secrets.yaml
# ---------------------------------------------------------------------------


def _yaml_entry(key: str, value: str) -> str:
    return yaml.safe_dump(
        {key: value},
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=float("inf"),
    )


def _is_continuation(lines: list[str], index: int) -> bool:
    """True when ``lines[index]`` still belongs to the previous top-level value."""
    line = lines[index]
    if line[:1] in (" ", "\t"):
        return line.strip() != "" or _next_content_is_indented(lines, index)
    if line.strip() == "":
        return _next_content_is_indented(lines, index)
    return False


def _next_content_is_indented(lines: list[str], index: int) -> bool:
    for later in lines[index + 1 :]:
        if later.strip():
            return later[:1] in (" ", "\t")
    return False


def _upsert_yaml_text(text: str, values: Mapping[str, str]) -> str:
    """Replace or append top-level ``KEY: value`` entries, keeping other lines."""
    lines = text.splitlines(keepends=True)
    for key, value in values.items():
        entry = _yaml_entry(key, value)
        pattern = re.compile(rf"^(?:{key}|'{key}'|\"{key}\")[ \t]*:(?:[ \t]|\r?\n|$)")
        out: list[str] = []
        replaced = False
        i = 0
        while i < len(lines):
            if pattern.match(lines[i]):
                j = i + 1
                while j < len(lines) and _is_continuation(lines, j):
                    j += 1
                if not replaced:
                    out.append(entry)
                    replaced = True
                i = j
                continue
            out.append(lines[i])
            i += 1
        if not replaced:
            if out and not out[-1].endswith("\n"):
                out[-1] += "\n"
            out.append(entry)
        lines = out
    return "".join(lines)


def _atomic_write_private(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` via a same-directory temp file with mode 0600."""
    target = path.resolve() if path.is_symlink() else path
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    os.chmod(target, 0o600)


class SecretsFileSink:
    """Upsert keys into ``.secrets.yaml`` (YAML ``KEY: value``), mode 0600."""

    name = SinkName.SECRETS_FILE

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else get_secrets_path()

    @property
    def target(self) -> str:
        return f"secrets file {self.path}"

    @property
    def next_step_hint(self) -> str:
        return "Local processes read the secrets file at startup; restart them to apply."

    def _read(self) -> tuple[str, dict[str, Any]]:
        if not self.path.exists():
            return "", {}
        text = self.path.read_text(encoding="utf-8")
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise SecretSinkError(
                f"{self.path} is not valid YAML; fix it before writing (use 'KEY: value')"
            ) from exc
        if data is None:
            return text, {}
        if not isinstance(data, dict):
            raise SecretSinkError(f"{self.path} must be a YAML mapping of KEY: value")
        return text, data

    def check(self) -> None:
        self._read()
        parent = self.path.resolve().parent
        if not parent.is_dir():
            raise SecretSinkError(f"Directory for {self.path} does not exist")

    def write(self, values: Mapping[str, str]) -> list[str]:
        secrets = _validated(values)
        original, existing = self._read()
        expected = {**existing, **secrets}

        new_text = _upsert_yaml_text(original, secrets)
        try:
            round_trip = yaml.safe_load(new_text) or {}
        except yaml.YAMLError:
            round_trip = None
        if round_trip != expected:
            # The in-place edit could not be proven lossless (exotic YAML such
            # as anchors or flow mappings). Fall back to a full re-dump, which
            # keeps every key but drops comments.
            new_text = yaml.safe_dump(
                expected,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                width=float("inf"),
            )
            typer.echo(
                f"Warning: could not edit {self.path} in place; rewrote it with all keys "
                "preserved but without comments.",
                err=True,
            )

        _atomic_write_private(self.path, new_text)
        typer.echo(f"Wrote {', '.join(secrets)} to {self.path} (mode 0600).")
        return list(secrets)


def build_sink(name: SinkName, *, service: str | None = None) -> SecretSink:
    """Construct the sink selected by ``--to``."""
    if name is SinkName.RAILWAY:
        return RailwaySink(service=service)
    if name is SinkName.BAO:
        return BaoSink()
    if name is SinkName.SECRETS_FILE:
        return SecretsFileSink()
    raise SecretSinkError(f"Unknown secret sink {name!r}")
