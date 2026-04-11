"""Integration tests for FalkorDB provider against real FalkorDB Lite.

These tests verify the provider layer works correctly with an actual
FalkorDB instance — Cypher compatibility, query routing, health checks,
and citation edge creation (ReferenceGraphSync pattern).

Requires: falkordblite package (pip install falkordblite)
"""

from __future__ import annotations

import pytest

from tests.integration.fixtures.falkordb import requires_falkordb


@requires_falkordb
class TestFalkorDBProviderIntegration:
    """Test FalkorDBGraphDBProvider against real FalkorDB Lite."""

    @pytest.mark.asyncio
    async def test_health_check(self, falkordb_provider):
        """Health check should return True on live instance."""
        assert await falkordb_provider.health_check() is True

    @pytest.mark.asyncio
    async def test_execute_query_return_1(self, falkordb_provider):
        """Basic RETURN query should work."""
        records = await falkordb_provider.execute_query("RETURN 1 AS n")
        assert len(records) == 1
        assert records[0]["n"] == 1

    @pytest.mark.asyncio
    async def test_create_and_query_node(self, falkordb_provider):
        """CREATE + MATCH round-trip should work."""
        await falkordb_provider.execute_write(
            "CREATE (n:TestNode {uuid: 'test-1', name: 'Hello FalkorDB'})"
        )

        records = await falkordb_provider.execute_query(
            "MATCH (n:TestNode {uuid: 'test-1'}) RETURN n.name AS name"
        )
        assert len(records) == 1
        assert records[0]["name"] == "Hello FalkorDB"

    @pytest.mark.asyncio
    async def test_merge_idempotent(self, falkordb_provider):
        """MERGE should be idempotent — no duplicate nodes."""
        for _ in range(3):
            await falkordb_provider.execute_write(
                "MERGE (n:TestNode {uuid: 'merge-1'}) SET n.name = 'merged'"
            )

        records = await falkordb_provider.execute_query(
            "MATCH (n:TestNode {uuid: 'merge-1'}) RETURN count(n) AS cnt"
        )
        assert records[0]["cnt"] == 1

    @pytest.mark.asyncio
    async def test_execute_write_returns_stats(self, falkordb_provider):
        """Write operations should return creation statistics."""
        stats = await falkordb_provider.execute_write(
            "CREATE (n:StatsTest {uuid: 'stats-1', name: 'test'})"
        )
        assert stats["nodes_created"] >= 1
        assert stats["properties_set"] >= 1

    @pytest.mark.asyncio
    async def test_parameterized_query(self, falkordb_provider):
        """Parameterized queries should work."""
        await falkordb_provider.execute_write(
            "CREATE (n:ParamTest {uuid: $uuid, name: $name})",
            {"uuid": "param-1", "name": "parameterized"},
        )

        records = await falkordb_provider.execute_query(
            "MATCH (n:ParamTest {uuid: $uuid}) RETURN n.name AS name",
            {"uuid": "param-1"},
        )
        assert records[0]["name"] == "parameterized"

    @pytest.mark.asyncio
    async def test_relationship_creation(self, falkordb_provider):
        """Relationship creation and traversal should work."""
        await falkordb_provider.execute_write(
            "CREATE (a:Person {uuid: 'p1', name: 'Alice'})"
        )
        await falkordb_provider.execute_write(
            "CREATE (b:Person {uuid: 'p2', name: 'Bob'})"
        )
        await falkordb_provider.execute_write(
            "MATCH (a:Person {uuid: 'p1'}), (b:Person {uuid: 'p2'}) "
            "CREATE (a)-[:KNOWS]->(b)"
        )

        records = await falkordb_provider.execute_query(
            "MATCH (a:Person)-[:KNOWS]->(b:Person) "
            "RETURN a.name AS from_name, b.name AS to_name"
        )
        assert len(records) == 1
        assert records[0]["from_name"] == "Alice"
        assert records[0]["to_name"] == "Bob"

    @pytest.mark.asyncio
    async def test_tolower_contains(self, falkordb_provider):
        """toLower() and CONTAINS should work (used in theme queries)."""
        await falkordb_provider.execute_write(
            "CREATE (e:Episode {uuid: 'ep-1', name: 'Large Language Models', "
            "content: 'Discussion about LLM advances'})"
        )

        records = await falkordb_provider.execute_query(
            "MATCH (e:Episode) "
            "WHERE toLower(e.name) CONTAINS toLower($theme) "
            "RETURN e.uuid AS uuid, e.name AS name",
            {"theme": "language models"},
        )
        assert len(records) == 1
        assert records[0]["uuid"] == "ep-1"

    @pytest.mark.asyncio
    async def test_order_by_and_limit(self, falkordb_provider):
        """ORDER BY and LIMIT should work."""
        for i in range(5):
            await falkordb_provider.execute_write(
                f"CREATE (n:Ordered {{uuid: 'o-{i}', val: {i}}})"
            )

        records = await falkordb_provider.execute_query(
            "MATCH (n:Ordered) RETURN n.val AS val ORDER BY n.val DESC LIMIT 3"
        )
        assert len(records) == 3
        assert records[0]["val"] == 4
        assert records[2]["val"] == 2

    @pytest.mark.asyncio
    async def test_close_marks_closed(self):
        """After close, provider should be marked closed.

        Uses a standalone provider (not the fixture) to avoid
        closing the session-scoped FalkorDB Lite instance.
        """
        from src.storage.falkordb_provider import FalkorDBGraphDBProvider

        provider = FalkorDBGraphDBProvider(host="h", port=6379, mode="local")
        provider.close()
        assert provider._closed is True


@requires_falkordb
class TestReferenceGraphSyncOnFalkorDB:
    """Test ReferenceGraphSync citation patterns against FalkorDB Lite."""

    @pytest.mark.asyncio
    async def test_cites_edge_creation(self, falkordb_provider):
        """The CITES edge MERGE pattern from reference_graph_sync should work."""
        # Create two Episode nodes (simulating graph population)
        await falkordb_provider.execute_write(
            "CREATE (e:Episode {uuid: 'src-uuid', source_id: '100', "
            "name: 'Source Article', content: 'content here'})"
        )
        await falkordb_provider.execute_write(
            "CREATE (e:Episode {uuid: 'tgt-uuid', source_id: '200', "
            "name: 'Target Article', content: 'referenced content'})"
        )

        # Run the exact CITES MERGE query from reference_graph_sync.py
        await falkordb_provider.execute_write(
            """
            MATCH (s:Episode {uuid: $source_uuid})
            MATCH (t:Episode {uuid: $target_uuid})
            MERGE (s)-[r:CITES]->(t)
            SET r.reference_type = $reference_type,
                r.confidence = $confidence
            """,
            {
                "source_uuid": "src-uuid",
                "target_uuid": "tgt-uuid",
                "reference_type": "citation",
                "confidence": 0.95,
            },
        )

        # Verify the edge exists
        records = await falkordb_provider.execute_query(
            "MATCH (s:Episode)-[r:CITES]->(t:Episode) "
            "RETURN s.uuid AS source, t.uuid AS target, "
            "r.reference_type AS ref_type, r.confidence AS conf"
        )
        assert len(records) == 1
        assert records[0]["source"] == "src-uuid"
        assert records[0]["target"] == "tgt-uuid"
        assert records[0]["ref_type"] == "citation"
        assert records[0]["conf"] == 0.95

    @pytest.mark.asyncio
    async def test_episode_uuid_lookup(self, falkordb_provider):
        """The episode UUID lookup pattern from reference_graph_sync should work."""
        await falkordb_provider.execute_write(
            "CREATE (e:Episode {uuid: 'ep-uuid-123', source_id: '42', "
            "name: 'Test Episode'})"
        )

        # Run the exact lookup query from reference_graph_sync.py
        records = await falkordb_provider.execute_query(
            """
            MATCH (e:Episode)
            WHERE e.source_id = $content_id OR e.content_id = $content_id
            RETURN e.uuid AS uuid
            LIMIT 1
            """,
            {"content_id": "42"},
        )
        assert len(records) == 1
        assert records[0]["uuid"] == "ep-uuid-123"

    @pytest.mark.asyncio
    async def test_episode_uuid_not_found(self, falkordb_provider):
        """Lookup for non-existent content_id should return empty."""
        records = await falkordb_provider.execute_query(
            """
            MATCH (e:Episode)
            WHERE e.source_id = $content_id
            RETURN e.uuid AS uuid
            LIMIT 1
            """,
            {"content_id": "nonexistent"},
        )
        assert records == []

    @pytest.mark.asyncio
    async def test_cites_merge_is_idempotent(self, falkordb_provider):
        """Running CITES MERGE twice should not create duplicate edges."""
        await falkordb_provider.execute_write(
            "CREATE (s:Episode {uuid: 'a'}), (t:Episode {uuid: 'b'})"
        )

        merge_query = """
            MATCH (s:Episode {uuid: $src}), (t:Episode {uuid: $tgt})
            MERGE (s)-[r:CITES]->(t)
            SET r.reference_type = 'citation'
        """
        params = {"src": "a", "tgt": "b"}

        await falkordb_provider.execute_write(merge_query, params)
        await falkordb_provider.execute_write(merge_query, params)

        records = await falkordb_provider.execute_query(
            "MATCH (:Episode {uuid: 'a'})-[r:CITES]->(:Episode {uuid: 'b'}) "
            "RETURN count(r) AS cnt"
        )
        assert records[0]["cnt"] == 1
