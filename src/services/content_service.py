"""Content service for unified content management.

Provides CRUD operations and deduplication logic for the Content model.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.content import (
    Content,
    ContentCreate,
    ContentSource,
    ContentStatus,
    ContentUpdate,
)
from src.utils.content_hash import generate_markdown_hash


class ContentService:
    """Service for managing Content records with deduplication support."""

    def __init__(self, db: Session):
        """Initialize with database session.

        Args:
            db: SQLAlchemy session
        """
        self.db = db

    def create(
        self,
        data: ContentCreate,
        *,
        check_duplicate: bool = True,
    ) -> Content:
        """Create a new Content record with optional deduplication.

        If check_duplicate is True and content with same hash exists,
        creates a new record linked to the canonical via canonical_id.

        Args:
            data: Content creation data
            check_duplicate: Whether to check for existing content

        Returns:
            Created Content record (may be linked to canonical if duplicate)
        """
        # Generate hash if not provided
        content_hash = data.content_hash or generate_markdown_hash(data.markdown_content)

        canonical: Content | None = None
        if check_duplicate:
            canonical = self.find_by_hash(content_hash)

        content = Content(
            source_type=data.source_type,
            source_id=data.source_id,
            source_url=data.source_url,
            title=data.title,
            author=data.author,
            publication=data.publication,
            published_date=data.published_date,
            markdown_content=data.markdown_content,
            tables_json=data.tables_json,
            links_json=data.links_json,
            metadata_json=data.metadata_json,
            raw_content=data.raw_content,
            raw_format=data.raw_format,
            parser_used=data.parser_used,
            parser_version=data.parser_version,
            content_hash=content_hash,
            canonical_id=canonical.id if canonical else None,
            status=ContentStatus.PENDING,
            ingested_at=datetime.now(UTC),
        )

        self.db.add(content)
        self.db.commit()
        self.db.refresh(content)

        return content

    def get(self, content_id: int) -> Content | None:
        """Get Content by ID.

        Args:
            content_id: Content record ID

        Returns:
            Content record or None if not found
        """
        return self.db.get(Content, content_id)

    def get_by_source(
        self,
        source_type: ContentSource,
        source_id: str,
    ) -> Content | None:
        """Get Content by source type and ID.

        Uses the unique composite index on (source_type, source_id).

        Args:
            source_type: Content source type
            source_id: Source-specific identifier

        Returns:
            Content record or None if not found
        """
        stmt = select(Content).where(
            Content.source_type == source_type,
            Content.source_id == source_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def find_by_hash(self, content_hash: str) -> Content | None:
        """Find Content by content hash for deduplication.

        Returns the canonical (non-duplicate) content if exists.

        Args:
            content_hash: SHA-256 hash of normalized markdown

        Returns:
            Canonical Content record or None if not found
        """
        stmt = (
            select(Content)
            .where(
                Content.content_hash == content_hash,
                Content.canonical_id.is_(None),  # Only return canonical records
            )
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def update(
        self,
        content_id: int,
        data: ContentUpdate,
    ) -> Content | None:
        """Update Content record.

        Args:
            content_id: Content record ID
            data: Fields to update

        Returns:
            Updated Content record or None if not found
        """
        content = self.get(content_id)
        if not content:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(content, field, value)

        # Recalculate hash if markdown changed
        if "markdown_content" in update_data:
            content.content_hash = generate_markdown_hash(content.markdown_content)

        self.db.commit()
        self.db.refresh(content)

        return content

    def delete(self, content_id: int) -> bool:
        """Delete Content record.

        Also unlinks any content that references this as canonical.

        Args:
            content_id: Content record ID

        Returns:
            True if deleted, False if not found
        """
        content = self.get(content_id)
        if not content:
            return False

        # Unlink any records that reference this as canonical
        stmt = select(Content).where(Content.canonical_id == content_id)
        duplicates = self.db.execute(stmt).scalars().all()
        for dup in duplicates:
            dup.canonical_id = None

        self.db.delete(content)
        self.db.commit()

        return True

    def list_contents(
        self,
        *,
        source_type: ContentSource | None = None,
        status: ContentStatus | None = None,
        publication: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Content], int]:
        """List Content records with optional filtering.

        Args:
            source_type: Filter by source type
            status: Filter by processing status
            publication: Filter by publication name
            offset: Pagination offset
            limit: Maximum records to return

        Returns:
            Tuple of (list of Content records, total count)
        """
        # Build base query
        stmt = select(Content)
        count_stmt = select(func.count(Content.id))

        # Apply filters
        if source_type:
            stmt = stmt.where(Content.source_type == source_type)
            count_stmt = count_stmt.where(Content.source_type == source_type)

        if status:
            stmt = stmt.where(Content.status == status)
            count_stmt = count_stmt.where(Content.status == status)

        if publication:
            stmt = stmt.where(Content.publication == publication)
            count_stmt = count_stmt.where(Content.publication == publication)

        # Get total count
        total = self.db.execute(count_stmt).scalar_one()

        # Apply pagination and ordering
        stmt = stmt.order_by(Content.ingested_at.desc()).offset(offset).limit(limit)

        contents = self.db.execute(stmt).scalars().all()

        return list(contents), total

    def update_status(
        self,
        content_id: int,
        status: ContentStatus,
        error_message: str | None = None,
    ) -> Content | None:
        """Update Content processing status.

        Convenience method for status updates during processing pipeline.

        Args:
            content_id: Content record ID
            status: New status
            error_message: Optional error message (for FAILED status)

        Returns:
            Updated Content record or None if not found
        """
        content = self.get(content_id)
        if not content:
            return None

        content.status = status
        content.error_message = error_message

        # Update timestamps based on status
        now = datetime.now(UTC)
        if status == ContentStatus.PARSED:
            content.parsed_at = now
        elif status in (ContentStatus.COMPLETED, ContentStatus.FAILED):
            content.processed_at = now

        self.db.commit()
        self.db.refresh(content)

        return content

    def get_duplicates(self, content_id: int) -> list[Content]:
        """Get all duplicates of a canonical Content record.

        Args:
            content_id: Canonical Content record ID

        Returns:
            List of Content records that are duplicates of this one
        """
        stmt = (
            select(Content)
            .where(Content.canonical_id == content_id)
            .order_by(Content.ingested_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def merge_duplicates(
        self,
        canonical_id: int,
        duplicate_id: int,
    ) -> Content | None:
        """Mark one Content as duplicate of another.

        Args:
            canonical_id: ID of the canonical (original) content
            duplicate_id: ID of the duplicate content

        Returns:
            Updated duplicate Content or None if either not found
        """
        canonical = self.get(canonical_id)
        duplicate = self.get(duplicate_id)

        if not canonical or not duplicate:
            return None

        if canonical_id == duplicate_id:
            raise ValueError("Cannot mark content as duplicate of itself")

        duplicate.canonical_id = canonical_id
        self.db.commit()
        self.db.refresh(duplicate)

        return duplicate
