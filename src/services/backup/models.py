"""Closed value types for one backup run.

The shape here is deliberately per-store rather than a single aggregate status.
The backup this change replaces reported nothing at all; the failure mode it must
not reproduce is a run that reports success while one store silently produced
nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any, Literal

# Closed reason tokens. The manifest contract types `reason` as a lowercase token
# rather than free text, because the obvious thing to put there — a subprocess
# stderr body — can echo a connection string into the one object on the backup
# target that is not encrypted.
SKIP_NOT_CONFIGURED = "not_configured"
SKIP_MANAGED_PROVIDER = "managed_provider_no_filesystem_access"
SKIP_NO_ARTIFACT_DIRECTORIES = "no_artifact_directories_present"
FAIL_STAGE_EXIT = "pipeline_stage_exit_nonzero"
FAIL_SIZE_MISMATCH = "uploaded_size_mismatch"
FAIL_SNAPSHOT_FAILED = "snapshot_command_failed"
FAIL_DATABASE_MUST_BE_STOPPED = "database_must_be_stopped_to_dump"


class StoreName(StrEnum):
    POSTGRES = "postgres"
    GRAPHDB = "graphdb"
    ARTIFACTS = "artifacts"
    OPENBAO = "openbao"


class StoreOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class RetentionTier(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


#: Which stores make the whole run a failure when they do not succeed.
#: Postgres is the only store whose loss is unrecoverable from anywhere else.
REQUIRED_STORES: frozenset[StoreName] = frozenset({StoreName.POSTGRES})


def retention_tier_for(run_date: date) -> RetentionTier:
    """Promotion rule, applied at WRITE time.

    Design A5: lifecycle rules expire by age under a prefix, and R2 does not
    support tag filters. Age-based expiry over one flat prefix keeps everything
    for N days and then nothing — the weekly and monthly tiers could not exist.
    So the tier is a segment of the key, decided here:

    * first of the month  -> monthly
    * Sunday              -> weekly
    * otherwise           -> daily

    Checked most-specific-first, so the 1st of a month that falls on a Sunday is
    monthly, not weekly. A run belongs to exactly one tier.
    """
    if run_date.day == 1:
        return RetentionTier.MONTHLY
    if run_date.weekday() == 6:  # Monday is 0; Sunday is 6.
        return RetentionTier.WEEKLY
    return RetentionTier.DAILY


@dataclass(frozen=True)
class StoreResult:
    """One store's contribution to a run."""

    store: StoreName
    outcome: StoreOutcome
    required: bool
    reason: str | None = None
    artifact_key: str | None = None
    bytes: int | None = None
    checksum_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.outcome is StoreOutcome.SUCCEEDED:
            missing = [
                name
                for name in ("artifact_key", "bytes", "checksum_sha256")
                if getattr(self, name) is None
            ]
            if missing:
                # A7 — a succeeded store without its evidence makes an empty
                # upload indistinguishable from a good one. Refuse to construct it.
                raise ValueError(
                    f"succeeded store {self.store} is missing evidence: {', '.join(missing)}"
                )
        elif self.reason is None:
            raise ValueError(f"non-succeeded store {self.store} must name a reason")

    def to_manifest_entry(self) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "store": str(self.store),
            "outcome": str(self.outcome),
            "required": self.required,
        }
        if self.reason is not None:
            entry["reason"] = self.reason
        if self.artifact_key is not None:
            entry["artifact_key"] = self.artifact_key
        if self.bytes is not None:
            entry["bytes"] = self.bytes
        if self.checksum_sha256 is not None:
            entry["checksum_sha256"] = self.checksum_sha256
        return entry

    @classmethod
    def succeeded(
        cls,
        store: StoreName,
        *,
        artifact_key: str,
        size: int,
        checksum_sha256: str,
    ) -> StoreResult:
        return cls(
            store=store,
            outcome=StoreOutcome.SUCCEEDED,
            required=store in REQUIRED_STORES,
            artifact_key=artifact_key,
            bytes=size,
            checksum_sha256=checksum_sha256,
        )

    @classmethod
    def failed(cls, store: StoreName, reason: str) -> StoreResult:
        return cls(
            store=store,
            outcome=StoreOutcome.FAILED,
            required=store in REQUIRED_STORES,
            reason=reason,
        )

    @classmethod
    def skipped(cls, store: StoreName, reason: str) -> StoreResult:
        return cls(
            store=store,
            outcome=StoreOutcome.SKIPPED,
            required=store in REQUIRED_STORES,
            reason=reason,
        )


@dataclass(frozen=True)
class BackupRunResult:
    """The outcome of one `aca backup run`."""

    environment: str
    started_at: datetime
    completed_at: datetime
    retention_tier: RetentionTier
    prefix: str
    stores: tuple[StoreResult, ...] = field(default_factory=tuple)

    @property
    def failed_required_stores(self) -> tuple[StoreResult, ...]:
        return tuple(
            store
            for store in self.stores
            if store.required and store.outcome is not StoreOutcome.SUCCEEDED
        )

    @property
    def succeeded(self) -> bool:
        """A run succeeds only when every REQUIRED store succeeded.

        A non-required store that failed still makes the command exit non-zero
        (see `exit_code`) — it just does not invalidate the manifest.
        """
        return not self.failed_required_stores

    @property
    def overall_outcome(self) -> Literal["succeeded", "partial"]:
        if all(store.outcome is StoreOutcome.SUCCEEDED for store in self.stores):
            return "succeeded"
        return "partial"

    @property
    def exit_code(self) -> int:
        """Non-zero when ANY store failed, required or not.

        Deliberately stricter than `succeeded`: a failing store must never
        silently pass, and the timer's notion of a bad run is the exit status.
        """
        return 1 if any(s.outcome is StoreOutcome.FAILED for s in self.stores) else 0

    def manifest(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "environment": self.environment,
            "started_at": _isoformat(self.started_at),
            "completed_at": _isoformat(self.completed_at),
            "overall_outcome": self.overall_outcome,
            "retention_tier": str(self.retention_tier),
            "prefix": self.prefix,
            "stores": [store.to_manifest_entry() for store in self.stores],
        }


def _isoformat(value: datetime) -> str:
    """Serialize as UTC with a `Z` suffix.

    Always UTC: the manifest is read by a different host in a different timezone,
    and freshness is an age computation. A local-time stamp would make staleness
    wrong by the offset — silently, and only outside UTC.
    """
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
