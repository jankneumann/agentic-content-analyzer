"""Knowledge base Topic and TopicNote models.

Topics are persistent, versioned knowledge entities that promote ephemeral
ThemeData (extracted by ThemeAnalysis) into first-class DB records. The
KnowledgeBaseService incrementally compiles topic articles from evidence
(themes, summaries, content items) and maintains relationships, indices,
and quality metrics.

Design notes:
- The ``embedding`` column (pgvector) is intentionally NOT mapped here.
  It is created in the Alembic migration via raw SQL and queried via
  raw SQL in the KB service. This avoids importing pgvector Python
  bindings at model load time and matches the DocumentChunk pattern.
- ``related_topic_ids`` is the canonical relationship store (D2);
  optional Graphiti sync is layered on top with graceful degradation.
- ``status`` controls visibility — archived topics are excluded from
  indices and recompilation but remain queryable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, relationship

from src.models.base import Base


class TopicStatus(StrEnum):
    """Topic lifecycle status."""

    DRAFT = "draft"  # Just created, not yet compiled
    ACTIVE = "active"  # Compiled and current
    STALE = "stale"  # No new evidence in >threshold days
    ARCHIVED = "archived"  # Hidden from indices, not recompiled
    MERGED = "merged"  # Merged into another topic (see merged_into_id)


class TopicNoteType(StrEnum):
    """Type of note attached to a topic."""

    OBSERVATION = "observation"
    QUESTION = "question"
    CORRECTION = "correction"
    INSIGHT = "insight"


class Topic(Base):  # type: ignore[valid-type, misc]
    """A knowledge base topic compiled from theme analysis evidence.

    Each topic has a compiled article (markdown), a versioned identity
    (slug + article_version), and tracks its source evidence and
    relationships to other topics.

    The ``embedding`` column exists in the database (managed via raw SQL
    in migrations) but is NOT declared as a SQLAlchemy column. Use raw
    SQL in services to read/write embeddings (see DocumentChunk pattern).
    """

    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Identity
    slug = Column(String(255), nullable=False, unique=True)
    name = Column(String(500), nullable=False)
    category = Column(String(50), nullable=False)  # ThemeCategory value
    status = Column(
        Enum(
            TopicStatus,
            name="topicstatus",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=TopicStatus.DRAFT,
        index=True,
    )

    # Article content
    summary = Column(Text, nullable=True)  # 1-2 sentence overview
    article_md = Column(Text, nullable=True)  # Full compiled article markdown
    article_version = Column(Integer, nullable=False, default=1)

    # Trend / scoring
    trend = Column(String(50), nullable=True)  # ThemeTrend value
    relevance_score = Column(Float, nullable=False, default=0.0)
    novelty_score = Column(Float, nullable=False, default=0.0)
    mention_count = Column(Integer, nullable=False, default=0)

    # Source evidence (JSON arrays of IDs)
    source_content_ids = Column(JSON, nullable=False, default=list)
    source_summary_ids = Column(JSON, nullable=False, default=list)
    source_theme_ids = Column(JSON, nullable=False, default=list)

    # Relationships (DB-primary store, see D2)
    related_topic_ids = Column(JSON, nullable=False, default=list)
    parent_topic_id = Column(
        Integer,
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
    )
    merged_into_id = Column(
        Integer,
        ForeignKey("topics.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Timestamps
    last_compiled_at = Column(DateTime, nullable=True)
    last_evidence_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # LLM provenance
    compilation_model = Column(String(100), nullable=True)
    compilation_token_usage = Column(Integer, nullable=True)

    # Self-referential relationships
    parent: Mapped[Topic | None] = relationship(
        "Topic",
        remote_side="Topic.id",
        foreign_keys=[parent_topic_id],
        post_update=True,
    )
    notes: Mapped[list[TopicNote]] = relationship(
        "TopicNote",
        back_populates="topic",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_topics_category", "category"),
        Index("ix_topics_trend", "trend"),
        Index("ix_topics_status_relevance", "status", "relevance_score"),
        Index("ix_topics_last_compiled", "last_compiled_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Topic(id={self.id}, slug='{self.slug}', "
            f"status='{self.status}', version={self.article_version})>"
        )


class TopicNote(Base):  # type: ignore[valid-type, misc]
    """A note attached to a topic.

    Notes are created by humans, agents, or the Q&A system. They feed
    back into the next compilation cycle when ``filed_back=False``.
    """

    __tablename__ = "topic_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic_id = Column(
        Integer,
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    note_type = Column(
        Enum(
            TopicNoteType,
            name="topicnotetype",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=TopicNoteType.OBSERVATION,
    )
    content = Column(Text, nullable=False)
    author = Column(String(255), nullable=False, default="system")
    filed_back = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True)

    topic: Mapped[Topic] = relationship("Topic", back_populates="notes")

    def __repr__(self) -> str:
        return (
            f"<TopicNote(id={self.id}, topic_id={self.topic_id}, "
            f"type='{self.note_type}', filed_back={self.filed_back})>"
        )


class KBIndex(Base):  # type: ignore[valid-type, misc]
    """Cached KB index markdown.

    One row per index_type. Regenerated at the end of each compilation
    cycle. See D4 (cached markdown in DB).
    """

    __tablename__ = "kb_indices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    index_type = Column(String(100), nullable=False, unique=True)
    content = Column(Text, nullable=False, default="")
    generated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"<KBIndex(type='{self.index_type}', generated_at={self.generated_at})>"
