"""
Newsletter API Routes

CRUD operations and ingestion endpoints for newsletters.
Includes SSE endpoints for real-time progress tracking.

DEPRECATION NOTICE:
These endpoints are deprecated in favor of the unified /api/v1/contents endpoints.
The Newsletter model is being replaced by the Content model as part of the
unified content model refactor. These endpoints will be removed in a future version.

See: /api/v1/contents for the new unified content API.
"""

import asyncio
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func

from src.models.newsletter import Newsletter, NewsletterSource, ProcessingStatus
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/newsletters", tags=["newsletters"])

# Deprecation warning message
DEPRECATION_MESSAGE = (
    "This endpoint is deprecated. Use /api/v1/contents instead. "
    "The Newsletter model is being replaced by the unified Content model."
)


def add_deprecation_headers(response: Response) -> None:
    """Add standard deprecation headers to response."""
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2025-12-31"
    response.headers["Link"] = '</api/v1/contents>; rel="successor-version"'
    response.headers["X-Deprecation-Notice"] = DEPRECATION_MESSAGE


# ============================================================================
# Request/Response Models
# ============================================================================


class NewsletterListItem(BaseModel):
    """Lightweight newsletter for list views."""

    id: int
    source: NewsletterSource
    title: str
    sender: str | None
    publication: str | None
    published_date: datetime
    status: ProcessingStatus
    has_summary: bool = False
    ingested_at: datetime

    class Config:
        from_attributes = True


class NewsletterDetail(BaseModel):
    """Full newsletter details."""

    id: int
    source: NewsletterSource
    source_id: str
    title: str
    sender: str | None
    publication: str | None
    published_date: datetime
    url: str | None
    raw_text: str | None
    extracted_links: list[str] | None
    # YouTube transcripts store metadata as dict in extracted_links column
    transcript_metadata: dict | None = None
    content_hash: str | None
    canonical_newsletter_id: int | None
    status: ProcessingStatus
    ingested_at: datetime
    processed_at: datetime | None
    error_message: str | None

    class Config:
        from_attributes = True


class PaginatedNewsletterResponse(BaseModel):
    """Paginated newsletter list response."""

    items: list[NewsletterListItem]
    total: int
    offset: int
    limit: int
    has_more: bool


class IngestRequest(BaseModel):
    """Request to trigger newsletter ingestion."""

    source: NewsletterSource = Field(
        default=NewsletterSource.GMAIL, description="Source to ingest from"
    )
    max_results: int = Field(default=50, ge=1, le=200, description="Maximum newsletters to fetch")
    days_back: int = Field(default=7, ge=1, le=90, description="Days back to search")


class IngestResponse(BaseModel):
    """Response from ingestion trigger."""

    task_id: str
    message: str
    source: NewsletterSource
    max_results: int


class NewsletterStats(BaseModel):
    """Newsletter statistics."""

    total: int
    by_status: dict[str, int]
    by_source: dict[str, int]
    pending_count: int
    summarized_count: int


# ============================================================================
# In-memory task storage (would use Redis in production)
# ============================================================================

_ingestion_tasks: dict[str, dict] = {}


# ============================================================================
# Endpoints
# ============================================================================


@router.get("", response_model=PaginatedNewsletterResponse, deprecated=True)
async def list_newsletters(
    response: Response,
    source: NewsletterSource | None = Query(None, description="Filter by source"),
    status: ProcessingStatus | None = Query(None, description="Filter by status"),
    publication: str | None = Query(None, description="Filter by publication"),
    start_date: datetime | None = Query(None, description="Filter after this date"),
    end_date: datetime | None = Query(None, description="Filter before this date"),
    search: str | None = Query(None, description="Search in title"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PaginatedNewsletterResponse:
    """
    List newsletters with optional filters.

    **DEPRECATED**: Use GET /api/v1/contents instead.

    Supports filtering by source, status, publication, date range, and search.
    Results are paginated and sorted by published date (newest first).
    """
    add_deprecation_headers(response)
    logger.warning("Deprecated endpoint called: GET /api/v1/newsletters")
    with get_db() as db:
        query = db.query(Newsletter)

        # Apply filters
        if source:
            query = query.filter(Newsletter.source == source)
        if status:
            query = query.filter(Newsletter.status == status)
        if publication:
            query = query.filter(Newsletter.publication.ilike(f"%{publication}%"))
        if start_date:
            query = query.filter(Newsletter.published_date >= start_date)
        if end_date:
            query = query.filter(Newsletter.published_date <= end_date)
        if search:
            query = query.filter(Newsletter.title.ilike(f"%{search}%"))

        # Get total count
        total = query.count()

        # Apply pagination and ordering
        newsletters = (
            query.order_by(Newsletter.published_date.desc()).offset(offset).limit(limit).all()
        )

        # Convert to response models
        items = [
            NewsletterListItem(
                id=n.id,
                source=n.source,
                title=n.title,
                sender=n.sender,
                publication=n.publication,
                published_date=n.published_date,
                status=n.status,
                has_summary=n.status == ProcessingStatus.COMPLETED,
                ingested_at=n.ingested_at,
            )
            for n in newsletters
        ]

        return PaginatedNewsletterResponse(
            items=items,
            total=total,
            offset=offset,
            limit=limit,
            has_more=(offset + limit) < total,
        )


@router.get("/stats", response_model=NewsletterStats, deprecated=True)
async def get_newsletter_stats(response: Response) -> NewsletterStats:
    """Get newsletter statistics.

    **DEPRECATED**: Use GET /api/v1/contents/stats instead.
    """
    add_deprecation_headers(response)
    logger.warning("Deprecated endpoint called: GET /api/v1/newsletters/stats")
    with get_db() as db:
        total = db.query(Newsletter).count()

        # Count by status
        status_counts = (
            db.query(Newsletter.status, func.count(Newsletter.id)).group_by(Newsletter.status).all()
        )
        by_status = {status.value: count for status, count in status_counts}

        # Count by source
        source_counts = (
            db.query(Newsletter.source, func.count(Newsletter.id)).group_by(Newsletter.source).all()
        )
        by_source = {source.value: count for source, count in source_counts}

        return NewsletterStats(
            total=total,
            by_status=by_status,
            by_source=by_source,
            pending_count=by_status.get("pending", 0),
            summarized_count=by_status.get("completed", 0),
        )


@router.get("/{newsletter_id}", response_model=NewsletterDetail, deprecated=True)
async def get_newsletter(newsletter_id: int, response: Response) -> NewsletterDetail:
    """Get a single newsletter by ID.

    **DEPRECATED**: Use GET /api/v1/contents/{id} instead.
    """
    add_deprecation_headers(response)
    logger.warning(f"Deprecated endpoint called: GET /api/v1/newsletters/{newsletter_id}")
    with get_db() as db:
        newsletter = db.query(Newsletter).filter(Newsletter.id == newsletter_id).first()

        if not newsletter:
            raise HTTPException(status_code=404, detail="Newsletter not found")

        # Handle extracted_links based on type (list for normal, dict for YouTube)
        extracted_links = newsletter.extracted_links
        transcript_metadata = None

        if isinstance(extracted_links, dict):
            # YouTube transcript metadata stored as dict
            transcript_metadata = extracted_links
            extracted_links = []
        elif not isinstance(extracted_links, list):
            extracted_links = []

        return NewsletterDetail(
            id=newsletter.id,
            source=newsletter.source,
            source_id=newsletter.source_id,
            title=newsletter.title,
            sender=newsletter.sender,
            publication=newsletter.publication,
            published_date=newsletter.published_date,
            url=newsletter.url,
            raw_text=newsletter.raw_text,
            extracted_links=extracted_links,
            transcript_metadata=transcript_metadata,
            content_hash=newsletter.content_hash,
            canonical_newsletter_id=newsletter.canonical_newsletter_id,
            status=newsletter.status,
            ingested_at=newsletter.ingested_at,
            processed_at=newsletter.processed_at,
            error_message=newsletter.error_message,
        )


@router.delete("/{newsletter_id}", deprecated=True)
async def delete_newsletter(newsletter_id: int, response: Response):
    """Delete a newsletter.

    **DEPRECATED**: Use DELETE /api/v1/contents/{id} instead.
    """
    add_deprecation_headers(response)
    logger.warning(f"Deprecated endpoint called: DELETE /api/v1/newsletters/{newsletter_id}")
    with get_db() as db:
        newsletter = db.query(Newsletter).filter(Newsletter.id == newsletter_id).first()

        if not newsletter:
            raise HTTPException(status_code=404, detail="Newsletter not found")

        db.delete(newsletter)
        db.commit()

        return {"message": "Newsletter deleted", "id": newsletter_id}


@router.post("/ingest", response_model=IngestResponse, deprecated=True)
async def trigger_ingestion(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    response: Response,
) -> IngestResponse:
    """
    Trigger newsletter ingestion from a source.

    **DEPRECATED**: Use POST /api/v1/contents/ingest instead (coming soon).

    Starts a background task and returns a task ID for progress tracking.
    Use the /ingest/status/{task_id} endpoint to get real-time progress via SSE.
    """
    add_deprecation_headers(response)
    logger.warning("Deprecated endpoint called: POST /api/v1/newsletters/ingest")
    import uuid

    task_id = str(uuid.uuid4())

    # Initialize task state
    _ingestion_tasks[task_id] = {
        "status": "queued",
        "progress": 0,
        "total": 0,
        "processed": 0,
        "source": request.source.value,
        "message": "Ingestion queued",
        "started_at": datetime.utcnow().isoformat(),
    }

    # Start background ingestion
    background_tasks.add_task(
        _run_ingestion,
        task_id,
        request.source,
        request.max_results,
        request.days_back,
    )

    return IngestResponse(
        task_id=task_id,
        message="Ingestion started",
        source=request.source,
        max_results=request.max_results,
    )


async def _run_ingestion(
    task_id: str,
    source: NewsletterSource,
    max_results: int,
    days_back: int,
):
    """Background ingestion task."""
    try:
        _ingestion_tasks[task_id]["status"] = "processing"
        _ingestion_tasks[task_id]["message"] = f"Starting {source.value} ingestion"

        if source == NewsletterSource.GMAIL:
            from src.ingestion.gmail import GmailIngester

            ingester = GmailIngester()
            newsletters = await asyncio.to_thread(
                ingester.fetch_newsletters,
                max_results=max_results,
                days_back=days_back,
            )
        elif source in (NewsletterSource.RSS, NewsletterSource.SUBSTACK_RSS):
            from src.ingestion.substack import SubstackIngester

            ingester = SubstackIngester()
            newsletters = await asyncio.to_thread(
                ingester.fetch_newsletters,
                days_back=days_back,
            )
        else:
            _ingestion_tasks[task_id]["status"] = "error"
            _ingestion_tasks[task_id]["message"] = f"Unsupported source: {source}"
            return

        total = len(newsletters)
        _ingestion_tasks[task_id]["total"] = total

        # Store newsletters
        with get_db() as db:
            for i, data in enumerate(newsletters):
                # Check for existing
                existing = (
                    db.query(Newsletter).filter(Newsletter.source_id == data.source_id).first()
                )
                if existing:
                    _ingestion_tasks[task_id]["processed"] = i + 1
                    _ingestion_tasks[task_id]["progress"] = int((i + 1) / total * 100)
                    _ingestion_tasks[task_id]["message"] = (
                        f"Skipped duplicate: {data.title[:50]}..."
                    )
                    continue

                newsletter = Newsletter(
                    source=data.source,
                    source_id=data.source_id,
                    title=data.title,
                    sender=data.sender,
                    publication=data.publication,
                    published_date=data.published_date,
                    url=data.url,
                    raw_html=data.raw_html,
                    raw_text=data.raw_text,
                    extracted_links=data.extracted_links,
                    content_hash=data.content_hash,
                    status=ProcessingStatus.PENDING,
                )
                db.add(newsletter)

                _ingestion_tasks[task_id]["processed"] = i + 1
                _ingestion_tasks[task_id]["progress"] = int((i + 1) / total * 100)
                _ingestion_tasks[task_id]["message"] = f"Ingested: {data.title[:50]}..."

            db.commit()

        _ingestion_tasks[task_id]["status"] = "completed"
        _ingestion_tasks[task_id]["progress"] = 100
        _ingestion_tasks[task_id]["message"] = f"Ingested {total} newsletters"

    except Exception as e:
        _ingestion_tasks[task_id]["status"] = "error"
        _ingestion_tasks[task_id]["message"] = str(e)


@router.get("/ingest/status/{task_id}")
async def get_ingestion_status(task_id: str):
    """
    Get ingestion task status via Server-Sent Events.

    Stream real-time progress updates for the ingestion task.
    """
    if task_id not in _ingestion_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        import json

        while True:
            if task_id not in _ingestion_tasks:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Task not found'})}\n\n"
                break

            task = _ingestion_tasks[task_id]
            yield f"data: {json.dumps(task)}\n\n"

            if task["status"] in ("completed", "error"):
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
