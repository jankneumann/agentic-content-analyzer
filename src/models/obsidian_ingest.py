"""Private, digest-only persistence models for Obsidian vault ingestion."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from src.models.base import Base


class ObsidianIngestStatus(StrEnum):
    DISCOVERED = "discovered"
    CLAIMED = "claimed"
    INGESTED = "ingested"
    FAILED = "failed"
    DEFERRED = "deferred"


OBSIDIAN_ERROR_CODES = frozenset(
    {
        "invalid_encoding",
        "note_too_large",
        "missing_frontmatter",
        "invalid_frontmatter",
        "frontmatter_too_large",
        "frontmatter_not_mapping",
        "yaml_invalid",
        "yaml_custom_tag",
        "yaml_unsupported_type",
        "yaml_duplicate_key",
        "yaml_node_limit",
        "yaml_depth_limit",
        "yaml_alias_limit",
        "yaml_string_limit",
        "missing_required_metadata",
        "invalid_url",
        "invalid_captured_at",
        "invalid_capture_client",
        "invalid_content_type_hint",
        "body_too_large",
        "unsafe_path",
        "directory_unavailable",
        "file_unavailable",
        "normalization_collision",
        "scan_depth_limit",
        "scan_entry_limit",
        "scan_file_limit",
        "non_regular_file",
        "file_unstable",
        "scan_byte_limit",
        "generated_content",
        "scan_duration_limit",
        "source_unavailable",
        "invalid_cursor",
        "persistence_error",
        "file_missing",
        "retry_exhausted",
        "claim_released",
        "claim_lost",
    }
)

_ERROR_SQL = ",".join(f"'{code}'" for code in sorted(OBSIDIAN_ERROR_CODES))


class ObsidianIngestState(Base):
    """Current processing state for one opaque configured-source/path pair."""

    __tablename__ = "obsidian_ingest_state"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    configured_source_digest = Column(CHAR(64), nullable=False)
    relative_path_digest = Column(CHAR(64), nullable=False)
    current_file_hash = Column(CHAR(64), nullable=False)
    observed_mtime_ns = Column(BigInteger, nullable=False)
    observed_size = Column(BigInteger, nullable=False)
    status = Column(String(16), nullable=False, default="discovered", server_default="discovered")
    claim_token = Column(UUID(as_uuid=True), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    # pgqueuer_jobs is managed by its own persistence layer and has no ORM
    # model. The migration enforces this column's FK with ON DELETE SET NULL.
    operation_id = Column(BigInteger, nullable=True)
    content_id = Column(
        Integer,
        ForeignKey("contents.id", name="fk_obsidian_ingest_state_content", ondelete="SET NULL"),
        nullable=True,
    )
    error_code = Column(String(32), nullable=True)
    attempt_count = Column(SmallInteger, nullable=False, default=0, server_default=text("0"))
    missing_since = Column(DateTime(timezone=True), nullable=True)
    first_seen_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "configured_source_digest",
            "relative_path_digest",
            name="uq_obsidian_ingest_state_source_path",
        ),
        CheckConstraint(
            "configured_source_digest ~ '^[0-9a-f]{64}$' AND relative_path_digest ~ '^[0-9a-f]{64}$' AND current_file_hash ~ '^[0-9a-f]{64}$'",
            name="ck_obsidian_ingest_state_digests",
        ),
        CheckConstraint(
            "status IN ('discovered','claimed','ingested','failed','deferred')",
            name="ck_obsidian_ingest_state_status",
        ),
        CheckConstraint(
            f"error_code IS NULL OR error_code IN ({_ERROR_SQL})",
            name="ck_obsidian_ingest_state_error_code",
        ),
        CheckConstraint(
            "attempt_count BETWEEN 0 AND 10", name="ck_obsidian_ingest_state_attempt_count"
        ),
        CheckConstraint(
            "observed_mtime_ns >= 0 AND observed_size >= 0",
            name="ck_obsidian_ingest_state_observation",
        ),
        CheckConstraint(
            "(status = 'discovered' AND claim_token IS NULL AND lease_expires_at IS NULL AND error_code IS NULL) OR (status = 'claimed' AND claim_token IS NOT NULL AND lease_expires_at IS NOT NULL AND attempt_count >= 1 AND error_code IS NULL) OR (status = 'ingested' AND claim_token IS NULL AND lease_expires_at IS NULL AND error_code IS NULL) OR (status = 'failed' AND claim_token IS NULL AND lease_expires_at IS NULL AND error_code IS NOT NULL) OR (status = 'deferred' AND claim_token IS NULL AND lease_expires_at IS NULL AND error_code IS NOT NULL)",
            name="ck_obsidian_ingest_state_shape",
        ),
        Index(
            "ix_obsidian_ingest_state_claim_expiry",
            "lease_expires_at",
            "id",
            postgresql_where=text("status = 'claimed'"),
        ),
        Index("ix_obsidian_ingest_state_status_updated", "status", "updated_at", "id"),
    )


class ObsidianIngestEvent(Base):
    """Immutable file-version identity with mutable bounded processing state."""

    __tablename__ = "obsidian_ingest_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    state_id = Column(
        BigInteger,
        ForeignKey(
            "obsidian_ingest_state.id", name="fk_obsidian_ingest_events_state", ondelete="RESTRICT"
        ),
        nullable=False,
    )
    configured_source_digest = Column(CHAR(64), nullable=False)
    relative_path_digest = Column(CHAR(64), nullable=False)
    file_hash = Column(CHAR(64), nullable=False)
    status = Column(String(16), nullable=False, default="discovered", server_default="discovered")
    claim_token = Column(UUID(as_uuid=True), nullable=True, default=None)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    # The migration owns the FK to the non-ORM pgqueuer_jobs table.
    operation_id = Column(BigInteger, nullable=True)
    content_id = Column(
        Integer,
        ForeignKey("contents.id", name="fk_obsidian_ingest_events_content", ondelete="SET NULL"),
        nullable=True,
    )
    error_code = Column(String(32), nullable=True)
    attempt_count = Column(SmallInteger, nullable=False, default=0, server_default=text("0"))
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "configured_source_digest",
            "relative_path_digest",
            "file_hash",
            name="uq_obsidian_ingest_events_file_version",
        ),
        CheckConstraint(
            "configured_source_digest ~ '^[0-9a-f]{64}$' AND relative_path_digest ~ '^[0-9a-f]{64}$' AND file_hash ~ '^[0-9a-f]{64}$'",
            name="ck_obsidian_ingest_events_digests",
        ),
        CheckConstraint(
            "status IN ('discovered','claimed','ingested','failed','deferred')",
            name="ck_obsidian_ingest_events_status",
        ),
        CheckConstraint(
            f"error_code IS NULL OR error_code IN ({_ERROR_SQL})",
            name="ck_obsidian_ingest_events_error_code",
        ),
        CheckConstraint(
            "attempt_count BETWEEN 0 AND 10", name="ck_obsidian_ingest_events_attempt_count"
        ),
        CheckConstraint(
            "(status = 'discovered' AND claim_token IS NULL AND lease_expires_at IS NULL AND operation_id IS NULL AND content_id IS NULL AND error_code IS NULL AND completed_at IS NULL) OR (status = 'claimed' AND claim_token IS NOT NULL AND lease_expires_at IS NOT NULL AND content_id IS NULL AND error_code IS NULL AND attempt_count >= 1 AND completed_at IS NULL) OR (status = 'ingested' AND claim_token IS NULL AND lease_expires_at IS NULL AND error_code IS NULL AND completed_at IS NOT NULL) OR (status IN ('failed','deferred') AND claim_token IS NULL AND lease_expires_at IS NULL AND error_code IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_obsidian_ingest_events_shape",
        ),
        Index(
            "ix_obsidian_ingest_events_claim_expiry",
            "lease_expires_at",
            "id",
            postgresql_where=text("status = 'claimed'"),
        ),
        Index("ix_obsidian_ingest_events_state_created", "state_id", "created_at", "id"),
    )
