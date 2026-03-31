"""Tests for ReferenceGraphSync service.

All tests use mocked Neo4j driver (AsyncMock) — no live Neo4j needed.
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


def _make_session(
    records: dict[str, str | None] | None = None,
    run_side_effect: Exception | None = None,
) -> MagicMock:
    """Create an async context manager session mock.

    The neo4j async driver's session() returns an async context manager
    (not a coroutine), so driver.session must be a regular MagicMock
    that returns an object with __aenter__/__aexit__.

    Args:
        records: mapping of content_id (str) -> uuid (str | None).
        run_side_effect: if set, session.run raises this exception.
    """
    if records is None:
        records = {}

    session = AsyncMock()

    if run_side_effect:
        session.run = AsyncMock(side_effect=run_side_effect)
    else:

        async def _run(query: str, **kwargs):  # type: ignore[no-untyped-def]
            result = AsyncMock()
            content_id = kwargs.get("content_id")
            if content_id and content_id in records:
                uuid_val = records[content_id]
                if uuid_val is not None:
                    result.single.return_value = {"uuid": uuid_val}
                else:
                    result.single.return_value = None
            else:
                result.single.return_value = None
            return result

        session.run = AsyncMock(side_effect=_run)

    # Make it work as async context manager
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return session


def _make_driver(
    records: dict[str, str | None] | None = None,
    run_side_effect: Exception | None = None,
) -> MagicMock:
    """Create a mock Neo4j driver whose .session() returns an async CM."""
    session = _make_session(records=records, run_side_effect=run_side_effect)
    driver = MagicMock()
    # driver.session() must return an async context manager (not a coroutine)
    driver.session.return_value = session
    return driver, session


# --- Tests ---


class TestSyncReference:
    """Tests for sync_reference method."""

    @pytest.mark.asyncio
    async def test_sync_reference_resolved(self) -> None:
        """Syncs a resolved reference: finds both episodes, creates edge."""
        driver, session = _make_driver({"10": "uuid-source", "20": "uuid-target"})
        sync = ReferenceGraphSync(driver=driver)
        ref = _make_ref()

        await sync.sync_reference(ref)

        # 2x _find_episode_uuid + 1x _create_citation_edge
        assert session.run.call_count == 3

    @pytest.mark.asyncio
    async def test_sync_reference_unresolved_skipped(self) -> None:
        """Skips references that are not resolved."""
        driver, _session = _make_driver()
        sync = ReferenceGraphSync(driver=driver)
        ref = _make_ref(resolution_status=ResolutionStatus.UNRESOLVED)

        await sync.sync_reference(ref)

        driver.session.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_reference_external_skipped(self) -> None:
        """Skips references with EXTERNAL status."""
        driver, _session = _make_driver()
        sync = ReferenceGraphSync(driver=driver)
        ref = _make_ref(resolution_status=ResolutionStatus.EXTERNAL)

        await sync.sync_reference(ref)

        driver.session.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_reference_no_target_skipped(self) -> None:
        """Skips resolved references with no target_content_id."""
        driver, _session = _make_driver()
        sync = ReferenceGraphSync(driver=driver)
        ref = _make_ref(target_content_id=None)

        await sync.sync_reference(ref)

        driver.session.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_reference_no_driver(self) -> None:
        """Handles missing driver gracefully (no-op)."""
        sync = ReferenceGraphSync(driver=None)
        ref = _make_ref()

        # Should not raise
        await sync.sync_reference(ref)

    @pytest.mark.asyncio
    async def test_sync_reference_no_episode(self) -> None:
        """Handles missing Episode nodes in Neo4j (logs debug, no edge created)."""
        # Source episode exists, target does not
        driver, session = _make_driver({"10": "uuid-source"})
        sync = ReferenceGraphSync(driver=driver)
        ref = _make_ref()

        await sync.sync_reference(ref)

        # Only 2 calls for _find_episode_uuid; no _create_citation_edge
        assert session.run.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_reference_error_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """Errors are logged, not raised (fire-and-forget).

        Patches _find_episode_uuid to succeed, then _create_citation_edge
        to raise — so the outer try/except in sync_reference catches it.
        """
        driver, _session = _make_driver({"10": "uuid-s", "20": "uuid-t"})
        sync = ReferenceGraphSync(driver=driver)
        ref = _make_ref()

        # Make _create_citation_edge raise after episode lookups succeed
        original_create = sync._create_citation_edge
        sync._create_citation_edge = AsyncMock(side_effect=RuntimeError("Neo4j connection lost"))

        with caplog.at_level(logging.WARNING):
            # Must not raise
            await sync.sync_reference(ref)

        assert "Failed to sync citation edge for reference 1" in caplog.text


class TestSyncResolvedForContent:
    """Tests for sync_resolved_for_content method."""

    @pytest.mark.asyncio
    async def test_sync_resolved_for_content(self) -> None:
        """Syncs multiple resolved refs for a content item."""
        driver, _session = _make_driver({"10": "uuid-source", "20": "uuid-t1", "30": "uuid-t2"})
        sync = ReferenceGraphSync(driver=driver)

        ref1 = _make_ref(id=1, target_content_id=20)
        ref2 = _make_ref(id=2, target_content_id=30)

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [ref1, ref2]

        count = await sync.sync_resolved_for_content(content_id=10, db=db)

        assert count == 2

    @pytest.mark.asyncio
    async def test_sync_resolved_for_content_no_driver(self) -> None:
        """Returns 0 when driver is not available."""
        sync = ReferenceGraphSync(driver=None)
        db = MagicMock()

        count = await sync.sync_resolved_for_content(content_id=10, db=db)

        assert count == 0
        db.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_resolved_for_content_no_db(self) -> None:
        """Returns 0 when db session is not provided."""
        driver, _session = _make_driver()
        sync = ReferenceGraphSync(driver=driver)

        count = await sync.sync_resolved_for_content(content_id=10, db=None)

        assert count == 0

    @pytest.mark.asyncio
    async def test_sync_resolved_for_content_error_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """DB errors are logged, not raised."""
        driver, _session = _make_driver()
        sync = ReferenceGraphSync(driver=driver)

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
        driver, session = _make_driver({"42": "abc-123"})
        sync = ReferenceGraphSync(driver=driver)

        uuid = await sync._find_episode_uuid(42)

        assert uuid == "abc-123"
        session.run.assert_called_once()
        call_args = session.run.call_args
        # content_id should be passed as string
        assert call_args.kwargs["content_id"] == "42"
        # Query should match Episode nodes
        assert "MATCH (e:Episode)" in call_args.args[0]

    @pytest.mark.asyncio
    async def test_find_episode_uuid_not_found(self) -> None:
        """Returns None when no Episode matches."""
        driver, _session = _make_driver()
        sync = ReferenceGraphSync(driver=driver)

        uuid = await sync._find_episode_uuid(999)

        assert uuid is None

    @pytest.mark.asyncio
    async def test_find_episode_uuid_error_returns_none(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Errors return None and log a warning."""
        driver, _session = _make_driver(run_side_effect=RuntimeError("Connection refused"))
        sync = ReferenceGraphSync(driver=driver)

        with caplog.at_level(logging.WARNING):
            uuid = await sync._find_episode_uuid(42)

        assert uuid is None
        assert "Failed to find episode for content_id 42" in caplog.text


class TestCreateCitationEdge:
    """Tests for _create_citation_edge method."""

    @pytest.mark.asyncio
    async def test_create_citation_edge(self) -> None:
        """MERGE query is called with correct parameters."""
        driver, session = _make_driver()
        sync = ReferenceGraphSync(driver=driver)

        await sync._create_citation_edge(
            source_uuid="uuid-src",
            target_uuid="uuid-tgt",
            reference_type="cites",
            confidence=0.9,
        )

        session.run.assert_called_once()
        call_args = session.run.call_args
        query = call_args.args[0]

        # Verify MERGE pattern
        assert "MERGE (s)-[r:CITES]->(t)" in query
        # Verify parameters
        assert call_args.kwargs["source_uuid"] == "uuid-src"
        assert call_args.kwargs["target_uuid"] == "uuid-tgt"
        assert call_args.kwargs["reference_type"] == "cites"
        assert call_args.kwargs["confidence"] == 0.9
