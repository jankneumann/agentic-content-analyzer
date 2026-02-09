"""Neo4j JSONL importer for knowledge graph sync.

Reads a JSONL export file containing Neo4j node and relationship records
and imports them into a target Neo4j database via Cypher MERGE statements.
Supports merge mode (skip existing by UUID) and clean mode (delete all + import).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.sync.models import Neo4jManifest, Neo4jNodeRecord, Neo4jRelationshipRecord

logger = logging.getLogger(__name__)


class Neo4jImporter:
    """Import Neo4j knowledge graph data from a JSONL export file.

    Uses MERGE statements for idempotent node creation (keyed on UUID)
    and MATCH + MERGE for relationships.

    Args:
        driver: Neo4j driver instance (from GraphDatabase.driver()).
        mode: Import mode — 'merge' (skip existing by UUID) or 'clean'
              (delete all nodes/relationships, then import).
    """

    def __init__(self, driver: Any, mode: str = "merge") -> None:
        self._driver = driver
        self._mode = mode
        self._stats = {
            "nodes_imported": 0,
            "relationships_imported": 0,
            "errors": 0,
        }

    @property
    def stats(self) -> dict[str, int]:
        """Import statistics."""
        return self._stats

    def import_file(
        self,
        input_path: Path,
        dry_run: bool = False,
    ) -> dict[str, int]:
        """Import Neo4j data from a JSONL file.

        Args:
            input_path: Path to the JSONL export file.
            dry_run: If True, parse and validate without writing.

        Returns:
            Dict with import statistics.

        Raises:
            FileNotFoundError: If input_path doesn't exist.
        """
        if not input_path.exists():
            raise FileNotFoundError(f"Import file not found: {input_path}")

        # Parse JSONL
        manifest, nodes, relationships = self._parse_jsonl(input_path)

        if manifest:
            total_nodes = sum(manifest.nodes.values())
            total_rels = sum(manifest.relationships.values())
            logger.info(
                "Neo4j import plan: %d nodes, %d relationships",
                total_nodes,
                total_rels,
            )

        # Clean mode: delete all nodes and relationships
        if self._mode == "clean" and not dry_run:
            self._delete_all()

        # Import nodes first (relationships reference them by UUID)
        for node in nodes:
            if dry_run:
                self._stats["nodes_imported"] += 1
                continue
            self._import_node(node)

        # Import relationships
        for rel in relationships:
            if dry_run:
                self._stats["relationships_imported"] += 1
                continue
            self._import_relationship(rel)

        logger.info(
            "Neo4j import complete: nodes_imported=%d, relationships_imported=%d, errors=%d",
            self._stats["nodes_imported"],
            self._stats["relationships_imported"],
            self._stats["errors"],
        )

        # Remind about index rebuild
        logger.info(
            "Remember to run graphiti.build_indices_and_constraints() "
            "to rebuild indexes after import."
        )

        return self._stats

    def _parse_jsonl(
        self,
        path: Path,
    ) -> tuple[Neo4jManifest | None, list[Neo4jNodeRecord], list[Neo4jRelationshipRecord]]:
        """Parse JSONL file for Neo4j records.

        Skips PostgreSQL records (manifest, row) and extracts
        neo4j_manifest, neo4j_node, and neo4j_relationship records.
        """
        manifest: Neo4jManifest | None = None
        nodes: list[Neo4jNodeRecord] = []
        relationships: list[Neo4jRelationshipRecord] = []

        with open(path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError as e:
                    logger.warning("Skipping malformed line %d: %s", line_num, e)
                    self._stats["errors"] += 1
                    continue

                record_type = data.get("_type")

                if record_type == "neo4j_manifest":
                    manifest = Neo4jManifest.model_validate(data)
                elif record_type == "neo4j_node":
                    nodes.append(Neo4jNodeRecord.model_validate(data))
                elif record_type == "neo4j_relationship":
                    relationships.append(Neo4jRelationshipRecord.model_validate(data))
                # Skip PG records silently

        return manifest, nodes, relationships

    def _delete_all(self) -> None:
        """Delete all nodes and relationships (clean mode)."""
        with self._driver.session() as session:
            # Delete relationships first, then nodes
            result = session.run("MATCH ()-[r]->() DELETE r RETURN count(r) AS cnt")
            record = result.single()
            rel_count = record["cnt"] if record else 0

            result = session.run("MATCH (n) DELETE n RETURN count(n) AS cnt")
            record = result.single()
            node_count = record["cnt"] if record else 0

            logger.info(
                "Clean mode: deleted %d relationships and %d nodes",
                rel_count,
                node_count,
            )

    def _import_node(self, node: Neo4jNodeRecord) -> None:
        """Import a single node using MERGE on UUID."""
        try:
            with self._driver.session() as session:
                # MERGE on uuid for idempotency
                # SET all properties on the merged node
                cypher = (
                    f"MERGE (n:{node.label} {{uuid: $uuid}}) "
                    "ON CREATE SET n += $props "
                    "ON MATCH SET n += $props "
                    "RETURN n.uuid AS uuid"
                )
                session.run(
                    cypher,
                    uuid=node.uuid,
                    props=node.properties,
                )
                self._stats["nodes_imported"] += 1

        except Exception as e:
            logger.warning(
                "Failed to import %s node %s: %s",
                node.label,
                node.uuid,
                e,
            )
            self._stats["errors"] += 1

    def _import_relationship(self, rel: Neo4jRelationshipRecord) -> None:
        """Import a single relationship using MERGE."""
        try:
            with self._driver.session() as session:
                # Match source and target by UUID, create relationship
                cypher = (
                    "MATCH (a {uuid: $source_uuid}) "
                    "MATCH (b {uuid: $target_uuid}) "
                    f"MERGE (a)-[r:{rel.type}]->(b) "
                    "SET r += $props "
                    "RETURN type(r) AS rel_type"
                )
                result = session.run(
                    cypher,
                    source_uuid=rel.source_uuid,
                    target_uuid=rel.target_uuid,
                    props=rel.properties,
                )
                record = result.single()
                if record:
                    self._stats["relationships_imported"] += 1
                else:
                    logger.warning(
                        "Could not create %s relationship: source=%s or target=%s not found",
                        rel.type,
                        rel.source_uuid,
                        rel.target_uuid,
                    )
                    self._stats["errors"] += 1

        except Exception as e:
            logger.warning(
                "Failed to import %s relationship %s->%s: %s",
                rel.type,
                rel.source_uuid,
                rel.target_uuid,
                e,
            )
            self._stats["errors"] += 1
