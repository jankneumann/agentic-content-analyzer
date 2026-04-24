"""Highlight model: user annotations anchored to content, summaries, or digests.

A highlight is a child row of `Content`. The `content_id` column is the
retrieval root — every highlight belongs to exactly one Content, even if the
actual highlighted span lives inside a derived summary or digest. The
`(target_kind, target_id)` pair identifies which text stream the offsets
refer to.

Sources:
- `readwise`: imported from the Readwise Highlights API v2 (kindle, instapaper,
  pocket, apple_books, airr, reader, podcast, supplemental)
- `native`: created directly in the ACA frontend/API
- `import`: other import paths (manual CSV, Kindle clippings, etc.)

Deletion is soft (``deleted_at`` timestamp). Readwise tombstones produced by
``includeDeleted=true`` set ``deleted_at`` rather than removing the row.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, relationship, validates

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.content import Content


class HighlightTargetKind(StrEnum):
    """What kind of entity the highlight is anchored to.

    ``chunk`` is reserved for a future phase and intentionally omitted.
    """

    CONTENT = "content"
    SUMMARY = "summary"
    DIGEST = "digest"


class HighlightSource(StrEnum):
    """Where the highlight originated."""

    READWISE = "readwise"
    NATIVE = "native"
    IMPORT = "import"


class Highlight(Base):  # type: ignore[valid-type, misc]
    """User highlight/annotation on content, a summary, or a digest.

    Every highlight roots to a Content row via ``content_id`` — even when the
    ``target_kind`` is ``summary`` or ``digest``, ``content_id`` points to the
    underlying article/book so per-content retrieval stays a single index scan.

    The highlighted ``text`` is denormalized so regenerating a summary or
    digest doesn't break highlights anchored to it.
    """

    __tablename__ = "highlights"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Root content (always set, even for summary/digest-targeted highlights)
    content_id = Column(
        Integer,
        ForeignKey("contents.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Polymorphic target: what the offsets are anchored to
    target_kind = Column(String(20), nullable=False, default="content")
    target_id = Column(Integer, nullable=False)

    # Highlighted span (denormalized — survives regeneration of target)
    text = Column(Text, nullable=False)
    note = Column(Text, nullable=True)

    # Free-form color string (no enum — keep migration-free)
    color = Column(String(50), nullable=True)

    # Position within the target text
    start_offset = Column(Integer, nullable=True)
    end_offset = Column(Integer, nullable=True)

    # Upstream-native location (Kindle location, PDF page, podcast seconds, …)
    location = Column(Integer, nullable=True)
    location_type = Column(String(20), nullable=True)  # location|page|order|time_offset|char

    # Tags (free-form list, e.g. ["favorite", ".h1"])
    tags = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))

    # Provenance
    source = Column(String(20), nullable=False, default="native")
    readwise_id = Column(String(64), nullable=True)  # unique when source='readwise'
    source_url = Column(Text, nullable=True)  # e.g. readwise_url backlink

    # Timestamps
    highlighted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("NOW()"),
    )

    # Soft delete (Readwise tombstone OR user-removed)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "target_kind IN ('content','summary','digest')",
            name="chk_highlight_target_kind",
        ),
        CheckConstraint(
            "target_kind <> 'content' OR target_id = content_id",
            name="chk_highlight_content_target_matches_root",
        ),
        Index(
            "ix_highlights_content_active",
            "content_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_highlights_target", "target_kind", "target_id"),
        Index(
            "uq_highlights_readwise_id",
            "readwise_id",
            unique=True,
            postgresql_where=text("readwise_id IS NOT NULL"),
        ),
    )

    # Relationships
    content: Mapped["Content"] = relationship(
        "Content",
        foreign_keys=[content_id],
        back_populates="highlights",
    )

    @validates("target_kind")
    def _validate_target_kind(self, key: str, value: str) -> str:
        valid = {e.value for e in HighlightTargetKind}
        if value not in valid:
            raise ValueError(
                f"Invalid target_kind '{value}'. Must be one of: {', '.join(sorted(valid))}"
            )
        return value

    @validates("source")
    def _validate_source(self, key: str, value: str) -> str:
        valid = {e.value for e in HighlightSource}
        if value not in valid:
            raise ValueError(
                f"Invalid source '{value}'. Must be one of: {', '.join(sorted(valid))}"
            )
        return value

    def __repr__(self) -> str:
        preview = (self.text or "")[:40].replace("\n", " ")
        return (
            f"<Highlight(id={self.id}, content_id={self.content_id}, "
            f"target={self.target_kind}:{self.target_id}, source={self.source}, "
            f"text='{preview}...')>"
        )


# --- Pydantic Schemas ---


class HighlightResponse(BaseModel):
    """Schema for highlight API responses."""

    id: int
    content_id: int
    target_kind: str
    target_id: int
    text: str
    note: str | None = None
    color: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    location: int | None = None
    location_type: str | None = None
    tags: list[str] = []
    source: str
    readwise_id: str | None = None
    source_url: str | None = None
    highlighted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
