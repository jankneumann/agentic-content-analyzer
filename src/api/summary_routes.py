"""
Summary API Routes

CRUD operations and summarization endpoints for newsletter summaries.
Includes SSE endpoints for real-time progress tracking.
"""

import asyncio
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func

from src.models.newsletter import Newsletter, ProcessingStatus
from src.models.summary import NewsletterSummary
from src.storage.database import get_db
from src.utils.summary_markdown import parse_markdown_summary

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
    newsletter_publication: str | None
    executive_summary_preview: str
    key_themes: list[str]
    model_used: str
    created_at: datetime
    processing_time_seconds: float | None

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
    model_version: str | None
    created_at: datetime
    token_usage: int | None
    processing_time_seconds: float | None
    # New markdown-first fields (Phase 5)
    markdown_content: str | None = None
    theme_tags: list[str] | None = None
    # Optional parsed sections (when include_parsed_sections=True)
    parsed_sections: dict | None = None

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
    model: str | None = Field(
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


class NavigationResponse(BaseModel):
    """Navigation info for prev/next within a filtered list."""

    prev_id: int | None
    next_id: int | None
    prev_newsletter_id: int | None
    next_newsletter_id: int | None
    position: int
    total: int


class ContextSelection(BaseModel):
    """A text selection from the review interface."""

    text: str = Field(..., max_length=500)
    source: str = Field(..., pattern="^(newsletter|summary)$")


class RegenerateWithFeedbackRequest(BaseModel):
    """Request to regenerate summary with feedback."""

    feedback: str | None = Field(None, max_length=1000)
    context_selections: list[ContextSelection] | None = Field(None, max_length=5)
    preview_only: bool = Field(
        default=True,
        description="If true, returns preview without saving",
    )


class CommitPreviewRequest(BaseModel):
    """Request to commit a previewed regeneration."""

    executive_summary: str
    key_themes: list[str]
    strategic_insights: list[str]
    technical_details: list[str]
    actionable_items: list[str]
    notable_quotes: list[str]


# ============================================================================
# In-memory task storage (would use Redis in production)
# ============================================================================

_summarization_tasks: dict[str, dict] = {}


# ============================================================================
# Endpoints
# ============================================================================


@router.get("", response_model=PaginatedSummaryResponse)
async def list_summaries(
    newsletter_id: int | None = Query(None, description="Filter by newsletter"),
    model_used: str | None = Query(None, description="Filter by model"),
    start_date: datetime | None = Query(None, description="Filter after this date"),
    end_date: datetime | None = Query(None, description="Filter before this date"),
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
            query.order_by(NewsletterSummary.created_at.desc()).offset(offset).limit(limit).all()
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
        avg_time_result = db.query(func.avg(NewsletterSummary.processing_time_seconds)).scalar()
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
async def get_summary_by_newsletter(
    newsletter_id: int,
    include_parsed_sections: bool = Query(
        False,
        description="Include parsed sections from markdown content",
    ),
) -> SummaryDetail:
    """Get summary for a specific newsletter."""
    with get_db() as db:
        summary = (
            db.query(NewsletterSummary)
            .filter(NewsletterSummary.newsletter_id == newsletter_id)
            .first()
        )

        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found for this newsletter")

        return _summary_to_detail(summary, include_parsed_sections=include_parsed_sections)


@router.get("/{summary_id}", response_model=SummaryDetail)
async def get_summary(
    summary_id: int,
    include_parsed_sections: bool = Query(
        False,
        description="Include parsed sections from markdown content",
    ),
) -> SummaryDetail:
    """Get a single summary by ID."""
    with get_db() as db:
        summary = db.query(NewsletterSummary).filter(NewsletterSummary.id == summary_id).first()

        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found")

        return _summary_to_detail(summary, include_parsed_sections=include_parsed_sections)


@router.get("/{summary_id}/navigation", response_model=NavigationResponse)
async def get_summary_navigation(
    summary_id: int,
    model_used: str | None = Query(None, description="Filter by model"),
    start_date: datetime | None = Query(None, description="Filter after this date"),
    end_date: datetime | None = Query(None, description="Filter before this date"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
) -> NavigationResponse:
    """
    Get navigation info for prev/next item within a filtered list.

    Returns the IDs of the previous and next summaries based on the
    current filter and sort settings. This enables prev/next navigation
    in the review interface while respecting the list filters.
    """
    with get_db() as db:
        # Build base query with same filters as list view
        query = db.query(NewsletterSummary).join(Newsletter)

        if model_used:
            query = query.filter(NewsletterSummary.model_used == model_used)
        if start_date:
            query = query.filter(NewsletterSummary.created_at >= start_date)
        if end_date:
            query = query.filter(NewsletterSummary.created_at <= end_date)

        # Determine sort column and order
        sort_column = getattr(NewsletterSummary, sort_by, NewsletterSummary.created_at)
        if sort_order.lower() == "asc":
            ordered_query = query.order_by(sort_column.asc())
        else:
            ordered_query = query.order_by(sort_column.desc())

        # Get all summaries with their IDs and newsletter IDs
        all_summaries = ordered_query.all()
        summary_data = [(s.id, s.newsletter_id) for s in all_summaries]
        total = len(summary_data)

        # Find current summary position
        current_idx = next(
            (i for i, (sid, _) in enumerate(summary_data) if sid == summary_id),
            None,
        )

        if current_idx is None:
            raise HTTPException(
                status_code=404,
                detail="Summary not found in current filtered list",
            )

        # Find position and neighbors
        position = current_idx + 1  # 1-indexed
        prev_id = summary_data[current_idx - 1][0] if current_idx > 0 else None
        prev_newsletter_id = summary_data[current_idx - 1][1] if current_idx > 0 else None
        next_id = summary_data[current_idx + 1][0] if current_idx < total - 1 else None
        next_newsletter_id = summary_data[current_idx + 1][1] if current_idx < total - 1 else None

        return NavigationResponse(
            prev_id=prev_id,
            next_id=next_id,
            prev_newsletter_id=prev_newsletter_id,
            next_newsletter_id=next_newsletter_id,
            position=position,
            total=total,
        )


@router.delete("/{summary_id}")
async def delete_summary(summary_id: int):
    """Delete a summary."""
    with get_db() as db:
        summary = db.query(NewsletterSummary).filter(NewsletterSummary.id == summary_id).first()

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
                db.query(Newsletter).filter(Newsletter.id.in_(request.newsletter_ids)).all()
            )
            if not request.force:
                # Filter out already summarized
                newsletters = [n for n in newsletters if n.status != ProcessingStatus.COMPLETED]
        else:
            newsletters = (
                db.query(Newsletter).filter(Newsletter.status == ProcessingStatus.PENDING).all()
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
        summary = db.query(NewsletterSummary).filter(NewsletterSummary.id == summary_id).first()

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


@router.post("/{summary_id}/regenerate-with-feedback")
async def regenerate_with_feedback(
    summary_id: int,
    request: RegenerateWithFeedbackRequest,
) -> StreamingResponse:
    """
    Regenerate a summary with user feedback via SSE streaming.

    Uses the feedback and context selections to guide regeneration.
    If preview_only=True (default), returns the preview without saving.

    Returns SSE stream with progress and final result.
    """
    import json

    with get_db() as db:
        summary = db.query(NewsletterSummary).filter(NewsletterSummary.id == summary_id).first()
        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found")

        newsletter = db.query(Newsletter).filter(Newsletter.id == summary.newsletter_id).first()
        if not newsletter:
            raise HTTPException(status_code=404, detail="Newsletter not found")

        newsletter_id = newsletter.id

    async def generate_preview():
        """Generator for SSE streaming."""
        try:
            # Send initial status
            yield f"data: {json.dumps({'status': 'processing', 'message': 'Starting regeneration...', 'progress': 0})}\n\n"

            # Build the feedback context
            feedback_parts = []
            if request.feedback:
                feedback_parts.append(f"User feedback: {request.feedback}")

            if request.context_selections:
                for ctx in request.context_selections:
                    source_label = "newsletter" if ctx.source == "newsletter" else "summary"
                    feedback_parts.append(f'Selected from {source_label}: "{ctx.text}"')

            feedback_context = "\n".join(feedback_parts) if feedback_parts else None

            yield f"data: {json.dumps({'status': 'processing', 'message': 'Generating with feedback...', 'progress': 30})}\n\n"

            # Use the summarizer with feedback
            from src.processors.summarizer import NewsletterSummarizer

            summarizer = NewsletterSummarizer()

            # Generate new summary (in thread to not block)
            new_summary_data = await asyncio.to_thread(
                summarizer.summarize_with_feedback,
                newsletter_id,
                feedback_context,
            )

            yield f"data: {json.dumps({'status': 'processing', 'message': 'Finalizing...', 'progress': 80})}\n\n"

            if new_summary_data:
                # Return the preview data
                result = {
                    "status": "completed",
                    "progress": 100,
                    "preview": {
                        "executive_summary": new_summary_data.get("executive_summary", ""),
                        "key_themes": new_summary_data.get("key_themes", []),
                        "strategic_insights": new_summary_data.get("strategic_insights", []),
                        "technical_details": new_summary_data.get("technical_details", []),
                        "actionable_items": new_summary_data.get("actionable_items", []),
                        "notable_quotes": new_summary_data.get("notable_quotes", []),
                        "model_used": new_summary_data.get("model_used", "unknown"),
                    },
                }
                yield f"data: {json.dumps(result)}\n\n"
            else:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Failed to generate summary'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate_preview(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/{summary_id}/commit-preview", response_model=SummaryDetail)
async def commit_preview(
    summary_id: int,
    request: CommitPreviewRequest,
) -> SummaryDetail:
    """
    Commit a previewed regeneration, replacing the current summary.

    Takes the preview data and saves it as the new summary.
    """
    from src.utils.summary_markdown import (
        extract_summary_theme_tags,
        generate_summary_markdown,
    )

    with get_db() as db:
        summary = db.query(NewsletterSummary).filter(NewsletterSummary.id == summary_id).first()
        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found")

        # Update the summary with preview data
        summary.executive_summary = request.executive_summary
        summary.key_themes = request.key_themes
        summary.strategic_insights = request.strategic_insights
        summary.technical_details = request.technical_details
        summary.actionable_items = request.actionable_items
        summary.notable_quotes = request.notable_quotes

        # Regenerate markdown content and theme tags
        summary_dict = {
            "executive_summary": request.executive_summary,
            "key_themes": request.key_themes,
            "strategic_insights": request.strategic_insights,
            "technical_details": request.technical_details,
            "actionable_items": request.actionable_items,
            "notable_quotes": request.notable_quotes,
            "relevant_links": summary.relevant_links or [],
            "relevance_scores": summary.relevance_scores or {},
        }
        summary.markdown_content = generate_summary_markdown(summary_dict)
        summary.theme_tags = extract_summary_theme_tags(summary_dict)

        # Update timestamp
        summary.created_at = datetime.utcnow()

        db.commit()
        db.refresh(summary)

        return _summary_to_detail(summary)


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
                _summarization_tasks[task_id]["message"] = f"Error: {e!s}"

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


def _summary_to_detail(
    summary: NewsletterSummary,
    include_parsed_sections: bool = False,
) -> SummaryDetail:
    """Convert NewsletterSummary ORM object to SummaryDetail response.

    Args:
        summary: The NewsletterSummary ORM object
        include_parsed_sections: If True, parse markdown_content into structured sections

    Returns:
        SummaryDetail response model
    """
    relevance = summary.relevance_scores or {}

    # Parse sections from markdown if requested and markdown exists
    parsed_sections = None
    if include_parsed_sections and summary.markdown_content:
        parsed_sections = parse_markdown_summary(summary.markdown_content)

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
        markdown_content=summary.markdown_content,
        theme_tags=summary.theme_tags,
        parsed_sections=parsed_sections,
    )
