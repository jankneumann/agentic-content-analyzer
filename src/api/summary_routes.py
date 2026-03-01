"""
Summary API Routes

CRUD operations for content summaries.
All summaries are now linked to Content records (unified model).
"""

import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func

from src.models.content import Content, ContentStatus
from src.models.summary import Summary
from src.storage.database import get_db
from src.utils.logging import get_logger
from src.utils.summary_markdown import parse_markdown_summary

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/summaries", tags=["summaries"])

# Allowed fields for sorting
SUMMARY_SORT_FIELDS = {"id", "content_id", "model_used", "created_at"}


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
    content_id: int
    title: str
    publication: str | None
    executive_summary_preview: str
    key_themes: list[str]
    model_used: str
    created_at: datetime
    processing_time_seconds: float | None

    model_config = ConfigDict(from_attributes=True)


class SummaryDetail(BaseModel):
    """Full summary details."""

    id: int
    content_id: int
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
    # Markdown-first fields
    markdown_content: str | None = None
    theme_tags: list[str] | None = None
    # Optional parsed sections (when include_parsed_sections=True)
    parsed_sections: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedSummaryResponse(BaseModel):
    """Paginated summary list response."""

    items: list[SummaryListItem]
    total: int
    offset: int
    limit: int
    has_more: bool


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
    prev_content_id: int | None
    next_content_id: int | None
    position: int
    total: int


class ContextSelection(BaseModel):
    """A text selection from the review interface."""

    text: str = Field(..., max_length=500)
    source: str = Field(..., pattern="^(content|summary)$")


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
# Endpoints
# ============================================================================


@router.get("", response_model=PaginatedSummaryResponse)
async def list_summaries(
    content_id: int | None = Query(None, description="Filter by content"),
    model_used: str | None = Query(None, description="Filter by model"),
    start_date: datetime | None = Query(None, description="Filter after this date"),
    end_date: datetime | None = Query(None, description="Filter before this date"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PaginatedSummaryResponse:
    """
    List summaries with optional filters.

    Results are paginated and sorted by creation date (newest first).
    """
    with get_db() as db:
        # Join with Content to get title/publication
        # OPTIMIZATION: Select specific columns to avoid loading heavy JSON/Text fields
        # and full ORM objects. Also fetch only a substring of executive_summary.
        query = db.query(
            Summary.id,
            Summary.content_id,
            Summary.key_themes,
            Summary.model_used,
            Summary.created_at,
            Summary.processing_time_seconds,
            func.substr(Summary.executive_summary, 1, 203).label("executive_summary_preview"),
            Content.title,
            Content.publication,
        ).join(Content, Summary.content_id == Content.id)

        # Apply filters
        if content_id:
            query = query.filter(Summary.content_id == content_id)
        if model_used:
            query = query.filter(Summary.model_used == model_used)
        if start_date:
            query = query.filter(Summary.created_at >= start_date)
        if end_date:
            query = query.filter(Summary.created_at <= end_date)

        # Get total count
        total = query.count()

        # Validate and apply dynamic sorting
        if sort_by not in SUMMARY_SORT_FIELDS:
            sort_by = "created_at"

        sort_column = getattr(Summary, sort_by, Summary.created_at)
        if sort_order.lower() == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        # Apply pagination
        summaries = query.offset(offset).limit(limit).all()

        # Convert to response models
        items = []
        for row in summaries:
            # Unpack the row (named tuple-like)
            (
                s_id,
                s_content_id,
                s_key_themes,
                s_model_used,
                s_created_at,
                s_processing_time,
                s_exec_preview,
                c_title,
                c_publication,
            ) = row

            # Handle preview truncation
            preview_text = s_exec_preview or ""
            if len(preview_text) > 200:
                preview_text = preview_text[:200] + "..."

            items.append(
                SummaryListItem(
                    id=s_id,
                    content_id=s_content_id,
                    title=c_title,
                    publication=c_publication,
                    executive_summary_preview=preview_text,
                    key_themes=s_key_themes or [],
                    model_used=s_model_used,
                    created_at=s_created_at,
                    processing_time_seconds=s_processing_time,
                )
            )

        return PaginatedSummaryResponse(
            items=items,
            total=total,
            offset=offset,
            limit=limit,
            has_more=(offset + limit) < total,
        )


@router.get("/stats", response_model=SummaryStats)
async def get_summary_stats() -> SummaryStats:
    """Get summary statistics (only content-linked summaries)."""
    with get_db() as db:
        # Count by model (only content-linked)
        model_counts = (
            db.query(Summary.model_used, func.count(Summary.id))
            .filter(Summary.content_id.isnot(None))
            .group_by(Summary.model_used)
            .all()
        )
        by_model = {model: count for model, count in model_counts}

        # OPTIMIZATION: Calculate total from model counts instead of separate count query
        # Since model_used is non-nullable, the sum of counts equals the total count
        total = sum(by_model.values())

        # Average processing time (only content-linked)
        avg_time_result = (
            db.query(func.avg(Summary.processing_time_seconds))
            .filter(Summary.content_id.isnot(None))
            .scalar()
        )
        avg_processing_time = float(avg_time_result) if avg_time_result else 0.0

        # Average token usage (only content-linked)
        avg_tokens_result = (
            db.query(func.avg(Summary.token_usage)).filter(Summary.content_id.isnot(None)).scalar()
        )
        avg_token_usage = float(avg_tokens_result) if avg_tokens_result else 0.0

        return SummaryStats(
            total=total,
            by_model=by_model,
            avg_processing_time=avg_processing_time,
            avg_token_usage=avg_token_usage,
        )


@router.get("/by-content/{content_id}", response_model=SummaryDetail)
async def get_summary_by_content(
    content_id: int,
    include_parsed_sections: bool = Query(
        False,
        description="Include parsed sections from markdown content",
    ),
) -> SummaryDetail:
    """Get summary for a specific content."""
    with get_db() as db:
        summary = db.query(Summary).filter(Summary.content_id == content_id).first()

        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found for this content")

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
        summary = db.query(Summary).filter(Summary.id == summary_id).first()

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
    current filter and sort settings.
    """
    with get_db() as db:
        # Build base query with Content join
        # OPTIMIZATION: Only fetch IDs to avoid loading full Summary objects for navigation
        query = db.query(Summary.id, Summary.content_id).join(Content)

        if model_used:
            query = query.filter(Summary.model_used == model_used)
        if start_date:
            query = query.filter(Summary.created_at >= start_date)
        if end_date:
            query = query.filter(Summary.created_at <= end_date)

        # Determine sort column and order
        sort_column = getattr(Summary, sort_by, Summary.created_at)
        if sort_order.lower() == "asc":
            ordered_query = query.order_by(sort_column.asc())
        else:
            ordered_query = query.order_by(sort_column.desc())

        # Get all summaries with their IDs and content IDs
        all_summaries = ordered_query.all()
        summary_data = [(s.id, s.content_id) for s in all_summaries]
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
        prev_content_id = summary_data[current_idx - 1][1] if current_idx > 0 else None
        next_id = summary_data[current_idx + 1][0] if current_idx < total - 1 else None
        next_content_id = summary_data[current_idx + 1][1] if current_idx < total - 1 else None

        return NavigationResponse(
            prev_id=prev_id,
            next_id=next_id,
            prev_content_id=prev_content_id,
            next_content_id=next_content_id,
            position=position,
            total=total,
        )


@router.delete("/{summary_id}")
async def delete_summary(summary_id: int):
    """Delete a summary and reset content status."""
    with get_db() as db:
        summary = db.query(Summary).filter(Summary.id == summary_id).first()

        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found")

        # Reset content status to allow re-summarization
        if summary.content_id:
            content = db.query(Content).filter(Content.id == summary.content_id).first()
            if content:
                content.status = ContentStatus.PARSED
                content.processed_at = None

        db.delete(summary)
        db.commit()

        return {"message": "Summary deleted", "id": summary_id}


@router.post("/{summary_id}/regenerate")
async def regenerate_summary(summary_id: int):
    """
    Regenerate an existing summary.

    Deletes the current summary and resets content status for re-summarization.
    Use /api/v1/contents/summarize to trigger the actual summarization.
    """
    with get_db() as db:
        summary = db.query(Summary).filter(Summary.id == summary_id).first()

        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found")

        content_id = summary.content_id

        # Delete existing summary
        db.delete(summary)

        # Reset content status
        if content_id:
            content = db.query(Content).filter(Content.id == content_id).first()
            if content:
                content.status = ContentStatus.PARSED
                content.processed_at = None

        db.commit()

    return {
        "message": "Summary deleted, content ready for re-summarization",
        "content_id": content_id,
    }


@router.post("/{summary_id}/regenerate-with-feedback")
async def regenerate_with_feedback(
    summary_id: int,
    request: RegenerateWithFeedbackRequest,
) -> StreamingResponse:
    """
    Regenerate a summary with user feedback via SSE streaming.

    Uses the feedback and context selections to guide regeneration.
    """
    import json

    with get_db() as db:
        summary = db.query(Summary).filter(Summary.id == summary_id).first()
        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found")

        content = db.query(Content).filter(Content.id == summary.content_id).first()
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")

        content_id = content.id

    async def generate_preview():
        """Generator for SSE streaming."""
        try:
            yield f"data: {json.dumps({'status': 'processing', 'message': 'Starting regeneration...', 'progress': 0})}\n\n"

            # Build the feedback context
            feedback_parts = []
            if request.feedback:
                feedback_parts.append(f"User feedback: {request.feedback}")

            if request.context_selections:
                for ctx in request.context_selections:
                    source_label = "content" if ctx.source == "content" else "summary"
                    feedback_parts.append(f'Selected from {source_label}: "{ctx.text}"')

            feedback_context = "\n".join(feedback_parts) if feedback_parts else None

            yield f"data: {json.dumps({'status': 'processing', 'message': 'Generating with feedback...', 'progress': 30})}\n\n"

            from src.processors.summarizer import NewsletterSummarizer

            summarizer = NewsletterSummarizer()

            # Generate new summary using content
            new_summary_data = await asyncio.to_thread(
                summarizer.summarize_content_with_feedback,
                content_id,
                feedback_context,
            )

            yield f"data: {json.dumps({'status': 'processing', 'message': 'Finalizing...', 'progress': 80})}\n\n"

            if new_summary_data:
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
            logger.error(f"Error regenerating summary: {e}", exc_info=True)
            yield f"data: {json.dumps({'status': 'error', 'message': 'An internal error occurred during regeneration.'})}\n\n"

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
    """
    from src.utils.summary_markdown import (
        extract_summary_theme_tags,
        generate_summary_markdown,
    )

    with get_db() as db:
        summary = db.query(Summary).filter(Summary.id == summary_id).first()
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


def _summary_to_detail(
    summary: Summary,
    include_parsed_sections: bool = False,
) -> SummaryDetail:
    """Convert Summary ORM object to SummaryDetail response."""
    relevance = summary.relevance_scores or {}

    # Parse sections from markdown if requested and markdown exists
    parsed_sections = None
    if include_parsed_sections and summary.markdown_content:
        parsed_sections = parse_markdown_summary(summary.markdown_content)

    return SummaryDetail(
        id=summary.id,
        content_id=summary.content_id,
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
