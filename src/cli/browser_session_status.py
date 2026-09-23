"""Browser-session rows for ``aca auth status``.

One row per browser session (``substack``, ``x``) with presence, source,
``saved_at``, ``last_verified_at`` and the command that refreshes it. Values
come from :class:`~src.config.credentials.CredentialProvider` metadata, which
never carries a credential value; nothing in this module reads one.

``last_verified_at`` has to survive across processes, and the provider only
keeps it in the memory of the worker that verified the value. The durable
record is the ingestion history in ``pgqueuer_jobs``: the completion time of
the most recent successful ingestion (outcome ``success`` or ``zero_items``) of
the source the session gates. The lookup follows the active profile the same
way other read commands do (HTTP to ``/api/v1/ingestions`` under a remote
profile, the local queue database otherwise) and is bounded by a short
timeout. When it cannot answer, ``last_verified_at`` is reported as unknown and
the status command still succeeds.
"""

from __future__ import annotations

import asyncio
import os
import secrets
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, cast

from src.config.credentials import (
    SUBSTACK_SESSION_COOKIE,
    X_AUTH_TOKEN,
    X_CT0,
    CredentialMetadata,
    get_credential_provider,
)

LOOKUP_TIMEOUT_S = 5.0
"""Upper bound for the ingestion-history lookup, so status never hangs."""

VERIFYING_OUTCOMES: tuple[Literal["success", "zero_items"], ...] = ("success", "zero_items")
"""Ingestion outcomes that prove the remote site accepted the session.

``partial`` is excluded: some of its sources failed, possibly on the session.
"""


@dataclass(frozen=True)
class BrowserSessionSpec:
    """One browser session and the credentials that make it up."""

    session: str
    credentials: tuple[str, ...]
    """Registered credential names; the session is present only if all are."""
    verified_by: str
    """Ingestion ``command_key`` whose success proves the session works."""
    refresh_command: str


BROWSER_SESSIONS: tuple[BrowserSessionSpec, ...] = (
    BrowserSessionSpec(
        session="substack",
        credentials=(SUBSTACK_SESSION_COOKIE,),
        verified_by="substack",
        refresh_command="aca auth session substack",
    ),
    BrowserSessionSpec(
        session="x",
        credentials=(X_AUTH_TOKEN, X_CT0),
        verified_by="x_bookmarks",
        refresh_command="aca auth session x",
    ),
)


@dataclass(frozen=True)
class VerificationLookup:
    """Result of the durable ``last_verified_at`` lookup. Never secret."""

    available: bool
    last_success: Mapping[str, datetime | None] = field(default_factory=dict)
    """``command_key`` -> completion time of its latest successful ingestion."""
    via: str | None = None
    """``"api"`` or ``"database"`` when available."""
    reason: str | None = None
    """Why the lookup is unavailable (exception type or policy), never a value."""


LastVerifiedLookup = Callable[[Sequence[str]], VerificationLookup]


# -- durable last_verified_at lookup -------------------------------------


def _latest(current: datetime | None, candidate: datetime | None) -> datetime | None:
    if candidate is None:
        return current
    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=UTC)
    return candidate if current is None or candidate > current else current


def _lookup_via_api(
    command_keys: Sequence[str], timeout_s: float, transport: Any | None = None
) -> dict[str, datetime | None]:
    from src.clients.workflow_api_client import WorkflowApiClient
    from src.config.settings import get_settings

    settings = get_settings()
    found: dict[str, datetime | None] = {}
    with WorkflowApiClient(
        settings.api_base_url,
        admin_key=settings.admin_api_key,
        timeout=timeout_s,
        transport=transport,
    ) as client:
        for key in command_keys:
            latest: datetime | None = None
            for outcome in VERIFYING_OUTCOMES:
                page = client.list_ingestion_history(command_key=key, outcome=outcome, limit=1)
                for item in page.data:
                    latest = _latest(latest, item.completed_at)
            found[key] = latest
    return found


async def _lookup_via_database_async(
    command_keys: Sequence[str], connection: Any | None
) -> dict[str, datetime | None]:
    from src.services.operation_service import OperationService

    # Cursors never leave this process, so a throwaway signing key avoids
    # requiring OPERATION_CURSOR_SIGNING_KEY just to read one row.
    service = OperationService(connection=connection, cursor_signing_key=secrets.token_hex(32))
    found: dict[str, datetime | None] = {}
    for key in command_keys:
        latest: datetime | None = None
        for outcome in VERIFYING_OUTCOMES:
            page = await service.list_ingestion_history(command_key=key, outcome=outcome, limit=1)
            for item in page.data:
                latest = _latest(latest, item.completed_at)
        found[key] = latest
    return found


def _lookup_via_database(
    command_keys: Sequence[str], timeout_s: float, connection: Any | None = None
) -> dict[str, datetime | None]:
    return asyncio.run(
        asyncio.wait_for(_lookup_via_database_async(command_keys, connection), timeout_s)
    )


def lookup_last_verified(
    command_keys: Sequence[str], *, timeout_s: float = LOOKUP_TIMEOUT_S
) -> VerificationLookup:
    """Find the latest successful ingestion per ``command_key``. Never raises.

    Routes like other read commands: a remote profile reads the API (the local
    database would be the wrong data, see ``is_remote_backend``); a local
    profile, ``--direct`` or ``--remote-db`` reads the queue database. Any
    failure (connection refused, timeout, HTTP problem, missing settings)
    yields ``available=False`` with the exception type as the reason.
    """
    from src.cli.output import is_direct_mode, is_remote_backend, is_remote_db

    try:
        remote = is_remote_backend()
        if remote and not is_direct_mode():
            return VerificationLookup(
                available=True, last_success=_lookup_via_api(command_keys, timeout_s), via="api"
            )
        if remote and not is_remote_db():
            return VerificationLookup(
                available=False,
                reason="--direct under a remote profile reads local data; add --remote-db",
            )
        return VerificationLookup(
            available=True,
            last_success=_lookup_via_database(command_keys, timeout_s),
            via="database",
        )
    except Exception as exc:
        return VerificationLookup(available=False, reason=type(exc).__name__)


# -- rows -----------------------------------------------------------------


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _source(meta: CredentialMetadata, environ: Mapping[str, str]) -> str | None:
    """``openbao``, ``env`` (a process environment variable), ``settings``, or None."""
    if meta.source == "settings" and environ.get(meta.name):
        return "env"
    return meta.source


def build_session_rows(
    *,
    metadata: Callable[[str], CredentialMetadata] | None = None,
    lookup: LastVerifiedLookup | None = None,
    environ: Mapping[str, str] | None = None,
) -> tuple[list[dict[str, Any]], VerificationLookup]:
    """Return one JSON-safe row per browser session plus the lookup result.

    Rows contain names, booleans, source labels, timestamps and commands only.
    """
    metadata = metadata or get_credential_provider().metadata
    env = os.environ if environ is None else environ
    verification = (lookup or lookup_last_verified)([spec.verified_by for spec in BROWSER_SESSIONS])

    rows: list[dict[str, Any]] = []
    for spec in BROWSER_SESSIONS:
        metas = [metadata(name) for name in spec.credentials]
        credentials = [
            {
                "name": meta.name,
                "label": meta.label,
                "present": meta.present,
                "source": _source(meta, env),
                "saved_at": _iso(meta.saved_at),
            }
            for meta in metas
        ]
        present = all(meta.present for meta in metas)
        sources = {cred["source"] for cred in credentials if cred["present"]}
        source = (sources.pop() if len(sources) == 1 else "mixed") if sources else None
        saved_ats = [meta.saved_at for meta in metas]
        # The session is only as fresh as its oldest part.
        saved_at = (
            min(cast(list[datetime], saved_ats))
            if present and all(at is not None for at in saved_ats)
            else None
        )
        last_verified = (
            verification.last_success.get(spec.verified_by) if verification.available else None
        )
        rows.append(
            {
                "session": spec.session,
                "present": present,
                "source": source,
                "saved_at": _iso(saved_at),
                "last_verified_at": _iso(last_verified),
                "last_verified_status": (
                    "unknown"
                    if not verification.available
                    else ("verified" if last_verified is not None else "never")
                ),
                "verified_by": spec.verified_by,
                "refresh_command": spec.refresh_command,
                "credentials": credentials,
            }
        )
    return rows, verification


def render_session_rows(
    rows: Sequence[Mapping[str, Any]],
    verification: VerificationLookup,
    echo: Callable[[str], None],
) -> None:
    """Render ``rows`` as the human-readable ``aca auth status`` section."""
    echo("Browser session status:\n")
    for row in rows:
        state = "present" if row["present"] else "missing"
        source = f", source {row['source']}" if row["source"] else ""
        echo(f"  {row['session']}: [{state}{source}]")
        for cred in row["credentials"]:
            cred_state = "present" if cred["present"] else "missing"
            cred_source = f" ({cred['source']})" if cred["source"] else ""
            echo(f"    {cred['name']}: [{cred_state}]{cred_source}")
        echo(f"    saved_at:         {row['saved_at'] or 'unknown'}")
        if row["last_verified_status"] == "unknown":
            verified = "unknown (ingestion history unavailable)"
        elif row["last_verified_at"] is None:
            verified = f"never (no successful {row['verified_by']} ingestion)"
        else:
            verified = f"{row['last_verified_at']} (last successful {row['verified_by']} ingestion)"
            if row["saved_at"] and row["saved_at"] > row["last_verified_at"]:
                verified += "; not yet verified since the last save"
        echo(f"    last_verified_at: {verified}")
        echo(f"    refresh:          {row['refresh_command']}")
        echo("")
