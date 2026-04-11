"""Tests for ReferenceGraphSync service.

All tests use mocked GraphDBProvider (AsyncMock) — no live graph DB needed.
Verifies fire-and-forget semantics: errors are logged, never raised.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.content_reference import ResolutionStatus
from src.services.reference_graph_sync import ReferenceGraphSync

# --- Helpers ---


def _make_ref(
    id: int = 1,
    source_content_id: int = 10,
    target_content_id: int | None = 20,
    reference_type: str = "cites",
    confidence: float = 0.95,
    resolution_status: str = ResolutionStatus.RESOLVED,
) -> MagicMock:
    """Create a mock ContentReference."""
    ref = MagicMock()
    ref.id = id
    ref.source_content_id = source_content_id
    ref.target_content_id = target_content_id
    ref.reference_type = reference_type
    ref.confidence = confidence
    ref.resolution_status = resolution_status
    return ref


def _make_provider(
    records: dict[str, str | None] | None = None,
    query_side_effect: Exception | None = None,
) -> MagicMock:
    """Create a mock GraphDBProvider.

    Args:
        records: mapping of content_id (str) -> uuid (str | None).
        query_side_effect: if set, execute_query raises this exception.
    """
    if records is None:
        records = {}

    provider = MagicMock()

    if query_side_effect:
        provider.execute_query = AsyncMock(side_effect=query_side_effect)
        provider.execute_write = AsyncMock(side_effect=query_side_effect)
    else:

        async def _execute_query(query: str, params: dict | None = None):  # type: ignore[no-untyped-def]
            if params:
                content_id = params.get("content_id")
                if content_id and content_id in records:
                    uuid_val = records[content_id]
                    if uuid_val is not None:
                        return [{"uuid": uuid_val}]
            return []

        provider.execute_query = AsyncMock(side_effect=_execute_query)
        provider.execute_write = AsyncMock(return_value={"relationships_created": 1})

    return provider


# --- Tests ---


class TestSyncReference:
    """Tests for sync_reference method."""

    @pytest.mark.asyncio
    async def test_sync_reference_resolved(self) -> None:
        """Syncs a resolved reference: finds both episodes, creates edge."""
        provider = _make_provider({"10": "uuid-source", "20": "uuid-target"})
        sync = ReferenceGraphSync(provider=provider)
        ref = _make_ref()

        await sync.sync_reference(ref)

        # 2x _find_episode_uuid (execute_query) + 1x _create_citation_edge (execute_write)
        assert provider.execute_query.call_count == 2
        assert provider.execute_write.call_count == 1

    @pytest.mark.asyncio
    async def test_sync_reference_unresolved_skipped(self) -> None:
        """Skips references that are not resolved."""
        provider = _make_provider()
        sync = ReferenceGraphSync(provider=provider)
        ref = _make_ref(resolution_status=ResolutionStatus.UNRESOLVED)

        await sync.sync_reference(ref)

        provider.execute_query.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_reference_external_skipped(self) -> None:
        """Skips references with EXTERNAL status."""
        provider = _make_provider()
        sync = ReferenceGraphSync(provider=provider)
        ref = _make_ref(resolution_status=ResolutionStatus.EXTERNAL)

        await sync.sync_reference(ref)

        provider.execute_query.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_reference_no_target_skipped(self) -> None:
        """Skips resolved references with no target_content_id."""
        provider = _make_provider()
        sync = ReferenceGraphSync(provider=provider)
        ref = _make_ref(target_content_id=None)

        await sync.sync_reference(ref)

        provider.execute_query.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_reference_no_provider(self) -> None:
        """Handles missing provider gracefully (no-op)."""
        sync = ReferenceGraphSync(provider=None)
        ref = _make_ref()

        # Should not raise
        await sync.sync_reference(ref)

    @pytest.mark.asyncio
    async def test_sync_reference_no_episode(self) -> None:
        """Handles missing Episode nodes in graph (logs debug, no edge created)."""
        # Source episode exists, target does not
        provider = _make_provider({"10": "uuid-source"})
        sync = ReferenceGraphSync(provider=provider)
        ref = _make_ref()

        await sync.sync_reference(ref)

        # 2 calls for _find_episode_uuid; no _create_citation_edge
        assert provider.execute_query.call_count == 2
        assert provider.execute_write.call_count == 0

    @pytest.mark.asyncio
    async def test_sync_reference_error_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """Errors are logged, not raised (fire-and-forget).

        Patches _create_citation_edge to raise — so the outer try/except
        in sync_reference catches it.
        """
        provider = _make_provider({"10": "uuid-s", "20": "uuid-t"})
        sync = ReferenceGraphSync(provider=provider)
        ref = _make_ref()

        # Make _create_citation_edge raise after episode lookups succeed
        sync._create_citation_edge = AsyncMock(side_effect=RuntimeError("Connection lost"))

        with caplog.at_level(logging.WARNING):
            # Must not raise
            await sync.sync_reference(ref)

        assert "Failed to sync citation edge for reference 1" in caplog.text


class TestSyncResolvedForContent:
    """Tests for sync_resolved_for_content method."""

    @pytest.mark.asyncio
    async def test_sync_resolved_for_content(self) -> None:
        """Syncs multiple resolved refs for a content item."""
        provider = _make_provider({"10": "uuid-source", "20": "uuid-t1", "30": "uuid-t2"})
        sync = ReferenceGraphSync(provider=provider)

        ref1 = _make_ref(id=1, target_content_id=20)
        ref2 = _make_ref(id=2, target_content_id=30)

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [ref1, ref2]

        count = await sync.sync_resolved_for_content(content_id=10, db=db)

        assert count == 2

    @pytest.mark.asyncio
    async def test_sync_resolved_for_content_no_provider(self) -> None:
        """Returns 0 when provider is not available."""
        sync = ReferenceGraphSync(provider=None)
        db = MagicMock()

        count = await sync.sync_resolved_for_content(content_id=10, db=db)

        assert count == 0
        db.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_resolved_for_content_no_db(self) -> None:
        """Returns 0 when db session is not provided."""
        provider = _make_provider()
        sync = ReferenceGraphSync(provider=provider)

        count = await sync.sync_resolved_for_content(content_id=10, db=None)

        assert count == 0

    @pytest.mark.asyncio
    async def test_sync_resolved_for_content_error_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """DB errors are logged, not raised."""
        provider = _make_provider()
        sync = ReferenceGraphSync(provider=provider)

        db = MagicMock()
        db.query.side_effect = RuntimeError("DB connection lost")

        with caplog.at_level(logging.WARNING):
            count = await sync.sync_resolved_for_content(content_id=10, db=db)

        assert count == 0
        assert "Failed to sync references for content 10" in caplog.text


class TestFindEpisodeUuid:
    """Tests for _find_episode_uuid method."""

    @pytest.mark.asyncio
    async def test_find_episode_uuid(self) -> None:
        """Correct Cypher query is called with content_id as string."""
        provider = _make_provider({"42": "abc-123"})
        sync = ReferenceGraphSync(provider=provider)

        uuid = await sync._find_episode_uuid(42)

        assert uuid == "abc-123"
        provider.execute_query.assert_called_once()
        call_args = provider.execute_query.call_args
        # content_id should be passed as string in params dict
        assert call_args.args[1]["content_id"] == "42"
        # Query should match Episode nodes
        assert "MATCH (e:Episode)" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_find_episode_uuid_not_found(self) -> None:
        """Returns None when no Episode matches."""
        provider = _make_provider()
        sync = ReferenceGraphSync(provider=provider)

        uuid = await sync._find_episode_uuid(999)

        assert uuid is None

    @pytest.mark.asyncio
    async def test_find_episode_uuid_error_returns_none(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Errors return None and log a warning."""
        provider = _make_provider(query_side_effect=RuntimeError("Connection refused"))
        sync = ReferenceGraphSync(provider=provider)

        with caplog.at_level(logging.WARNING):
            uuid = await sync._find_episode_uuid(42)

        assert uuid is None
        assert "Failed to find episode for content_id 42" in caplog.text


class TestCreateCitationEdge:
    """Tests for _create_citation_edge method."""

    @pytest.mark.asyncio
    async def test_create_citation_edge(self) -> None:
        """execute_write is called with correct parameters."""
        provider = _make_provider()
        sync = ReferenceGraphSync(provider=provider)

        await sync._create_citation_edge(
            source_uuid="uuid-src",
            target_uuid="uuid-tgt",
            reference_type="cites",
            confidence=0.9,
        )

        provider.execute_write.assert_called_once()
        call_args = provider.execute_write.call_args
        query = call_args.args[0]
        params = call_args.args[1]

        # Verify MERGE pattern
        assert "MERGE (s)-[r:CITES]->(t)" in query
        # Verify parameters
        assert params["source_uuid"] == "uuid-src"
        assert params["target_uuid"] == "uuid-tgt"
        assert params["reference_type"] == "cites"
        assert params["confidence"] == 0.9
