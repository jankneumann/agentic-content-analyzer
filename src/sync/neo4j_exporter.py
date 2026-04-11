"""Neo4j JSONL exporter for knowledge graph sync.

Exports nodes and relationships from Neo4j to a JSONL file.
Nodes are exported by label (Episode, Entity, Relation), and
relationships by type. Vector embeddings and internal index
metadata are excluded — they are rebuilt by Graphiti after import.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.sync.models import GraphManifest, GraphNodeRecord, GraphRelationshipRecord

logger = logging.getLogger(__name__)

# Property name patterns to exclude from export (large, rebuilt by Graphiti)
EXCLUDED_PROPERTY_PATTERNS: tuple[str, ...] = (
    "embedding",
    "_embedding",
    "_vector",
)

# Node labels to export (Graphiti's core types)
EXPORT_NODE_LABELS: list[str] = ["Episode", "Entity", "Relation"]

# Relationship types to export
EXPORT_RELATIONSHIP_TYPES: list[str] = [
    "HAS_ENTITY",
    "RELATES_TO",
    "HAS_EPISODE",
    "MENTIONED_IN",
]


class Neo4jExporter:
    """Export Neo4j knowledge graph to JSONL format.

    Reads nodes and relationships via Cypher queries and writes them
    as JSONL records. Accepts an explicit Neo4j driver instance rather
    than using a global singleton.

    Args:
        driver: Neo4j driver instance (from GraphDatabase.driver()).
    """

    def __init__(self, driver: Any) -> None:
        self._driver = driver

    def export(self, output_path: Path, force: bool = False) -> dict[str, int]:
        """Export Neo4j graph data to a JSONL file.

        Args:
            output_path: Destination file path for the JSONL export.
            force: If True, overwrite existing output file.

        Returns:
            Dict with keys 'nodes' and 'relationships' mapping to counts.

        Raises:
            FileExistsError: If output_path exists and force is False.
        """
        if output_path.exists() and not force:
            raise FileExistsError(
                f"Output file already exists: {output_path}. Use --force to overwrite."
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Count nodes and relationships for the manifest
        node_counts = self._count_nodes()
        rel_counts = self._count_relationships()

        total_nodes = sum(node_counts.values())
        total_rels = sum(rel_counts.values())
        logger.info(
            "Neo4j export plan: %d nodes across %d labels, %d relationships across %d types",
            total_nodes,
            len(node_counts),
            total_rels,
            len(rel_counts),
        )

        # Build manifest
        manifest = GraphManifest(
            exported_at=datetime.now(UTC),
            node_labels=EXPORT_NODE_LABELS,
            nodes=node_counts,
            relationship_types=EXPORT_RELATIONSHIP_TYPES,
            relationships=rel_counts,
        )

        # Write JSONL
        exported_nodes = 0
        exported_rels = 0

        with open(output_path, "w", encoding="utf-8") as f:
            # Line 1: manifest
            f.write(manifest.model_dump_json(by_alias=True) + "\n")

            # Export nodes by label
            for label in EXPORT_NODE_LABELS:
                count = self._export_nodes(f, label)
                exported_nodes += count
                if count > 0:
                    logger.info("Exported %s nodes: %d", label, count)

            # Export relationships by type
            for rel_type in EXPORT_RELATIONSHIP_TYPES:
                count = self._export_relationships(f, rel_type)
                exported_rels += count
                if count > 0:
                    logger.info("Exported %s relationships: %d", rel_type, count)

        logger.info(
            "Neo4j export complete: %d nodes, %d relationships",
            exported_nodes,
            exported_rels,
        )

        return {
            "nodes": exported_nodes,
            "relationships": exported_rels,
        }

    def _count_nodes(self) -> dict[str, int]:
        """Count nodes per label."""
        counts: dict[str, int] = {}
        with self._driver.session() as session:
            for label in EXPORT_NODE_LABELS:
                result = session.run(f"MATCH (n:{label}) RETURN count(n) AS cnt")
                record = result.single()
                count = record["cnt"] if record else 0
                if count > 0:
                    counts[label] = count
        return counts

    def _count_relationships(self) -> dict[str, int]:
        """Count relationships per type."""
        counts: dict[str, int] = {}
        with self._driver.session() as session:
            for rel_type in EXPORT_RELATIONSHIP_TYPES:
                result = session.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS cnt")
                record = result.single()
                count = record["cnt"] if record else 0
                if count > 0:
                    counts[rel_type] = count
        return counts

    def _export_nodes(self, f: Any, label: str) -> int:
        """Export all nodes of a given label."""
        count = 0
        with self._driver.session() as session:
            result = session.run(f"MATCH (n:{label}) RETURN n")
            for record in result:
                node = record["n"]
                properties = _filter_properties(dict(node))
                uuid_val = properties.pop("uuid", None)
                if uuid_val is None:
                    # Nodes without UUID can't be merged on import — skip
                    logger.warning(
                        "Skipping %s node without uuid: %s",
                        label,
                        properties.get("name", "unknown"),
                    )
                    continue

                node_record = GraphNodeRecord(
                    label=label,
                    uuid=str(uuid_val),
                    properties=_serialize_properties(properties),
                )
                f.write(node_record.model_dump_json(by_alias=True) + "\n")
                count += 1
        return count

    def _export_relationships(self, f: Any, rel_type: str) -> int:
        """Export all relationships of a given type."""
        count = 0
        with self._driver.session() as session:
            result = session.run(
                f"MATCH (a)-[r:{rel_type}]->(b) "
                "RETURN a.uuid AS source_uuid, b.uuid AS target_uuid, r"
            )
            for record in result:
                source_uuid = record["source_uuid"]
                target_uuid = record["target_uuid"]

                if source_uuid is None or target_uuid is None:
                    logger.warning(
                        "Skipping %s relationship with missing endpoint UUID",
                        rel_type,
                    )
                    continue

                rel = record["r"]
                properties = _filter_properties(dict(rel))

                rel_record = GraphRelationshipRecord(
                    type=rel_type,
                    source_uuid=str(source_uuid),
                    target_uuid=str(target_uuid),
                    properties=_serialize_properties(properties),
                )
                f.write(rel_record.model_dump_json(by_alias=True) + "\n")
                count += 1
        return count


def _filter_properties(props: dict[str, Any]) -> dict[str, Any]:
    """Remove excluded properties (embeddings, vectors, internal metadata).

    Uses exact match or suffix match with underscore prefix to avoid
    excluding unrelated properties (e.g., 'embedding_model' is kept,
    but 'name_embedding' and 'embedding' are excluded).
    """

    def _is_excluded(key: str) -> bool:
        for pattern in EXCLUDED_PROPERTY_PATTERNS:
            if key == pattern or key.endswith(f"_{pattern}"):
                return True
        return False

    return {k: v for k, v in props.items() if not _is_excluded(k)}


def _serialize_properties(props: dict[str, Any]) -> dict[str, Any]:
    """Convert Neo4j property values to JSON-serializable types."""
    result: dict[str, Any] = {}
    for key, value in props.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif hasattr(value, "isoformat"):
            # neo4j DateTime, Date, Time objects
            result[key] = value.isoformat()
        elif isinstance(value, (list, tuple)):
            result[key] = [v.isoformat() if hasattr(v, "isoformat") else v for v in value]
        else:
            result[key] = value
    return result
