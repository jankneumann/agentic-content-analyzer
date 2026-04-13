"""FalkorDB implementation of GraphDBProvider.

Supports local (Docker), cloud (hosted), and embedded (FalkorDB Lite) modes.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC
from pathlib import Path
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)


class FalkorDBGraphDBProvider:
    """FalkorDB implementation of GraphDBProvider.

    Uses graphiti-core's FalkorDriver for Graphiti integration and
    the falkordb Python client for raw Cypher queries.

    Connection is lazy — deferred to first use to support graceful degradation.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        username: str | None = None,
        password: str | None = None,
        database: str = "newsletter_graph",
        mode: str = "local",
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._database = database
        self._mode = mode
        self._closed = False
        self._client: Any = None
        self._graph: Any = None

        logger.info(
            "Initialized FalkorDB graph provider: host=%s, port=%d, database=%s, mode=%s",
            host,
            port,
            database,
            mode,
        )

    def _ensure_connected(self) -> Any:
        """Lazy connection — connect on first use."""
        if self._graph is None:
            import falkordb

            self._client = falkordb.FalkorDB(
                host=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
            )
            self._graph = self._client.select_graph(self._database)
        return self._graph

    def create_graphiti_driver(self) -> Any:
        """Create a FalkorDriver for graphiti-core."""
        from graphiti_core.driver.falkordb_driver import FalkorDriver

        return FalkorDriver(
            host=self._host,
            port=self._port,
            username=self._username or "",
            password=self._password or "",
            database=self._database,
        )

    async def execute_query(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a read query via FalkorDB graph (offloaded to thread)."""
        start = time.monotonic()
        try:
            return await asyncio.to_thread(self._run_query, query, params or {})
        finally:
            elapsed = time.monotonic() - start
            if elapsed > 5.0:
                logger.warning("Slow FalkorDB query (%.1fs): %s", elapsed, query[:200])

    def _run_query(self, query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Sync query execution — called from thread pool."""
        graph = self._ensure_connected()
        result = graph.query(query, params=params)
        records = []
        if result.result_set:
            headers = result.header
            for row in result.result_set:
                record = {}
                for i, header in enumerate(headers):
                    col_name = header[1] if isinstance(header, (list, tuple)) else header
                    record[col_name] = row[i]
                records.append(record)
        return records

    async def execute_write(
        self, query: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a write query via FalkorDB graph (offloaded to thread)."""
        start = time.monotonic()
        try:
            return await asyncio.to_thread(self._run_write, query, params or {})
        finally:
            elapsed = time.monotonic() - start
            if elapsed > 5.0:
                logger.warning("Slow FalkorDB write (%.1fs): %s", elapsed, query[:200])

    def _run_write(self, query: str, params: dict[str, Any]) -> dict[str, Any]:
        """Sync write execution — called from thread pool."""
        graph = self._ensure_connected()
        result = graph.query(query, params=params)
        # FalkorDB QueryResult exposes statistics as properties
        return {
            "nodes_created": getattr(result, "nodes_created", 0),
            "relationships_created": getattr(result, "relationships_created", 0),
            "properties_set": getattr(result, "properties_set", 0),
        }

    def close(self) -> None:
        """Close FalkorDB connection (sync)."""
        if not self._closed:
            if self._client is not None:
                try:
                    self._client.close()
                except AttributeError:
                    # Fallback for different falkordb client versions
                    try:
                        self._client.connection.close()
                    except Exception as e:
                        logger.debug("FalkorDB close fallback: %s", e)
                except Exception as e:
                    logger.debug("FalkorDB close error: %s", e)
            self._closed = True
            logger.debug("Closed FalkorDB graph provider")

    async def aclose(self) -> None:
        """Close FalkorDB connection (async wrapper)."""
        self.close()

    async def health_check(self) -> bool:
        """Verify FalkorDB connectivity."""
        try:
            graph = self._ensure_connected()
            # Simple query to verify the graph is responsive
            graph.query("RETURN 1 AS n")
            return True
        except Exception:
            logger.warning("FalkorDB health check failed", exc_info=True)
            return False

    def export_graph(self, output_path: Path, force: bool = False) -> dict[str, int]:
        """Export graph data to JSONL file.

        Uses the same JSONL format as Neo4j exporter for cross-backend portability.

        Args:
            output_path: Destination file path for the JSONL export.
            force: If True, overwrite existing output file.

        Returns:
            Dict with keys 'nodes' and 'relationships' mapping to counts.

        Raises:
            FileExistsError: If output_path exists and force is False.
        """
        from datetime import datetime

        from src.sync.models import GraphManifest, GraphNodeRecord, GraphRelationshipRecord

        if output_path.exists() and not force:
            raise FileExistsError(
                f"Output file already exists: {output_path}. Use --force to overwrite."
            )

        graph = self._ensure_connected()

        node_labels = ["Episode", "Entity", "Relation"]
        rel_types = ["HAS_ENTITY", "RELATES_TO", "HAS_EPISODE", "MENTIONED_IN", "CITES"]

        node_counts: dict[str, int] = {}
        rel_counts: dict[str, int] = {}
        all_nodes: list[GraphNodeRecord] = []
        all_rels: list[GraphRelationshipRecord] = []

        for label in node_labels:
            result = graph.query(f"MATCH (n:{label}) RETURN n")
            nodes: list[GraphNodeRecord] = []
            if result.result_set:
                for row in result.result_set:
                    node = row[0]  # FalkorDB returns node objects
                    props = node.properties if hasattr(node, "properties") else {}
                    uuid = props.get("uuid", "")
                    # Filter out embedding properties
                    filtered = {
                        k: v
                        for k, v in props.items()
                        if "embedding" not in k.lower() and "vector" not in k.lower()
                    }
                    nodes.append(GraphNodeRecord(label=label, uuid=uuid, properties=filtered))
            node_counts[label] = len(nodes)
            all_nodes.extend(nodes)

        for rel_type in rel_types:
            result = graph.query(
                f"MATCH (a)-[r:{rel_type}]->(b) "
                "RETURN a.uuid AS source_uuid, b.uuid AS target_uuid, r"
            )
            rels: list[GraphRelationshipRecord] = []
            if result.result_set:
                for row in result.result_set:
                    source_uuid = row[0]
                    target_uuid = row[1]
                    rel = row[2]
                    props = rel.properties if hasattr(rel, "properties") else {}
                    rels.append(
                        GraphRelationshipRecord(
                            type=rel_type,
                            source_uuid=source_uuid,
                            target_uuid=target_uuid,
                            properties=props,
                        )
                    )
            rel_counts[rel_type] = len(rels)
            all_rels.extend(rels)

        manifest = GraphManifest(
            exported_at=datetime.now(UTC).isoformat(),
            node_labels=node_labels,
            relationship_types=rel_types,
            nodes=node_counts,
            relationships=rel_counts,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(manifest.model_dump_json(by_alias=True) + "\n")
            for node in all_nodes:
                f.write(node.model_dump_json(by_alias=True) + "\n")
            for rel in all_rels:
                f.write(rel.model_dump_json(by_alias=True) + "\n")

        return {"nodes": sum(node_counts.values()), "relationships": sum(rel_counts.values())}

    def import_graph(
        self, input_path: Path, mode: str = "merge", dry_run: bool = False
    ) -> dict[str, int]:
        """Import graph data from JSONL file.

        Args:
            input_path: Path to the JSONL export file.
            mode: Import mode -- 'merge' or 'clean'.
            dry_run: If True, parse and validate without writing.

        Returns:
            Dict with import statistics.

        Raises:
            FileNotFoundError: If input_path doesn't exist.
        """
        if not input_path.exists():
            raise FileNotFoundError(f"Import file not found: {input_path}")

        graph = self._ensure_connected()

        if mode == "clean" and not dry_run:
            graph.query("MATCH (n) DETACH DELETE n")

        nodes_imported = 0
        rels_imported = 0

        with open(input_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                record_type = data.get("_type")

                if record_type in ("graph_node", "neo4j_node"):
                    if not dry_run:
                        label = data.get("label", "Node")
                        uuid = data.get("uuid", "")
                        props = data.get("properties", {})
                        # Build SET clause
                        set_parts = ", ".join(f"n.{k} = ${k}" for k in props)
                        params: dict[str, Any] = {"uuid": uuid, **props}
                        query = f"MERGE (n:{label} {{uuid: $uuid}})"
                        if set_parts:
                            query += f" ON CREATE SET {set_parts} ON MATCH SET {set_parts}"
                        graph.query(query, params=params)
                    nodes_imported += 1

                elif record_type in ("graph_relationship", "neo4j_relationship"):
                    if not dry_run:
                        rel_type = data.get("type", "RELATES_TO")
                        source = data.get("source_uuid", "")
                        target = data.get("target_uuid", "")
                        props = data.get("properties", {})
                        set_parts = ", ".join(f"r.{k} = ${k}" for k in props)
                        params = {
                            "source_uuid": source,
                            "target_uuid": target,
                            **props,
                        }
                        query = (
                            "MATCH (a {uuid: $source_uuid}) "
                            "MATCH (b {uuid: $target_uuid}) "
                            f"MERGE (a)-[r:{rel_type}]->(b)"
                        )
                        if set_parts:
                            query += f" SET {set_parts}"
                        graph.query(query, params=params)
                    rels_imported += 1

        return {"nodes_imported": nodes_imported, "relationships_imported": rels_imported}
