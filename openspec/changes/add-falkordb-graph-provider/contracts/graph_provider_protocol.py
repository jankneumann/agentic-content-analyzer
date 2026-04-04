"""Contract: GraphDBProvider protocol and related types.

This file defines the interface that all graph database providers must implement.
It serves as the coordination boundary between work packages.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol, runtime_checkable

GraphDBProviderType = Literal["neo4j", "falkordb"]
Neo4jSubProviderType = Literal["local", "auradb"]
FalkorDBSubProviderType = Literal["local", "lite"]


class NodeRecord:
    """Backend-agnostic node representation for export/import."""

    label: str
    uuid: str
    properties: dict[str, Any]


class RelationshipRecord:
    """Backend-agnostic relationship representation for export/import."""

    rel_type: str
    source_uuid: str
    target_uuid: str
    properties: dict[str, Any]


class ExportManifest:
    """Metadata about a graph export operation."""

    backend: GraphDBProviderType
    exported_at: str  # ISO-8601
    node_counts: dict[str, int]  # label -> count
    relationship_counts: dict[str, int]  # type -> count


@runtime_checkable
class GraphExporter(Protocol):
    """Protocol for exporting graph data from any backend."""

    async def export_nodes(self, label: str) -> AsyncIterator[NodeRecord]: ...
    async def export_relationships(self, rel_type: str) -> AsyncIterator[RelationshipRecord]: ...
    async def count_nodes(self, label: str) -> int: ...
    async def count_relationships(self, rel_type: str) -> int: ...


@runtime_checkable
class GraphImporter(Protocol):
    """Protocol for importing graph data to any backend."""

    async def import_node(self, record: NodeRecord) -> str: ...
    async def import_relationship(self, record: RelationshipRecord) -> str: ...
    async def delete_all(self) -> tuple[int, int]: ...


@runtime_checkable
class GraphDBProvider(Protocol):
    """Protocol for graph database providers.

    Implementations provide:
    1. A graphiti-core GraphDriver for the Graphiti() constructor
    2. Raw query execution for reference_graph_sync and export/import
    3. Lifecycle management
    4. Export/import factory methods
    """

    def create_graphiti_driver(self) -> Any:
        """Construct a graphiti-core GraphDriver instance.

        Returns a Neo4jDriver, FalkorDriver, or other GraphDriver subclass
        suitable for passing to Graphiti(graph_driver=...).
        """
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

    async def close(self) -> None:
        """Close all connections and release resources."""
        ...

    async def health_check(self) -> bool:
        """Check backend connectivity. Returns False on failure (no exceptions)."""
        ...

    def create_exporter(self) -> GraphExporter:
        """Create an exporter for this backend."""
        ...

    def create_importer(self, mode: str = "merge") -> GraphImporter:
        """Create an importer for this backend. Mode: 'merge' or 'clean'."""
        ...
