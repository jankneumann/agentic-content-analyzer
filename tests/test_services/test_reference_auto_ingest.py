"""Tests for AutoIngestTrigger service."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.reference_auto_ingest import AutoIngestTrigger


class TestAutoIngestTrigger:
    def _make_ref(self, external_id="10.1234/test", id_type="doi", source_id=1):
        ref = MagicMock()
        ref.external_id = external_id
        ref.external_id_type = id_type
        ref.source_content_id = source_id
        return ref

    def _make_content(self, depth=0, source_id=None):
        content = MagicMock()
        content.metadata_json = {"auto_ingest_depth": depth}
        if source_id is not None:
            content.source_id = source_id
        return content

    @pytest.mark.asyncio
    async def test_disabled_returns_none(self):
        db = MagicMock()
        trigger = AutoIngestTrigger(db, enabled=False)
        result = await trigger.maybe_ingest(self._make_ref())
        assert result is None

    @pytest.mark.asyncio
    async def test_no_external_id_returns_none(self):
        db = MagicMock()
        trigger = AutoIngestTrigger(db, enabled=True)
        ref = self._make_ref()
        ref.external_id = None
        result = await trigger.maybe_ingest(ref)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_external_id_type_returns_none(self):
        db = MagicMock()
        trigger = AutoIngestTrigger(db, enabled=True)
        ref = self._make_ref()
        ref.external_id_type = None
        result = await trigger.maybe_ingest(ref)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_source_content_returns_none(self):
        db = MagicMock()
        db.get.return_value = None
        trigger = AutoIngestTrigger(db, enabled=True)
        result = await trigger.maybe_ingest(self._make_ref())
        assert result is None

    @pytest.mark.asyncio
    async def test_depth_limit_respected(self):
        source = self._make_content(depth=1)
        db = MagicMock()
        db.get.return_value = source

        trigger = AutoIngestTrigger(db, enabled=True, max_depth=1)
        result = await trigger.maybe_ingest(self._make_ref())
        assert result is None

    @pytest.mark.asyncio
    async def test_depth_zero_at_max_zero_blocked(self):
        """max_depth=0 means no auto-ingest even at depth 0."""
        source = self._make_content(depth=0)
        db = MagicMock()
        db.get.return_value = source

        trigger = AutoIngestTrigger(db, enabled=True, max_depth=0)
        result = await trigger.maybe_ingest(self._make_ref())
        assert result is None

    @pytest.mark.asyncio
    async def test_doi_auto_ingest_success(self):
        source = self._make_content(depth=0)
        ingested = self._make_content(source_id="DOI:10.1234/test")
        ingested.metadata_json = {}

        db = MagicMock()
        db.get.return_value = source
        # Mock the query chain for _find_and_tag_by_doi
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            ingested
        )

        trigger = AutoIngestTrigger(db, enabled=True, max_depth=1)

        with patch(
            "src.ingestion.orchestrator.ingest_scholar_paper",
            return_value=1,
        ):
            result = await trigger.maybe_ingest(self._make_ref())

        assert result is ingested
        assert ingested.metadata_json["ingestion_mode"] == "auto_ingest"
        assert ingested.metadata_json["auto_ingest_depth"] == 1

    @pytest.mark.asyncio
    async def test_doi_auto_ingest_zero_count_returns_none(self):
        source = self._make_content(depth=0)
        db = MagicMock()
        db.get.return_value = source

        trigger = AutoIngestTrigger(db, enabled=True, max_depth=1)

        with patch(
            "src.ingestion.orchestrator.ingest_scholar_paper",
            return_value=0,
        ):
            result = await trigger.maybe_ingest(self._make_ref())

        assert result is None

    @pytest.mark.asyncio
    async def test_doi_not_found_after_ingest_returns_none(self):
        """Orchestrator reports success but content not found by DOI query."""
        source = self._make_content(depth=0)
        db = MagicMock()
        db.get.return_value = source
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

        trigger = AutoIngestTrigger(db, enabled=True, max_depth=1)

        with patch(
            "src.ingestion.orchestrator.ingest_scholar_paper",
            return_value=1,
        ):
            result = await trigger.maybe_ingest(self._make_ref())

        assert result is None

    @pytest.mark.asyncio
    async def test_arxiv_deferred_returns_none(self):
        source = self._make_content(depth=0)
        db = MagicMock()
        db.get.return_value = source

        trigger = AutoIngestTrigger(db, enabled=True, max_depth=1)
        ref = self._make_ref(external_id="2301.12345", id_type="arxiv")
        result = await trigger.maybe_ingest(ref)
        assert result is None

    @pytest.mark.asyncio
    async def test_unsupported_id_type_returns_none(self):
        source = self._make_content(depth=0)
        db = MagicMock()
        db.get.return_value = source

        trigger = AutoIngestTrigger(db, enabled=True, max_depth=1)
        ref = self._make_ref(external_id="PMC12345", id_type="pmid")
        result = await trigger.maybe_ingest(ref)
        assert result is None

    @pytest.mark.asyncio
    async def test_error_returns_none_does_not_raise(self):
        source = self._make_content(depth=0)
        db = MagicMock()
        db.get.return_value = source

        trigger = AutoIngestTrigger(db, enabled=True)

        with patch(
            "src.ingestion.orchestrator.ingest_scholar_paper",
            side_effect=Exception("network error"),
        ):
            result = await trigger.maybe_ingest(self._make_ref())

        assert result is None

    @pytest.mark.asyncio
    async def test_depth_increments_correctly(self):
        """Verify depth=0 source produces depth=1 on ingested content."""
        source = self._make_content(depth=0)
        ingested = self._make_content()
        ingested.metadata_json = {}

        db = MagicMock()
        db.get.return_value = source
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            ingested
        )

        trigger = AutoIngestTrigger(db, enabled=True, max_depth=2)

        with patch(
            "src.ingestion.orchestrator.ingest_scholar_paper",
            return_value=1,
        ):
            result = await trigger.maybe_ingest(self._make_ref())

        assert result is ingested
        assert ingested.metadata_json["auto_ingest_depth"] == 1

    @pytest.mark.asyncio
    async def test_missing_metadata_json_treated_as_depth_zero(self):
        """Source with metadata_json=None should be treated as depth 0."""
        source = MagicMock()
        source.metadata_json = None

        ingested = self._make_content()
        ingested.metadata_json = {}

        db = MagicMock()
        db.get.return_value = source
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            ingested
        )

        trigger = AutoIngestTrigger(db, enabled=True, max_depth=1)

        with patch(
            "src.ingestion.orchestrator.ingest_scholar_paper",
            return_value=1,
        ):
            result = await trigger.maybe_ingest(self._make_ref())

        assert result is ingested
        assert ingested.metadata_json["auto_ingest_depth"] == 1

    def test_tag_auto_ingested_sets_metadata(self):
        db = MagicMock()
        trigger = AutoIngestTrigger(db, enabled=True)
        content = MagicMock()
        content.metadata_json = {"existing_key": "value"}

        trigger._tag_auto_ingested(content, 2)

        assert content.metadata_json["ingestion_mode"] == "auto_ingest"
        assert content.metadata_json["auto_ingest_depth"] == 2
        assert content.metadata_json["existing_key"] == "value"

    def test_tag_auto_ingested_none_metadata(self):
        db = MagicMock()
        trigger = AutoIngestTrigger(db, enabled=True)
        content = MagicMock()
        content.metadata_json = None

        trigger._tag_auto_ingested(content, 1)

        assert content.metadata_json["ingestion_mode"] == "auto_ingest"
        assert content.metadata_json["auto_ingest_depth"] == 1
