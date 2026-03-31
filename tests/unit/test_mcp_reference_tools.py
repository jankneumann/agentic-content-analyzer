"""Tests for MCP content reference tools.

Tests verify that the 4 reference MCP tools delegate correctly to
services and return well-formed JSON responses.  All database and
service interactions are mocked.

The ``mcp`` package is an optional dependency that may not be installed
in the test environment.  We mock the FastMCP import so the module can
be loaded without the real SDK.
"""

from __future__ import annotations

import json
import sys
import types
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Bootstrap: mock the ``mcp`` package so ``src.mcp_server`` can be imported
# even when the MCP SDK is not installed.
# ---------------------------------------------------------------------------

_mcp_module = types.ModuleType("mcp")
_mcp_server_module = types.ModuleType("mcp.server")
_mcp_fastmcp_module = types.ModuleType("mcp.server.fastmcp")


class _FakeFastMCP:
    """Minimal stand-in for FastMCP that makes ``@mcp.tool()`` a no-op decorator."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def tool(self) -> object:
        def decorator(fn: object) -> object:
            return fn

        return decorator

    def run(self) -> None:
        pass

    def sse_app(self) -> None:
        return None

    def streamable_http_app(self) -> None:
        return None


_mcp_fastmcp_module.FastMCP = _FakeFastMCP  # type: ignore[attr-defined]
_mcp_server_module.fastmcp = _mcp_fastmcp_module  # type: ignore[attr-defined]
_mcp_module.server = _mcp_server_module  # type: ignore[attr-defined]

# Only inject if the real module is not present
if "mcp" not in sys.modules:
    sys.modules["mcp"] = _mcp_module
    sys.modules["mcp.server"] = _mcp_server_module
    sys.modules["mcp.server.fastmcp"] = _mcp_fastmcp_module


# ---------------------------------------------------------------------------
# get_content_references
# ---------------------------------------------------------------------------


class TestGetContentReferences:
    """Tests for the get_content_references MCP tool."""

    @patch("src.storage.database.get_db")
    def test_outgoing_references(self, mock_get_db: MagicMock) -> None:
        """Returns outgoing refs (default direction) for a content item."""
        from src.mcp_server import get_content_references

        ref = MagicMock()
        ref.id = 1
        ref.reference_type = "cites"
        ref.external_id = "2301.12345"
        ref.external_id_type = "arxiv"
        ref.external_url = "https://arxiv.org/abs/2301.12345"
        ref.resolution_status = "resolved"
        ref.target_content_id = 42
        ref.confidence = 0.95

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [ref]
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = json.loads(get_content_references(content_id=10))

        assert result["count"] == 1
        assert result["direction"] == "outgoing"
        assert result["references"][0]["id"] == 1
        assert result["references"][0]["reference_type"] == "cites"
        assert result["references"][0]["external_id"] == "2301.12345"
        assert result["references"][0]["target_content_id"] == 42

    @patch("src.storage.database.get_db")
    def test_incoming_references(self, mock_get_db: MagicMock) -> None:
        """Returns incoming refs (what cites this) filtered by RESOLVED status."""
        from src.mcp_server import get_content_references

        ref = MagicMock()
        ref.id = 5
        ref.reference_type = "discusses"
        ref.external_id = "10.1234/foo"
        ref.external_id_type = "doi"
        ref.external_url = None
        ref.resolution_status = "resolved"
        ref.target_content_id = 10
        ref.confidence = 1.0

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = [ref]
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = json.loads(get_content_references(content_id=10, direction="incoming"))

        assert result["count"] == 1
        assert result["direction"] == "incoming"
        assert result["references"][0]["reference_type"] == "discusses"

    @patch("src.storage.database.get_db")
    def test_empty_references(self, mock_get_db: MagicMock) -> None:
        """Returns empty list when no references exist."""
        from src.mcp_server import get_content_references

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = json.loads(get_content_references(content_id=999))

        assert result["count"] == 0
        assert result["references"] == []


# ---------------------------------------------------------------------------
# extract_references
# ---------------------------------------------------------------------------


class TestExtractReferences:
    """Tests for the extract_references MCP tool."""

    @patch("src.storage.database.get_db")
    @patch("src.services.reference_extractor.ReferenceExtractor", autospec=False)
    def test_extract_stores_references(
        self, mock_extractor_cls: MagicMock, mock_get_db: MagicMock
    ) -> None:
        """Extracts and stores references when dry_run=False."""
        from src.mcp_server import extract_references

        content1 = MagicMock()
        content1.id = 1
        ref1 = MagicMock()

        mock_extractor = MagicMock()
        mock_extractor_cls.return_value = mock_extractor
        mock_extractor.extract_from_content.return_value = [ref1]
        mock_extractor.store_references.return_value = 1

        mock_db = MagicMock()
        mock_db.query.return_value.limit.return_value.all.return_value = [content1]
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = json.loads(extract_references())

        assert result["scanned"] == 1
        assert result["references_found"] == 1
        assert result["dry_run"] is False

    @patch("src.storage.database.get_db")
    @patch("src.services.reference_extractor.ReferenceExtractor", autospec=False)
    def test_extract_dry_run(self, mock_extractor_cls: MagicMock, mock_get_db: MagicMock) -> None:
        """Dry run counts but does not store references."""
        from src.mcp_server import extract_references

        content1 = MagicMock()
        content1.id = 1
        ref1 = MagicMock()
        ref2 = MagicMock()

        mock_extractor = MagicMock()
        mock_extractor_cls.return_value = mock_extractor
        mock_extractor.extract_from_content.return_value = [ref1, ref2]

        mock_db = MagicMock()
        mock_db.query.return_value.limit.return_value.all.return_value = [content1]
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = json.loads(extract_references(dry_run=True))

        assert result["scanned"] == 1
        assert result["references_found"] == 2
        assert result["dry_run"] is True
        mock_extractor.store_references.assert_not_called()

    @patch("src.storage.database.get_db")
    @patch("src.services.reference_extractor.ReferenceExtractor", autospec=False)
    def test_extract_no_content(
        self, mock_extractor_cls: MagicMock, mock_get_db: MagicMock
    ) -> None:
        """Returns zero counts when no content matches."""
        from src.mcp_server import extract_references

        mock_db = MagicMock()
        mock_db.query.return_value.limit.return_value.all.return_value = []
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = json.loads(extract_references())

        assert result["scanned"] == 0
        assert result["references_found"] == 0


# ---------------------------------------------------------------------------
# resolve_references
# ---------------------------------------------------------------------------


class TestResolveReferences:
    """Tests for the resolve_references MCP tool."""

    @patch("src.storage.database.get_db")
    @patch("src.services.reference_resolver.ReferenceResolver")
    def test_resolve_batch(self, mock_resolver_cls: MagicMock, mock_get_db: MagicMock) -> None:
        """Resolves a batch and returns the resolved count."""
        from src.mcp_server import resolve_references

        mock_resolver = MagicMock()
        mock_resolver_cls.return_value = mock_resolver
        mock_resolver.resolve_batch.return_value = 7

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = json.loads(resolve_references(batch_size=50))

        assert result["resolved"] == 7
        assert result["batch_size"] == 50
        mock_resolver.resolve_batch.assert_called_once_with(50)

    @patch("src.storage.database.get_db")
    @patch("src.services.reference_resolver.ReferenceResolver")
    def test_resolve_batch_default_size(
        self, mock_resolver_cls: MagicMock, mock_get_db: MagicMock
    ) -> None:
        """Uses default batch_size of 100."""
        from src.mcp_server import resolve_references

        mock_resolver = MagicMock()
        mock_resolver_cls.return_value = mock_resolver
        mock_resolver.resolve_batch.return_value = 0

        mock_db = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = json.loads(resolve_references())

        assert result["batch_size"] == 100
        mock_resolver.resolve_batch.assert_called_once_with(100)


# ---------------------------------------------------------------------------
# ingest_reference
# ---------------------------------------------------------------------------


class TestIngestReference:
    """Tests for the ingest_reference MCP tool."""

    @patch("src.storage.database.get_db")
    def test_not_found(self, mock_get_db: MagicMock) -> None:
        """Returns error when reference ID does not exist."""
        from src.mcp_server import ingest_reference

        mock_db = MagicMock()
        mock_db.get.return_value = None
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = json.loads(ingest_reference(reference_id=999))

        assert "error" in result
        assert "999" in result["error"]

    @patch("src.storage.database.get_db")
    def test_already_resolved(self, mock_get_db: MagicMock) -> None:
        """Returns already_resolved when ref is already resolved."""
        from src.mcp_server import ingest_reference

        ref = MagicMock()
        ref.resolution_status = "resolved"
        ref.target_content_id = 42

        mock_db = MagicMock()
        mock_db.get.return_value = ref
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = json.loads(ingest_reference(reference_id=1))

        assert result["status"] == "already_resolved"
        assert result["target_content_id"] == 42

    @patch("src.storage.database.get_db")
    def test_no_structured_id(self, mock_get_db: MagicMock) -> None:
        """Returns error when reference has no external_id for ingestion."""
        from src.mcp_server import ingest_reference

        ref = MagicMock()
        ref.resolution_status = "unresolved"
        ref.external_id = None
        ref.external_id_type = None

        mock_db = MagicMock()
        mock_db.get.return_value = ref
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        result = json.loads(ingest_reference(reference_id=1))

        assert "error" in result
        assert "structured ID" in result["error"]

    @patch("src.config.settings.get_settings")
    @patch("src.services.reference_auto_ingest.AutoIngestTrigger")
    @patch("src.storage.database.get_db")
    def test_successful_ingest(
        self,
        mock_get_db: MagicMock,
        mock_trigger_cls: MagicMock,
        mock_get_settings: MagicMock,
    ) -> None:
        """Successfully ingests content for an unresolved reference."""
        from src.mcp_server import ingest_reference

        ref = MagicMock()
        ref.resolution_status = "unresolved"
        ref.external_id = "2301.12345"
        ref.external_id_type = "arxiv"

        mock_db = MagicMock()
        mock_db.get.return_value = ref
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        mock_settings = MagicMock()
        mock_settings.reference_auto_ingest_max_depth = 1
        mock_get_settings.return_value = mock_settings

        ingested_content = MagicMock()
        ingested_content.id = 99

        mock_trigger = MagicMock()
        mock_trigger_cls.return_value = mock_trigger

        async def fake_ingest(r: object) -> object:
            return ingested_content

        mock_trigger.maybe_ingest.side_effect = fake_ingest

        result = json.loads(ingest_reference(reference_id=1))

        assert result["status"] == "ingested"
        assert result["content_id"] == 99
        # Verify trigger was created with enabled=True (ad-hoc, independent of setting)
        mock_trigger_cls.assert_called_once_with(
            db=mock_db,
            enabled=True,
            max_depth=1,
        )

    @patch("src.config.settings.get_settings")
    @patch("src.services.reference_auto_ingest.AutoIngestTrigger")
    @patch("src.storage.database.get_db")
    def test_ingestion_failed(
        self,
        mock_get_db: MagicMock,
        mock_trigger_cls: MagicMock,
        mock_get_settings: MagicMock,
    ) -> None:
        """Returns ingestion_failed when maybe_ingest returns None."""
        from src.mcp_server import ingest_reference

        ref = MagicMock()
        ref.resolution_status = "unresolved"
        ref.external_id = "10.1234/foo"
        ref.external_id_type = "doi"

        mock_db = MagicMock()
        mock_db.get.return_value = ref
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        mock_settings = MagicMock()
        mock_settings.reference_auto_ingest_max_depth = 1
        mock_get_settings.return_value = mock_settings

        mock_trigger = MagicMock()
        mock_trigger_cls.return_value = mock_trigger

        async def fake_ingest(r: object) -> None:
            return None

        mock_trigger.maybe_ingest.side_effect = fake_ingest

        result = json.loads(ingest_reference(reference_id=1))

        assert result["status"] == "ingestion_failed"
