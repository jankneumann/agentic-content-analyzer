"""Graph database provider abstraction.

Provides a pluggable interface for graph backends (Neo4j, FalkorDB).
The factory reads graphdb_provider + graphdb_mode from Settings to construct
the appropriate provider implementation.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from src.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class GraphBackendUnavailableError(Exception):
    """Raised when the graph backend is unreachable during client creation."""


@runtime_checkable
class GraphDBProvider(Protocol):
    """Protocol for graph database providers.

    Implementations provide:
    1. A graphiti-core GraphDriver for the Graphiti() constructor
    2. Raw query execution for reference_graph_sync and export/import
    3. Lifecycle management (sync and async close)
    4. File-level export/import matching CLI sync workflow
    """

    def create_graphiti_driver(self) -> Any:
        """Construct a graphiti-core GraphDriver instance."""
        ...

    async def execute_query(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a read-only openCypher query and return results as dicts."""
        ...

    async def execute_write(
        self, query: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a write openCypher query within a transaction."""
        ...

    def close(self) -> None:
        """Sync close for CLI and non-async callers."""
        ...

    async def aclose(self) -> None:
        """Async close for async callers."""
        ...

    async def health_check(self) -> bool:
        """Check backend connectivity. Returns False on failure (no exceptions)."""
        ...


class Neo4jGraphDBProvider:
    """Neo4j implementation of GraphDBProvider.

    Supports local (Docker) and cloud (AuraDB) deployment modes.
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
    ) -> None:
        from neo4j import GraphDatabase

        self._uri = uri
        self._user = user
        self._password = password
        self._database = database
        self._driver = GraphDatabase.driver(uri, auth=(user, password))
        self._closed = False

        logger.info(
            "Initialized Neo4j graph provider: uri=%s, database=%s",
            uri,
            database,
        )

    def create_graphiti_driver(self) -> Any:
        """Create a Neo4jDriver for graphiti-core."""
        from graphiti_core.driver.neo4j_driver import Neo4jDriver

        return Neo4jDriver(
            uri=self._uri,
            user=self._user,
            password=self._password,
            database=self._database,
        )

    async def execute_query(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a read query via Neo4j driver session."""
        start = time.monotonic()
        try:
            with self._driver.session(database=self._database) as session:
                result = session.run(query, parameters=params or {})
                records = [dict(record) for record in result]
            return records
        finally:
            elapsed = time.monotonic() - start
            if elapsed > 5.0:
                logger.warning(
                    "Slow graph query (%.1fs): %s",
                    elapsed,
                    query[:200],
                )

    async def execute_write(
        self, query: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a write query via Neo4j driver session."""
        start = time.monotonic()
        try:
            with self._driver.session(database=self._database) as session:
                result = session.run(query, parameters=params or {})
                summary = result.consume()
                return {
                    "nodes_created": summary.counters.nodes_created,
                    "relationships_created": summary.counters.relationships_created,
                    "properties_set": summary.counters.properties_set,
                }
        finally:
            elapsed = time.monotonic() - start
            if elapsed > 5.0:
                logger.warning(
                    "Slow graph write (%.1fs): %s",
                    elapsed,
                    query[:200],
                )

    def close(self) -> None:
        """Close Neo4j driver (sync)."""
        if not self._closed:
            self._driver.close()
            self._closed = True
            logger.debug("Closed Neo4j graph provider")

    async def aclose(self) -> None:
        """Close Neo4j driver (async wrapper)."""
        self.close()

    async def health_check(self) -> bool:
        """Verify Neo4j connectivity."""
        try:
            with self._driver.session(database=self._database) as session:
                session.run("RETURN 1 AS n").consume()
            return True
        except Exception:
            logger.warning("Neo4j health check failed", exc_info=True)
            return False


def get_graph_provider() -> GraphDBProvider:
    """Factory: construct the graph provider from Settings.

    Reads graphdb_provider and graphdb_mode to determine backend and connection.
    """
    from src.config.settings import get_settings

    settings = get_settings()

    provider_type = getattr(settings, "graphdb_provider", "neo4j")
    mode = getattr(settings, "graphdb_mode", "local")

    if provider_type == "neo4j":
        return _create_neo4j_provider(settings, mode)
    elif provider_type == "falkordb":
        return _create_falkordb_provider(settings, mode)
    else:
        raise ValueError(f"Unknown graphdb_provider: {provider_type}")


def _create_neo4j_provider(settings: Any, mode: str) -> Neo4jGraphDBProvider:
    """Create Neo4j provider based on deployment mode."""
    if mode == "embedded":
        raise ValueError("Neo4j does not support embedded mode. Use falkordb instead.")

    if mode == "cloud":
        uri = getattr(settings, "neo4j_cloud_uri", None)
        user = getattr(settings, "neo4j_cloud_user", "neo4j")
        password = getattr(settings, "neo4j_cloud_password", None)
        if not uri or not password:
            raise ValueError("Neo4j cloud mode requires neo4j_cloud_uri and neo4j_cloud_password")
    else:
        # local mode — use existing neo4j_uri fields
        uri = settings.neo4j_uri
        user = settings.neo4j_user
        password = settings.neo4j_password

    return Neo4jGraphDBProvider(uri=uri, user=user, password=password)


def _create_falkordb_provider(settings: Any, mode: str) -> GraphDBProvider:
    """Create FalkorDB provider based on deployment mode.

    Lazily imports from falkordb_provider to keep this module clean.
    """
    from src.storage.falkordb_provider import FalkorDBGraphDBProvider

    if mode == "cloud":
        host = getattr(settings, "falkordb_cloud_host", None)
        port = getattr(settings, "falkordb_cloud_port", 6379)
        password = getattr(settings, "falkordb_cloud_password", None)
        if not host:
            raise ValueError("FalkorDB cloud mode requires falkordb_cloud_host")
        return FalkorDBGraphDBProvider(
            host=host,
            port=port,
            password=password,
            database=getattr(settings, "falkordb_database", "newsletter_graph"),
        )
    elif mode == "embedded":
        data_dir = getattr(settings, "falkordb_lite_data_dir", None)
        return FalkorDBGraphDBProvider(
            host="localhost",
            port=0,  # will be assigned by Lite
            database=getattr(settings, "falkordb_database", "newsletter_graph"),
            lite_data_dir=data_dir,
        )
    else:
        # local mode — Docker FalkorDB
        return FalkorDBGraphDBProvider(
            host=getattr(settings, "falkordb_host", "localhost"),
            port=getattr(settings, "falkordb_port", 6379),
            username=getattr(settings, "falkordb_username", None),
            password=getattr(settings, "falkordb_password", None),
            database=getattr(settings, "falkordb_database", "newsletter_graph"),
        )
