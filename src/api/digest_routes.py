"""API endpoints for digest management and review.

Provides REST endpoints for:
- Digest listing with filters
- Digest detail retrieval
- Digest generation (daily/weekly)
- Review workflow (approve/reject/revise)
- Section-level revision
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.dependencies import verify_admin_key
from src.models.digest import (
    Digest,
    DigestRequest,
    DigestStatus,
    DigestType,
)
from src.models.query import ContentQuery
from src.processors.digest_creator import DigestCreator
from src.storage.database import get_db
from src.utils.digest_markdown import parse_markdown_digest
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/digests",
    tags=["digests"],
    dependencies=[Depends(verify_admin_key)],
)

# Allowed fields for sorting digests
DIGEST_SORT_FIELDS = {"id", "digest_type", "status", "created_at", "period_start", "period_end"}


# --- Request/Response Models ---


class GenerateDigestRequest(BaseModel):
    """Request to generate a new digest."""

    digest_type: str = Field(..., description="Type of digest: 'daily' or 'weekly'")
    period_start: datetime | None = Field(
        None, description="Start of period (defaults based on type)"
    )
    period_end: datetime | None = Field(None, description="End of period (defaults to now)")
    max_strategic_insights: int = Field(default=5)
    max_technical_developments: int = Field(default=5)
    max_emerging_trends: int = Field(default=3)
    include_historical_context: bool = Field(default=True)
    content_query: "ContentQuery | None" = Field(
        default=None, description="Optional content selection override"
    )
    dry_run: bool = Field(default=False, description="Return preview without generating digest")


class DigestSummary(BaseModel):
    """Summary of a digest for listing."""

    id: int
    digest_type: str
    title: str
    period_start: str
    period_end: str
    newsletter_count: int
    status: str
    created_at: str
    model_used: str
    revision_count: int
    reviewed_by: str | None = None


class DigestSectionResponse(BaseModel):
    """A section within a digest."""

    title: str
    summary: str
    details: list[str]
    themes: list[str]
    continuity: str | None = None


class DigestDetail(BaseModel):
    """Full digest detail for viewing."""

    id: int
    digest_type: str
    title: str
    period_start: str
    period_end: str
    executive_overview: str
    strategic_insights: list[DigestSectionResponse]
    technical_developments: list[DigestSectionResponse]
    emerging_trends: list[DigestSectionResponse]
    actionable_recommendations: dict
    sources: list[dict]
    newsletter_count: int
    status: str
    created_at: str
    completed_at: str | None = None
    model_used: str
    model_version: str | None = None
    processing_time_seconds: int | None = None
    revision_count: int
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    review_notes: str | None = None
    is_combined: bool = False
    child_digest_ids: list[int] | None = None
    # New markdown-first fields (Phase 5)
    markdown_content: str | None = None
    theme_tags: list[str] | None = None
    source_content_ids: list[int] | None = None
    # Optional parsed sections (when include_parsed_sections=True)
    parsed_sections: dict | None = None


class DigestStatistics(BaseModel):
    """Statistics about digests."""

    total: int
    pending: int
    generating: int
    completed: int
    pending_review: int
    approved: int
    delivered: int
    by_type: dict


class ReviewRequest(BaseModel):
    """Request to submit a review."""

    action: str = Field(..., description="Review action: approve, reject, or request_revision")
    reviewer: str = Field(..., description="Reviewer identifier")
    notes: str | None = Field(None, description="Review notes")
    section_feedback: dict | None = Field(
        default_factory=dict,
        description="Section-specific feedback (key = section type, value = feedback)",
    )


class SectionRevisionRequest(BaseModel):
    """Request to revise a specific section."""

    feedback: str = Field(..., description="Feedback for revision")


# --- Background Tasks ---


async def regenerate_digest_task(digest_id: int) -> None:
    """Background task for digest regeneration."""
    logger.info(f"Starting background digest regeneration for ID: {digest_id}")

    # Fetch existing digest
    with get_db() as db:
        digest_record = db.query(Digest).filter(Digest.id == digest_id).first()
        if not digest_record:
            logger.error(f"Digest {digest_id} not found for regeneration")
            return

        # Update status
        digest_record.status = DigestStatus.GENERATING
        digest_record.title = f"Regenerating {digest_record.digest_type.value} digest..."
        db.commit()

        # Create request from existing digest data
        request = DigestRequest(
            digest_type=digest_record.digest_type,
            period_start=digest_record.period_start,
            period_end=digest_record.period_end,
            include_historical_context=True,  # Default to True for now
        )

    try:
        # Generate digest
        creator = DigestCreator()
        digest_data = await creator.create_digest(request)

        # Update record with generated content
        with get_db() as db:
            digest_record = db.query(Digest).filter(Digest.id == digest_id).first()

            # Convert DigestSection objects to dicts
            digest_record.title = digest_data.title
            digest_record.executive_overview = digest_data.executive_overview
            digest_record.strategic_insights = [
                s.model_dump() for s in digest_data.strategic_insights
            ]
            digest_record.technical_developments = [
                s.model_dump() for s in digest_data.technical_developments
            ]
            digest_record.emerging_trends = [s.model_dump() for s in digest_data.emerging_trends]
            digest_record.actionable_recommendations = digest_data.actionable_recommendations
            digest_record.sources = digest_data.sources
            digest_record.newsletter_count = digest_data.newsletter_count
            digest_record.status = DigestStatus.PENDING_REVIEW
            digest_record.completed_at = datetime.utcnow()
            digest_record.agent_framework = digest_data.agent_framework
            digest_record.model_used = digest_data.model_used
            digest_record.model_version = digest_data.model_version
            digest_record.processing_time_seconds = (
                int(digest_data.processing_time_seconds)
                if digest_data.processing_time_seconds
                else None
            )
            digest_record.is_combined = 1 if digest_data.is_combined else 0
            digest_record.child_digest_ids = digest_data.child_digest_ids
            # New markdown-first fields (Phase 5)
            digest_record.markdown_content = digest_data.markdown_content
            digest_record.theme_tags = digest_data.theme_tags
            digest_record.source_content_ids = digest_data.source_content_ids
            digest_record.revision_count = (digest_record.revision_count or 0) + 1

            db.commit()

        logger.info(f"Digest {digest_id} regenerated successfully")

    except Exception as e:
        logger.error(f"Digest regeneration failed: {e}", exc_info=True)
        with get_db() as db:
            digest_record = db.query(Digest).filter(Digest.id == digest_id).first()
            if digest_record:
                digest_record.status = DigestStatus.FAILED
                digest_record.review_notes = (
                    "An internal error occurred during digest regeneration."
                )
                db.commit()


async def generate_digest_task(request: DigestRequest) -> None:
    """Background task for digest generation."""
    logger.info(
        f"Starting background digest generation: {request.digest_type.value} "
        f"from {request.period_start} to {request.period_end}"
    )

    # Create initial record
    with get_db() as db:
        digest_record = Digest(
            digest_type=request.digest_type,
            period_start=request.period_start,
            period_end=request.period_end,
            title=f"Generating {request.digest_type.value} digest...",
            executive_overview="",
            strategic_insights=[],
            technical_developments=[],
            emerging_trends=[],
            actionable_recommendations={},
            sources=[],
            newsletter_count=0,
            status=DigestStatus.GENERATING,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )
        db.add(digest_record)
        db.commit()
        db.refresh(digest_record)
        digest_id = digest_record.id

    try:
        # Generate digest
        creator = DigestCreator()
        digest_data = await creator.create_digest(request)

        # Update record with generated content
        with get_db() as db:
            digest_record = db.query(Digest).filter(Digest.id == digest_id).first()

            # Convert DigestSection objects to dicts
            digest_record.title = digest_data.title
            digest_record.executive_overview = digest_data.executive_overview
            digest_record.strategic_insights = [
                s.model_dump() for s in digest_data.strategic_insights
            ]
            digest_record.technical_developments = [
                s.model_dump() for s in digest_data.technical_developments
            ]
            digest_record.emerging_trends = [s.model_dump() for s in digest_data.emerging_trends]
            digest_record.actionable_recommendations = digest_data.actionable_recommendations
            digest_record.sources = digest_data.sources
            digest_record.newsletter_count = digest_data.newsletter_count
            digest_record.status = DigestStatus.PENDING_REVIEW
            digest_record.completed_at = datetime.utcnow()
            digest_record.agent_framework = digest_data.agent_framework
            digest_record.model_used = digest_data.model_used
            digest_record.model_version = digest_data.model_version
            digest_record.processing_time_seconds = (
                int(digest_data.processing_time_seconds)
                if digest_data.processing_time_seconds
                else None
            )
            digest_record.is_combined = 1 if digest_data.is_combined else 0
            digest_record.child_digest_ids = digest_data.child_digest_ids
            # New markdown-first fields (Phase 5)
            digest_record.markdown_content = digest_data.markdown_content
            digest_record.theme_tags = digest_data.theme_tags
            digest_record.source_content_ids = digest_data.source_content_ids

            db.commit()

        logger.info(f"Digest {digest_id} generated successfully")

    except Exception as e:
        logger.error(f"Digest generation failed: {e}", exc_info=True)
        with get_db() as db:
            digest_record = db.query(Digest).filter(Digest.id == digest_id).first()
            digest_record.status = DigestStatus.FAILED
            digest_record.review_notes = "An internal error occurred during digest generation."
            db.commit()


# --- Endpoints ---


@router.post("/generate", response_model=dict)
async def generate_digest(
    request: GenerateDigestRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Generate a new digest (daily or weekly).

    Starts digest generation in background and returns immediately.
    When dry_run is true, returns a preview of matching content without generating.
    Poll GET /digests/{digest_id} for status.
    """
    logger.info(f"Received digest generation request: {request.digest_type}")

    # Validate digest type
    try:
        digest_type = DigestType(request.digest_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid digest type. Must be 'daily' or 'weekly'",
        )

    # Calculate default period based on type
    now = datetime.utcnow()
    if request.period_end is None:
        period_end = now
    else:
        period_end = request.period_end

    if request.period_start is None:
        if digest_type == DigestType.DAILY:
            period_start = period_end - timedelta(days=1)
        else:  # WEEKLY
            period_start = period_end - timedelta(days=7)
    else:
        period_start = request.period_start

    # Handle dry_run: return preview without generating
    if request.dry_run:
        from src.models.content import ContentStatus
        from src.models.query import ContentQuery
        from src.services.content_query import ContentQueryService

        query = request.content_query or ContentQuery()
        if not query.start_date:
            query = query.model_copy(update={"start_date": period_start})
        if not query.end_date:
            query = query.model_copy(update={"end_date": period_end})
        if not query.statuses:
            query = query.model_copy(update={"statuses": [ContentStatus.COMPLETED]})

        svc = ContentQueryService()
        return svc.preview(query).model_dump(mode="json")

    # Create digest request
    digest_request = DigestRequest(
        digest_type=digest_type,
        period_start=period_start,
        period_end=period_end,
        max_strategic_insights=request.max_strategic_insights,
        max_technical_developments=request.max_technical_developments,
        max_emerging_trends=request.max_emerging_trends,
        include_historical_context=request.include_historical_context,
        content_query=request.content_query,
    )

    # Queue background task
    background_tasks.add_task(generate_digest_task, digest_request)

    return {
        "status": "queued",
        "message": f"{digest_type.value.title()} digest generation started",
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
    }


@router.post("/{digest_id}/regenerate", response_model=dict)
async def regenerate_digest(
    digest_id: int,
    background_tasks: BackgroundTasks,
) -> dict:
    """Regenerate an existing digest.

    Starts digest regeneration in background and returns immediately.
    This re-runs the full generation process for the existing digest ID.
    Poll GET /digests/{digest_id} for status.
    """
    logger.info(f"Received digest regeneration request for ID: {digest_id}")

    with get_db() as db:
        digest = db.query(Digest).filter(Digest.id == digest_id).first()
        if not digest:
            raise HTTPException(status_code=404, detail="Digest not found")

        if digest.status == DigestStatus.GENERATING:
            raise HTTPException(
                status_code=400,
                detail="Digest is already generating",
            )

        # Set status to generating immediately
        digest.status = DigestStatus.GENERATING
        db.commit()

    # Queue background task
    background_tasks.add_task(regenerate_digest_task, digest_id)

    return {
        "status": "queued",
        "message": "Digest regeneration started",
        "digest_id": digest_id,
    }


@router.get("/", response_model=list[DigestSummary])
async def list_digests(
    status: str | None = Query(None, description="Filter by status"),
    digest_type: str | None = Query(None, description="Filter by type"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
) -> list[DigestSummary]:
    """List digests with optional filtering."""
    with get_db() as db:
        query = db.query(Digest)

        # Only show daily and weekly digests (exclude sub-digests if they exist)
        query = query.filter(Digest.digest_type.in_([DigestType.DAILY, DigestType.WEEKLY]))

        if status:
            try:
                status_enum = DigestStatus(status)
                query = query.filter(Digest.status == status_enum)
            except ValueError:
                pass  # Invalid status, ignore filter

        if digest_type:
            try:
                type_enum = DigestType(digest_type)
                query = query.filter(Digest.digest_type == type_enum)
            except ValueError:
                pass  # Invalid type, ignore filter

        # Apply dynamic sorting
        if sort_by not in DIGEST_SORT_FIELDS:
            sort_by = "created_at"

        sort_column = getattr(Digest, sort_by, Digest.created_at)
        if sort_order.lower() == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        digests = query.offset(offset).limit(limit).all()

        return [
            DigestSummary(
                id=d.id,
                digest_type=d.digest_type.value if d.digest_type else "unknown",
                title=d.title,
                period_start=d.period_start.isoformat() if d.period_start else "",
                period_end=d.period_end.isoformat() if d.period_end else "",
                newsletter_count=d.newsletter_count or 0,
                status=d.status.value if d.status else "unknown",
                created_at=d.created_at.isoformat() if d.created_at else "",
                model_used=d.model_used or "",
                revision_count=d.revision_count or 0,
                reviewed_by=d.reviewed_by,
            )
            for d in digests
        ]


@router.get("/statistics", response_model=DigestStatistics)
async def get_digest_statistics() -> DigestStatistics:
    """Get statistics about digests."""
    with get_db() as db:
        # Only count daily and weekly digests
        main_types = [DigestType.DAILY, DigestType.WEEKLY]
        total = db.query(Digest).filter(Digest.digest_type.in_(main_types)).count()

        def count_by_status(status: DigestStatus) -> int:
            return (
                db.query(Digest)
                .filter(Digest.status == status)
                .filter(Digest.digest_type.in_(main_types))
                .count()
            )

        # Count by type
        by_type = {}
        for dtype in [DigestType.DAILY, DigestType.WEEKLY]:
            by_type[dtype.value] = db.query(Digest).filter(Digest.digest_type == dtype).count()

        return DigestStatistics(
            total=total,
            pending=count_by_status(DigestStatus.PENDING),
            generating=count_by_status(DigestStatus.GENERATING),
            completed=count_by_status(DigestStatus.COMPLETED),
            pending_review=count_by_status(DigestStatus.PENDING_REVIEW),
            approved=count_by_status(DigestStatus.APPROVED),
            delivered=count_by_status(DigestStatus.DELIVERED),
            by_type=by_type,
        )


@router.get("/{digest_id}", response_model=DigestDetail)
async def get_digest(
    digest_id: int,
    include_parsed_sections: bool = Query(
        False,
        description="Include parsed sections from markdown content",
    ),
) -> DigestDetail:
    """Get full digest details."""
    with get_db() as db:
        digest = db.query(Digest).filter(Digest.id == digest_id).first()

        if not digest:
            raise HTTPException(status_code=404, detail="Digest not found")

        # Convert JSON sections to response models
        def parse_sections_json(sections_json: list) -> list[DigestSectionResponse]:
            if not sections_json:
                return []
            return [
                DigestSectionResponse(
                    title=s.get("title", ""),
                    summary=s.get("summary", ""),
                    details=s.get("details", []),
                    themes=s.get("themes", []),
                    continuity=s.get("continuity"),
                )
                for s in sections_json
            ]

        # Parse sections from markdown if requested and markdown exists
        parsed_sections = None
        if include_parsed_sections and digest.markdown_content:
            parsed_sections = parse_markdown_digest(digest.markdown_content)

        return DigestDetail(
            id=digest.id,
            digest_type=digest.digest_type.value if digest.digest_type else "unknown",
            title=digest.title,
            period_start=digest.period_start.isoformat() if digest.period_start else "",
            period_end=digest.period_end.isoformat() if digest.period_end else "",
            executive_overview=digest.executive_overview or "",
            strategic_insights=parse_sections_json(digest.strategic_insights),
            technical_developments=parse_sections_json(digest.technical_developments),
            emerging_trends=parse_sections_json(digest.emerging_trends),
            actionable_recommendations=digest.actionable_recommendations or {},
            sources=digest.sources or [],
            newsletter_count=digest.newsletter_count or 0,
            status=digest.status.value if digest.status else "unknown",
            created_at=digest.created_at.isoformat() if digest.created_at else "",
            completed_at=digest.completed_at.isoformat() if digest.completed_at else None,
            model_used=digest.model_used or "",
            model_version=digest.model_version,
            processing_time_seconds=digest.processing_time_seconds,
            revision_count=digest.revision_count or 0,
            reviewed_by=digest.reviewed_by,
            reviewed_at=digest.reviewed_at.isoformat() if digest.reviewed_at else None,
            review_notes=digest.review_notes,
            is_combined=bool(digest.is_combined),
            child_digest_ids=digest.child_digest_ids,
            markdown_content=digest.markdown_content,
            theme_tags=digest.theme_tags,
            source_content_ids=digest.source_content_ids,
            parsed_sections=parsed_sections,
        )


@router.get("/{digest_id}/sources")
async def get_digest_sources(
    digest_id: int,
    limit: int = Query(100, ge=1, le=200, description="Maximum results"),
) -> list[dict]:
    """Get all source summaries used to create a digest.

    Returns full summaries from content within the digest's period.
    """
    from src.models.content import Content
    from src.models.summary import Summary

    with get_db() as db:
        digest = db.query(Digest).filter(Digest.id == digest_id).first()

        if not digest:
            raise HTTPException(status_code=404, detail="Digest not found")

        results = []

        # Strategy 1: Use source_content_ids if available (new flow)
        if digest.source_content_ids:
            content_summaries = (
                db.query(Summary)
                .join(Content, Summary.content_id == Content.id)
                .filter(Summary.content_id.in_(digest.source_content_ids))
                .order_by(Content.published_date.desc())
                .limit(limit)
                .all()
            )
            for s in content_summaries:
                results.append(
                    {
                        "id": s.id,
                        "content_id": s.content_id,
                        "newsletter_title": s.content.title if s.content else "Unknown",
                        "newsletter_publication": s.content.publication if s.content else None,
                        "executive_summary": s.executive_summary,
                        "key_themes": s.key_themes or [],
                        "strategic_insights": s.strategic_insights or [],
                        "technical_details": s.technical_details or [],
                        "actionable_items": s.actionable_items or [],
                        "notable_quotes": s.notable_quotes or [],
                        "model_used": s.model_used,
                        "created_at": s.created_at.isoformat() if s.created_at else None,
                        "processing_time_seconds": s.processing_time_seconds,
                    }
                )

        # Strategy 2: Query Content by period (if no explicit source_content_ids)
        if not results and digest.period_start and digest.period_end:
            content_summaries = (
                db.query(Summary)
                .join(Content, Summary.content_id == Content.id)
                .filter(Content.published_date >= digest.period_start)
                .filter(Content.published_date <= digest.period_end)
                .order_by(Content.published_date.desc())
                .limit(limit)
                .all()
            )
            for s in content_summaries:
                results.append(
                    {
                        "id": s.id,
                        "content_id": s.content_id,
                        "newsletter_title": s.content.title if s.content else "Unknown",
                        "newsletter_publication": s.content.publication if s.content else None,
                        "executive_summary": s.executive_summary,
                        "key_themes": s.key_themes or [],
                        "strategic_insights": s.strategic_insights or [],
                        "technical_details": s.technical_details or [],
                        "actionable_items": s.actionable_items or [],
                        "notable_quotes": s.notable_quotes or [],
                        "model_used": s.model_used,
                        "created_at": s.created_at.isoformat() if s.created_at else None,
                        "processing_time_seconds": s.processing_time_seconds,
                    }
                )

        return results


@router.get("/{digest_id}/navigation")
async def get_digest_navigation(
    digest_id: int,
    status: str | None = Query(None, description="Filter by status"),
    digest_type: str | None = Query(None, description="Filter by type"),
) -> dict:
    """Get navigation info for prev/next digest within a filtered list."""
    with get_db() as db:
        # OPTIMIZATION: explicitly select only Digest.id instead of fetching full
        # ORM objects. This prevents hydrating large text/JSON columns into memory,
        # avoiding O(N) memory allocation and excess database I/O for navigation.
        query = db.query(Digest.id)
        query = query.filter(Digest.digest_type.in_([DigestType.DAILY, DigestType.WEEKLY]))

        if status:
            try:
                status_enum = DigestStatus(status)
                query = query.filter(Digest.status == status_enum)
            except ValueError:
                pass

        if digest_type:
            try:
                type_enum = DigestType(digest_type)
                query = query.filter(Digest.digest_type == type_enum)
            except ValueError:
                pass

        # Order by created_at descending (matching list view)
        ordered_query = query.order_by(Digest.created_at.desc())
        all_digests = ordered_query.all()
        digest_ids = [d[0] for d in all_digests]
        total = len(digest_ids)

        # Find current position
        try:
            current_idx = digest_ids.index(digest_id)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail="Digest not found in current filtered list",
            )

        # Find neighbors
        position = current_idx + 1
        prev_id = digest_ids[current_idx - 1] if current_idx > 0 else None
        next_id = digest_ids[current_idx + 1] if current_idx < total - 1 else None

        return {
            "prev_id": prev_id,
            "next_id": next_id,
            "position": position,
            "total": total,
        }


@router.post("/{digest_id}/review")
async def submit_review(
    digest_id: int,
    request: ReviewRequest,
) -> dict:
    """Submit a review for a digest.

    Actions:
    - approve: Mark digest as approved for delivery
    - reject: Mark digest as rejected
    - request_revision: Mark for revision with feedback
    """
    with get_db() as db:
        digest = db.query(Digest).filter(Digest.id == digest_id).first()

        if not digest:
            raise HTTPException(status_code=404, detail="Digest not found")

        if request.action == "approve":
            digest.status = DigestStatus.APPROVED
        elif request.action == "reject":
            digest.status = DigestStatus.REJECTED
        elif request.action == "request_revision":
            digest.status = DigestStatus.PENDING_REVIEW
            digest.revision_count = (digest.revision_count or 0) + 1
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid action. Must be 'approve', 'reject', or 'request_revision'",
            )

        digest.reviewed_by = request.reviewer
        digest.reviewed_at = datetime.utcnow()
        digest.review_notes = request.notes

        # Store section feedback in revision history
        if request.section_feedback:
            revision_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "reviewer": request.reviewer,
                "action": request.action,
                "section_feedback": request.section_feedback,
            }
            if digest.revision_history:
                digest.revision_history.append(revision_entry)
            else:
                digest.revision_history = [revision_entry]

        db.commit()

        return {
            "digest_id": digest.id,
            "status": digest.status.value,
            "reviewed_by": digest.reviewed_by,
            "reviewed_at": digest.reviewed_at.isoformat(),
        }


@router.post("/{digest_id}/approve")
async def quick_approve(
    digest_id: int,
    reviewer: str = Query(..., description="Reviewer identifier"),
    notes: str | None = Query(None, description="Approval notes"),
) -> dict:
    """Quick approve a digest for delivery."""
    with get_db() as db:
        digest = db.query(Digest).filter(Digest.id == digest_id).first()

        if not digest:
            raise HTTPException(status_code=404, detail="Digest not found")

        digest.status = DigestStatus.APPROVED
        digest.reviewed_by = reviewer
        digest.reviewed_at = datetime.utcnow()
        if notes:
            digest.review_notes = notes

        db.commit()

        return {
            "digest_id": digest.id,
            "status": digest.status.value,
            "approved_at": digest.reviewed_at.isoformat(),
        }


@router.post("/{digest_id}/reject")
async def quick_reject(
    digest_id: int,
    reviewer: str = Query(..., description="Reviewer identifier"),
    reason: str = Query(..., description="Rejection reason"),
) -> dict:
    """Quick reject a digest."""
    with get_db() as db:
        digest = db.query(Digest).filter(Digest.id == digest_id).first()

        if not digest:
            raise HTTPException(status_code=404, detail="Digest not found")

        digest.status = DigestStatus.REJECTED
        digest.reviewed_by = reviewer
        digest.reviewed_at = datetime.utcnow()
        digest.review_notes = reason

        db.commit()

        return {
            "digest_id": digest.id,
            "status": digest.status.value,
        }


@router.get("/{digest_id}/sections/{section_type}")
async def get_digest_section(
    digest_id: int,
    section_type: str,
) -> dict:
    """Get a specific section type from a digest.

    Section types: strategic_insights, technical_developments, emerging_trends
    """
    with get_db() as db:
        digest = db.query(Digest).filter(Digest.id == digest_id).first()

        if not digest:
            raise HTTPException(status_code=404, detail="Digest not found")

        section_map = {
            "strategic_insights": digest.strategic_insights,
            "technical_developments": digest.technical_developments,
            "emerging_trends": digest.emerging_trends,
        }

        if section_type not in section_map:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid section type. Must be one of: {list(section_map.keys())}",
            )

        sections = section_map[section_type] or []

        return {
            "digest_id": digest_id,
            "section_type": section_type,
            "sections": sections,
            "count": len(sections),
        }


@router.post("/{digest_id}/sections/{section_type}/{section_index}/revise")
async def revise_section(
    digest_id: int,
    section_type: str,
    section_index: int,
    request: SectionRevisionRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Revise a specific section based on feedback.

    The AI will regenerate the section based on the feedback
    while maintaining the overall digest context.
    """
    # For now, just acknowledge the request - full revision requires
    # integration with digest_reviser.py processor
    with get_db() as db:
        digest = db.query(Digest).filter(Digest.id == digest_id).first()

        if not digest:
            raise HTTPException(status_code=404, detail="Digest not found")

        section_map = {
            "strategic_insights": digest.strategic_insights,
            "technical_developments": digest.technical_developments,
            "emerging_trends": digest.emerging_trends,
        }

        if section_type not in section_map:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid section type. Must be one of: {list(section_map.keys())}",
            )

        sections = section_map[section_type] or []

        if section_index < 0 or section_index >= len(sections):
            raise HTTPException(
                status_code=404,
                detail=f"Section index {section_index} not found. Section has {len(sections)} items.",
            )

        # Store revision request in history
        revision_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "section_type": section_type,
            "section_index": section_index,
            "feedback": request.feedback,
            "status": "pending",
        }

        if digest.revision_history:
            digest.revision_history.append(revision_entry)
        else:
            digest.revision_history = [revision_entry]

        digest.revision_count = (digest.revision_count or 0) + 1
        db.commit()

        return {
            "digest_id": digest_id,
            "section_type": section_type,
            "section_index": section_index,
            "status": "revision_queued",
            "message": "Section revision has been queued",
        }
