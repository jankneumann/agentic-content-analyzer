"""Transactional repository for digest-only Obsidian ingest state."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.obsidian_ingest import (
    OBSIDIAN_ERROR_CODES,
    ObsidianIngestEvent,
    ObsidianIngestState,
)

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_MAX_ATTEMPTS = 10
_MAX_LEASE_SECONDS = 3600


class ObsidianIngestRepositoryError(ValueError):
    """A bounded error code that never contains caller-provided private data."""


@dataclass(frozen=True, slots=True)
class ObsidianObservation:
    state_id: int
    event_id: int
    status: str
    eligible: bool
    unchanged: bool
    content_id: int | None
    error_code: str | None


@dataclass(frozen=True, slots=True)
class ObsidianClaim:
    state_id: int
    event_id: int
    configured_source_digest: str
    relative_path_digest: str
    file_hash: str
    claim_token: uuid.UUID
    lease_expires_at: datetime
    attempt_count: int
    operation_id: int


class ObsidianIngestRepository:
    """Own state/event transitions without committing the caller's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _validate_digest(value: str) -> None:
        if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
            raise ObsidianIngestRepositoryError("invalid_digest")

    @staticmethod
    def _validate_now(now: datetime) -> None:
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ObsidianIngestRepositoryError("invalid_timestamp")

    @staticmethod
    def _validate_positive_id(value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ObsidianIngestRepositoryError("invalid_identifier")

    @staticmethod
    def _observation(
        state: ObsidianIngestState,
        event: ObsidianIngestEvent,
        *,
        eligible: bool,
        unchanged: bool,
    ) -> ObsidianObservation:
        return ObsidianObservation(
            state_id=cast(int, state.id),
            event_id=cast(int, event.id),
            status=str(event.status),
            eligible=eligible,
            unchanged=unchanged,
            content_id=event.content_id,
            error_code=event.error_code,
        )

    async def observe_file_version(
        self,
        configured_source_digest: str,
        relative_path_digest: str,
        file_hash: str,
        *,
        observed_mtime_ns: int,
        observed_size: int,
        now: datetime,
    ) -> ObsidianObservation:
        """Record one scan observation and return whether it is newly eligible."""
        self._validate_digest(configured_source_digest)
        self._validate_digest(relative_path_digest)
        self._validate_digest(file_hash)
        self._validate_now(now)
        if (
            not isinstance(observed_mtime_ns, int)
            or isinstance(observed_mtime_ns, bool)
            or observed_mtime_ns < 0
            or not isinstance(observed_size, int)
            or isinstance(observed_size, bool)
            or observed_size < 0
        ):
            raise ObsidianIngestRepositoryError("invalid_observation")

        await self._session.execute(
            insert(ObsidianIngestState)
            .values(
                configured_source_digest=configured_source_digest,
                relative_path_digest=relative_path_digest,
                current_file_hash=file_hash,
                observed_mtime_ns=observed_mtime_ns,
                observed_size=observed_size,
                status="discovered",
                attempt_count=0,
                first_seen_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(
                index_elements=["configured_source_digest", "relative_path_digest"]
            )
        )
        state = (
            await self._session.execute(
                select(ObsidianIngestState)
                .where(
                    ObsidianIngestState.configured_source_digest == configured_source_digest,
                    ObsidianIngestState.relative_path_digest == relative_path_digest,
                )
                .with_for_update()
            )
        ).scalar_one()
        previous_hash = str(state.current_file_hash)

        event_insert_result = await self._session.execute(
            insert(ObsidianIngestEvent)
            .values(
                state_id=state.id,
                configured_source_digest=configured_source_digest,
                relative_path_digest=relative_path_digest,
                file_hash=file_hash,
                status="discovered",
                attempt_count=0,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    "configured_source_digest",
                    "relative_path_digest",
                    "file_hash",
                ]
            )
            .returning(ObsidianIngestEvent.id)
        )
        inserted_event_id = event_insert_result.scalar_one_or_none()
        event = (
            await self._session.execute(
                select(ObsidianIngestEvent)
                .where(
                    ObsidianIngestEvent.configured_source_digest == configured_source_digest,
                    ObsidianIngestEvent.relative_path_digest == relative_path_digest,
                    ObsidianIngestEvent.file_hash == file_hash,
                )
                .with_for_update()
            )
        ).scalar_one()

        event_was_missing = event.status == "deferred" and event.error_code == "file_missing"
        if event_was_missing:
            event.status = "discovered"
            event.error_code = None
            event.completed_at = None
            event.updated_at = now

        is_new_version = inserted_event_id is not None
        changed = previous_hash != file_hash
        state.current_file_hash = file_hash
        state.observed_mtime_ns = observed_mtime_ns
        state.observed_size = observed_size
        state.status = event.status
        state.claim_token = event.claim_token
        state.lease_expires_at = event.lease_expires_at
        state.operation_id = event.operation_id
        state.content_id = event.content_id
        state.error_code = event.error_code
        state.attempt_count = event.attempt_count
        state.missing_since = None
        state.updated_at = now
        await self._session.flush()

        eligible = bool(changed or is_new_version or event_was_missing)
        return self._observation(
            state,
            event,
            eligible=eligible,
            unchanged=not changed and not is_new_version and not event_was_missing,
        )

    async def lookup_event(
        self,
        configured_source_digest: str,
        relative_path_digest: str,
        file_hash: str,
    ) -> ObsidianObservation | None:
        self._validate_digest(configured_source_digest)
        self._validate_digest(relative_path_digest)
        self._validate_digest(file_hash)
        event = (
            await self._session.execute(
                select(ObsidianIngestEvent).where(
                    ObsidianIngestEvent.configured_source_digest == configured_source_digest,
                    ObsidianIngestEvent.relative_path_digest == relative_path_digest,
                    ObsidianIngestEvent.file_hash == file_hash,
                )
            )
        ).scalar_one_or_none()
        if event is None:
            return None
        state = await self._session.get(ObsidianIngestState, event.state_id)
        if state is None:
            return None
        return self._observation(state, event, eligible=False, unchanged=True)

    async def claim_file_version(
        self,
        event_id: int,
        operation_id: int,
        *,
        now: datetime,
        lease_seconds: int = 300,
        max_attempts: int = 3,
    ) -> ObsidianClaim | None:
        """Acquire or recover one file-version lease under row locks."""
        self._validate_positive_id(event_id)
        self._validate_positive_id(operation_id)
        self._validate_now(now)
        if (
            not isinstance(lease_seconds, int)
            or isinstance(lease_seconds, bool)
            or not 1 <= lease_seconds <= _MAX_LEASE_SECONDS
        ):
            raise ObsidianIngestRepositoryError("invalid_lease")
        if (
            not isinstance(max_attempts, int)
            or isinstance(max_attempts, bool)
            or not 1 <= max_attempts <= _MAX_ATTEMPTS
        ):
            raise ObsidianIngestRepositoryError("invalid_attempt_limit")

        state_id = await self._session.scalar(
            select(ObsidianIngestEvent.state_id).where(ObsidianIngestEvent.id == event_id)
        )
        if state_id is None:
            return None
        state = (
            await self._session.execute(
                select(ObsidianIngestState)
                .where(ObsidianIngestState.id == state_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if state is None:
            return None
        event = (
            await self._session.execute(
                select(ObsidianIngestEvent)
                .where(ObsidianIngestEvent.id == event_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if event is None or state.current_file_hash != event.file_hash:
            return None
        if event.status == "ingested":
            return None
        if event.status == "claimed" and cast(datetime, event.lease_expires_at) > now:
            return None
        attempt_count = cast(int, event.attempt_count)
        if attempt_count >= max_attempts:
            event.status = "failed"
            event.claim_token = None
            event.lease_expires_at = None
            event.error_code = "retry_exhausted"
            event.completed_at = now
            event.updated_at = now
            self._copy_event_to_state(state, event, now=now)
            await self._session.flush()
            return None

        token = uuid.uuid4()
        lease_expires_at = now + timedelta(seconds=lease_seconds)
        event.status = "claimed"
        event.claim_token = cast(Any, token)
        event.lease_expires_at = lease_expires_at
        event.operation_id = operation_id
        event.content_id = None
        event.error_code = None
        event.attempt_count = attempt_count + 1
        event.completed_at = None
        event.updated_at = now
        self._copy_event_to_state(state, event, now=now)
        await self._session.flush()
        return ObsidianClaim(
            state_id=cast(int, state.id),
            event_id=cast(int, event.id),
            configured_source_digest=str(event.configured_source_digest),
            relative_path_digest=str(event.relative_path_digest),
            file_hash=str(event.file_hash),
            claim_token=token,
            lease_expires_at=lease_expires_at,
            attempt_count=int(event.attempt_count),
            operation_id=operation_id,
        )

    async def complete_claim(
        self,
        claim: ObsidianClaim,
        *,
        content_id: int,
        now: datetime,
    ) -> bool:
        self._validate_positive_id(content_id)
        self._validate_now(now)
        locked = await self._lock_claim(claim)
        if locked is None:
            return False
        state, event = locked
        if not self._claim_matches(state, event, claim, now=now):
            return False
        event.status = "ingested"
        event.claim_token = None
        event.lease_expires_at = None
        event.content_id = content_id
        event.error_code = None
        event.completed_at = now
        event.updated_at = now
        self._copy_event_to_state(state, event, now=now)
        await self._session.flush()
        return True

    async def fail_claim(
        self,
        claim: ObsidianClaim,
        *,
        error_code: str,
        now: datetime,
        deferred: bool = False,
    ) -> bool:
        if error_code not in OBSIDIAN_ERROR_CODES:
            raise ObsidianIngestRepositoryError("invalid_error_code")
        self._validate_now(now)
        locked = await self._lock_claim(claim)
        if locked is None:
            return False
        state, event = locked
        if not self._claim_matches(state, event, claim, now=now):
            return False
        event.status = "deferred" if deferred else "failed"
        event.claim_token = None
        event.lease_expires_at = None
        event.error_code = error_code
        event.completed_at = now
        event.updated_at = now
        self._copy_event_to_state(state, event, now=now)
        await self._session.flush()
        return True

    async def mark_missing(
        self,
        configured_source_digest: str,
        relative_path_digest: str,
        *,
        now: datetime,
    ) -> bool:
        """Tombstone a missing file without deleting its event or content."""
        self._validate_digest(configured_source_digest)
        self._validate_digest(relative_path_digest)
        self._validate_now(now)
        state = (
            await self._session.execute(
                select(ObsidianIngestState)
                .where(
                    ObsidianIngestState.configured_source_digest == configured_source_digest,
                    ObsidianIngestState.relative_path_digest == relative_path_digest,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if state is None or state.status == "claimed":
            return False
        event = (
            await self._session.execute(
                select(ObsidianIngestEvent)
                .where(
                    ObsidianIngestEvent.state_id == state.id,
                    ObsidianIngestEvent.file_hash == state.current_file_hash,
                )
                .with_for_update()
            )
        ).scalar_one()
        state.status = "deferred"
        state.claim_token = None
        state.lease_expires_at = None
        state.error_code = "file_missing"
        state.missing_since = state.missing_since or now
        state.updated_at = now
        if event.status != "ingested":
            event.status = "deferred"
            event.claim_token = None
            event.lease_expires_at = None
            event.error_code = "file_missing"
            event.completed_at = now
            event.updated_at = now
        await self._session.flush()
        return True

    async def reconcile_content(
        self,
        event_id: int,
        *,
        content_id: int,
        now: datetime,
    ) -> bool:
        """Idempotently close the gap after content committed before state."""
        self._validate_positive_id(event_id)
        self._validate_positive_id(content_id)
        self._validate_now(now)
        state_id = await self._session.scalar(
            select(ObsidianIngestEvent.state_id).where(ObsidianIngestEvent.id == event_id)
        )
        if state_id is None:
            return False
        state = (
            await self._session.execute(
                select(ObsidianIngestState)
                .where(ObsidianIngestState.id == state_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if state is None:
            return False
        event = (
            await self._session.execute(
                select(ObsidianIngestEvent)
                .where(ObsidianIngestEvent.id == event_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if event is None:
            return False
        if event.status == "ingested":
            return event.content_id == content_id
        event.status = "ingested"
        event.claim_token = None
        event.lease_expires_at = None
        event.content_id = content_id
        event.error_code = None
        event.completed_at = now
        event.updated_at = now
        if state.current_file_hash == event.file_hash:
            self._copy_event_to_state(state, event, now=now)
        await self._session.flush()
        return True

    async def _lock_claim(
        self, claim: ObsidianClaim
    ) -> tuple[ObsidianIngestState, ObsidianIngestEvent] | None:
        if not isinstance(claim, ObsidianClaim):
            raise ObsidianIngestRepositoryError("invalid_claim")
        state = (
            await self._session.execute(
                select(ObsidianIngestState)
                .where(ObsidianIngestState.id == claim.state_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if state is None:
            return None
        event = (
            await self._session.execute(
                select(ObsidianIngestEvent)
                .where(ObsidianIngestEvent.id == claim.event_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if event is None:
            return None
        return state, event

    @staticmethod
    def _claim_matches(
        state: ObsidianIngestState,
        event: ObsidianIngestEvent,
        claim: ObsidianClaim,
        *,
        now: datetime,
    ) -> bool:
        return bool(
            state.current_file_hash == claim.file_hash
            and state.status == "claimed"
            and event.status == "claimed"
            and state.claim_token == claim.claim_token
            and event.claim_token == claim.claim_token
            and state.operation_id == claim.operation_id
            and event.operation_id == claim.operation_id
            and state.lease_expires_at is not None
            and event.lease_expires_at is not None
            and state.lease_expires_at > now
            and event.lease_expires_at > now
        )

    @staticmethod
    def _copy_event_to_state(
        state: ObsidianIngestState,
        event: ObsidianIngestEvent,
        *,
        now: datetime,
    ) -> None:
        state.status = event.status
        state.claim_token = event.claim_token
        state.lease_expires_at = event.lease_expires_at
        state.operation_id = event.operation_id
        state.content_id = event.content_id
        state.error_code = event.error_code
        state.attempt_count = event.attempt_count
        state.missing_since = None
        state.updated_at = now
