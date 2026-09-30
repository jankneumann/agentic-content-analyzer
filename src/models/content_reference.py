"""ContentReference model for tracking relationships between content items.

This module provides a ContentReference model that captures citation and
reference relationships between ingested content. References can point to
internal content (resolved via target_content_id) or external resources
(via external_url / external_id).

Reference Types:
- cites: Direct citation of another work
- extends: Builds upon or extends another work
- discusses: Discusses or analyzes another work
- contradicts: Contradicts findings of another work
- supplements: Provides supplementary material
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, relationship, validates

from src.models.base import Base


class ReferenceType(StrEnum):
    """Types of reference relationships between content."""

    CITES = "cites"
    EXTENDS = "extends"
    DISCUSSES = "discusses"
    CONTRADICTS = "contradicts"
    SUPPLEMENTS = "supplements"


class ExternalIdType(StrEnum):
    """Types of external identifiers for referenced works."""

    ARXIV = "arxiv"
    DOI = "doi"
    S2 = "s2"
    PMID = "pmid"
    URL = "url"


class ResolutionStatus(StrEnum):
    """Resolution status for content references."""

    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    EXTERNAL = "external"
    FAILED = "failed"
    NOT_FOUND = "not_found"


class ExpansionState(StrEnum):
    """What X bookmark link expansion did with a reference's link.

    NULL (no state) means the reference is not an expansion candidate: only
    references recorded for X bookmark rows carry a state.
    """

    PENDING = "pending"
    SUBMITTED = "submitted"
    SKIPPED = "skipped"
    FAILED = "failed"


class ContentReference(Base):  # type: ignore[valid-type, misc]
    """Model for tracking references between content items.

    A reference links a source content item to either an internal
    content item (target_content_id) or an external resource
    (external_url / external_id). At least one of external_id
    or external_url must be provided (enforced by CHECK constraint).
    """

    __tablename__ = "content_references"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Source content that contains the reference
    source_content_id = Column(
        Integer,
        ForeignKey("contents.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Type of reference relationship
    reference_type = Column(String(20), nullable=False, default="cites")

    # Target content (resolved internal reference)
    target_content_id = Column(
        Integer,
        ForeignKey("contents.id", ondelete="SET NULL"),
        nullable=True,
    )

    # External reference identifiers
    external_url = Column(Text, nullable=True)
    external_id = Column(Text, nullable=True)
    external_id_type = Column(String(20), nullable=True)

    # Resolution tracking
    resolution_status = Column(String(20), nullable=False, default="unresolved")
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Context from the source content
    source_chunk_id = Column(
        Integer,
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
    )
    context_snippet = Column(Text, nullable=True)
    confidence = Column(Float, default=1.0)

    # Linked-article expansion (X bookmarks only; NULL for other sources)
    expansion_state = Column(String(16), nullable=True)
    expansion_attempts = Column(SmallInteger, nullable=False, default=0, server_default=text("0"))
    expansion_attempted_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    # Table constraints and indexes
    __table_args__ = (
        CheckConstraint(
            "external_id IS NOT NULL OR external_url IS NOT NULL",
            name="chk_has_identifier",
        ),
        CheckConstraint(
            "expansion_state IS NULL OR expansion_state IN "
            "('pending', 'submitted', 'skipped', 'failed')",
            name="chk_content_refs_expansion_state",
        ),
        CheckConstraint(
            "expansion_attempts >= 0 AND expansion_attempts <= 100",
            name="chk_content_refs_expansion_attempts",
        ),
        UniqueConstraint(
            "source_content_id",
            "external_id",
            "external_id_type",
            name="uq_content_reference",
        ),
        Index("ix_content_refs_source", "source_content_id"),
        Index(
            "ix_content_refs_target",
            "target_content_id",
            postgresql_where=text("target_content_id IS NOT NULL"),
        ),
        Index(
            "ix_content_refs_external_id",
            "external_id_type",
            "external_id",
            postgresql_where=text("external_id IS NOT NULL"),
        ),
        Index(
            "ix_content_refs_unresolved",
            "resolution_status",
            postgresql_where=text("resolution_status = 'unresolved'"),
        ),
        Index(
            "ix_content_refs_expansion_retry",
            "created_at",
            postgresql_where=text("expansion_state IN ('pending', 'failed')"),
        ),
    )

    # Relationships
    source_content: Mapped["Content"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Content",
        foreign_keys=[source_content_id],
        back_populates="references",
    )

    target_content: Mapped["Content | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Content",
        foreign_keys=[target_content_id],
        back_populates="cited_by",
    )

    source_chunk: Mapped["DocumentChunk | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "DocumentChunk",
        foreign_keys=[source_chunk_id],
    )

    # Validators
    @validates("reference_type")
    def validate_reference_type(self, key: str, value: str) -> str:
        """Validate reference_type against ReferenceType enum."""
        valid = {e.value for e in ReferenceType}
        if value not in valid:
            raise ValueError(
                f"Invalid reference_type '{value}'. Must be one of: {', '.join(sorted(valid))}"
            )
        return value

    @validates("external_id_type")
    def validate_external_id_type(self, key: str, value: str | None) -> str | None:
        """Validate external_id_type against ExternalIdType enum."""
        if value is None:
            return value
        valid = {e.value for e in ExternalIdType}
        if value not in valid:
            raise ValueError(
                f"Invalid external_id_type '{value}'. Must be one of: {', '.join(sorted(valid))}"
            )
        return value

    @validates("resolution_status")
    def validate_resolution_status(self, key: str, value: str) -> str:
        """Validate resolution_status against ResolutionStatus enum."""
        valid = {e.value for e in ResolutionStatus}
        if value not in valid:
            raise ValueError(
                f"Invalid resolution_status '{value}'. Must be one of: {', '.join(sorted(valid))}"
            )
        return value

    @validates("expansion_state")
    def validate_expansion_state(self, key: str, value: str | None) -> str | None:
        """Validate expansion_state against ExpansionState enum (None allowed)."""
        if value is None:
            return value
        valid = {e.value for e in ExpansionState}
        if value not in valid:
            raise ValueError(
                f"Invalid expansion_state '{value}'. Must be one of: {', '.join(sorted(valid))}"
            )
        return value

    def __repr__(self) -> str:
        return (
            f"<ContentReference(id={self.id}, "
            f"source={self.source_content_id}, "
            f"type={self.reference_type}, "
            f"status={self.resolution_status})>"
        )


# --- Pydantic Schemas ---


class ReferenceResponse(BaseModel):
    """Schema for content reference API responses."""

    id: int
    source_content_id: int
    reference_type: str
    target_content_id: int | None = None
    external_url: str | None = None
    external_id: str | None = None
    external_id_type: str | None = None
    resolution_status: str
    resolved_at: datetime | None = None
    source_chunk_id: int | None = None
    context_snippet: str | None = None
    confidence: float = 1.0
    expansion_state: str | None = None
    expansion_attempts: int = 0
    expansion_attempted_at: datetime | None = None
    created_at: datetime
    # Enriched fields from target content (when resolved)
    target_title: str | None = None
    target_source_type: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ReferenceListResponse(BaseModel):
    """Paginated reference list response."""

    items: list[ReferenceResponse]
    total: int
    page: int = Field(default=1)
    page_size: int = Field(default=20)
