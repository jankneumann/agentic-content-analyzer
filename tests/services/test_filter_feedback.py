"""Unit tests for the filter feedback emitter.

Uses in-memory fake Session so we don't need a real DB.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.models.content import Content
from src.models.filter_feedback_event import FilterFeedbackEvent
from src.services.filter_feedback import emit_feedback


class _FakeSession:
    def __init__(self, content: Content | None = None) -> None:
        self._content = content
        self.added: list[Any] = []
        self.flushed: int = 0

    def get(self, model: type, pk: Any) -> Any | None:
        if model is Content and self._content and self._content.id == pk:
            return self._content
        return None

    def add(self, row: Any) -> None:
        self.added.append(row)

    def flush(self) -> None:
        self.flushed += 1


def _content(**kw: Any) -> Content:
    c = Content()
    c.id = kw.get("id", 7)
    c.filter_score = kw.get("filter_score", 0.48)
    c.filter_decision = kw.get("filter_decision", "keep")
    c.filter_tier = kw.get("filter_tier", "embedding")
    return c


def test_emits_event_for_content_with_decision() -> None:
    content = _content()
    session = _FakeSession(content=content)
    payload = emit_feedback(
        session,
        content_id=7,
        persona_id="default",
        reviewer_decision="approve",
        reviewer_id="alice",
    )
    assert payload is not None
    assert payload.content_id == 7
    assert payload.reviewer_decision == "approve"
    assert payload.original_score == 0.48
    assert len(session.added) == 1
    assert isinstance(session.added[0], FilterFeedbackEvent)
    assert session.flushed == 1


def test_skip_when_content_has_no_filter_decision() -> None:
    content = _content(filter_decision=None, filter_score=None)
    session = _FakeSession(content=content)
    payload = emit_feedback(
        session,
        content_id=7,
        persona_id="default",
        reviewer_decision="reject",
    )
    assert payload is None
    assert session.added == []


def test_returns_none_when_content_not_found() -> None:
    session = _FakeSession(content=None)
    payload = emit_feedback(
        session,
        content_id=999,
        persona_id="default",
        reviewer_decision="approve",
    )
    assert payload is None
    assert session.added == []


def test_metadata_is_preserved() -> None:
    content = _content()
    session = _FakeSession(content=content)
    payload = emit_feedback(
        session,
        content_id=7,
        persona_id="ai-ml-technology",
        reviewer_decision="demote",
        metadata={"reason": "too shallow"},
    )
    assert payload is not None
    assert payload.metadata == {"reason": "too shallow"}
    row = session.added[0]
    assert row.metadata_json == {"reason": "too shallow"}


def test_reviewed_at_is_populated() -> None:
    from datetime import UTC

    content = _content()
    session = _FakeSession(content=content)
    before = datetime.now(UTC).replace(tzinfo=None)
    payload = emit_feedback(
        session,
        content_id=7,
        persona_id="default",
        reviewer_decision="approve",
    )
    after = datetime.now(UTC).replace(tzinfo=None)
    assert payload is not None
    assert before <= payload.reviewed_at <= after
