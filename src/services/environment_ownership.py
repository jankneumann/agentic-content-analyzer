"""Shared-database ownership fence for mutually exclusive mutation environments."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.contracts.workflow_models import EnvironmentOwnershipStatus, OwnershipDryRun

MAX_INT64 = 9_223_372_036_854_775_807
_UNCONFIGURED_FINGERPRINT = "0" * 64
_CUTOVER_CHECKS = [
    "shared_authority.match",
    "current_owner.fence_first",
    "passive_target.verify_second",
    "target_mutations.enable_last",
]


class OwnershipFenceRejected(RuntimeError):  # noqa: N818 - closed fence outcome
    """The caller is not the one current shared-database mutation owner."""


class EnvironmentOwnershipUnavailable(RuntimeError):  # noqa: N818 - closed fence outcome
    """The authoritative ownership record cannot be verified."""


@dataclass(frozen=True, slots=True)
class OwnershipIdentity:
    """Configured identity which a process must prove at mutation time."""

    configured_environment: str
    authority_fingerprint: str
    expected_epoch: int | None


@dataclass(frozen=True, slots=True)
class EnvironmentOwnershipRecord:
    """One verified snapshot of the singleton authoritative ownership row."""

    authority_fingerprint: str
    active_environment: str
    epoch: int
    database_authority_fingerprint: str


def configured_ownership_identity() -> OwnershipIdentity:
    """Build the inactive-by-default local identity for status reporting.

    This package deliberately does not activate GX-10. No local epoch is
    inferred from the database: a later cutover must distribute the selected
    shared epoch explicitly before mutation gates can open.
    """

    settings = get_settings()
    return OwnershipIdentity(
        configured_environment="gx10" if settings.gx10_runtime_enabled else settings.environment,
        authority_fingerprint=(settings.gx10_authority_fingerprint or _UNCONFIGURED_FINGERPRINT),
        expected_epoch=None,
    )


def database_authority_fingerprint(session: Session) -> str:
    """Return a credential-free identity for the database behind the session.

    The ownership row is meaningful only when read from the configured shared
    PostgreSQL authority. Binding it to the connection endpoint prevents an
    independently cloned database with the same row and epoch from presenting
    itself as that authority.
    """

    try:
        bind = session.get_bind()
        url = getattr(bind, "url", None)
        if url is None:
            url = getattr(getattr(bind, "engine", None), "url", None)
        if not isinstance(url, URL) or url.get_backend_name() != "postgresql":
            raise ValueError("ownership authority requires PostgreSQL")
        host = (url.host or "").lower().rstrip(".")
        port = url.port or 5432
        database = (url.database or "").lstrip("/")
        if not host or not database:
            raise ValueError("ownership authority endpoint is incomplete")
    except (SQLAlchemyError, AttributeError, TypeError, ValueError) as exc:
        raise EnvironmentOwnershipUnavailable(
            "environment ownership database authority unavailable"
        ) from exc

    authority = f"{host}:{port}/{database}".encode()
    return hashlib.sha256(authority).hexdigest()


def _read_ownership(session: Session, *, locking: bool) -> EnvironmentOwnershipRecord:
    suffix = " FOR SHARE" if locking else ""
    try:
        row = (
            session.execute(
                text(
                    "SELECT authority_fingerprint, active_environment, epoch "
                    "FROM environment_ownership WHERE singleton IS TRUE" + suffix
                )
            )
            .mappings()
            .one_or_none()
        )
    except SQLAlchemyError as exc:
        raise EnvironmentOwnershipUnavailable(
            "environment ownership authority unavailable"
        ) from exc
    if row is None:
        raise EnvironmentOwnershipUnavailable("environment ownership authority unavailable")
    database_fingerprint = database_authority_fingerprint(session)
    return EnvironmentOwnershipRecord(
        authority_fingerprint=str(row["authority_fingerprint"]),
        active_environment=str(row["active_environment"]),
        epoch=int(row["epoch"]),
        database_authority_fingerprint=database_fingerprint,
    )


def _passive_reasons(
    record: EnvironmentOwnershipRecord,
    identity: OwnershipIdentity,
) -> list[str]:
    reasons: list[str] = []
    if record.authority_fingerprint != identity.authority_fingerprint:
        reasons.append("authority.mismatch")
    if record.authority_fingerprint != record.database_authority_fingerprint:
        reasons.append("authority.database_mismatch")
    if record.active_environment != identity.configured_environment:
        reasons.append("environment.passive")
    if identity.expected_epoch is None:
        reasons.append("epoch.unconfigured")
    elif record.epoch != identity.expected_epoch:
        reasons.append("epoch.stale")
    return reasons


def _dry_run(
    record: EnvironmentOwnershipRecord,
    identity: OwnershipIdentity,
    target: str,
) -> OwnershipDryRun:
    if record.authority_fingerprint != identity.authority_fingerprint:
        checks = ["shared_authority.mismatch"]
    elif record.authority_fingerprint != record.database_authority_fingerprint:
        checks = ["shared_database_authority.mismatch"]
    elif identity.expected_epoch is None:
        checks = ["epoch.unconfigured"]
    elif record.epoch != identity.expected_epoch:
        checks = ["epoch.stale"]
    elif target == record.active_environment:
        checks = ["target.already_active"]
    elif record.epoch == MAX_INT64:
        checks = ["epoch.exhausted"]
    else:
        return OwnershipDryRun(
            target_environment=target,
            allowed=True,
            next_epoch=str(record.epoch + 1),
            checks=_CUTOVER_CHECKS,
        )
    return OwnershipDryRun(
        target_environment=target,
        allowed=False,
        next_epoch=None,
        checks=checks,
    )


def evaluate_environment_ownership(
    session: Session,
    identity: OwnershipIdentity,
    *,
    dry_run_target: str | None = None,
) -> EnvironmentOwnershipStatus:
    """Return a bounded, read-only ownership verdict from the shared authority."""

    record = _read_ownership(session, locking=False)
    reasons = _passive_reasons(record, identity)
    authority_matches = (
        record.authority_fingerprint == identity.authority_fingerprint
        and record.authority_fingerprint == record.database_authority_fingerprint
    )
    mode: Literal["active", "passive", "conflict"]
    if not authority_matches or "epoch.stale" in reasons:
        mode = "conflict"
    elif reasons:
        mode = "passive"
    else:
        mode = "active"
    return EnvironmentOwnershipStatus(
        configured_environment=identity.configured_environment,
        active_environment=record.active_environment,
        mode=mode,
        authority_matches=authority_matches,
        authority_fingerprint_prefix=record.authority_fingerprint[:12],
        epoch=str(record.epoch),
        passive_reasons=reasons,
        dry_run=(
            _dry_run(record, identity, dry_run_target) if dry_run_target is not None else None
        ),
    )


def require_mutation_ownership(
    session: Session,
    identity: OwnershipIdentity,
) -> EnvironmentOwnershipRecord:
    """Lock and verify exact environment, authority, and epoch before mutation."""

    record = _read_ownership(session, locking=True)
    reasons = _passive_reasons(record, identity)
    if reasons:
        raise OwnershipFenceRejected("environment ownership fence rejected: " + ", ".join(reasons))
    return record
