"""FalkorDB implementation of GraphDBProvider.

Supports local (Docker), cloud (hosted), and embedded (FalkorDB Lite) modes.
"""

from __future__ import annotations

import asyncio
import time
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
