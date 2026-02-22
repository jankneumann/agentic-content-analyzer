"""API endpoints for podcast script management and review.

Provides REST endpoints for:
- Script generation from digests
- Script retrieval and listing
- Section-based review workflow
- Script approval/rejection
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.dependencies import verify_admin_key
from src.models.chat import Conversation, MessageRole
from src.models.podcast import (
    PodcastLength,
    PodcastRequest,
    PodcastScriptRecord,
    PodcastStatus,
    ScriptReviewAction,
    ScriptReviewRequest,
)
from src.processors.podcast_script_generator import PodcastScriptGenerator
from src.services.script_review_service import ScriptReviewService
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/scripts", tags=["podcast-scripts"], dependencies=[Depends(verify_admin_key)]
)

# Allowed sort fields for script listing
SCRIPT_SORT_FIELDS = {"id", "digest_id", "status", "created_at"}

# Initialize services
review_service = ScriptReviewService()
script_generator = PodcastScriptGenerator()


# --- Request/Response Models ---


class GenerateScriptRequest(BaseModel):
    """Request to generate a podcast script from a digest."""

    digest_id: int = Field(..., description="ID of the digest to convert")
    length: PodcastLength = Field(
        default=PodcastLength.STANDARD, description="Target podcast length"
    )
    enable_web_search: bool = Field(default=True, description="Allow model to use web search tool")
    custom_focus_topics: list[str] = Field(
        default_factory=list, description="Optional topics to emphasize"
    )


class ScriptSummary(BaseModel):
    """Summary of a script for listing."""

    id: int
    digest_id: int
    title: str | None
    length: str
    word_count: int | None
    estimated_duration: str | None
    status: str
    revision_count: int
    created_at: str | None
    reviewed_by: str | None


class SectionFeedbackRequest(BaseModel):
    """Request to revise a section with feedback."""

    feedback: str = Field(..., description="Reviewer feedback for this section")


class RegenerateScriptRequest(BaseModel):
    """Request to regenerate a script based on chat conversation."""

    conversation_id: str = Field(..., description="Conversation ID containing instructions")


class ReviewRequest(BaseModel):
    """Request to submit a review."""

    action: ScriptReviewAction = Field(..., description="Review action")
    reviewer: str = Field(..., description="Reviewer identifier")
    section_feedback: dict = Field(
        default_factory=dict,
        description="Section-specific feedback (key = section index, value = feedback)",
    )
    general_notes: str | None = Field(None, description="General review notes")


class ReviewStatistics(BaseModel):
    """Review workflow statistics."""

    pending_review: int
    revision_requested: int
    approved_ready_for_audio: int
    completed_with_audio: int
    failed_rejected: int
    total: int


# --- Background Tasks ---


async def generate_script_task(request: PodcastRequest) -> None:
    """Background task for script generation."""
    logger.info(f"Starting background script generation for digest {request.digest_id}")

    # Create initial record
    with get_db() as db:
        script_record = PodcastScriptRecord(
            digest_id=request.digest_id,
            length=request.length.value if hasattr(request.length, "value") else request.length,
            status=PodcastStatus.SCRIPT_GENERATING.value,
        )
        db.add(script_record)
        db.commit()
        db.refresh(script_record)
        script_id = script_record.id

    await regenerate_script_task(script_id, request)


async def regenerate_script_task(script_id: int, request: PodcastRequest) -> None:
    """Background task for script regeneration."""
    logger.info(f"Starting background script generation/regeneration for script {script_id}")

    try:
        # Generate script
        generator = PodcastScriptGenerator()
        script, metadata = await generator.generate_script(request)

        # Update record with generated content
        with get_db() as db:
            script_record = (
                db.query(PodcastScriptRecord).filter(PodcastScriptRecord.id == script_id).first()
            )
            if not script_record:
                logger.error(f"Script {script_id} not found during generation")
                return

            script_record.script_json = script.model_dump()
            script_record.title = script.title
            script_record.word_count = script.word_count
            script_record.estimated_duration_seconds = script.estimated_duration_seconds
            script_record.status = PodcastStatus.SCRIPT_PENDING_REVIEW.value
            script_record.newsletter_ids_fetched = metadata.content_ids_fetched
            script_record.web_search_queries = metadata.web_searches
            script_record.tool_call_count = metadata.tool_call_count
            script_record.model_used = generator.model
            script_record.model_version = generator.model_version
            script_record.token_usage = {
                "input_tokens": generator.input_tokens,
                "output_tokens": generator.output_tokens,
            }

            # If there are custom instructions, save them in review notes/history
            if request.custom_instructions:
                history_entry = {
                    "timestamp": getattr(script_record, "created_at", None)
                    and script_record.created_at.isoformat(),
                    "action": "regeneration",
                    "instructions": request.custom_instructions,
                }
                history = script_record.revision_history or []
                history.append(history_entry)
                script_record.revision_history = history

            db.commit()

        logger.info(f"Script {script_id} generated successfully")

    except Exception as e:
        logger.error(f"Script generation failed: {e}", exc_info=True)
        with get_db() as db:
            script_record = (
                db.query(PodcastScriptRecord).filter(PodcastScriptRecord.id == script_id).first()
            )
            if script_record:
                script_record.status = PodcastStatus.FAILED.value
                script_record.error_message = "Script generation failed due to an internal error."
                db.commit()


# --- Endpoints ---


@router.post("/generate", response_model=dict)
async def generate_script(
    request: GenerateScriptRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Generate a podcast script from a digest (Phase 1).

    Starts script generation in background and returns immediately.
    Poll GET /scripts/{script_id} for status.
    """
    logger.info(f"Received script generation request for digest {request.digest_id}")

    # Convert to PodcastRequest
    podcast_request = PodcastRequest(
        digest_id=request.digest_id,
        length=request.length,
        enable_web_search=request.enable_web_search,
        custom_focus_topics=request.custom_focus_topics,
    )

    # Queue background task
    background_tasks.add_task(generate_script_task, podcast_request)

    return {
        "status": "queued",
        "message": f"Script generation started for digest {request.digest_id}",
        "length": request.length.value if hasattr(request.length, "value") else request.length,
    }


@router.post("/{script_id}/regenerate", response_model=dict)
async def regenerate_script(
    script_id: int,
    request: RegenerateScriptRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Regenerate a podcast script based on chat conversation.

    Creates a new script record (preview) and triggers generation.
    Returns the new script ID immediately.
    """
    logger.info(f"Received script regeneration request for script {script_id}")

    with get_db() as db:
        # Get original script to find digest_id
        original_script = (
            db.query(PodcastScriptRecord).filter(PodcastScriptRecord.id == script_id).first()
        )
        if not original_script:
            raise HTTPException(status_code=404, detail="Script not found")

        digest_id = original_script.digest_id
        length_str = original_script.length

        # Get conversation to build instructions
        conversation = (
            db.query(Conversation).filter(Conversation.id == request.conversation_id).first()
        )

        custom_instructions = None
        if conversation:
            # Extract user messages as instructions
            user_messages = [
                msg.content for msg in conversation.messages if msg.role == MessageRole.USER.value
            ]
            if user_messages:
                custom_instructions = "User instructions:\n" + "\n".join(
                    f"- {msg}" for msg in user_messages
                )

        # Create new script record
        new_script = PodcastScriptRecord(
            digest_id=digest_id,
            length=length_str,
            status=PodcastStatus.SCRIPT_GENERATING.value,
        )
        db.add(new_script)
        db.commit()
        db.refresh(new_script)
        new_script_id = new_script.id

    # Build PodcastRequest
    try:
        podcast_length = PodcastLength(length_str)
    except ValueError:
        podcast_length = PodcastLength.STANDARD

    podcast_request = PodcastRequest(
        digest_id=digest_id,
        length=podcast_length,
        custom_instructions=custom_instructions,
        # Inherit other settings from original if available, otherwise defaults
    )

    # Queue background task
    background_tasks.add_task(regenerate_script_task, new_script_id, podcast_request)

    return {
        "status": "queued",
        "script_id": new_script_id,
        "message": f"Script regeneration started for script {script_id}",
    }


@router.get("/", response_model=list[ScriptSummary])
async def list_scripts(
    status: PodcastStatus | None = Query(None, description="Filter by status"),
    digest_id: int | None = Query(None, description="Filter by digest ID"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
) -> list[ScriptSummary]:
    """List podcast scripts with optional filtering."""
    from src.models.podcast import PodcastScriptRecord

    with get_db() as db:
        query = db.query(PodcastScriptRecord)

        if status:
            query = query.filter(PodcastScriptRecord.status == status)
        if digest_id:
            query = query.filter(PodcastScriptRecord.digest_id == digest_id)

        # Apply dynamic sorting
        if sort_by not in SCRIPT_SORT_FIELDS:
            sort_by = "created_at"

        sort_column = getattr(PodcastScriptRecord, sort_by, PodcastScriptRecord.created_at)
        if sort_order.lower() == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        scripts = query.limit(limit).all()

        return [
            ScriptSummary(
                id=s.id,
                digest_id=s.digest_id,
                title=s.title,
                length=s.length or "unknown",
                word_count=s.word_count,
                estimated_duration=(
                    f"{s.estimated_duration_seconds // 60} min"
                    if s.estimated_duration_seconds
                    else None
                ),
                status=s.status or "unknown",
                revision_count=s.revision_count or 0,
                created_at=s.created_at.isoformat() if s.created_at else None,
                reviewed_by=s.reviewed_by,
            )
            for s in scripts
        ]


@router.get("/pending-review", response_model=list[ScriptSummary])
async def list_pending_scripts() -> list[ScriptSummary]:
    """List all scripts pending review."""
    scripts = await review_service.list_pending_reviews()

    return [
        ScriptSummary(
            id=s.id,
            digest_id=s.digest_id,
            title=s.title,
            length=s.length or "unknown",
            word_count=s.word_count,
            estimated_duration=(
                f"{s.estimated_duration_seconds // 60} min"
                if s.estimated_duration_seconds
                else None
            ),
            status=s.status or "unknown",
            revision_count=s.revision_count or 0,
            created_at=s.created_at.isoformat() if s.created_at else None,
            reviewed_by=s.reviewed_by,
        )
        for s in scripts
    ]


@router.get("/approved", response_model=list[ScriptSummary])
async def list_approved_scripts() -> list[ScriptSummary]:
    """List all approved scripts ready for audio generation."""
    scripts = await review_service.list_approved_scripts()

    return [
        ScriptSummary(
            id=s.id,
            digest_id=s.digest_id,
            title=s.title,
            length=s.length or "unknown",
            word_count=s.word_count,
            estimated_duration=(
                f"{s.estimated_duration_seconds // 60} min"
                if s.estimated_duration_seconds
                else None
            ),
            status=s.status or "unknown",
            revision_count=s.revision_count or 0,
            created_at=s.created_at.isoformat() if s.created_at else None,
            reviewed_by=s.reviewed_by,
        )
        for s in scripts
    ]


@router.get("/statistics", response_model=ReviewStatistics)
async def get_review_statistics() -> ReviewStatistics:
    """Get statistics about script review workflow."""
    stats = await review_service.get_review_statistics()
    return ReviewStatistics(**stats)


@router.get("/digest/{digest_id}", response_model=list[ScriptSummary])
async def list_scripts_for_digest(digest_id: int) -> list[ScriptSummary]:
    """List all scripts generated from a specific digest."""
    scripts = await review_service.get_scripts_for_digest(digest_id)

    return [
        ScriptSummary(
            id=s.id,
            digest_id=s.digest_id,
            title=s.title,
            length=s.length or "unknown",
            word_count=s.word_count,
            estimated_duration=(
                f"{s.estimated_duration_seconds // 60} min"
                if s.estimated_duration_seconds
                else None
            ),
            status=s.status or "unknown",
            revision_count=s.revision_count or 0,
            created_at=s.created_at.isoformat() if s.created_at else None,
            reviewed_by=s.reviewed_by,
        )
        for s in scripts
    ]


@router.get("/{script_id}")
async def get_script(script_id: int) -> dict:
    """Get script with full details for review.

    Returns the complete script with section indices suitable for review UI.
    """
    try:
        return review_service.get_script_for_review(script_id)
    except ValueError as e:
        logger.error(f"Error retrieving script {script_id}: {e}", exc_info=True)
        raise HTTPException(status_code=404, detail="Script not found or unavailable")


@router.get("/{script_id}/sections/{section_index}")
async def get_script_section(script_id: int, section_index: int) -> dict:
    """Get a specific section of a script.

    Useful for displaying individual section content.
    """
    try:
        script_data = review_service.get_script_for_review(script_id)

        if section_index < 0 or section_index >= len(script_data["sections"]):
            raise HTTPException(
                status_code=404,
                detail=f"Section {section_index} not found. Script has {len(script_data['sections'])} sections.",
            )

        section = script_data["sections"][section_index]
        section["script_title"] = script_data["title"]
        return section

    except ValueError as e:
        logger.error(
            f"Error retrieving section {section_index} for script {script_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=404, detail="Section not found or unavailable")


@router.get("/{script_id}/sections/{section_index}/dialogue")
async def get_section_dialogue(script_id: int, section_index: int) -> dict:
    """Get formatted dialogue text for a specific section.

    Returns dialogue as formatted text suitable for display.
    """
    try:
        text = review_service.get_section_dialogue_text(script_id, section_index)
        return {"section_index": section_index, "dialogue_text": text}

    except ValueError as e:
        logger.error(
            f"Error retrieving dialogue for section {section_index} of script {script_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(status_code=404, detail="Dialogue unavailable")


@router.post("/{script_id}/review")
async def submit_review(
    script_id: int,
    request: ReviewRequest,
) -> dict:
    """Submit review with optional section-specific feedback.

    Actions:
    - approve: Mark script as ready for audio generation
    - request_revision: Apply section feedback and return to pending review
    - reject: Mark script as failed
    """
    try:
        review_request = ScriptReviewRequest(
            script_id=script_id,
            action=request.action,
            reviewer=request.reviewer,
            section_feedback={int(k): v for k, v in request.section_feedback.items()},
            general_notes=request.general_notes,
        )

        script = await review_service.submit_review(review_request)

        return {
            "script_id": script.id,
            "status": script.status or "unknown",
            "revision_count": script.revision_count or 0,
            "reviewed_by": script.reviewed_by,
            "reviewed_at": script.reviewed_at.isoformat() if script.reviewed_at else None,
        }

    except ValueError as e:
        logger.error(f"Error submitting review for script {script_id}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Review submission failed")


@router.post("/{script_id}/sections/{section_index}/revise")
async def revise_section(
    script_id: int,
    section_index: int,
    request: SectionFeedbackRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Revise a single section based on feedback.

    The AI will regenerate the section dialogue based on the feedback
    while maintaining persona voices and conversational flow.
    """
    from src.models.podcast import ScriptRevisionRequest

    try:
        revision_request = ScriptRevisionRequest(
            script_id=script_id,
            section_index=section_index,
            feedback=request.feedback,
        )

        script = await review_service.revise_section(revision_request)

        return {
            "script_id": script.id,
            "section_revised": section_index,
            "status": script.status or "unknown",
            "revision_count": script.revision_count or 0,
        }

    except ValueError as e:
        logger.error(
            f"Error revising section {section_index} of script {script_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=400, detail="Section revision failed")


@router.post("/{script_id}/approve")
async def quick_approve(
    script_id: int,
    reviewer: str = Query(..., description="Reviewer identifier"),
    notes: str | None = Query(None, description="Approval notes"),
) -> dict:
    """Quick approve a script for audio generation.

    Convenience endpoint for approving without detailed review.
    """
    try:
        script = await review_service.quick_approve(script_id, reviewer, notes)

        return {
            "script_id": script.id,
            "status": script.status or "unknown",
            "approved_at": script.approved_at.isoformat() if script.approved_at else None,
        }

    except ValueError as e:
        logger.error(f"Error approving script {script_id}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Approval failed")


@router.post("/{script_id}/reject")
async def quick_reject(
    script_id: int,
    reviewer: str = Query(..., description="Reviewer identifier"),
    reason: str = Query(..., description="Rejection reason"),
) -> dict:
    """Quick reject a script.

    Convenience endpoint for rejection.
    """
    try:
        script = await review_service.quick_reject(script_id, reviewer, reason)

        return {
            "script_id": script.id,
            "status": script.status or "unknown",
        }

    except ValueError as e:
        logger.error(f"Error rejecting script {script_id}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Rejection failed")


@router.get("/{script_id}/navigation")
async def get_script_navigation(script_id: int) -> dict:
    """Get navigation info for prev/next script.

    Returns prev and next script IDs for navigation in review UI.
    """
    from src.models.podcast import PodcastScriptRecord

    with get_db() as db:
        # Get all scripts ordered by creation date
        scripts = (
            db.query(PodcastScriptRecord).order_by(PodcastScriptRecord.created_at.desc()).all()
        )

        if not scripts:
            raise HTTPException(status_code=404, detail="No scripts found")

        # Find current position
        script_ids = [s.id for s in scripts]
        try:
            current_index = script_ids.index(script_id)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Script {script_id} not found")

        # Calculate prev/next
        prev_id = script_ids[current_index - 1] if current_index > 0 else None
        next_id = script_ids[current_index + 1] if current_index < len(script_ids) - 1 else None

        return {
            "prev_id": prev_id,
            "next_id": next_id,
            "position": current_index + 1,
            "total": len(script_ids),
        }
