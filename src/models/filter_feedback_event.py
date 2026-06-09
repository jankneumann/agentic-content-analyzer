"""FilterFeedbackEvent — append-only log of reviewer vs filter decisions.

Every row captures the original filter score/decision alongside the reviewer's
action (approve / reject / promote / demote). v1 only writes rows; a future
change may train a calibration model from this log.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from src.models.base import Base


class FilterFeedbackEvent(Base):  # type: ignore[valid-type, misc]
    __tablename__ = "filter_feedback_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    content_id = Column(
        Integer,
        ForeignKey("contents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    persona_id = Column(String(200), nullable=False)

    original_score = Column(Float, nullable=False)
    original_decision = Column(String(20), nullable=False)
    original_tier = Column(String(20), nullable=True)

    reviewer_decision = Column(String(20), nullable=False)
    reviewer_id = Column(String(200), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    metadata_json = Column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<FilterFeedbackEvent(id={self.id}, content_id={self.content_id}, "
            f"persona_id={self.persona_id!r}, reviewer_decision={self.reviewer_decision!r})>"
        )
