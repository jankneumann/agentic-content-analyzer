"""Script review service for podcast script review operations.

Provides business logic for podcast script review workflow:
- Script status management
- Section-based feedback and revisions
- Approval/rejection workflow
- Review history tracking

Separates presentation layer from core review functionality.
"""

from datetime import UTC, datetime
from typing import Any

from src.config.models import ModelConfig
from src.models.podcast import (
    PodcastScript,
    PodcastScriptRecord,
    PodcastStatus,
    ScriptReviewAction,
    ScriptReviewRequest,
    ScriptRevisionRequest,
)
from src.processors.script_reviser import PodcastScriptReviser
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ScriptReviewService:
    """Service layer for podcast script review operations.

    Provides stateless methods suitable for both CLI and web interfaces.
    Manages the script review workflow:
    1. SCRIPT_PENDING_REVIEW - Initial state after generation
    2. SCRIPT_REVISION_REQUESTED - Reviewer requested changes
    3. SCRIPT_APPROVED - Ready for audio generation
    4. FAILED - Rejected by reviewer
    """

    def __init__(self, model_config: ModelConfig | None = None):
        """Initialize script review service.

        Args:
            model_config: Model configuration (defaults to global config)
        """
        from src.config import settings

        self.model_config = model_config or settings.get_model_config()
        self.reviser = PodcastScriptReviser(model_config=self.model_config)
        logger.info("Initialized ScriptReviewService")

    async def list_pending_reviews(self) -> list[PodcastScriptRecord]:
        """Get all scripts awaiting review.

        Returns:
            List of scripts with status SCRIPT_PENDING_REVIEW,
            ordered by creation date (newest first)
        """
        logger.info("Listing scripts pending review")

        with get_db() as db:
            scripts = (
                db.query(PodcastScriptRecord)
                .filter(PodcastScriptRecord.status == PodcastStatus.SCRIPT_PENDING_REVIEW.value)
                .order_by(PodcastScriptRecord.created_at.desc())
                .all()
            )

            logger.info(f"Found {len(scripts)} scripts pending review")
            return scripts

    async def list_approved_scripts(self) -> list[PodcastScriptRecord]:
        """Get all scripts that are approved and ready for audio generation.

        Returns:
            List of approved scripts, ordered by approved date (newest first)
        """
        logger.info("Listing approved scripts")

        with get_db() as db:
            scripts = (
                db.query(PodcastScriptRecord)
                .filter(PodcastScriptRecord.status == PodcastStatus.SCRIPT_APPROVED.value)
                .order_by(PodcastScriptRecord.approved_at.desc())
                .all()
            )

            logger.info(f"Found {len(scripts)} approved scripts")
            return scripts

    async def get_script(self, script_id: int) -> PodcastScriptRecord | None:
        """Load script by ID.

        Args:
            script_id: Script ID to load

        Returns:
            PodcastScriptRecord or None if not found
        """
        logger.info(f"Loading script {script_id}")

        with get_db() as db:
            script = (
                db.query(PodcastScriptRecord).filter(PodcastScriptRecord.id == script_id).first()
            )

            if not script:
                logger.warning(f"Script {script_id} not found")

            return script

    async def get_scripts_for_digest(self, digest_id: int) -> list[PodcastScriptRecord]:
        """Get all scripts generated from a specific digest.

        Args:
            digest_id: Digest ID

        Returns:
            List of scripts for this digest
        """
        logger.info(f"Loading scripts for digest {digest_id}")

        with get_db() as db:
            scripts = (
                db.query(PodcastScriptRecord)
                .filter(PodcastScriptRecord.digest_id == digest_id)
                .order_by(PodcastScriptRecord.created_at.desc())
                .all()
            )

            return scripts

    def get_script_for_review(self, script_id: int) -> dict[str, Any]:
        """Get script with review-friendly formatting.

        Transforms the script into a structure suitable for review UI,
        with section indices and formatted dialogue.

        Args:
            script_id: Script ID

        Returns:
            Dict with formatted script data for review

        Raises:
            ValueError: If script not found
        """
        logger.info(f"Getting script {script_id} for review")

        with get_db() as db:
            script_record = (
                db.query(PodcastScriptRecord).filter(PodcastScriptRecord.id == script_id).first()
            )

            if not script_record:
                raise ValueError(f"Script {script_id} not found")

            if not script_record.script_json:
                raise ValueError(f"Script {script_id} has no content")

            script = PodcastScript.model_validate(script_record.script_json)

        # Format for review
        return {
            "id": script_record.id,
            "digest_id": script_record.digest_id,
            "title": script.title,
            "length": script.length.value,
            "word_count": script.word_count,
            "estimated_duration": f"{script.estimated_duration_seconds // 60} min",
            "estimated_duration_seconds": script.estimated_duration_seconds,
            "status": script_record.status,
            "revision_count": script_record.revision_count or 0,
            "created_at": script_record.created_at.isoformat()
            if script_record.created_at
            else None,
            "reviewed_by": script_record.reviewed_by,
            "reviewed_at": script_record.reviewed_at.isoformat()
            if script_record.reviewed_at
            else None,
            "sections": [
                {
                    "index": i,
                    "type": s.section_type,
                    "title": s.title,
                    "word_count": sum(len(t.text.split()) for t in s.dialogue),
                    "dialogue": [
                        {
                            "speaker": t.speaker.upper(),
                            "text": t.text,
                            "emphasis": t.emphasis,
                            "pause_after": t.pause_after,
                        }
                        for t in s.dialogue
                    ],
                    "sources_cited": s.sources_cited,
                }
                for i, s in enumerate(script.sections)
            ],
            "sources_summary": script.sources_summary,
            "revision_history": script_record.revision_history or [],
            "newsletter_ids_fetched": script_record.newsletter_ids_fetched or [],
            "web_search_queries": script_record.web_search_queries or [],
            "tool_call_count": script_record.tool_call_count or 0,
        }

    async def submit_review(
        self,
        request: ScriptReviewRequest,
    ) -> PodcastScriptRecord:
        """Submit a review for a script.

        Handles the review action:
        - APPROVE: Mark as SCRIPT_APPROVED, ready for audio
        - REQUEST_REVISION: Apply section-based feedback, return to PENDING_REVIEW
        - REJECT: Mark as FAILED

        Args:
            request: Review request with action and feedback

        Returns:
            Updated PodcastScriptRecord

        Raises:
            ValueError: If script not found or not in reviewable state
        """
        logger.info(
            f"Submitting review for script {request.script_id}: "
            f"action={request.action.value}, reviewer={request.reviewer}"
        )

        with get_db() as db:
            script_record = (
                db.query(PodcastScriptRecord)
                .filter(PodcastScriptRecord.id == request.script_id)
                .first()
            )

            if not script_record:
                raise ValueError(f"Script {request.script_id} not found")

            # Verify script is in reviewable state
            reviewable_states = [
                PodcastStatus.SCRIPT_PENDING_REVIEW.value,
                PodcastStatus.SCRIPT_REVISION_REQUESTED.value,
            ]
            if script_record.status not in reviewable_states:
                raise ValueError(
                    f"Script {request.script_id} is not reviewable. Status: {script_record.status}"
                )

            # Apply review action
            if request.action == ScriptReviewAction.APPROVE:
                script_record.status = PodcastStatus.SCRIPT_APPROVED.value
                script_record.reviewed_by = request.reviewer
                script_record.reviewed_at = datetime.now(UTC)
                script_record.review_notes = request.general_notes
                script_record.approved_at = datetime.now(UTC)

                db.commit()
                db.refresh(script_record)

                logger.info(f"Script {request.script_id} approved by {request.reviewer}")

            elif request.action == ScriptReviewAction.REQUEST_REVISION:
                script_record.status = PodcastStatus.SCRIPT_REVISION_REQUESTED.value
                script_record.reviewed_by = request.reviewer
                script_record.reviewed_at = datetime.now(UTC)
                script_record.review_notes = request.general_notes

                db.commit()
                db.refresh(script_record)

                # Apply section-specific revisions
                if request.section_feedback:
                    logger.info(f"Applying {len(request.section_feedback)} section revisions")
                    script_record = await self.reviser.apply_multiple_revisions(
                        request.script_id,
                        request.section_feedback,
                    )

                logger.info(
                    f"Revision requested for script {request.script_id}. "
                    f"Revision count: {script_record.revision_count}"
                )

            elif request.action == ScriptReviewAction.REJECT:
                script_record.status = PodcastStatus.FAILED.value
                script_record.reviewed_by = request.reviewer
                script_record.reviewed_at = datetime.now(UTC)
                script_record.review_notes = request.general_notes
                script_record.error_message = "Rejected by reviewer"

                db.commit()
                db.refresh(script_record)

                logger.info(f"Script {request.script_id} rejected by {request.reviewer}")

            return script_record

    async def revise_section(
        self,
        request: ScriptRevisionRequest,
    ) -> PodcastScriptRecord:
        """Revise a single section based on feedback.

        Args:
            request: Revision request with section index and feedback

        Returns:
            Updated PodcastScriptRecord
        """
        logger.info(f"Revising section {request.section_index} of script {request.script_id}")

        # Check if direct replacement is provided
        if request.replacement_dialogue:
            return await self.reviser.replace_section_dialogue(
                script_id=request.script_id,
                section_index=request.section_index,
                replacement_dialogue=request.replacement_dialogue,
                reviewer="manual",
            )
        else:
            return await self.reviser.apply_revision(
                script_id=request.script_id,
                section_index=request.section_index,
                feedback=request.feedback,
            )

    async def quick_approve(
        self,
        script_id: int,
        reviewer: str,
        notes: str | None = None,
    ) -> PodcastScriptRecord:
        """Quick approve a script without detailed review.

        Convenience method for batch approval operations.

        Args:
            script_id: Script ID
            reviewer: Reviewer name/email
            notes: Optional approval notes

        Returns:
            Updated PodcastScriptRecord
        """
        logger.info(f"Quick approving script {script_id} by {reviewer}")

        request = ScriptReviewRequest(
            script_id=script_id,
            action=ScriptReviewAction.APPROVE,
            reviewer=reviewer,
            general_notes=notes,
        )

        return await self.submit_review(request)

    async def quick_reject(
        self,
        script_id: int,
        reviewer: str,
        reason: str,
    ) -> PodcastScriptRecord:
        """Quick reject a script.

        Args:
            script_id: Script ID
            reviewer: Reviewer name/email
            reason: Rejection reason

        Returns:
            Updated PodcastScriptRecord
        """
        logger.info(f"Quick rejecting script {script_id} by {reviewer}")

        request = ScriptReviewRequest(
            script_id=script_id,
            action=ScriptReviewAction.REJECT,
            reviewer=reviewer,
            general_notes=reason,
        )

        return await self.submit_review(request)

    def get_section_dialogue_text(
        self,
        script_id: int,
        section_index: int,
    ) -> str:
        """Get formatted dialogue text for a specific section.

        Useful for displaying section content in review UI.

        Args:
            script_id: Script ID
            section_index: Section index

        Returns:
            Formatted dialogue text

        Raises:
            ValueError: If script or section not found
        """
        with get_db() as db:
            script_record = (
                db.query(PodcastScriptRecord).filter(PodcastScriptRecord.id == script_id).first()
            )

            if not script_record or not script_record.script_json:
                raise ValueError(f"Script {script_id} not found")

            script = PodcastScript.model_validate(script_record.script_json)

            if section_index < 0 or section_index >= len(script.sections):
                raise ValueError(
                    f"Section {section_index} not found. "
                    f"Script has {len(script.sections)} sections."
                )

            section = script.sections[section_index]

            lines = []
            for turn in section.dialogue:
                speaker = turn.speaker.upper()
                emphasis = f" [{turn.emphasis}]" if turn.emphasis else ""
                lines.append(f"{speaker}{emphasis}: {turn.text}")

            return "\n\n".join(lines)

    async def get_review_statistics(self) -> dict[str, Any]:
        """Get statistics about script review workflow.

        Returns:
            Dict with review statistics
        """
        with get_db() as db:
            # Count by status
            pending = (
                db.query(PodcastScriptRecord)
                .filter(PodcastScriptRecord.status == PodcastStatus.SCRIPT_PENDING_REVIEW.value)
                .count()
            )
            revision_requested = (
                db.query(PodcastScriptRecord)
                .filter(PodcastScriptRecord.status == PodcastStatus.SCRIPT_REVISION_REQUESTED.value)
                .count()
            )
            approved = (
                db.query(PodcastScriptRecord)
                .filter(PodcastScriptRecord.status == PodcastStatus.SCRIPT_APPROVED.value)
                .count()
            )
            completed = (
                db.query(PodcastScriptRecord)
                .filter(PodcastScriptRecord.status == PodcastStatus.COMPLETED.value)
                .count()
            )
            failed = (
                db.query(PodcastScriptRecord)
                .filter(PodcastScriptRecord.status == PodcastStatus.FAILED.value)
                .count()
            )

            return {
                "pending_review": pending,
                "revision_requested": revision_requested,
                "approved_ready_for_audio": approved,
                "completed_with_audio": completed,
                "failed_rejected": failed,
                "total": pending + revision_requested + approved + completed + failed,
            }

    def calculate_revision_cost(self) -> float:
        """Calculate cost of revisions in current session.

        Returns:
            Total cost in USD based on reviser's token usage
        """
        if not self.reviser.provider_used:
            return 0.0

        return self.model_config.calculate_cost(
            model_id=self.reviser.model,
            input_tokens=self.reviser.input_tokens,
            output_tokens=self.reviser.output_tokens,
            provider=self.reviser.provider_used,
        )
