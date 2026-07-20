"""Collect canonical content IDs committed during an ingestion command."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session, SessionTransaction

from src.models.content import Content


class ContentReferences(set[int]):
    """Canonical ID set with touched-row identity normalization."""

    def __init__(self) -> None:
        super().__init__()
        self._canonical_by_touched: dict[int, int] = {}

    def record(self, mappings: dict[int, int]) -> None:
        self._canonical_by_touched.update(mappings)
        self.clear()
        self.update(
            self.canonicalize(canonical_id) for canonical_id in self._canonical_by_touched.values()
        )

    def canonicalize(self, content_id: int) -> int:
        seen: set[int] = set()
        while content_id not in seen:
            seen.add(content_id)
            canonical_id = self._canonical_by_touched.get(content_id, content_id)
            if canonical_id == content_id:
                return content_id
            content_id = canonical_id
        return content_id


_ACTIVE_REFERENCES: ContextVar[ContentReferences | None] = ContextVar(
    "ingestion_content_references",
    default=None,
)
_STAGED_KEY = "aca_ingestion_content_references"
type StagedReferences = list[tuple[ContentReferences, dict[int, int]]]


@contextmanager
def collect_content_references() -> Iterator[ContentReferences]:
    """Collect canonical IDs published by commits in the current context."""
    references = ContentReferences()
    token = _ACTIVE_REFERENCES.set(references)
    try:
        yield references
    finally:
        _ACTIVE_REFERENCES.reset(token)


def record_content_reference(content_id: int, canonical_id: int | None = None) -> None:
    """Record content found through a query path that does not load an ORM entity."""
    collector = _ACTIVE_REFERENCES.get()
    resolved_canonical_id = canonical_id or content_id
    if (
        collector is not None
        and isinstance(content_id, int)
        and content_id > 0
        and isinstance(resolved_canonical_id, int)
        and resolved_canonical_id > 0
    ):
        collector.record({content_id: resolved_canonical_id})


def _record_loaded_content_reference(_session: Session, instance: object) -> None:
    """Record existing content encountered while an ingestion command is active."""

    if not isinstance(instance, Content):
        return
    record_content_reference(instance.id, instance.canonical_id)


def _stage_session_content_references(session: Session, _flush_context: Any) -> None:
    collector = _ACTIVE_REFERENCES.get()
    if collector is None:
        return
    mappings = {
        content.id: content.canonical_id or content.id
        for content in (*session.new, *session.dirty)
        if isinstance(content, Content)
        and isinstance(content.id, int)
        and content.id > 0
        and isinstance(content.canonical_id or content.id, int)
        and (content.canonical_id or content.id) > 0
    }
    if not mappings:
        return
    transaction = _current_transaction(session)
    if transaction is None:
        return
    transactions: dict[SessionTransaction, StagedReferences] = session.info.setdefault(
        _STAGED_KEY, {}
    )
    staged = transactions.setdefault(transaction, [])
    for target, target_mappings in staged:
        if target is collector:
            target_mappings.update(mappings)
            break
    else:
        staged.append((collector, mappings))


def _commit_session_content_references(session: Session) -> None:
    transaction = _current_transaction(session)
    transactions: dict[SessionTransaction, StagedReferences] = session.info.get(_STAGED_KEY, {})
    if transaction is None:
        return
    staged = transactions.pop(transaction, [])
    if transaction.nested and transaction.parent is not None:
        parent_staged = transactions.setdefault(transaction.parent, [])
        for collector, mappings in staged:
            _merge_staged(parent_staged, collector, mappings)
        return
    for collector, mappings in staged:
        collector.record(mappings)
    session.info.pop(_STAGED_KEY, None)


def _clear_session_content_references(session: Session) -> None:
    transaction = _current_transaction(session)
    transactions: dict[SessionTransaction, StagedReferences] = session.info.get(_STAGED_KEY, {})
    if transaction is not None:
        transactions.pop(transaction, None)
    if not transactions:
        session.info.pop(_STAGED_KEY, None)


def _current_transaction(session: Session) -> SessionTransaction | None:
    return session.get_nested_transaction() or session.get_transaction()


def _merge_staged(
    staged: StagedReferences,
    collector: ContentReferences,
    mappings: dict[int, int],
) -> None:
    for target, target_mappings in staged:
        if target is collector:
            target_mappings.update(mappings)
            return
    staged.append((collector, dict(mappings)))


event.listen(Session, "after_flush", _stage_session_content_references)
event.listen(Session, "after_commit", _commit_session_content_references)
event.listen(Session, "after_rollback", _clear_session_content_references)
event.listen(Session, "loaded_as_persistent", _record_loaded_content_reference)
