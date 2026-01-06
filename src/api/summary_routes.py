"""
Summary API Routes

CRUD operations and summarization endpoints for newsletter summaries.
Includes SSE endpoints for real-time progress tracking.
"""

import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func

from src.models.newsletter import Newsletter, ProcessingStatus
from src.models.summary import NewsletterSummary
from src.storage.database import get_db

router = APIRouter(prefix="/api/v1/summaries", tags=["summaries"])


# ============================================================================
# Request/Response Models
# ============================================================================


class RelevanceScores(BaseModel):
    """Relevance scores for different audience segments."""

    cto_leadership: float = 0.0
    technical_teams: float = 0.0
    individual_developers: float = 0.0


class SummaryListItem(BaseModel):
    """Lightweight summary for list views."""

    id: int
    newsletter_id: int
    newsletter_title: str
    newsletter_publication: Optional[str]
    executive_summary_preview: str
    key_themes: list[str]
    model_used: str
    created_at: datetime
    processing_time_seconds: Optional[float]

    class Config:
        from_attributes = True


class SummaryDetail(BaseModel):
    """Full summary details."""

    id: int
    newsletter_id: int
    executive_summary: str
    key_themes: list[str]
    strategic_insights: list[str]
    technical_details: list[str]
    actionable_items: list[str]
    notable_quotes: list[str]
    relevant_links: list[dict]
    relevance_scores: RelevanceScores
    agent_framework: str
    model_used: str
    model_version: Optional[str]
    created_at: datetime
    token_usage: Optional[int]
    processing_time_seconds: Optional[float]

    class Config:
        from_attributes = True


class PaginatedSummaryResponse(BaseModel):
    """Paginated summary list response."""

    items: list[SummaryListItem]
    total: int
    offset: int
    limit: int
    has_more: bool


class SummarizeRequest(BaseModel):
    """Request to trigger summarization."""

    newsletter_ids: list[int] = Field(
        default_factory=list,
        description="Specific newsletter IDs to summarize (empty = all pending)",
    )
    force: bool = Field(
        default=False,
        description="Force re-summarization even if summary exists",
    )
    model: Optional[str] = Field(
        default=None,
        description="Model to use (uses default if not specified)",
    )


class SummarizeResponse(BaseModel):
    """Response from summarization trigger."""

    task_id: str
    message: str
    queued_count: int
    newsletter_ids: list[int]


class SummaryStats(BaseModel):
    """Summary statistics."""

    total: int
    by_model: dict[str, int]
    avg_processing_time: float
    avg_token_usage: float


# ============================================================================
# In-memory task storage (would use Redis in production)
# ============================================================================

_summarization_tasks: dict[str, dict] = {}


# ============================================================================
# Endpoints
# ============================================================================


@router.get("", response_model=PaginatedSummaryResponse)
async def list_summaries(
    newsletter_id: Optional[int] = Query(None, description="Filter by newsletter"),
    model_used: Optional[str] = Query(None, description="Filter by model"),
    start_date: Optional[datetime] = Query(None, description="Filter after this date"),
    end_date: Optional[datetime] = Query(None, description="Filter before this date"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PaginatedSummaryResponse:
    """
    List summaries with optional filters.

    Results are paginated and sorted by creation date (newest first).
    """
    with get_db() as db:
        query = db.query(NewsletterSummary).join(Newsletter)

        # Apply filters
        if newsletter_id:
            query = query.filter(NewsletterSummary.newsletter_id == newsletter_id)
        if model_used:
            query = query.filter(NewsletterSummary.model_used == model_used)
        if start_date:
            query = query.filter(NewsletterSummary.created_at >= start_date)
        if end_date:
            query = query.filter(NewsletterSummary.created_at <= end_date)

        # Get total count
        total = query.count()

        # Apply pagination and ordering
        summaries = (
            query.order_by(NewsletterSummary.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        # Convert to response models
        items = [
            SummaryListItem(
                id=s.id,
                newsletter_id=s.newsletter_id,
                newsletter_title=s.newsletter.title if s.newsletter else "Unknown",
                newsletter_publication=s.newsletter.publication if s.newsletter else None,
                executive_summary_preview=s.executive_summary[:200] + "..."
                if len(s.executive_summary) > 200
                else s.executive_summary,
                key_themes=s.key_themes or [],
                model_used=s.model_used,
                created_at=s.created_at,
                processing_time_seconds=s.processing_time_seconds,
            )
            for s in summaries
        ]

        return PaginatedSummaryResponse(
            items=items,
            total=total,
            offset=offset,
            limit=limit,
            has_more=(offset + limit) < total,
        )


@router.get("/stats", response_model=SummaryStats)
async def get_summary_stats() -> SummaryStats:
    """Get summary statistics."""
    with get_db() as db:
        total = db.query(NewsletterSummary).count()

        # Count by model
        model_counts = (
            db.query(NewsletterSummary.model_used, func.count(NewsletterSummary.id))
            .group_by(NewsletterSummary.model_used)
            .all()
        )
        by_model = {model: count for model, count in model_counts}

        # Average processing time
        avg_time_result = db.query(
            func.avg(NewsletterSummary.processing_time_seconds)
        ).scalar()
        avg_processing_time = float(avg_time_result) if avg_time_result else 0.0

        # Average token usage
        avg_tokens_result = db.query(func.avg(NewsletterSummary.token_usage)).scalar()
        avg_token_usage = float(avg_tokens_result) if avg_tokens_result else 0.0

        return SummaryStats(
            total=total,
            by_model=by_model,
            avg_processing_time=avg_processing_time,
            avg_token_usage=avg_token_usage,
        )


@router.get("/by-newsletter/{newsletter_id}", response_model=SummaryDetail)
async def get_summary_by_newsletter(newsletter_id: int) -> SummaryDetail:
    """Get summary for a specific newsletter."""
    with get_db() as db:
        summary = (
            db.query(NewsletterSummary)
            .filter(NewsletterSummary.newsletter_id == newsletter_id)
            .first()
        )

        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found for this newsletter")

        return _summary_to_detail(summary)


@router.get("/{summary_id}", response_model=SummaryDetail)
async def get_summary(summary_id: int) -> SummaryDetail:
    """Get a single summary by ID."""
    with get_db() as db:
        summary = (
            db.query(NewsletterSummary)
            .filter(NewsletterSummary.id == summary_id)
            .first()
        )

        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found")

        return _summary_to_detail(summary)


@router.delete("/{summary_id}")
async def delete_summary(summary_id: int):
    """Delete a summary."""
    with get_db() as db:
        summary = (
            db.query(NewsletterSummary)
            .filter(NewsletterSummary.id == summary_id)
            .first()
        )

        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found")

        # Reset newsletter status to pending
        newsletter = db.query(Newsletter).filter(Newsletter.id == summary.newsletter_id).first()
        if newsletter:
            newsletter.status = ProcessingStatus.PENDING
            newsletter.processed_at = None

        db.delete(summary)
        db.commit()

        return {"message": "Summary deleted", "id": summary_id}


@router.post("/generate", response_model=SummarizeResponse)
async def trigger_summarization(
    request: SummarizeRequest,
    background_tasks: BackgroundTasks,
) -> SummarizeResponse:
    """
    Trigger summarization for newsletters.

    If newsletter_ids is empty, summarizes all pending newsletters.
    Use the /status/{task_id} endpoint to get real-time progress via SSE.
    """
    import uuid

    task_id = str(uuid.uuid4())

    # Get newsletters to process
    with get_db() as db:
        if request.newsletter_ids:
            newsletters = (
                db.query(Newsletter)
                .filter(Newsletter.id.in_(request.newsletter_ids))
                .all()
            )
            if not request.force:
                # Filter out already summarized
                newsletters = [
                    n for n in newsletters if n.status != ProcessingStatus.COMPLETED
                ]
        else:
            newsletters = (
                db.query(Newsletter)
                .filter(Newsletter.status == ProcessingStatus.PENDING)
                .all()
            )

        newsletter_ids = [n.id for n in newsletters]

    if not newsletter_ids:
        return SummarizeResponse(
            task_id=task_id,
            message="No newsletters to summarize",
            queued_count=0,
            newsletter_ids=[],
        )

    # Initialize task state
    _summarization_tasks[task_id] = {
        "status": "queued",
        "progress": 0,
        "total": len(newsletter_ids),
        "processed": 0,
        "completed": 0,
        "failed": 0,
        "current_newsletter_id": None,
        "message": "Summarization queued",
        "started_at": datetime.utcnow().isoformat(),
    }

    # Start background summarization
    background_tasks.add_task(
        _run_summarization,
        task_id,
        newsletter_ids,
        request.force,
    )

    return SummarizeResponse(
        task_id=task_id,
        message="Summarization started",
        queued_count=len(newsletter_ids),
        newsletter_ids=newsletter_ids,
    )


@router.post("/{summary_id}/regenerate", response_model=SummarizeResponse)
async def regenerate_summary(
    summary_id: int,
    background_tasks: BackgroundTasks,
) -> SummarizeResponse:
    """
    Regenerate an existing summary.

    Forces re-summarization of the associated newsletter.
    """
    import uuid

    with get_db() as db:
        summary = (
            db.query(NewsletterSummary)
            .filter(NewsletterSummary.id == summary_id)
            .first()
        )

        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found")

        newsletter_id = summary.newsletter_id

        # Delete existing summary
        db.delete(summary)

        # Reset newsletter status
        newsletter = db.query(Newsletter).filter(Newsletter.id == newsletter_id).first()
        if newsletter:
            newsletter.status = ProcessingStatus.PENDING
            newsletter.processed_at = None

        db.commit()

    task_id = str(uuid.uuid4())

    _summarization_tasks[task_id] = {
        "status": "queued",
        "progress": 0,
        "total": 1,
        "processed": 0,
        "completed": 0,
        "failed": 0,
        "current_newsletter_id": newsletter_id,
        "message": "Regeneration queued",
        "started_at": datetime.utcnow().isoformat(),
    }

    background_tasks.add_task(
        _run_summarization,
        task_id,
        [newsletter_id],
        True,
    )

    return SummarizeResponse(
        task_id=task_id,
        message="Regeneration started",
        queued_count=1,
        newsletter_ids=[newsletter_id],
    )


async def _run_summarization(
    task_id: str,
    newsletter_ids: list[int],
    force: bool,
):
    """Background summarization task."""
    try:
        from src.processors.summarizer import NewsletterSummarizer

        _summarization_tasks[task_id]["status"] = "processing"
        _summarization_tasks[task_id]["message"] = "Starting summarization"

        summarizer = NewsletterSummarizer()
        total = len(newsletter_ids)

        for i, newsletter_id in enumerate(newsletter_ids):
            _summarization_tasks[task_id]["current_newsletter_id"] = newsletter_id
            _summarization_tasks[task_id]["message"] = f"Summarizing newsletter {newsletter_id}"

            try:
                success = await asyncio.to_thread(
                    summarizer.summarize_newsletter,
                    newsletter_id,
                )

                if success:
                    _summarization_tasks[task_id]["completed"] += 1
                else:
                    _summarization_tasks[task_id]["failed"] += 1

            except Exception as e:
                _summarization_tasks[task_id]["failed"] += 1
                _summarization_tasks[task_id]["message"] = f"Error: {str(e)}"

            _summarization_tasks[task_id]["processed"] = i + 1
            _summarization_tasks[task_id]["progress"] = int((i + 1) / total * 100)

        completed = _summarization_tasks[task_id]["completed"]
        failed = _summarization_tasks[task_id]["failed"]

        _summarization_tasks[task_id]["status"] = "completed"
        _summarization_tasks[task_id]["progress"] = 100
        _summarization_tasks[task_id]["message"] = (
            f"Completed: {completed} summaries created, {failed} failed"
        )
        _summarization_tasks[task_id]["current_newsletter_id"] = None

    except Exception as e:
        _summarization_tasks[task_id]["status"] = "error"
        _summarization_tasks[task_id]["message"] = str(e)


@router.get("/status/{task_id}")
async def get_summarization_status(task_id: str):
    """
    Get summarization task status via Server-Sent Events.

    Stream real-time progress updates for the summarization task.
    """
    if task_id not in _summarization_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        import json

        while True:
            if task_id not in _summarization_tasks:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Task not found'})}\n\n"
                break

            task = _summarization_tasks[task_id]
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


def _summary_to_detail(summary: NewsletterSummary) -> SummaryDetail:
    """Convert NewsletterSummary ORM object to SummaryDetail response."""
    relevance = summary.relevance_scores or {}
    return SummaryDetail(
        id=summary.id,
        newsletter_id=summary.newsletter_id,
        executive_summary=summary.executive_summary,
        key_themes=summary.key_themes or [],
        strategic_insights=summary.strategic_insights or [],
        technical_details=summary.technical_details or [],
        actionable_items=summary.actionable_items or [],
        notable_quotes=summary.notable_quotes or [],
        relevant_links=summary.relevant_links or [],
        relevance_scores=RelevanceScores(
            cto_leadership=relevance.get("cto_leadership", 0.0),
            technical_teams=relevance.get("technical_teams", 0.0),
            individual_developers=relevance.get("individual_developers", 0.0),
        ),
        agent_framework=summary.agent_framework,
        model_used=summary.model_used,
        model_version=summary.model_version,
        created_at=summary.created_at,
        token_usage=summary.token_usage,
        processing_time_seconds=summary.processing_time_seconds,
    )
