"""Contract: GraphDBProvider protocol and related types.

This file defines the interface that all graph database providers must implement.
It serves as the coordination boundary between work packages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

GraphDBProviderType = Literal["neo4j", "falkordb"]
GraphDBModeType = Literal["local", "cloud", "embedded"]


@dataclass
class NodeRecord:
    """Backend-agnostic node representation for export/import."""

    label: str
    uuid: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class RelationshipRecord:
    """Backend-agnostic relationship representation for export/import."""

    rel_type: str
    source_uuid: str
    target_uuid: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExportManifest:
    """Metadata about a graph export operation."""

    backend: GraphDBProviderType
    exported_at: str  # ISO-8601
    node_counts: dict[str, int] = field(default_factory=dict)  # label -> count
    relationship_counts: dict[str, int] = field(default_factory=dict)  # type -> count


@dataclass
class ImportStats:
    """Statistics from a graph import operation."""

    nodes_inserted: int = 0
    nodes_updated: int = 0
    nodes_skipped: int = 0
    nodes_failed: int = 0
    rels_inserted: int = 0
    rels_updated: int = 0
    rels_skipped: int = 0
    rels_failed: int = 0


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

    def close(self) -> None:
        """Sync close — for CLI and non-async callers."""
        ...

    async def aclose(self) -> None:
        """Async close — for async callers."""
        ...

    async def health_check(self) -> bool:
        """Check backend connectivity. Returns False on failure (no exceptions)."""
        ...

    def export_graph(self, output_path: Path) -> ExportManifest:
        """Export all graph data to JSONL file at output_path."""
        ...

    def import_graph(self, input_path: Path, mode: str = "merge") -> ImportStats:
        """Import graph data from JSONL file. Mode: 'merge' or 'clean'."""
        ...
