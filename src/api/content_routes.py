"""Content API Routes.

CRUD operations and ingestion for the unified Content model. Provides endpoints for
listing, retrieving, creating, deleting, and ingesting content records.
"""

import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import defer

from src.models.content import (
    Content,
    ContentCreate,
    ContentListItem,
    ContentResponse,
    ContentSource,
    ContentStatus,
)
from src.models.jobs import JobStatus
from src.services.content_service import ContentService
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Response Models
# ============================================================================


class ContentListResponse(BaseModel):
    """Paginated content list response."""

    items: list[ContentListItem]
    total: int
    page: int
    page_size: int
    has_next: bool = Field(default=False)
    has_prev: bool = Field(default=False)


# Allowed fields for sorting content list
CONTENT_SORT_FIELDS = {
    "id",
    "title",
    "source_type",
    "publication",
    "status",
    "published_date",
    "ingested_at",
}

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
    # Count of content items that don't have summaries yet
    needs_summarization_count: int = 0


class IngestRequest(BaseModel):
    """Request to trigger content ingestion."""

    source: ContentSource = Field(default=ContentSource.GMAIL, description="Source to ingest from")
    max_results: int = Field(default=50, ge=1, le=200, description="Maximum items to fetch")
    days_back: int = Field(default=7, ge=1, le=90, description="Days back to search")
    force_reprocess: bool = Field(default=False, description="Force reprocess existing content")


class IngestResponse(BaseModel):
    """Response from ingestion trigger."""

    task_id: str
    message: str
    source: ContentSource
    max_results: int


# ============================================================================
# Job Queue Integration for Ingestion (replaces in-memory task storage)
# ============================================================================


async def _enqueue_ingestion_job(
    source: ContentSource,
    max_results: int,
    days_back: int,
    force_reprocess: bool,
) -> int:
    """Enqueue an ingestion job to pgqueuer_jobs table.

    Returns the job ID for status tracking.
    """
    import json

    import asyncpg

    from src.queue.setup import (
        _sqlalchemy_url_to_asyncpg,
        get_queue_connection_string,
    )

    queue_url = get_queue_connection_string()
    asyncpg_url = _sqlalchemy_url_to_asyncpg(queue_url)
    conn = await asyncpg.connect(asyncpg_url)

    try:
        payload = json.dumps(
            {
                "source": source.value,
                "max_results": max_results,
                "days_back": days_back,
                "force_reprocess": force_reprocess,
                "progress": 0,
                "message": "Queued",
            }
        )

        job_id: int = await conn.fetchval(
            """
            INSERT INTO pgqueuer_jobs (entrypoint, payload, status, created_at, execute_after)
            VALUES ('ingest_content', $1::jsonb, 'queued', NOW(), NOW())
            RETURNING id
            """,
            payload,
        )

        # Notify workers
        await conn.execute("SELECT pg_notify('pgqueuer', 'ingest_content')")

        logger.info(f"Enqueued ingestion job {job_id} for source {source.value}")
        return job_id

    finally:
        await conn.close()


class DuplicateInfo(BaseModel):
    """Information about duplicate content."""

    canonical_id: int
    canonical_title: str
    duplicate_count: int

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/ingest", response_model=IngestResponse)
async def trigger_content_ingestion(
    request: IngestRequest,
) -> IngestResponse:
    """
    Trigger content ingestion from a source.

    Enqueues an ingestion job to the pgqueuer_jobs table and returns the job ID.
    Use the /ingest/status/{task_id} endpoint to get real-time progress via SSE.

    Supported sources:
    - gmail: Fetch newsletters from Gmail inbox
    - rss: Fetch articles from configured RSS feeds
    - youtube: Fetch transcripts from configured YouTube playlists
    - podcast: Fetch transcripts from configured podcast feeds
    """
    # Enqueue job to pgqueuer_jobs table (persistent, survives restarts)
    job_id = await _enqueue_ingestion_job(
        source=request.source,
        max_results=request.max_results,
        days_back=request.days_back,
        force_reprocess=request.force_reprocess,
    )

    return IngestResponse(
        task_id=str(job_id),
        message="Content ingestion queued",
        source=request.source,
        max_results=request.max_results,
    )


@router.get("/ingest/status/{task_id}")
async def get_ingestion_status(task_id: str) -> StreamingResponse:
    """
    Get content ingestion task status via Server-Sent Events.

    Stream real-time progress updates for the ingestion task.
    Reads from pgqueuer_jobs table for persistent status tracking.
    """
    from src.queue.setup import get_job_status

    # Validate task_id is a valid job ID
    try:
        job_id = int(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    # Check job exists
    job = await get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        import json

        while True:
            job = await get_job_status(job_id)
            if not job:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Task not found'})}\n\n"
                break

            # Map job record to SSE response format
            payload = job.payload or {}
            task_data = {
                "status": _map_job_status_to_task_status(job.status),
                "progress": payload.get("progress", 0),
                "total": payload.get("total", 0),
                "processed": payload.get("processed", 0),
                "source": payload.get("source", "unknown"),
                "message": payload.get("message", ""),
                "started_at": job.started_at.isoformat() if job.started_at else None,
            }

            if job.error:
                task_data["message"] = job.error

            yield f"data: {json.dumps(task_data)}\n\n"

            # Check for terminal states
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


def _map_job_status_to_task_status(job_status: JobStatus) -> str:
    """Map JobStatus enum to legacy task status strings for SSE compatibility."""
    mapping = {
        JobStatus.QUEUED: "queued",
        JobStatus.IN_PROGRESS: "processing",
        JobStatus.COMPLETED: "completed",
        JobStatus.FAILED: "error",
    }
    return mapping.get(job_status, "unknown")


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
    sort_by: str = Query("ingested_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
) -> ContentListResponse:
    """
    List contents with optional filters.

    Supports filtering by source type, status, publication, date range, and search.
    Results are paginated and sorted by the specified field (default: ingested_at desc).
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

        # Validate sort_by field
        if sort_by not in CONTENT_SORT_FIELDS:
            sort_by = "ingested_at"

        # Get sort column dynamically
        sort_column = getattr(Content, sort_by, Content.ingested_at)
        if sort_order.lower() == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        # OPTIMIZATION: Defer heavy text/json columns for list view
        # This is safer than load_only as it automatically includes new lightweight columns
        query = query.options(
            defer(Content.markdown_content),
            defer(Content.tables_json),
            defer(Content.links_json),
            defer(Content.metadata_json),
            defer(Content.raw_content),
            defer(Content.error_message),
        )

        # Apply pagination
        contents = query.offset(offset).limit(page_size).all()

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
    from src.models.summary import Summary

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

        # Count content items that don't have summaries yet
        # Use LEFT JOIN to find content without summaries (more efficient than NOT IN subquery)
        needs_summarization_count = (
            db.query(func.count(Content.id))
            .outerjoin(Summary, Content.id == Summary.content_id)
            .filter(Summary.id.is_(None))
            .scalar()
        )

        return ContentStats(
            total=total,
            by_status=by_status,
            by_source=by_source,
            pending_count=by_status.get(ContentStatus.PENDING.value, 0),
            completed_count=by_status.get(ContentStatus.COMPLETED.value, 0),
            failed_count=by_status.get(ContentStatus.FAILED.value, 0),
            needs_summarization_count=needs_summarization_count,
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


# ============================================================================
# Content Summarization Endpoints
# ============================================================================


class SummarizeContentRequest(BaseModel):
    """Request to trigger content summarization."""

    content_ids: list[int] = Field(
        default_factory=list,
        description="Specific content IDs to summarize (empty = all pending/parsed)",
    )
    force: bool = Field(
        default=False,
        description="Force re-summarization even if summary exists",
    )
    retry_failed: bool = Field(
        default=False,
        description="Include failed content items (reset to PARSED and retry)",
    )


class SummarizeContentResponse(BaseModel):
    """Response from content summarization trigger."""

    task_id: str
    message: str
    queued_count: int
    content_ids: list[int]


# ============================================================================
# Job Queue Integration for Summarization (replaces in-memory task storage)
# ============================================================================


async def _enqueue_summarization_batch_job(
    content_ids: list[int],
    force: bool,
) -> int:
    """Enqueue a batch summarization job to track overall progress.

    Individual content items are enqueued as separate jobs via enqueue_summarization_job.
    This function creates a parent job to track the batch progress.

    Returns the batch job ID for status tracking.
    """
    import json

    import asyncpg

    from src.queue.setup import (
        _sqlalchemy_url_to_asyncpg,
        enqueue_summarization_job,
        get_queue_connection_string,
    )

    queue_url = get_queue_connection_string()
    asyncpg_url = _sqlalchemy_url_to_asyncpg(queue_url)
    conn = await asyncpg.connect(asyncpg_url)

    try:
        # Create batch tracking job
        payload = json.dumps(
            {
                "content_ids": content_ids,
                "force": force,
                "total": len(content_ids),
                "enqueued": 0,
                "completed": 0,
                "failed": 0,
                "progress": 0,
                "message": "Enqueueing individual jobs",
            }
        )

        batch_job_id: int = await conn.fetchval(
            """
            INSERT INTO pgqueuer_jobs (entrypoint, payload, status, created_at, execute_after)
            VALUES ('summarize_batch', $1::jsonb, 'in_progress', NOW(), NOW())
            RETURNING id
            """,
            payload,
        )

        logger.info(f"Created batch summarization job {batch_job_id} for {len(content_ids)} items")

    finally:
        await conn.close()

    # Enqueue individual summarization jobs
    enqueued_count = 0
    for content_id in content_ids:
        job_id = await enqueue_summarization_job(content_id)
        if job_id is not None:
            enqueued_count += 1

    # Update batch job with enqueued count
    conn = await asyncpg.connect(asyncpg_url)
    try:
        await conn.execute(
            """
            UPDATE pgqueuer_jobs
            SET payload = payload || $1::jsonb
            WHERE id = $2
            """,
            json.dumps({"enqueued": enqueued_count, "message": f"Enqueued {enqueued_count} jobs"}),
            batch_job_id,
        )
    finally:
        await conn.close()

    return batch_job_id


@router.post("/summarize", response_model=SummarizeContentResponse)
async def trigger_content_summarization(
    request: SummarizeContentRequest,
) -> SummarizeContentResponse:
    """
    Trigger summarization for content records.

    If content_ids is empty, summarizes all pending/parsed content.
    Enqueues jobs to pgqueuer_jobs table for worker processing.
    Use the /summarize/status/{task_id} endpoint to get real-time progress via SSE.
    """
    from src.models.summary import Summary

    # Get content to process
    with get_db() as db:
        # Get all content IDs that already have summaries
        existing_summary_ids = {
            s.content_id
            for s in db.query(Summary.content_id).filter(Summary.content_id.isnot(None)).all()
        }

        if request.content_ids:
            # Filter specific content IDs
            query = db.query(Content).filter(Content.id.in_(request.content_ids))
            if not request.force:
                # Exclude content that already has summaries or is completed
                query = query.filter(
                    Content.status != ContentStatus.COMPLETED,
                    ~Content.id.in_(existing_summary_ids) if existing_summary_ids else True,
                )
            contents = query.all()
        else:
            # Determine which statuses to include
            statuses_to_include = [ContentStatus.PENDING, ContentStatus.PARSED]
            if request.retry_failed:
                statuses_to_include.append(ContentStatus.FAILED)

            # Get content in eligible statuses that doesn't have a summary
            query = db.query(Content).filter(Content.status.in_(statuses_to_include))
            if existing_summary_ids:
                query = query.filter(~Content.id.in_(existing_summary_ids))
            contents = query.all()

            # Reset failed content to PARSED so it can be retried
            if request.retry_failed:
                for content in contents:
                    if content.status == ContentStatus.FAILED:
                        content.status = ContentStatus.PARSED
                        content.error_message = None
                db.commit()

        content_ids = [c.id for c in contents]

    if not content_ids:
        return SummarizeContentResponse(
            task_id="0",
            message="No content to summarize",
            queued_count=0,
            content_ids=[],
        )

    # Enqueue batch job to pgqueuer_jobs table (persistent, survives restarts)
    batch_job_id = await _enqueue_summarization_batch_job(content_ids, request.force)

    return SummarizeContentResponse(
        task_id=str(batch_job_id),
        message="Content summarization queued",
        queued_count=len(content_ids),
        content_ids=content_ids,
    )


@router.get("/summarize/status/{task_id}")
async def get_content_summarization_status(task_id: str) -> StreamingResponse:
    """
    Get content summarization task status via Server-Sent Events.

    Stream real-time progress updates for the summarization task.
    Reads from pgqueuer_jobs table for persistent status tracking.

    For batch jobs, aggregates progress from individual summarization jobs.
    """
    from src.queue.setup import get_job_status

    # Validate task_id is a valid job ID
    try:
        job_id = int(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    # Check job exists
    job = await get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        import json

        import asyncpg

        from src.queue.setup import (
            _sqlalchemy_url_to_asyncpg,
            get_queue_connection_string,
        )

        queue_url = get_queue_connection_string()
        asyncpg_url = _sqlalchemy_url_to_asyncpg(queue_url)

        while True:
            job = await get_job_status(job_id)
            if not job:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Task not found'})}\n\n"
                break

            payload = job.payload or {}

            # For batch jobs, count individual job progress
            if job.entrypoint == "summarize_batch":
                content_ids = payload.get("content_ids", [])
                total = len(content_ids)

                if total > 0:
                    # Query status of individual summarize_content jobs
                    conn = await asyncpg.connect(asyncpg_url)
                    try:
                        # Count completed and failed jobs for our content_ids
                        # Jobs have payload->content_id matching our list
                        result = await conn.fetch(
                            """
                            SELECT status, COUNT(*) as cnt
                            FROM pgqueuer_jobs
                            WHERE entrypoint = 'summarize_content'
                              AND (payload->>'content_id')::int = ANY($1::int[])
                            GROUP BY status
                            """,
                            content_ids,
                        )

                        completed = 0
                        failed = 0
                        in_progress = 0
                        for row in result:
                            if row["status"] == "completed":
                                completed = row["cnt"]
                            elif row["status"] == "failed":
                                failed = row["cnt"]
                            elif row["status"] == "in_progress":
                                in_progress = row["cnt"]

                        processed = completed + failed
                        progress = int((processed / total) * 100) if total > 0 else 0

                        # Determine batch status
                        if processed == total:
                            batch_status = "completed"
                            # Update batch job to completed
                            await conn.execute(
                                """
                                UPDATE pgqueuer_jobs
                                SET status = 'completed', completed_at = NOW()
                                WHERE id = $1 AND status != 'completed'
                                """,
                                job_id,
                            )
                        elif in_progress > 0 or processed < total:
                            batch_status = "processing"
                        else:
                            batch_status = "queued"

                    finally:
                        await conn.close()

                    task_data = {
                        "status": batch_status,
                        "progress": progress,
                        "total": total,
                        "processed": processed,
                        "completed": completed,
                        "failed": failed,
                        "current_content_id": None,
                        "message": payload.get("message", f"Processed {processed}/{total}"),
                        "started_at": job.started_at.isoformat() if job.started_at else None,
                    }
                else:
                    task_data = {
                        "status": "completed",
                        "progress": 100,
                        "total": 0,
                        "processed": 0,
                        "completed": 0,
                        "failed": 0,
                        "current_content_id": None,
                        "message": "No content to summarize",
                        "started_at": job.started_at.isoformat() if job.started_at else None,
                    }
            else:
                # Single summarization job
                task_data = {
                    "status": _map_job_status_to_task_status(job.status),
                    "progress": payload.get("progress", 0),
                    "total": 1,
                    "processed": 1 if job.status in (JobStatus.COMPLETED, JobStatus.FAILED) else 0,
                    "completed": 1 if job.status == JobStatus.COMPLETED else 0,
                    "failed": 1 if job.status == JobStatus.FAILED else 0,
                    "current_content_id": payload.get("content_id"),
                    "message": payload.get("message", ""),
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                }

            if job.error:
                task_data["message"] = job.error

            yield f"data: {json.dumps(task_data)}\n\n"

            # Check for terminal states
            if task_data["status"] in ("completed", "error"):
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
