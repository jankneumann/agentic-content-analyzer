"""API endpoints for digest management and review.

Provides REST endpoints for:
- Digest listing with filters
- Digest detail retrieval
- Digest generation (daily/weekly)
- Review workflow (approve/reject/revise)
- Section-level revision
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from src.models.digest import (
    Digest,
    DigestData,
    DigestRequest,
    DigestSection,
    DigestStatus,
    DigestType,
)
from src.processors.digest_creator import DigestCreator
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/digests", tags=["digests"])


# --- Request/Response Models ---


class GenerateDigestRequest(BaseModel):
    """Request to generate a new digest."""

    digest_type: str = Field(..., description="Type of digest: 'daily' or 'weekly'")
    period_start: Optional[datetime] = Field(
        None, description="Start of period (defaults based on type)"
    )
    period_end: Optional[datetime] = Field(
        None, description="End of period (defaults to now)"
    )
    max_strategic_insights: int = Field(default=5)
    max_technical_developments: int = Field(default=5)
    max_emerging_trends: int = Field(default=3)
    include_historical_context: bool = Field(default=True)


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
    reviewed_by: Optional[str] = None


class DigestSectionResponse(BaseModel):
    """A section within a digest."""

    title: str
    summary: str
    details: List[str]
    themes: List[str]
    continuity: Optional[str] = None


class DigestDetail(BaseModel):
    """Full digest detail for viewing."""

    id: int
    digest_type: str
    title: str
    period_start: str
    period_end: str
    executive_overview: str
    strategic_insights: List[DigestSectionResponse]
    technical_developments: List[DigestSectionResponse]
    emerging_trends: List[DigestSectionResponse]
    actionable_recommendations: dict
    sources: List[dict]
    newsletter_count: int
    status: str
    created_at: str
    completed_at: Optional[str] = None
    model_used: str
    model_version: Optional[str] = None
    processing_time_seconds: Optional[int] = None
    revision_count: int
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_notes: Optional[str] = None
    is_combined: bool = False
    child_digest_ids: Optional[List[int]] = None


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
    notes: Optional[str] = Field(None, description="Review notes")
    section_feedback: Optional[dict] = Field(
        default_factory=dict,
        description="Section-specific feedback (key = section type, value = feedback)",
    )


class SectionRevisionRequest(BaseModel):
    """Request to revise a specific section."""

    feedback: str = Field(..., description="Feedback for revision")


# --- Background Tasks ---


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
            digest_record.emerging_trends = [
                s.model_dump() for s in digest_data.emerging_trends
            ]
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

            db.commit()

        logger.info(f"Digest {digest_id} generated successfully")

    except Exception as e:
        logger.error(f"Digest generation failed: {e}")
        with get_db() as db:
            digest_record = db.query(Digest).filter(Digest.id == digest_id).first()
            digest_record.status = DigestStatus.FAILED
            digest_record.review_notes = str(e)
            db.commit()


# --- Endpoints ---


@router.post("/generate", response_model=dict)
async def generate_digest(
    request: GenerateDigestRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Generate a new digest (daily or weekly).

    Starts digest generation in background and returns immediately.
    Poll GET /digests/{digest_id} for status.
    """
    logger.info(f"Received digest generation request: {request.digest_type}")

    # Validate digest type
    try:
        digest_type = DigestType(request.digest_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid digest type. Must be 'daily' or 'weekly'",
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

    # Create digest request
    digest_request = DigestRequest(
        digest_type=digest_type,
        period_start=period_start,
        period_end=period_end,
        max_strategic_insights=request.max_strategic_insights,
        max_technical_developments=request.max_technical_developments,
        max_emerging_trends=request.max_emerging_trends,
        include_historical_context=request.include_historical_context,
    )

    # Queue background task
    background_tasks.add_task(generate_digest_task, digest_request)

    return {
        "status": "queued",
        "message": f"{digest_type.value.title()} digest generation started",
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
    }


@router.get("/", response_model=List[DigestSummary])
async def list_digests(
    status: Optional[str] = Query(None, description="Filter by status"),
    digest_type: Optional[str] = Query(None, description="Filter by type"),
    limit: int = Query(50, le=100, description="Maximum results"),
    offset: int = Query(0, description="Offset for pagination"),
) -> List[DigestSummary]:
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

        digests = (
            query.order_by(Digest.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

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
            by_type[dtype.value] = (
                db.query(Digest)
                .filter(Digest.digest_type == dtype)
                .count()
            )

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
async def get_digest(digest_id: int) -> DigestDetail:
    """Get full digest details."""
    with get_db() as db:
        digest = db.query(Digest).filter(Digest.id == digest_id).first()

        if not digest:
            raise HTTPException(status_code=404, detail="Digest not found")

        # Convert JSON sections to response models
        def parse_sections(sections_json: list) -> List[DigestSectionResponse]:
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

        return DigestDetail(
            id=digest.id,
            digest_type=digest.digest_type.value if digest.digest_type else "unknown",
            title=digest.title,
            period_start=digest.period_start.isoformat() if digest.period_start else "",
            period_end=digest.period_end.isoformat() if digest.period_end else "",
            executive_overview=digest.executive_overview or "",
            strategic_insights=parse_sections(digest.strategic_insights),
            technical_developments=parse_sections(digest.technical_developments),
            emerging_trends=parse_sections(digest.emerging_trends),
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
        )


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
    notes: Optional[str] = Query(None, description="Approval notes"),
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
