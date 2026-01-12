"""Content API Routes.

CRUD operations for the unified Content model. Provides endpoints for
listing, retrieving, creating, and deleting content records.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func

from src.models.content import (
    Content,
    ContentCreate,
    ContentListItem,
    ContentListResponse,
    ContentResponse,
    ContentSource,
    ContentStatus,
)
from src.services.content_service import ContentService
from src.storage.database import get_db

router = APIRouter(prefix="/api/v1/contents", tags=["contents"])


# ============================================================================
# Request/Response Models (extending the base schemas)
# ============================================================================


class ContentCreateRequest(BaseModel):
    """Request body for creating content via API."""

    source_type: ContentSource = Field(
        default=ContentSource.MANUAL,
        description="Content source type",
    )
    source_id: str | None = Field(
        default=None,
        description="Source-specific ID (auto-generated if not provided)",
    )
    source_url: str | None = Field(
        default=None,
        description="Original URL of the content",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Content title",
    )
    author: str | None = Field(
        default=None,
        max_length=500,
        description="Content author",
    )
    publication: str | None = Field(
        default=None,
        max_length=500,
        description="Publication or source name",
    )
    published_date: datetime | None = Field(
        default=None,
        description="Original publication date",
    )
    markdown_content: str = Field(
        ...,
        min_length=1,
        description="Content in markdown format",
    )
    tables_json: list[dict] | None = Field(
        default=None,
        description="Structured table data extracted from content",
    )
    links_json: list[str] | None = Field(
        default=None,
        description="URLs extracted from content",
    )
    metadata_json: dict | None = Field(
        default=None,
        description="Additional metadata",
    )


class ContentStats(BaseModel):
    """Content statistics."""

    total: int
    by_status: dict[str, int]
    by_source: dict[str, int]
    pending_count: int
    completed_count: int
    failed_count: int


class DuplicateInfo(BaseModel):
    """Information about duplicate content."""

    canonical_id: int
    canonical_title: str
    duplicate_count: int

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Endpoints
# ============================================================================


@router.get("", response_model=ContentListResponse)
async def list_contents(
    source_type: ContentSource | None = Query(None, description="Filter by source type"),
    status: ContentStatus | None = Query(None, description="Filter by status"),
    publication: str | None = Query(None, description="Filter by publication"),
    start_date: datetime | None = Query(None, description="Filter after this date"),
    end_date: datetime | None = Query(None, description="Filter before this date"),
    search: str | None = Query(None, description="Search in title"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> ContentListResponse:
    """
    List contents with optional filters.

    Supports filtering by source type, status, publication, date range, and search.
    Results are paginated and sorted by ingested date (newest first).
    """
    with get_db() as db:
        query = db.query(Content)

        # Apply filters
        if source_type:
            query = query.filter(Content.source_type == source_type)
        if status:
            query = query.filter(Content.status == status)
        if publication:
            query = query.filter(Content.publication.ilike(f"%{publication}%"))
        if start_date:
            query = query.filter(Content.published_date >= start_date)
        if end_date:
            query = query.filter(Content.published_date <= end_date)
        if search:
            query = query.filter(Content.title.ilike(f"%{search}%"))

        # Get total count
        total = query.count()

        # Calculate offset from page
        offset = (page - 1) * page_size

        # Apply pagination and ordering
        contents = query.order_by(Content.ingested_at.desc()).offset(offset).limit(page_size).all()

        # Convert to response models
        items = [
            ContentListItem(
                id=c.id,
                source_type=c.source_type,
                title=c.title,
                publication=c.publication,
                published_date=c.published_date,
                status=c.status,
                ingested_at=c.ingested_at,
            )
            for c in contents
        ]

        return ContentListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=(offset + page_size) < total,
            has_prev=page > 1,
        )


@router.get("/stats", response_model=ContentStats)
async def get_content_stats() -> ContentStats:
    """Get content statistics."""
    with get_db() as db:
        total = db.query(Content).count()

        # Count by status
        status_counts = (
            db.query(Content.status, func.count(Content.id)).group_by(Content.status).all()
        )
        by_status = {status.value: count for status, count in status_counts}

        # Count by source
        source_counts = (
            db.query(Content.source_type, func.count(Content.id))
            .group_by(Content.source_type)
            .all()
        )
        by_source = {source.value: count for source, count in source_counts}

        return ContentStats(
            total=total,
            by_status=by_status,
            by_source=by_source,
            pending_count=by_status.get(ContentStatus.PENDING.value, 0),
            completed_count=by_status.get(ContentStatus.COMPLETED.value, 0),
            failed_count=by_status.get(ContentStatus.FAILED.value, 0),
        )


@router.get("/{content_id}", response_model=ContentResponse)
async def get_content(content_id: int) -> ContentResponse:
    """
    Get content by ID.

    Returns full content details including markdown content.
    """
    with get_db() as db:
        service = ContentService(db)
        content = service.get(content_id)

        if not content:
            raise HTTPException(status_code=404, detail="Content not found")

        return ContentResponse(
            id=content.id,
            source_type=content.source_type,
            source_id=content.source_id,
            source_url=content.source_url,
            title=content.title,
            author=content.author,
            publication=content.publication,
            published_date=content.published_date,
            markdown_content=content.markdown_content,
            tables_json=content.tables_json,
            links_json=content.links_json,
            metadata_json=content.metadata_json,
            parser_used=content.parser_used,
            content_hash=content.content_hash,
            canonical_id=content.canonical_id,
            status=content.status,
            error_message=content.error_message,
            ingested_at=content.ingested_at,
            parsed_at=content.parsed_at,
            processed_at=content.processed_at,
        )


@router.post("", response_model=ContentResponse, status_code=201)
async def create_content(request: ContentCreateRequest) -> ContentResponse:
    """
    Create new content.

    Primarily used for manual content creation via API.
    Automatically checks for duplicates and generates content hash.
    """
    from datetime import UTC, datetime as dt
    from uuid import uuid4

    with get_db() as db:
        service = ContentService(db)

        # Generate source_id if not provided
        source_id = request.source_id or f"manual_{uuid4().hex[:16]}"

        # Check if source already exists
        existing = service.get_by_source(request.source_type, source_id)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Content with source_type={request.source_type.value} "
                f"and source_id={source_id} already exists",
            )

        # Create content
        create_data = ContentCreate(
            source_type=request.source_type,
            source_id=source_id,
            source_url=request.source_url,
            title=request.title,
            author=request.author,
            publication=request.publication,
            published_date=request.published_date or dt.now(UTC),
            markdown_content=request.markdown_content,
            tables_json=request.tables_json,
            links_json=request.links_json,
            metadata_json=request.metadata_json,
            content_hash="",  # Will be generated by service
        )

        content = service.create(create_data, check_duplicate=True)

        return ContentResponse(
            id=content.id,
            source_type=content.source_type,
            source_id=content.source_id,
            source_url=content.source_url,
            title=content.title,
            author=content.author,
            publication=content.publication,
            published_date=content.published_date,
            markdown_content=content.markdown_content,
            tables_json=content.tables_json,
            links_json=content.links_json,
            metadata_json=content.metadata_json,
            parser_used=content.parser_used,
            content_hash=content.content_hash,
            canonical_id=content.canonical_id,
            status=content.status,
            error_message=content.error_message,
            ingested_at=content.ingested_at,
            parsed_at=content.parsed_at,
            processed_at=content.processed_at,
        )


@router.delete("/{content_id}", status_code=204)
async def delete_content(content_id: int) -> None:
    """
    Delete content by ID.

    Also unlinks any content that references this as canonical.
    """
    with get_db() as db:
        service = ContentService(db)
        deleted = service.delete(content_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Content not found")


@router.get("/{content_id}/duplicates", response_model=list[ContentListItem])
async def get_content_duplicates(content_id: int) -> list[ContentListItem]:
    """
    Get all duplicates of a content record.

    Returns content records that have this content as their canonical.
    """
    with get_db() as db:
        service = ContentService(db)

        # Verify content exists
        content = service.get(content_id)
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")

        duplicates = service.get_duplicates(content_id)

        return [
            ContentListItem(
                id=c.id,
                source_type=c.source_type,
                title=c.title,
                publication=c.publication,
                published_date=c.published_date,
                status=c.status,
                ingested_at=c.ingested_at,
            )
            for c in duplicates
        ]


@router.post("/{content_id}/merge/{duplicate_id}", response_model=ContentResponse)
async def merge_duplicate(content_id: int, duplicate_id: int) -> ContentResponse:
    """
    Mark one content as a duplicate of another.

    The duplicate_id content will be linked to content_id as its canonical.
    """
    with get_db() as db:
        service = ContentService(db)

        try:
            duplicate = service.merge_duplicates(content_id, duplicate_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        if not duplicate:
            raise HTTPException(
                status_code=404,
                detail="One or both content records not found",
            )

        return ContentResponse(
            id=duplicate.id,
            source_type=duplicate.source_type,
            source_id=duplicate.source_id,
            source_url=duplicate.source_url,
            title=duplicate.title,
            author=duplicate.author,
            publication=duplicate.publication,
            published_date=duplicate.published_date,
            markdown_content=duplicate.markdown_content,
            tables_json=duplicate.tables_json,
            links_json=duplicate.links_json,
            metadata_json=duplicate.metadata_json,
            parser_used=duplicate.parser_used,
            content_hash=duplicate.content_hash,
            canonical_id=duplicate.canonical_id,
            status=duplicate.status,
            error_message=duplicate.error_message,
            ingested_at=duplicate.ingested_at,
            parsed_at=duplicate.parsed_at,
            processed_at=duplicate.processed_at,
        )
