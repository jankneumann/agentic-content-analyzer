"""DocumentChunk model for search indexing.

Stores chunked document content with structural metadata, embeddings,
and full-text search vectors. Each chunk belongs to a Content record
and is automatically deleted when the parent Content is removed (CASCADE).
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, relationship

from src.models.base import Base


class ChunkType(StrEnum):
    """Types of document chunks based on content structure."""

    PARAGRAPH = "paragraph"
    TABLE = "table"
    CODE = "code"
    QUOTE = "quote"
    TRANSCRIPT = "transcript"
    SECTION = "section"


class DocumentChunk(Base):  # type: ignore[valid-type, misc]
    """A chunk of document content for search indexing.

    Each chunk represents a meaningful unit of text from a Content record,
    split by the appropriate ChunkingStrategy based on content type.
    Chunks store both dense embeddings (pgvector) for semantic search
    and TSVECTOR for native full-text search.

    The embedding and search_vector columns are managed via raw SQL
    in the migration (pgvector vector type and TSVECTOR with trigger).
    They are NOT declared as SQLAlchemy columns here to avoid import
    dependencies on pgvector Python bindings at model load time.
    Access them via raw SQL queries in the search strategies.
    """

    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(
        Integer,
        ForeignKey("contents.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Chunk content
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)  # Order within document (0, 1, 2...)

    # Structural metadata
    section_path = Column(String(500), nullable=True)  # "# Heading > ## Subheading"
    heading_text = Column(String(500), nullable=True)  # Nearest heading above chunk
    chunk_type = Column(String(50), nullable=False, default=ChunkType.PARAGRAPH)

    # Location anchors
    page_number = Column(Integer, nullable=True)  # For PDFs
    start_char = Column(Integer, nullable=True)  # Character offset in source
    end_char = Column(Integer, nullable=True)
    timestamp_start = Column(Float, nullable=True)  # For YouTube (seconds)
    timestamp_end = Column(Float, nullable=True)
    deep_link_url = Column(String(2000), nullable=True)  # Direct link to chunk location

    # Note: 'embedding' (vector) and 'search_vector' (tsvector) columns exist
    # in the database but are NOT mapped here. They are managed via raw SQL
    # in migrations and search strategy implementations.

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    content: Mapped["Content"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Content",
        back_populates="chunks",
        foreign_keys=[content_id],
    )

    __table_args__ = (
        Index("ix_document_chunks_content_id", "content_id"),
        Index("ix_document_chunks_chunk_type", "chunk_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk(id={self.id}, content_id={self.content_id}, "
            f"index={self.chunk_index}, type='{self.chunk_type}')>"
        )
