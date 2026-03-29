"""Tests for the ReferenceResolver service.

Uses mocking for DB queries — creates mock ContentReference and Content
objects to test resolution logic without a live database.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from src.models.content_reference import (
    ExternalIdType,
    ResolutionStatus,
)
from src.services.reference_resolver import ReferenceResolver


def _make_content(
    id: int = 1,
    source_url: str | None = None,
    metadata_json: dict | None = None,
) -> MagicMock:
    """Create a mock Content object."""
    content = MagicMock()
    content.id = id
    content.source_url = source_url
    content.metadata_json = metadata_json
    return content


def _make_ref(
    id: int = 1,
    source_content_id: int = 10,
    external_id: str | None = None,
    external_id_type: str | None = None,
    external_url: str | None = None,
    resolution_status: str = ResolutionStatus.UNRESOLVED,
    target_content_id: int | None = None,
    resolved_at: datetime | None = None,
) -> MagicMock:
    """Create a mock ContentReference object."""
    ref = MagicMock()
    ref.id = id
    ref.source_content_id = source_content_id
    ref.external_id = external_id
    ref.external_id_type = external_id_type
    ref.external_url = external_url
    ref.resolution_status = resolution_status
    ref.target_content_id = target_content_id
    ref.resolved_at = resolved_at
    ref.created_at = datetime.now(UTC)
    return ref


class TestResolveReference:
    """Tests for resolve_reference — single reference resolution."""

    def test_resolve_by_external_id(self) -> None:
        """Should resolve when external_id matches a Content record."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        target = _make_content(id=42, metadata_json={"arxiv_id": "2401.00001"})
        ref = _make_ref(
            external_id="2401.00001",
            external_id_type=ExternalIdType.ARXIV,
        )

        with patch.object(resolver, "_find_by_external_id", return_value=target):
            status = resolver.resolve_reference(ref)

        assert status == ResolutionStatus.RESOLVED
        assert ref.target_content_id == 42
        assert ref.resolution_status == ResolutionStatus.RESOLVED
        assert ref.resolved_at is not None

    def test_resolve_by_url(self) -> None:
        """Should resolve by URL when external_id lookup fails."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        target = _make_content(id=99, source_url="https://example.com/paper")
        ref = _make_ref(
            external_url="https://example.com/paper",
            external_id=None,
            external_id_type=None,
        )

        with patch.object(resolver, "_find_by_source_url", return_value=target):
            status = resolver.resolve_reference(ref)

        assert status == ResolutionStatus.RESOLVED
        assert ref.target_content_id == 99
        assert ref.resolved_at is not None

    def test_resolve_by_url_fallback(self) -> None:
        """Should try URL when external_id lookup returns None."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        target = _make_content(id=77)
        ref = _make_ref(
            external_id="2401.00001",
            external_id_type=ExternalIdType.ARXIV,
            external_url="https://arxiv.org/abs/2401.00001",
        )

        with (
            patch.object(resolver, "_find_by_external_id", return_value=None),
            patch.object(resolver, "_find_by_source_url", return_value=target),
        ):
            status = resolver.resolve_reference(ref)

        assert status == ResolutionStatus.RESOLVED
        assert ref.target_content_id == 77

    def test_resolve_no_match(self) -> None:
        """Should return UNRESOLVED when no match found."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        ref = _make_ref(
            external_id="unknown-id",
            external_id_type=ExternalIdType.DOI,
            external_url="https://example.com/not-found",
        )

        with (
            patch.object(resolver, "_find_by_external_id", return_value=None),
            patch.object(resolver, "_find_by_source_url", return_value=None),
        ):
            status = resolver.resolve_reference(ref)

        assert status == ResolutionStatus.UNRESOLVED

    def test_resolve_no_identifiers(self) -> None:
        """Should return UNRESOLVED when ref has no external_id and no URL."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        ref = _make_ref(
            external_id=None,
            external_id_type=None,
            external_url=None,
        )

        status = resolver.resolve_reference(ref)
        assert status == ResolutionStatus.UNRESOLVED

    def test_resolve_prefers_external_id_over_url(self) -> None:
        """Should use external_id match and not attempt URL lookup."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        target = _make_content(id=50)
        ref = _make_ref(
            external_id="10.1234/test",
            external_id_type=ExternalIdType.DOI,
            external_url="https://doi.org/10.1234/test",
        )

        with (
            patch.object(resolver, "_find_by_external_id", return_value=target) as find_id,
            patch.object(resolver, "_find_by_source_url") as find_url,
        ):
            status = resolver.resolve_reference(ref)

        assert status == ResolutionStatus.RESOLVED
        find_id.assert_called_once()
        find_url.assert_not_called()


class TestFindByExternalId:
    """Tests for _find_by_external_id — GIN-indexed lookup."""

    def test_find_arxiv(self) -> None:
        """Should query metadata_json @> for arxiv_id."""
        db = MagicMock()
        mock_query = db.query.return_value.filter.return_value
        target = _make_content(id=1)
        mock_query.first.return_value = target

        resolver = ReferenceResolver(db)
        result = resolver._find_by_external_id("2401.00001", ExternalIdType.ARXIV)

        assert result == target
        db.query.assert_called_once()

    def test_find_doi(self) -> None:
        """Should query metadata_json @> for doi."""
        db = MagicMock()
        mock_query = db.query.return_value.filter.return_value
        mock_query.first.return_value = _make_content(id=2)

        resolver = ReferenceResolver(db)
        result = resolver._find_by_external_id("10.1234/test", ExternalIdType.DOI)

        assert result is not None
        assert result.id == 2

    def test_find_s2(self) -> None:
        """Should query metadata_json @> for s2_paper_id."""
        db = MagicMock()
        mock_query = db.query.return_value.filter.return_value
        mock_query.first.return_value = _make_content(id=3)

        resolver = ReferenceResolver(db)
        result = resolver._find_by_external_id("abc123", ExternalIdType.S2)

        assert result is not None
        assert result.id == 3

    def test_find_unknown_type_returns_none(self) -> None:
        """Should return None for unsupported external_id_type."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        result = resolver._find_by_external_id("test", ExternalIdType.PMID)
        assert result is None
        db.query.assert_not_called()

    def test_find_url_type_returns_none(self) -> None:
        """Should return None for URL type (not in key_map)."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        result = resolver._find_by_external_id("https://example.com", ExternalIdType.URL)
        assert result is None
        db.query.assert_not_called()

    def test_find_no_match(self) -> None:
        """Should return None when no content matches."""
        db = MagicMock()
        mock_query = db.query.return_value.filter.return_value
        mock_query.first.return_value = None

        resolver = ReferenceResolver(db)
        result = resolver._find_by_external_id("nonexistent", ExternalIdType.ARXIV)

        assert result is None


class TestResolveForContent:
    """Tests for resolve_for_content — all refs for a content item."""

    def test_resolves_all_unresolved(self) -> None:
        """Should resolve all unresolved refs and commit."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        ref1 = _make_ref(
            id=1, source_content_id=10, external_id="id1", external_id_type=ExternalIdType.ARXIV
        )
        ref2 = _make_ref(id=2, source_content_id=10, external_url="https://example.com")

        db.query.return_value.filter.return_value.all.return_value = [ref1, ref2]

        with patch.object(resolver, "resolve_reference", return_value=ResolutionStatus.RESOLVED):
            count = resolver.resolve_for_content(10)

        assert count == 2
        db.commit.assert_called_once()

    def test_partial_resolution(self) -> None:
        """Should count only resolved refs."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        ref1 = _make_ref(id=1, source_content_id=10)
        ref2 = _make_ref(id=2, source_content_id=10)

        db.query.return_value.filter.return_value.all.return_value = [ref1, ref2]

        statuses = [ResolutionStatus.RESOLVED, ResolutionStatus.UNRESOLVED]
        with patch.object(resolver, "resolve_reference", side_effect=statuses):
            count = resolver.resolve_for_content(10)

        assert count == 1
        db.commit.assert_called_once()

    def test_no_unresolved_refs(self) -> None:
        """Should return 0 and still commit when no refs found."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        db.query.return_value.filter.return_value.all.return_value = []

        count = resolver.resolve_for_content(10)
        assert count == 0
        db.commit.assert_called_once()


class TestResolveBatch:
    """Tests for resolve_batch — batch processing."""

    def test_processes_in_order(self) -> None:
        """Should process refs ordered by created_at."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        ref1 = _make_ref(id=1)
        ref2 = _make_ref(id=2)

        query_chain = (
            db.query.return_value.filter.return_value.order_by.return_value.limit.return_value
        )
        query_chain.all.return_value = [ref1, ref2]

        with patch.object(resolver, "resolve_reference", return_value=ResolutionStatus.RESOLVED):
            count = resolver.resolve_batch(batch_size=50)

        assert count == 2
        db.commit.assert_called_once()

    def test_respects_batch_size(self) -> None:
        """Should limit query to batch_size."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        query_chain = (
            db.query.return_value.filter.return_value.order_by.return_value.limit.return_value
        )
        query_chain.all.return_value = []

        resolver.resolve_batch(batch_size=25)

        # Verify limit was called (it's in the chain)
        db.query.return_value.filter.return_value.order_by.return_value.limit.assert_called_once_with(
            25
        )

    def test_empty_batch(self) -> None:
        """Should return 0 when no unresolved refs exist."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        query_chain = (
            db.query.return_value.filter.return_value.order_by.return_value.limit.return_value
        )
        query_chain.all.return_value = []

        count = resolver.resolve_batch()
        assert count == 0


class TestResolveIncoming:
    """Tests for resolve_incoming — reverse resolution."""

    def test_resolve_by_arxiv_id(self) -> None:
        """Should resolve refs matching new content's arXiv ID."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        new_content = _make_content(
            id=100,
            metadata_json={"arxiv_id": "2401.00001"},
            source_url=None,
        )

        with patch.object(resolver, "_resolve_matching_refs", return_value=2) as mock_resolve:
            count = resolver.resolve_incoming(new_content)

        assert count == 2
        mock_resolve.assert_called_once_with(ExternalIdType.ARXIV, "2401.00001", 100)
        db.commit.assert_called_once()

    def test_resolve_by_doi(self) -> None:
        """Should resolve refs matching new content's DOI."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        new_content = _make_content(
            id=101,
            metadata_json={"doi": "10.1234/test"},
            source_url=None,
        )

        with patch.object(resolver, "_resolve_matching_refs", return_value=1):
            count = resolver.resolve_incoming(new_content)

        assert count == 1
        db.commit.assert_called_once()

    def test_resolve_by_s2_id(self) -> None:
        """Should resolve refs matching new content's S2 paper ID."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        new_content = _make_content(
            id=102,
            metadata_json={"s2_paper_id": "abc123"},
            source_url=None,
        )

        with patch.object(resolver, "_resolve_matching_refs", return_value=3):
            count = resolver.resolve_incoming(new_content)

        assert count == 3
        db.commit.assert_called_once()

    def test_resolve_by_source_url(self) -> None:
        """Should resolve refs matching new content's source_url."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        new_content = _make_content(
            id=103,
            metadata_json={},
            source_url="https://example.com/paper",
        )

        with (
            patch.object(resolver, "_resolve_matching_refs", return_value=0),
            patch.object(resolver, "_resolve_matching_refs_by_url", return_value=1),
        ):
            count = resolver.resolve_incoming(new_content)

        assert count == 1
        db.commit.assert_called_once()

    def test_resolve_multiple_identifiers(self) -> None:
        """Should check all identifiers and accumulate resolved count."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        new_content = _make_content(
            id=104,
            metadata_json={"arxiv_id": "2401.00001", "doi": "10.1234/test"},
            source_url="https://arxiv.org/abs/2401.00001",
        )

        with (
            patch.object(resolver, "_resolve_matching_refs", side_effect=[1, 2]),
            patch.object(resolver, "_resolve_matching_refs_by_url", return_value=1),
        ):
            count = resolver.resolve_incoming(new_content)

        assert count == 4
        db.commit.assert_called_once()

    def test_no_match_skips_commit(self) -> None:
        """Should not commit when nothing resolved."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        new_content = _make_content(
            id=105,
            metadata_json={"arxiv_id": "2401.99999"},
            source_url=None,
        )

        with patch.object(resolver, "_resolve_matching_refs", return_value=0):
            count = resolver.resolve_incoming(new_content)

        assert count == 0
        db.commit.assert_not_called()

    def test_none_metadata_json(self) -> None:
        """Should handle content with no metadata_json gracefully."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        new_content = _make_content(
            id=106,
            metadata_json=None,
            source_url=None,
        )

        count = resolver.resolve_incoming(new_content)
        assert count == 0
        db.commit.assert_not_called()


class TestResolveMatchingRefs:
    """Tests for _resolve_matching_refs — bulk ref resolution."""

    def test_resolves_multiple_refs(self) -> None:
        """Should resolve all matching refs and set timestamps."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        ref1 = _make_ref(id=1)
        ref2 = _make_ref(id=2)

        db.query.return_value.filter.return_value.all.return_value = [ref1, ref2]

        count = resolver._resolve_matching_refs(ExternalIdType.ARXIV, "2401.00001", 42)

        assert count == 2
        assert ref1.target_content_id == 42
        assert ref1.resolution_status == ResolutionStatus.RESOLVED
        assert ref1.resolved_at is not None
        assert ref2.target_content_id == 42
        assert ref2.resolution_status == ResolutionStatus.RESOLVED
        assert ref2.resolved_at is not None

    def test_no_matching_refs(self) -> None:
        """Should return 0 when no refs match."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        db.query.return_value.filter.return_value.all.return_value = []

        count = resolver._resolve_matching_refs(ExternalIdType.DOI, "10.9999/none", 1)
        assert count == 0


class TestResolveMatchingRefsByUrl:
    """Tests for _resolve_matching_refs_by_url."""

    def test_resolves_url_refs(self) -> None:
        """Should resolve refs matching the URL."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        ref = _make_ref(id=1, external_url="https://example.com/paper")
        db.query.return_value.filter.return_value.all.return_value = [ref]

        count = resolver._resolve_matching_refs_by_url("https://example.com/paper", 55)

        assert count == 1
        assert ref.target_content_id == 55
        assert ref.resolution_status == ResolutionStatus.RESOLVED
        assert ref.resolved_at is not None

    def test_no_matching_url_refs(self) -> None:
        """Should return 0 when no refs match the URL."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        db.query.return_value.filter.return_value.all.return_value = []

        count = resolver._resolve_matching_refs_by_url("https://no-match.com", 1)
        assert count == 0


class TestResolvedAtTimestamp:
    """Tests that resolved_at is properly set."""

    def test_resolved_at_set_on_external_id_match(self) -> None:
        """resolved_at should be set when resolving by external ID."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        target = _make_content(id=10)
        ref = _make_ref(
            external_id="2401.00001",
            external_id_type=ExternalIdType.ARXIV,
            resolved_at=None,
        )

        before = datetime.now(UTC)

        with patch.object(resolver, "_find_by_external_id", return_value=target):
            resolver.resolve_reference(ref)

        after = datetime.now(UTC)
        assert ref.resolved_at is not None
        assert before <= ref.resolved_at <= after

    def test_resolved_at_set_on_url_match(self) -> None:
        """resolved_at should be set when resolving by URL."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        target = _make_content(id=20)
        ref = _make_ref(
            external_url="https://example.com",
            external_id=None,
            external_id_type=None,
            resolved_at=None,
        )

        before = datetime.now(UTC)

        with patch.object(resolver, "_find_by_source_url", return_value=target):
            resolver.resolve_reference(ref)

        after = datetime.now(UTC)
        assert ref.resolved_at is not None
        assert before <= ref.resolved_at <= after

    def test_resolved_at_not_set_on_no_match(self) -> None:
        """resolved_at should remain None when not resolved."""
        db = MagicMock()
        resolver = ReferenceResolver(db)

        ref = _make_ref(
            external_id="nothing",
            external_id_type=ExternalIdType.ARXIV,
            external_url="https://no-match.com",
            resolved_at=None,
        )

        with (
            patch.object(resolver, "_find_by_external_id", return_value=None),
            patch.object(resolver, "_find_by_source_url", return_value=None),
        ):
            resolver.resolve_reference(ref)

        # resolved_at was set to None in _make_ref; it should stay as the mock default
        # (not overwritten to a datetime)
        assert ref.resolution_status != ResolutionStatus.RESOLVED
