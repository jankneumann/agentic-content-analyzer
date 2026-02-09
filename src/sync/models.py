"""Pydantic models for database sync operations.

Defines the JSONL record types for PostgreSQL and Neo4j export/import,
plus tracking models for import state and statistics.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SyncManifest(BaseModel):
    """Manifest record — first line of a PostgreSQL JSONL export file."""

    model_config = ConfigDict(populate_by_name=True)

    record_type: str = Field(default="manifest", alias="_type")
    alembic_rev: str
    exported_at: datetime
    tables: dict[str, int]  # {table_name: row_count}
    version: int = 1


class Neo4jManifest(BaseModel):
    """Manifest record — first line of a Neo4j JSONL export file."""

    model_config = ConfigDict(populate_by_name=True)

    record_type: str = Field(default="neo4j_manifest", alias="_type")
    exported_at: datetime
    nodes: dict[str, int]  # {label: count}
    relationships: dict[str, int]  # {type: count}
    version: int = 1


class SyncRecord(BaseModel):
    """A single data row in a PostgreSQL JSONL export."""

    model_config = ConfigDict(populate_by_name=True)

    record_type: str = Field(default="row", alias="_type")
    table: str
    data: dict  # Column name -> value mapping


class Neo4jNodeRecord(BaseModel):
    """A Neo4j node record in JSONL export."""

    model_config = ConfigDict(populate_by_name=True)

    record_type: str = Field(default="neo4j_node", alias="_type")
    label: str
    uuid: str
    properties: dict


class Neo4jRelationshipRecord(BaseModel):
    """A Neo4j relationship record in JSONL export."""

    model_config = ConfigDict(populate_by_name=True)

    record_type: str = Field(default="neo4j_relationship", alias="_type")
    type: str
    source_uuid: str
    target_uuid: str
    properties: dict


class ImportStats(BaseModel):
    """Per-table import statistics."""

    inserted: int = 0
    skipped: int = 0
    updated: int = 0
    failed: int = 0


class SyncError(BaseModel):
    """Non-fatal import error."""

    table: str
    row_index: int
    message: str


class SyncState(BaseModel):
    """Tracks state during import for FK remapping and dedup."""

    id_map: dict[str, dict[int, int]] = Field(default_factory=dict)  # {table: {old_id: new_id}}
    uuid_map: dict[str, dict[str, str]] = Field(
        default_factory=dict
    )  # {table: {old_uuid: new_uuid}}
    hash_map: dict[str, int] = Field(default_factory=dict)  # {content_hash: new_content_id}
    stats: dict[str, ImportStats] = Field(default_factory=dict)  # {table: stats}
    errors: list[SyncError] = Field(default_factory=list)
