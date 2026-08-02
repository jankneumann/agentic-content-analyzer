"""Private synchronous orchestration for bounded Obsidian vault ingestion.

This adapter is deliberately not registered as a public ingestion surface. The
canonical registry and protocol projection are added by the following work package.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.ingestion.content_references import record_content_reference
from src.ingestion.obsidian_parser import (
    ClipParseLimits,
    ObsidianClipError,
    ParsedObsidianClip,
    parse_obsidian_clip,
)
from src.ingestion.obsidian_scanner import AllowedRootPolicy, ScanLimits, ScannedNote, VaultScanner
from src.models.content import Content, ContentSource, ContentStatus
from src.models.obsidian_ingest import ObsidianIngestState
from src.queue.execution_claim import (
    ClaimRejected,
    ClaimSuperseded,
    check_execution_claim,
    guard_execution_claim,
)
from src.repositories.obsidian_ingest import ObsidianIngestRepository

_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ObsidianAdapterConfig:
    """Resolved server-owned configuration; filesystem locations stay out of reprs."""

    configured_source_digest: str
    vault_path: str | Path = field(repr=False)
    ingest_folder: str = field(repr=False)
    allowed_roots: tuple[str | Path, ...] = field(repr=False)
    scan_limits: ScanLimits = field(default_factory=ScanLimits)
    parse_limits: ClipParseLimits = field(
        default_factory=lambda: ClipParseLimits(max_url_chars=2_000)
    )
    narrowed_roots: tuple[str | Path, ...] | None = field(default=None, repr=False)
    compatible_worker: bool = True
    lease_seconds: int = 300
    max_attempts: int = 3
    missing_grace_seconds: int = 300

    def __post_init__(self) -> None:
        if (
            not isinstance(self.configured_source_digest, str)
            or _DIGEST.fullmatch(self.configured_source_digest) is None
        ):
            raise ValueError("invalid_source_digest")
        if not isinstance(self.allowed_roots, tuple):
            raise ValueError("invalid_allowed_roots")
        if not isinstance(self.compatible_worker, bool):
            raise ValueError("invalid_worker_compatibility")
        if self.parse_limits.max_url_chars > 2_000:
            raise ValueError("invalid_parse_limits")
        if isinstance(self.lease_seconds, bool) or not 1 <= self.lease_seconds <= 3_600:
            raise ValueError("invalid_lease")
        if isinstance(self.max_attempts, bool) or not 1 <= self.max_attempts <= 10:
            raise ValueError("invalid_attempt_limit")
        if (
            isinstance(self.missing_grace_seconds, bool)
            or not 1 <= self.missing_grace_seconds <= 86_400
        ):
            raise ValueError("invalid_missing_grace")

    def scanner(self) -> VaultScanner:
        """Build an isolated scanner using only resolved server-owned paths."""

        return VaultScanner(
            policy=AllowedRootPolicy(self.allowed_roots),
            vault_path=self.vault_path,
            ingest_folder=self.ingest_folder,
            limits=self.scan_limits,
            narrowed_roots=self.narrowed_roots,
            compatible_worker=self.compatible_worker,
        )


@dataclass(frozen=True, slots=True)
class ObsidianDiagnostic:
    """Bounded note or scan result with opaque identifiers only."""

    code: str
    path_digest: str | None = None
    event_id: int | None = None


@dataclass(frozen=True, slots=True)
class ObsidianAdapterOutcome:
    """Internal operation-native result consumed by the later surface package."""

    configured_source_digest: str
    source_outcome: Literal["success", "partial", "failed", "zero_items"]
    persisted: int
    skipped: int
    failed: int
    content_ids: tuple[int, ...]
    diagnostics: tuple[ObsidianDiagnostic, ...]
    next_cursor: str | None = None


@dataclass(frozen=True, slots=True)
class _NoteResult:
    status: Literal["persisted", "skipped", "failed"]
    content_id: int | None = None
    diagnostic: ObsidianDiagnostic | None = None
    canonical_id: int | None = None


@dataclass(frozen=True, slots=True)
class _ContentIdentity:
    id: int
    canonical_id: int | None


def obsidian_source_id(
    configured_source_digest: str,
    relative_path_digest: str,
    file_hash: str,
) -> str:
    """Return an opaque immutable Content identity for one note version."""

    if any(
        not isinstance(value, str) or _DIGEST.fullmatch(value) is None
        for value in (configured_source_digest, relative_path_digest, file_hash)
    ):
        raise ValueError("invalid_digest")
    material = f"{configured_source_digest}:{relative_path_digest}:{file_hash}".encode()
    return f"obsidian:{hashlib.sha256(material).hexdigest()}"


def ingest_obsidian_vault(
    session: Session,
    config: ObsidianAdapterConfig,
    *,
    force_reprocess: bool = False,
    now: datetime | None = None,
) -> ObsidianAdapterOutcome:
    """Scan and persist one configured vault in short per-note transactions."""

    if not isinstance(session, Session):
        raise TypeError("session must be a Session")
    if not isinstance(config, ObsidianAdapterConfig):
        raise TypeError("config must be ObsidianAdapterConfig")
    if not isinstance(force_reprocess, bool):
        raise TypeError("force_reprocess must be a bool")
    observed_at = now or datetime.now(UTC)
    if observed_at.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    _checkpoint_execution_claim(session)
    scan = config.scanner().scan(checkpoint=lambda: _checkpoint_execution_claim(session))
    diagnostics = [
        ObsidianDiagnostic(code=item.code, path_digest=item.path_digest)
        for item in scan.diagnostics
    ]
    failed = sum(item.code != "generated_content" for item in scan.diagnostics)
    skipped = sum(item.code == "generated_content" for item in scan.diagnostics)
    persisted = 0
    content_ids: list[int] = []

    if any(item.code == "source_unavailable" for item in scan.diagnostics):
        return _outcome(
            config,
            persisted=0,
            skipped=skipped,
            failed=failed,
            content_ids=(),
            diagnostics=tuple(diagnostics),
            next_cursor=scan.next_cursor,
        )

    for note in scan.notes:
        _checkpoint_execution_claim(session)
        try:
            result = _process_note(session, config, note, observed_at)
            _commit_transaction(session)
            if result.content_id is not None:
                record_content_reference(result.content_id, result.canonical_id)
        except ClaimRejected:
            session.rollback()
            raise
        except Exception:
            session.rollback()
            _record_persistence_failure(session, config, note, observed_at)
            result = _NoteResult(
                status="failed",
                diagnostic=ObsidianDiagnostic("persistence_error", note.path_digest),
            )

        if result.status == "persisted":
            persisted += 1
            if result.content_id is not None:
                content_ids.append(result.content_id)
        elif result.status == "skipped":
            skipped += 1
            if result.content_id is not None:
                content_ids.append(result.content_id)
        else:
            failed += 1
        if result.diagnostic is not None:
            diagnostics.append(result.diagnostic)

    blocking_diagnostics = [item for item in scan.diagnostics if item.code != "generated_content"]
    if not blocking_diagnostics and scan.next_cursor is None:
        state_enumeration_complete = _mark_missing_notes(
            session,
            config,
            {note.path_digest for note in scan.notes},
            observed_at,
        )
        if not state_enumeration_complete:
            failed += 1
            diagnostics.append(ObsidianDiagnostic("scan_entry_limit"))
    return _outcome(
        config,
        persisted=persisted,
        skipped=skipped,
        failed=failed,
        content_ids=tuple(content_ids),
        diagnostics=tuple(diagnostics),
        next_cursor=scan.next_cursor,
    )


def _process_note(
    session: Session,
    config: ObsidianAdapterConfig,
    note: ScannedNote,
    now: datetime,
) -> _NoteResult:
    try:
        parsed = parse_obsidian_clip(note.data, limits=config.parse_limits)
    except ObsidianClipError as exc:
        parsed = exc

    execution = guard_execution_claim(session)
    repository = ObsidianIngestRepository(session)
    observation = repository.observe_file_version(
        config.configured_source_digest,
        note.path_digest,
        note.content_sha256,
        observed_mtime_ns=note.identity.mtime_ns,
        observed_size=note.identity.size,
        now=now,
    )
    source_id = obsidian_source_id(
        config.configured_source_digest,
        note.path_digest,
        note.content_sha256,
    )
    claim = repository.claim_file_version(
        observation.event_id,
        execution.job_id,
        now=now,
        lease_seconds=config.lease_seconds,
        max_attempts=config.max_attempts,
    )
    if claim is None:
        disposition = repository.lookup_event(
            config.configured_source_digest,
            note.path_digest,
            note.content_sha256,
        )
        if disposition is not None and disposition.status == "failed":
            return _NoteResult(
                status="failed",
                diagnostic=ObsidianDiagnostic(
                    disposition.error_code or "persistence_error",
                    note.path_digest,
                    disposition.event_id,
                ),
            )
        return _NoteResult(status="skipped")

    if isinstance(parsed, ObsidianClipError):
        if not repository.fail_claim(claim, error_code=parsed.code, now=now):
            raise ClaimSuperseded("Obsidian parse failure lost its claim")
        return _NoteResult(
            status="failed",
            diagnostic=ObsidianDiagnostic(parsed.code, note.path_digest, claim.event_id),
        )

    _lock_canonical_identity(session, parsed.canonical_url_digest)
    existing = _existing_obsidian_content(session, source_id)
    if existing is not None:
        if not repository.reconcile_content(
            observation.event_id,
            content_id=existing.id,
            expected_source_id=source_id,
            now=now,
        ):
            raise ClaimSuperseded("Obsidian content reconciliation lost ownership")
        return _NoteResult(
            status="skipped",
            content_id=existing.id,
            canonical_id=existing.canonical_id,
        )

    content = _persist_content(session, parsed, source_id, now)
    if not repository.complete_claim(claim, content_id=content.id, now=now):
        raise ClaimSuperseded("Obsidian persistence lost its claim")
    return _NoteResult(
        status="persisted",
        content_id=content.id,
        canonical_id=content.canonical_id,
    )


def _record_persistence_failure(
    session: Session,
    config: ObsidianAdapterConfig,
    note: ScannedNote,
    now: datetime,
) -> None:
    """Best-effort durable failure mapping without retaining a raw exception."""

    try:
        execution = guard_execution_claim(session)
        repository = ObsidianIngestRepository(session)
        observation = repository.observe_file_version(
            config.configured_source_digest,
            note.path_digest,
            note.content_sha256,
            observed_mtime_ns=note.identity.mtime_ns,
            observed_size=note.identity.size,
            now=now,
        )
        claim = repository.claim_file_version(
            observation.event_id,
            execution.job_id,
            now=now,
            lease_seconds=config.lease_seconds,
            max_attempts=config.max_attempts,
        )
        if claim is not None:
            repository.fail_claim(claim, error_code="persistence_error", now=now)
        _commit_transaction(session)
    except ClaimRejected:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        # The operation result remains bounded even when recording evidence fails.
        return


def _existing_obsidian_content(session: Session, source_id: str) -> _ContentIdentity | None:
    row = session.execute(
        select(Content.id, Content.canonical_id)
        .where(
            Content.source_type == ContentSource.OBSIDIAN,
            Content.source_id == source_id,
        )
        .order_by(Content.id)
        .limit(1)
        .with_for_update()
    ).one_or_none()
    if row is None:
        return None
    return _ContentIdentity(id=int(row.id), canonical_id=row.canonical_id)


def _lock_canonical_identity(session: Session, canonical_url_digest: str) -> None:
    key = int.from_bytes(bytes.fromhex(canonical_url_digest)[:8], byteorder="big", signed=True)
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def _persist_content(
    session: Session,
    parsed: ParsedObsidianClip,
    source_id: str,
    now: datetime,
) -> Content:
    canonical = session.execute(
        select(Content.id, Content.canonical_id)
        .where(
            Content.source_type == ContentSource.OBSIDIAN,
            Content.source_url == parsed.canonical_url,
        )
        .order_by(Content.id)
        .limit(1)
        .with_for_update()
    ).one_or_none()
    canonical_id = None if canonical is None else canonical.canonical_id or canonical.id
    content = Content(
        source_type=ContentSource.OBSIDIAN,
        source_id=source_id,
        source_url=parsed.canonical_url,
        title="Obsidian clip",
        published_date=parsed.metadata.captured_at,
        markdown_content=parsed.markdown,
        metadata_json={
            "canonical_url_digest": parsed.canonical_url_digest,
            "capture_client": parsed.metadata.capture_client,
            "content_type_hint": parsed.metadata.content_type_hint,
        },
        raw_content=None,
        raw_format="markdown",
        parser_used="ObsidianClipParser",
        parser_version="1",
        content_hash=hashlib.sha256(parsed.markdown.encode()).hexdigest(),
        canonical_id=canonical_id,
        status=ContentStatus.PENDING,
        ingested_at=now,
    )
    session.add(content)
    session.flush()
    return content


def _mark_missing_notes(
    session: Session,
    config: ObsidianAdapterConfig,
    observed_path_digests: set[str],
    now: datetime,
) -> bool:
    _checkpoint_execution_claim(session)
    try:
        stored_rows = session.execute(
            select(
                ObsidianIngestState.relative_path_digest,
                ObsidianIngestState.observation_generation,
            )
            .where(ObsidianIngestState.configured_source_digest == config.configured_source_digest)
            .order_by(ObsidianIngestState.id)
            .limit(config.scan_limits.max_entries + 1)
        ).all()
        session.commit()
        if len(stored_rows) > config.scan_limits.max_entries:
            return False
    except Exception:
        session.rollback()
        raise

    for digest, observation_generation in stored_rows:
        if digest not in observed_path_digests:
            _checkpoint_execution_claim(session)
            try:
                guard_execution_claim(session)
                repository = ObsidianIngestRepository(session)
                repository.mark_missing(
                    config.configured_source_digest,
                    digest,
                    expected_observation_generation=observation_generation,
                    now=now,
                    grace_seconds=config.missing_grace_seconds,
                )
                _commit_transaction(session)
            except Exception:
                session.rollback()
                raise
    return True


def _checkpoint_execution_claim(session: Session) -> None:
    """Validate cancellation without retaining a transaction or row lock."""

    try:
        check_execution_claim(session)
        session.commit()
    except ClaimRejected:
        session.rollback()
        raise


def _commit_transaction(session: Session) -> None:
    """Commit one bounded adapter transaction and release all durable locks."""

    session.commit()


def _outcome(
    config: ObsidianAdapterConfig,
    *,
    persisted: int,
    skipped: int,
    failed: int,
    content_ids: tuple[int, ...],
    diagnostics: tuple[ObsidianDiagnostic, ...],
    next_cursor: str | None,
) -> ObsidianAdapterOutcome:
    if failed and (persisted or skipped):
        source_outcome: Literal["success", "partial", "failed", "zero_items"] = "partial"
    elif failed:
        source_outcome = "failed"
    elif persisted or skipped:
        source_outcome = "success"
    else:
        source_outcome = "zero_items"
    return ObsidianAdapterOutcome(
        configured_source_digest=config.configured_source_digest,
        source_outcome=source_outcome,
        persisted=persisted,
        skipped=skipped,
        failed=failed,
        content_ids=content_ids,
        diagnostics=diagnostics,
        next_cursor=next_cursor,
    )
