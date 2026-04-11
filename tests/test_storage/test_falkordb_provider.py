"""Tests for FalkorDBGraphDBProvider."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.storage.falkordb_provider import FalkorDBGraphDBProvider
from src.storage.graph_provider import GraphDBProvider


class TestConstruction:
    """Test provider construction and lazy connection."""

    @patch("src.storage.falkordb_provider.falkordb", create=True)
    def test_init_does_not_connect(self, mock_falkordb_mod):
        """Provider init should NOT eagerly connect (lazy pattern)."""
        provider = FalkorDBGraphDBProvider(
            host="myhost", port=6379, database="testdb", mode="local"
        )
        # falkordb module should NOT have been imported yet
        mock_falkordb_mod.FalkorDB.assert_not_called()
        assert provider._client is None
        assert provider._graph is None

    def test_ensure_connected_creates_client(self):
        """First call to _ensure_connected should create client and graph."""
        mock_client = MagicMock()
        mock_graph = MagicMock()
        mock_falkordb_mod = MagicMock()
        mock_falkordb_mod.FalkorDB.return_value = mock_client
        mock_client.select_graph.return_value = mock_graph

        provider = FalkorDBGraphDBProvider(
            host="myhost", port=6379, database="testdb", mode="local"
        )

        import sys
        with patch.dict(sys.modules, {"falkordb": mock_falkordb_mod}):
            result = provider._ensure_connected()

        mock_falkordb_mod.FalkorDB.assert_called_once_with(
            host="myhost", port=6379, username=None, password=None
        )
        mock_client.select_graph.assert_called_once_with("testdb")
        assert result is mock_graph

    def test_ensure_connected_reuses_existing(self):
        """Subsequent calls should reuse existing connection."""
        provider = FalkorDBGraphDBProvider(host="h", port=6379, database="db")

        # Pre-set client and graph to simulate first connection
        mock_graph = MagicMock()
        provider._client = MagicMock()
        provider._graph = mock_graph

        result1 = provider._ensure_connected()
        result2 = provider._ensure_connected()

        assert result1 is mock_graph
        assert result2 is mock_graph

    def test_stores_mode_explicitly(self):
        """Mode should come from constructor, not heuristic."""
        provider = FalkorDBGraphDBProvider(
            host="remote.falkor.io", port=6379, mode="cloud"
        )
        assert provider._mode == "cloud"

    def test_isinstance_protocol(self):
        """FalkorDBGraphDBProvider should satisfy GraphDBProvider protocol."""
        provider = FalkorDBGraphDBProvider.__new__(FalkorDBGraphDBProvider)
        assert isinstance(provider, GraphDBProvider)


class TestCreateGraphitiDriver:
    """Test graphiti-core FalkorDriver construction."""

    @patch("src.storage.falkordb_provider.FalkorDriver", create=True)
    def test_creates_falkor_driver(self, mock_driver_cls):
        mock_driver_cls.return_value = MagicMock()

        with patch(
            "graphiti_core.driver.falkordb_driver.FalkorDriver", mock_driver_cls
        ):
            provider = FalkorDBGraphDBProvider(
                host="h", port=6379, username="u", password="p", database="db"
            )
            driver = provider.create_graphiti_driver()

        mock_driver_cls.assert_called_once_with(
            host="h", port=6379, username="u", password="p", database="db"
        )
        assert driver is mock_driver_cls.return_value

    @patch("src.storage.falkordb_provider.FalkorDriver", create=True)
    def test_none_credentials_become_empty_string(self, mock_driver_cls):
        """None username/password should be passed as empty string to FalkorDriver."""
        with patch(
            "graphiti_core.driver.falkordb_driver.FalkorDriver", mock_driver_cls
        ):
            provider = FalkorDBGraphDBProvider(
                host="h", port=6379, username=None, password=None, database="db"
            )
            provider.create_graphiti_driver()

        call_kwargs = mock_driver_cls.call_args
        assert call_kwargs[1]["username"] == "" or call_kwargs[0][2] == ""


class TestExecuteQuery:
    """Test read query execution."""

    @pytest.mark.asyncio
    async def test_execute_query_returns_dicts(self):
        """Query results should be converted to list of dicts."""
        provider = FalkorDBGraphDBProvider(host="h", port=6379, database="db")

        mock_graph = MagicMock()
        mock_result = MagicMock()
        mock_result.result_set = [["uuid-1", "Test Title"]]
        mock_result.header = [(1, "uuid"), (1, "title")]
        mock_graph.query.return_value = mock_result
        provider._graph = mock_graph
        provider._client = MagicMock()

        records = await provider.execute_query(
            "MATCH (n) RETURN n.uuid AS uuid, n.name AS title"
        )

        assert records == [{"uuid": "uuid-1", "title": "Test Title"}]
        mock_graph.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_empty_result(self):
        """Empty result set should return empty list."""
        provider = FalkorDBGraphDBProvider(host="h", port=6379, database="db")

        mock_graph = MagicMock()
        mock_result = MagicMock()
        mock_result.result_set = []
        mock_graph.query.return_value = mock_result
        provider._graph = mock_graph
        provider._client = MagicMock()

        records = await provider.execute_query("MATCH (n) RETURN n")
        assert records == []

    @pytest.mark.asyncio
    async def test_execute_query_with_params(self):
        """Parameters should be passed through to graph.query."""
        provider = FalkorDBGraphDBProvider(host="h", port=6379, database="db")

        mock_graph = MagicMock()
        mock_result = MagicMock()
        mock_result.result_set = []
        mock_graph.query.return_value = mock_result
        provider._graph = mock_graph
        provider._client = MagicMock()

        await provider.execute_query("MATCH (n {id: $id}) RETURN n", {"id": "123"})

        mock_graph.query.assert_called_once_with(
            "MATCH (n {id: $id}) RETURN n", params={"id": "123"}
        )

    @pytest.mark.asyncio
    async def test_execute_query_string_headers(self):
        """Handle headers that are plain strings (not tuples)."""
        provider = FalkorDBGraphDBProvider(host="h", port=6379, database="db")

        mock_graph = MagicMock()
        mock_result = MagicMock()
        mock_result.result_set = [["value1"]]
        mock_result.header = ["col_name"]  # Plain strings, not tuples
        mock_graph.query.return_value = mock_result
        provider._graph = mock_graph
        provider._client = MagicMock()

        records = await provider.execute_query("RETURN 1 AS col_name")
        assert records == [{"col_name": "value1"}]


class TestExecuteWrite:
    """Test write query execution."""

    @pytest.mark.asyncio
    async def test_execute_write_returns_stats(self):
        """Write should return node/relationship/property counts."""
        provider = FalkorDBGraphDBProvider(host="h", port=6379, database="db")

        mock_graph = MagicMock()
        mock_result = MagicMock()
        mock_result.nodes_created = 2
        mock_result.relationships_created = 1
        mock_result.properties_set = 5
        mock_graph.query.return_value = mock_result
        provider._graph = mock_graph
        provider._client = MagicMock()

        stats = await provider.execute_write("CREATE (n:Test {name: 'foo'})")
        assert stats == {
            "nodes_created": 2,
            "relationships_created": 1,
            "properties_set": 5,
        }

    @pytest.mark.asyncio
    async def test_execute_write_missing_attrs_default_zero(self):
        """If result lacks stats attributes, should default to 0."""
        provider = FalkorDBGraphDBProvider(host="h", port=6379, database="db")

        mock_graph = MagicMock()
        mock_result = MagicMock(spec=[])  # No attributes
        mock_graph.query.return_value = mock_result
        provider._graph = mock_graph
        provider._client = MagicMock()

        stats = await provider.execute_write("CREATE (n:Test)")
        assert stats == {"nodes_created": 0, "relationships_created": 0, "properties_set": 0}


class TestHealthCheck:
    """Test health check."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Health check should return True when backend responds."""
        provider = FalkorDBGraphDBProvider(host="h", port=6379, database="db")

        mock_graph = MagicMock()
        mock_graph.query.return_value = MagicMock()
        provider._graph = mock_graph
        provider._client = MagicMock()

        assert await provider.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Health check should return False on connection error."""
        provider = FalkorDBGraphDBProvider(host="h", port=6379, database="db")

        mock_graph = MagicMock()
        mock_graph.query.side_effect = ConnectionError("refused")
        provider._graph = mock_graph
        provider._client = MagicMock()

        assert await provider.health_check() is False

    @pytest.mark.asyncio
    async def test_health_check_triggers_lazy_connect(self):
        """Health check on fresh provider should trigger _ensure_connected."""
        provider = FalkorDBGraphDBProvider(host="h", port=6379, database="db")
        assert provider._graph is None

        # Will fail because no real FalkorDB, but should attempt connection
        result = await provider.health_check()
        assert result is False  # Can't connect to non-existent server


class TestClose:
    """Test connection cleanup."""

    def test_close_with_client(self):
        """Close should call client.close()."""
        provider = FalkorDBGraphDBProvider(host="h", port=6379, database="db")
        mock_client = MagicMock()
        provider._client = mock_client

        provider.close()

        mock_client.close.assert_called_once()
        assert provider._closed is True

    def test_close_fallback(self):
        """If client.close() raises AttributeError, try connection.close()."""
        provider = FalkorDBGraphDBProvider(host="h", port=6379, database="db")
        mock_client = MagicMock()
        mock_client.close.side_effect = AttributeError("no close")
        mock_conn = MagicMock()
        mock_client.connection = mock_conn
        provider._client = mock_client

        provider.close()

        mock_conn.close.assert_called_once()
        assert provider._closed is True

    def test_close_idempotent(self):
        """Second close should be a no-op."""
        provider = FalkorDBGraphDBProvider(host="h", port=6379, database="db")
        mock_client = MagicMock()
        provider._client = mock_client

        provider.close()
        provider.close()

        assert mock_client.close.call_count == 1

    def test_close_without_client(self):
        """Close with no client (never connected) should not raise."""
        provider = FalkorDBGraphDBProvider(host="h", port=6379, database="db")
        provider.close()
        assert provider._closed is True

    @pytest.mark.asyncio
    async def test_aclose_calls_close(self):
        """aclose should delegate to sync close."""
        provider = FalkorDBGraphDBProvider(host="h", port=6379, database="db")
        mock_client = MagicMock()
        provider._client = mock_client

        await provider.aclose()

        mock_client.close.assert_called_once()
        assert provider._closed is True
