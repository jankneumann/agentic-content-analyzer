"""FalkorDB implementation of GraphDBProvider.

Supports local (Docker), cloud (hosted), and embedded (FalkorDB Lite) modes.
"""

from __future__ import annotations

import time
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)


class FalkorDBGraphDBProvider:
    """FalkorDB implementation of GraphDBProvider.

    Uses graphiti-core's FalkorDriver for Graphiti integration and
    the falkordb Python client for raw Cypher queries.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        username: str | None = None,
        password: str | None = None,
        database: str = "newsletter_graph",
        lite_data_dir: str | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._database = database
        self._lite_data_dir = lite_data_dir
        self._closed = False

        # Connect to FalkorDB
        import falkordb

        self._client = falkordb.FalkorDB(
            host=host,
            port=port,
            username=username,
            password=password,
        )
        self._graph = self._client.select_graph(database)

        mode = (
            "embedded"
            if lite_data_dir
            else ("cloud" if port != 6379 or host != "localhost" else "local")
        )
        logger.info(
            "Initialized FalkorDB graph provider: host=%s, port=%d, database=%s, mode=%s",
            host,
            port,
            database,
            mode,
        )

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
        """Execute a read query via FalkorDB graph."""
        start = time.monotonic()
        try:
            result = self._graph.query(query, params=params or {})
            # FalkorDB returns result sets differently from Neo4j
            # Convert to list of dicts matching the Neo4j format
            records = []
            if result.result_set:
                headers = result.header
                for row in result.result_set:
                    record = {}
                    for i, header in enumerate(headers):
                        # header is (type, name) tuple
                        col_name = header[1] if isinstance(header, (list, tuple)) else header
                        record[col_name] = row[i]
                    records.append(record)
            return records
        finally:
            elapsed = time.monotonic() - start
            if elapsed > 5.0:
                logger.warning(
                    "Slow FalkorDB query (%.1fs): %s",
                    elapsed,
                    query[:200],
                )

    async def execute_write(
        self, query: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a write query via FalkorDB graph."""
        start = time.monotonic()
        try:
            result = self._graph.query(query, params=params or {})
            stats = result.statistics if hasattr(result, "statistics") else {}
            return {
                "nodes_created": stats.get("Nodes created", 0) if isinstance(stats, dict) else 0,
                "relationships_created": stats.get("Relationships created", 0)
                if isinstance(stats, dict)
                else 0,
                "properties_set": stats.get("Properties set", 0) if isinstance(stats, dict) else 0,
            }
        finally:
            elapsed = time.monotonic() - start
            if elapsed > 5.0:
                logger.warning(
                    "Slow FalkorDB write (%.1fs): %s",
                    elapsed,
                    query[:200],
                )

    def close(self) -> None:
        """Close FalkorDB connection (sync)."""
        if not self._closed:
            try:
                self._client.connection.close()
            except Exception:
                pass
            self._closed = True
            logger.debug("Closed FalkorDB graph provider")

    async def aclose(self) -> None:
        """Close FalkorDB connection (async wrapper)."""
        self.close()

    async def health_check(self) -> bool:
        """Verify FalkorDB connectivity."""
        try:
            self._client.connection.ping()
            return True
        except Exception:
            logger.warning("FalkorDB health check failed", exc_info=True)
            return False
