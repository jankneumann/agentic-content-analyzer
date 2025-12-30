"""Review service layer for digest review operations.

Provides business logic for digest review, usable by both CLI and future web UI.
Separates presentation layer from core review functionality.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.config.models import ModelConfig
from src.models.digest import Digest, DigestStatus
from src.models.revision import RevisionContext, RevisionResult, RevisionTurn
from src.processors.digest_reviser import DigestReviser
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ReviewService:
    """Service layer for digest review operations.

    Provides stateless methods suitable for both CLI and web interfaces.
    All methods are async to support future web API integration.
    """

    def __init__(self, model_config: Optional[ModelConfig] = None):
        """
        Initialize review service.

        Args:
            model_config: Model configuration (defaults to global config)
        """
        from src.config import settings

        self.model_config = model_config or settings.get_model_config()
        self.reviser = DigestReviser(model_config=self.model_config)
        logger.info("Initialized ReviewService")

    async def list_pending_reviews(self) -> List[Digest]:
        """Get all digests awaiting review.

        Returns:
            List of digests with status PENDING_REVIEW, ordered by creation date (newest first)
        """
        logger.info("Listing pending reviews")

        with get_db() as db:
            # Disable expiration on commit so objects remain accessible after session closes
            db.expire_on_commit = False

            digests = (
                db.query(Digest)
                .filter(Digest.status == DigestStatus.PENDING_REVIEW)
                .order_by(Digest.created_at.desc())
                .all()
            )

            logger.info(f"Found {len(digests)} digests pending review")
            return digests

    async def get_digest(self, digest_id: int) -> Optional[Digest]:
        """Load digest by ID.

        Args:
            digest_id: Digest ID to load

        Returns:
            Digest object or None if not found
        """
        logger.info(f"Loading digest {digest_id}")

        with get_db() as db:
            # Disable expiration on commit so objects remain accessible after session closes
            db.expire_on_commit = False

            digest = db.query(Digest).filter_by(id=digest_id).first()

            if not digest:
                logger.warning(f"Digest {digest_id} not found")

            return digest

    async def start_revision_session(
        self,
        digest_id: int,
        session_id: str,
        reviewer: str,
    ) -> RevisionContext:
        """Initialize revision session with context.

        Args:
            digest_id: Digest ID to revise
            session_id: Unique session identifier
            reviewer: Reviewer name/email

        Returns:
            RevisionContext with loaded data

        Raises:
            ValueError: If digest not found or not in reviewable status
        """
        logger.info(
            f"Starting revision session {session_id} for digest {digest_id} "
            f"by reviewer {reviewer}"
        )

        # Load context via reviser
        context = await self.reviser.load_context(digest_id)

        # Validate digest status
        if context.digest.status not in [
            DigestStatus.PENDING_REVIEW,
            DigestStatus.COMPLETED,
        ]:
            raise ValueError(
                f"Digest {digest_id} is not reviewable. "
                f"Status: {context.digest.status}"
            )

        return context

    async def process_revision_turn(
        self,
        context: RevisionContext,
        user_input: str,
        conversation_history: List[Dict[str, Any]],
        session_id: str,
    ) -> RevisionResult:
        """Process single revision request.

        Args:
            context: Revision context
            user_input: User's revision request
            conversation_history: Previous turns in Anthropic SDK format
            session_id: Session identifier

        Returns:
            RevisionResult with revised content and explanation
        """
        logger.info(f"Processing revision turn in session {session_id}")

        result = await self.reviser.revise_section(
            context=context,
            user_request=user_input,
            conversation_history=conversation_history,
        )

        logger.info(
            f"Revision turn complete. Section: {result.section_modified}, "
            f"Tools used: {result.tools_used}"
        )

        return result

    async def apply_revision(
        self,
        digest_id: int,
        section: str,
        new_content: Any,
        increment_count: bool = True,
    ) -> Digest:
        """Apply revision to digest and persist to database.

        Args:
            digest_id: Digest ID
            section: Section to modify
            new_content: New content for section
            increment_count: Whether to increment revision_count

        Returns:
            Updated digest from database

        Raises:
            ValueError: If digest not found or section invalid
        """
        logger.info(f"Applying revision to digest {digest_id}, section: {section}")

        with get_db() as db:
            digest = db.query(Digest).filter_by(id=digest_id).first()

            if not digest:
                raise ValueError(f"Digest {digest_id} not found")

            # Apply revision via reviser
            updated_digest = await self.reviser.apply_revision(
                digest, section, new_content, increment_count
            )

            # Persist to database
            db.commit()
            db.refresh(updated_digest)

            logger.info(
                f"Revision applied. Section: {section}, "
                f"Revision count: {updated_digest.revision_count}"
            )

            return updated_digest

    async def finalize_review(
        self,
        digest_id: int,
        action: str,
        revision_history: Optional[Dict[str, Any]],
        reviewer: str,
        review_notes: Optional[str] = None,
    ) -> Digest:
        """Complete review process and update digest status.

        Args:
            digest_id: Digest ID
            action: Review action ('approve', 'reject', 'save-draft')
            revision_history: Complete revision history (JSON)
            reviewer: Reviewer name/email
            review_notes: Optional review notes

        Returns:
            Updated digest

        Raises:
            ValueError: If digest not found or action invalid
        """
        logger.info(
            f"Finalizing review for digest {digest_id}: "
            f"action={action}, reviewer={reviewer}"
        )

        valid_actions = ["approve", "reject", "save-draft"]
        if action not in valid_actions:
            raise ValueError(
                f"Invalid action '{action}'. Valid: {valid_actions}"
            )

        with get_db() as db:
            digest = db.query(Digest).filter_by(id=digest_id).first()

            if not digest:
                raise ValueError(f"Digest {digest_id} not found")

            # Update status based on action
            if action == "approve":
                digest.status = DigestStatus.APPROVED
            elif action == "reject":
                digest.status = DigestStatus.REJECTED
            elif action == "save-draft":
                digest.status = DigestStatus.PENDING_REVIEW

            # Update audit fields
            if revision_history:
                # Merge with existing history if present
                if digest.revision_history:
                    existing = digest.revision_history
                    if "sessions" in existing and "sessions" in revision_history:
                        existing["sessions"].extend(revision_history["sessions"])
                        digest.revision_history = existing
                    else:
                        digest.revision_history = revision_history
                else:
                    digest.revision_history = revision_history

            digest.reviewed_by = reviewer
            digest.review_notes = review_notes
            digest.reviewed_at = datetime.now(timezone.utc)

            db.commit()
            db.refresh(digest)

            logger.info(
                f"Review finalized. Status: {digest.status}, "
                f"Revision count: {digest.revision_count}"
            )

            return digest

    async def quick_review(
        self,
        digest_id: int,
        action: str,
        reviewer: str,
        notes: Optional[str] = None,
    ) -> Digest:
        """Quick approve/reject without interactive revision.

        Convenience method for batch review operations.

        Args:
            digest_id: Digest ID
            action: 'approve' or 'reject'
            reviewer: Reviewer name/email
            notes: Optional review notes

        Returns:
            Updated digest

        Raises:
            ValueError: If digest not found or action invalid
        """
        logger.info(
            f"Quick review for digest {digest_id}: "
            f"action={action}, reviewer={reviewer}"
        )

        if action not in ["approve", "reject"]:
            raise ValueError(
                f"Invalid action '{action}'. Valid: 'approve', 'reject'"
            )

        # Create minimal revision history for audit
        revision_history = {
            "sessions": [
                {
                    "session_id": str(uuid.uuid4()),
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                    "reviewer": reviewer,
                    "turns": [],  # No interactive turns
                    "final_action": action,
                    "review_type": "quick",
                }
            ]
        }

        return await self.finalize_review(
            digest_id=digest_id,
            action=action,
            revision_history=revision_history,
            reviewer=reviewer,
            review_notes=notes,
        )

    async def create_revision_turn(
        self,
        turn_number: int,
        user_input: str,
        ai_response: str,
        section_modified: str,
        change_accepted: bool,
        tools_called: Optional[List[str]] = None,
    ) -> RevisionTurn:
        """Create a revision turn object for audit trail.

        Args:
            turn_number: Turn number in conversation
            user_input: User's request
            ai_response: AI's explanation
            section_modified: Section that was changed
            change_accepted: Whether user accepted the change
            tools_called: Tools used by AI in this turn

        Returns:
            RevisionTurn object
        """
        return RevisionTurn(
            turn=turn_number,
            user_input=user_input,
            ai_response=ai_response,
            section_modified=section_modified,
            change_accepted=change_accepted,
            timestamp=datetime.now(timezone.utc),
            tools_called=tools_called or [],
        )

    def calculate_revision_cost(self) -> float:
        """Calculate cost of current revision session.

        Returns:
            Total cost in USD based on reviser's token usage
        """
        return self.reviser.calculate_cost()
