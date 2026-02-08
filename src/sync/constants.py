"""Constants for database sync operations.

This module is the single source of truth for table ordering,
natural key definitions, enum catalogs, and file path mappings.
All downstream sync tasks (export, import, file sync) reference
these constants rather than hardcoding table metadata.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Table dependency DAG — maps table to its FK parent tables
# Used for topological ordering during export/import
# ---------------------------------------------------------------------------
TABLE_DEPENDENCIES: dict[str, list[str]] = {
    # Level 0: no FK parents (except self-referential)
    "contents": [],
    "digests": [],
    "theme_analyses": [],
    "conversations": [],
    "prompt_overrides": [],
    # Level 1: depends on Level 0
    "summaries": ["contents"],
    "chat_messages": ["conversations"],
    # Level 2: depends on Level 0-1
    "images": ["contents", "summaries", "digests"],
    "audio_digests": ["digests"],
    "podcast_scripts": ["digests"],
    # Level 3: depends on Level 2
    "podcasts": ["podcast_scripts"],
}

# ---------------------------------------------------------------------------
# Self-referential FK columns that need two-pass import
# ---------------------------------------------------------------------------
SELF_REF_FKS: dict[str, str] = {
    "contents": "canonical_id",  # contents.canonical_id → contents.id
    "digests": "parent_digest_id",  # digests.parent_digest_id → digests.id
}

# ---------------------------------------------------------------------------
# Topological levels for ordered processing
# ---------------------------------------------------------------------------
TABLE_LEVELS: list[list[str]] = [
    # Level 0
    ["contents", "digests", "theme_analyses", "conversations", "prompt_overrides"],
    # Level 1
    ["summaries", "chat_messages"],
    # Level 2
    ["images", "audio_digests", "podcast_scripts"],
    # Level 3
    ["podcasts"],
]

# All syncable tables (flat list in topological order)
SYNC_TABLES: list[str] = [table for level in TABLE_LEVELS for table in level]

# Tables excluded from sync (managed by external systems)
EXCLUDED_TABLES: frozenset[str] = frozenset({"pgqueuer_jobs", "alembic_version"})

# ---------------------------------------------------------------------------
# Natural keys per table for deduplication during import
# These columns are used to check if a row already exists in the target.
# ---------------------------------------------------------------------------
NATURAL_KEYS: dict[str, list[str]] = {
    "contents": ["content_hash"],
    "summaries": ["content_id", "created_at"],
    "digests": ["digest_type", "period_start", "period_end"],
    "images": ["id"],  # UUID — globally unique
    "audio_digests": ["digest_id", "created_at"],
    "podcast_scripts": ["digest_id", "created_at"],
    "podcasts": ["script_id", "created_at"],
    "theme_analyses": ["analysis_date", "start_date", "end_date"],
    "conversations": ["id"],  # UUID string — globally unique
    "chat_messages": ["id"],  # UUID string — globally unique
    "prompt_overrides": ["key"],
}

# ---------------------------------------------------------------------------
# FK column mappings: {child_table: {fk_column: parent_table}}
# ---------------------------------------------------------------------------
FK_COLUMNS: dict[str, dict[str, str]] = {
    "contents": {"canonical_id": "contents"},
    "summaries": {"content_id": "contents"},
    "digests": {"parent_digest_id": "digests"},
    "images": {
        "source_content_id": "contents",
        "source_summary_id": "summaries",
        "source_digest_id": "digests",
    },
    "audio_digests": {"digest_id": "digests"},
    "podcast_scripts": {"digest_id": "digests"},
    "podcasts": {"script_id": "podcast_scripts"},
    "chat_messages": {"conversation_id": "conversations"},
}

# ---------------------------------------------------------------------------
# File path columns for file storage sync
# {table: {column: bucket}}
# ---------------------------------------------------------------------------
FILE_PATH_COLUMNS: dict[str, dict[str, str]] = {
    "images": {"storage_path": "images"},
    "audio_digests": {"audio_url": "audio-digests"},
    "podcasts": {"audio_url": "podcasts"},
}

# ---------------------------------------------------------------------------
# UUID primary key tables (use string UUIDs, not integer IDs)
# ---------------------------------------------------------------------------
UUID_PK_TABLES: frozenset[str] = frozenset({"images", "conversations", "chat_messages"})


# ---------------------------------------------------------------------------
# Enum catalog — built by introspecting actual SQLAlchemy model enum classes.
# Ensures the catalog stays synchronized as the schema evolves.
# ---------------------------------------------------------------------------
def _build_enum_catalog() -> dict[str, set[str]]:
    """Build enum catalog from SQLAlchemy model enum classes.

    Returns:
        Dict mapping "table.column" to set of valid enum string values.
    """
    from src.models.audio_digest import AudioDigestStatus
    from src.models.content import ContentSource, ContentStatus
    from src.models.digest import DigestStatus, DigestType
    from src.models.image import ImageSource

    return {
        "contents.source_type": {e.value for e in ContentSource},
        "contents.status": {e.value for e in ContentStatus},
        "digests.digest_type": {e.value for e in DigestType},
        "digests.status": {e.value for e in DigestStatus},
        "images.source_type": {e.value for e in ImageSource},
        "audio_digests.status": {e.value for e in AudioDigestStatus},
    }


# Lazy-init: only built when first accessed (avoids import-time model loading)
_enum_catalog: dict[str, set[str]] | None = None


def get_enum_catalog() -> dict[str, set[str]]:
    """Get the enum catalog, building it on first access."""
    global _enum_catalog
    if _enum_catalog is None:
        _enum_catalog = _build_enum_catalog()
    return _enum_catalog


def compute_table_closure(tables: list[str]) -> list[str]:
    """Compute transitive closure of FK parent dependencies.

    Given a list of requested tables, returns the full set of tables
    needed (including all ancestor dependencies) in topological order.

    Args:
        tables: List of requested table names

    Returns:
        List of tables in topological order including all FK parents
    """
    needed: set[str] = set()

    def _add_with_parents(table: str) -> None:
        if table in needed:
            return
        needed.add(table)
        for parent in TABLE_DEPENDENCIES.get(table, []):
            _add_with_parents(parent)

    for table in tables:
        _add_with_parents(table)

    # Return in topological order
    return [t for level in TABLE_LEVELS for t in level if t in needed]
