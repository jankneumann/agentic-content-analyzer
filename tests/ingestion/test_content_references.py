from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from unittest.mock import MagicMock

from src.ingestion.content_references import (
    _clear_session_content_references,
    _commit_session_content_references,
    _record_loaded_content_reference,
    _stage_session_content_references,
    collect_content_references,
    record_content_reference,
)
from src.models.content import Content, ContentSource, ContentStatus


@dataclass(eq=False)
class _Transaction:
    nested: bool
    parent: _Transaction | None = None


def _content(content_id: int, canonical_id: int | None = None) -> Content:
    return Content(
        id=content_id,
        source_type=ContentSource.RSS,
        source_id=f"rss:{content_id}",
        title="Item",
        markdown_content="Body",
        content_hash=str(content_id),
        status=ContentStatus.PARSED,
        canonical_id=canonical_id,
    )


def _publish(*contents: Content) -> set[int]:
    session = MagicMock()
    session.info = {}
    transaction = _Transaction(nested=False)
    session.get_nested_transaction.return_value = None
    session.get_transaction.return_value = transaction
    session.new = set(contents)
    session.dirty = set()
    with collect_content_references() as references:
        _stage_session_content_references(session, None)
        assert not references
        _commit_session_content_references(session)
        return set(references)


def test_collector_publishes_only_committed_canonical_ids() -> None:
    assert _publish(_content(11), _content(12, canonical_id=7)) == {7, 11}


def test_collector_records_preexisting_canonical_content_encountered_by_command() -> None:
    with collect_content_references() as references:
        _record_loaded_content_reference(MagicMock(), _content(12, canonical_id=7))

    assert references == {7}


def test_collector_records_content_from_non_orm_query_paths() -> None:
    with collect_content_references() as references:
        record_content_reference(12, 7)

    assert references == {7}


def test_collector_waits_for_outer_commit_after_savepoint_commit() -> None:
    session = MagicMock()
    session.info = {}
    outer = _Transaction(nested=False)
    nested = _Transaction(nested=True, parent=outer)
    session.get_nested_transaction.return_value = nested
    session.get_transaction.return_value = outer
    session.new = {_content(13)}
    session.dirty = set()

    with collect_content_references() as references:
        _stage_session_content_references(session, None)
        _commit_session_content_references(session)
        assert not references

        session.get_nested_transaction.return_value = None
        _commit_session_content_references(session)

    assert references == {13}


def test_collector_discards_only_rolled_back_savepoint_references() -> None:
    session = MagicMock()
    session.info = {}
    outer = _Transaction(nested=False)
    nested = _Transaction(nested=True, parent=outer)
    session.get_transaction.return_value = outer
    session.get_nested_transaction.return_value = None
    session.new = {_content(14)}
    session.dirty = set()

    with collect_content_references() as references:
        _stage_session_content_references(session, None)
        session.get_nested_transaction.return_value = nested
        session.new = {_content(15)}
        _stage_session_content_references(session, None)
        _clear_session_content_references(session)

        session.get_nested_transaction.return_value = None
        _commit_session_content_references(session)

    assert references == {14}


def test_collector_is_concurrency_isolated() -> None:
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda value: _publish(_content(value)), (21, 22)))

    assert results == [{21}, {22}]
