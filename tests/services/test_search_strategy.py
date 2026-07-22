"""Tests for backend-specific keyword search strategies."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.services.search_strategy import ParadeDBBM25Strategy


def test_paradedb_normalizes_query_language_punctuation() -> None:
    """API free text cannot be interpreted as malformed ParadeDB syntax."""
    session = MagicMock()
    session.execute.return_value = [SimpleNamespace(id=1, score=0.5, content_id=2)]

    results = ParadeDBBM25Strategy(session).search(r"[^a-z0-9\s-]")

    assert results == [(1, 0.5, 2)]
    assert session.execute.call_args.args[1]["query"] == "a z0 9 s"


def test_paradedb_skips_queries_without_searchable_terms() -> None:
    """Punctuation-only input produces an empty result without a DB query."""
    session = MagicMock()

    assert ParadeDBBM25Strategy(session).search("[({?!})]") == []
    session.execute.assert_not_called()
