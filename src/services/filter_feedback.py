"""Filter review feedback emission.

When a reviewer approves / rejects / promotes / demotes a content row in the
digest or content-review UI, we log an event pairing the reviewer decision
with the original filter score/decision. v1 is fire-and-forget — we write to
``filter_feedback_events`` and emit a log record. A future change may train
calibration from this log.

This service is intentionally standalone: any review workflow (digest review,
bulk re-ranking, user thumbs up/down) can call ``emit_feedback`` without
coupling to the review_service internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sqlalchemy.orm import Session

from src.models.content import Content
from src.models.filter_feedback_event import FilterFeedbackEvent
from src.utils.logging import get_logger

logger = get_logger(__name__)


ReviewerDecision = Literal["approve", "reject", "promote", "demote"]


@dataclass(frozen=True)
class FeedbackPayload:
    """Payload that mirrors contracts/events/filter.review.feedback.schema.json."""

    content_id: int
    persona_id: str
    original_score: float
    original_decision: str
    original_tier: str | None
    reviewer_decision: ReviewerDecision
    reviewer_id: str | None
    reviewed_at: datetime
    metadata: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_id": self.content_id,
            "persona_id": self.persona_id,
            "original_score": self.original_score,
            "original_decision": self.original_decision,
            "original_tier": self.original_tier,
            "reviewer_decision": self.reviewer_decision,
            "reviewer_id": self.reviewer_id,
            "reviewed_at": self.reviewed_at.isoformat(),
            "metadata": self.metadata,
        }


def emit_feedback(
    db: Session,
    *,
    content_id: int,
    persona_id: str,
    reviewer_decision: ReviewerDecision,
    reviewer_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> FeedbackPayload | None:
    """Record a reviewer's decision alongside the original filter score.

    Returns the payload that was written, or ``None`` if the content row
    has no recorded filter decision (nothing to compare against).
    """
    content = db.get(Content, content_id)
    if content is None:
        logger.warning(
            "filter_feedback: content not found",
            extra={"content_id": content_id},
        )
        return None
    if content.filter_decision is None or content.filter_score is None:
        # No original decision to pair with — skip silently.
        return None

    payload = FeedbackPayload(
        content_id=content.id,
        persona_id=persona_id,
        original_score=float(content.filter_score),
        original_decision=str(content.filter_decision),
        original_tier=str(content.filter_tier) if content.filter_tier else None,
        reviewer_decision=reviewer_decision,
        reviewer_id=reviewer_id,
        reviewed_at=datetime.utcnow(),
        metadata=metadata,
    )
    row = FilterFeedbackEvent(
        content_id=payload.content_id,
        persona_id=payload.persona_id,
        original_score=payload.original_score,
        original_decision=payload.original_decision,
        original_tier=payload.original_tier,
        reviewer_decision=payload.reviewer_decision,
        reviewer_id=payload.reviewer_id,
        reviewed_at=payload.reviewed_at,
        metadata_json=payload.metadata,
    )
    db.add(row)
    db.flush()
    logger.info("filter.review.feedback", extra=payload.to_dict())
    return payload
