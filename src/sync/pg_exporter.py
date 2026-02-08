"""PostgreSQL JSONL exporter for database sync.

Exports rows from PostgreSQL tables to a JSONL file in topological order.
Each line is a JSON record: a manifest (line 1) followed by data rows.
The exporter accepts an explicit SQLAlchemy Engine (not the global singleton)
to support profile-based sync without mutating global state.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any

from sqlalchemy import MetaData, Table, text
from sqlalchemy.engine import Engine

from src.sync.constants import (
    EXCLUDED_TABLES,
    SYNC_TABLES,
    compute_table_closure,
)
from src.sync.models import SyncManifest, SyncRecord

logger = logging.getLogger(__name__)

# Batch size for streaming reads (rows per fetch)
_STREAM_BATCH_SIZE = 1000


class PGExporter:
    """Export PostgreSQL tables to JSONL format.

    Reads rows in topological order (parents before children) and writes
    them as JSONL records. Uses server-side cursors via yield_per() for
    memory-safe streaming of large tables.

    Args:
        engine: SQLAlchemy Engine connected to the source database.
                Created externally via resolve_profile_settings().
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._metadata = MetaData()

    def export(
        self,
        output_path: Path,
        tables: list[str] | None = None,
        force: bool = False,
    ) -> dict[str, int]:
        """Export database tables to a JSONL file.

        Args:
            output_path: Destination file path for the JSONL export.
            tables: Optional list of tables to export. If provided,
                    FK parent tables are auto-included. If None, all
                    syncable tables are exported.
            force: If True, overwrite existing output file.

        Returns:
            Dict mapping table names to exported row counts.

        Raises:
            FileExistsError: If output_path exists and force is False.
            RuntimeError: If database connection or export fails.
        """
        # Resolve table list
        export_tables = self._resolve_tables(tables)

        # Check output file
        if output_path.exists() and not force:
            raise FileExistsError(
                f"Output file already exists: {output_path}. Use --force to overwrite."
            )

        # Create parent directories
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Pre-flight: count rows per table
        row_counts = self._count_rows(export_tables)
        total_rows = sum(row_counts.values())
        logger.info(
            "Export plan: %d tables, ~%d total rows",
            len(export_tables),
            total_rows,
        )

        # Get Alembic revision
        alembic_rev = self._get_alembic_revision()

        # Build manifest
        manifest = SyncManifest(
            alembic_rev=alembic_rev,
            exported_at=datetime.now(UTC),
            tables=row_counts,
        )

        # Reflect table metadata for column introspection
        self._metadata.reflect(bind=self._engine, only=export_tables)

        # Write JSONL
        exported_counts: dict[str, int] = {}
        with open(output_path, "w", encoding="utf-8") as f:
            # Line 1: manifest
            f.write(manifest.model_dump_json(by_alias=True) + "\n")

            # Data records in topological order
            for table_name in export_tables:
                count = self._export_table(f, table_name)
                exported_counts[table_name] = count
                logger.info("Exported %s: %d rows", table_name, count)

        file_size = output_path.stat().st_size
        total_exported = sum(exported_counts.values())
        logger.info(
            "Export complete: %d rows across %d tables (%s)",
            total_exported,
            len(exported_counts),
            _format_size(file_size),
        )

        return exported_counts

    def _resolve_tables(self, tables: list[str] | None) -> list[str]:
        """Resolve requested tables to a full export list.

        If tables is None, returns all SYNC_TABLES.
        Otherwise computes transitive FK closure and logs auto-included parents.
        """
        if tables is None:
            return list(SYNC_TABLES)

        # Validate requested tables
        unknown = set(tables) - set(SYNC_TABLES) - EXCLUDED_TABLES
        if unknown:
            raise ValueError(
                f"Unknown tables: {', '.join(sorted(unknown))}. Available: {', '.join(SYNC_TABLES)}"
            )

        # Compute closure (includes FK parents)
        resolved = compute_table_closure(tables)

        # Log auto-included parents
        auto_included = set(resolved) - set(tables)
        for parent in auto_included:
            logger.info(
                "Auto-including parent table: %s (required by FK dependency)",
                parent,
            )

        return resolved

    def _count_rows(self, tables: list[str]) -> dict[str, int]:
        """Count rows per table for the manifest and progress reporting."""
        counts: dict[str, int] = {}
        with self._engine.connect() as conn:
            for table_name in tables:
                result = conn.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")  # noqa: S608
                )
                counts[table_name] = result.scalar_one()
        return counts

    def _get_alembic_revision(self) -> str:
        """Read the current Alembic revision from the database."""
        try:
            with self._engine.connect() as conn:
                result = conn.execute(text("SELECT version_num FROM alembic_version"))
                rows = result.fetchall()
                if not rows:
                    return "unknown"
                if len(rows) > 1:
                    logger.warning(
                        "Multiple Alembic heads detected: %s",
                        [r[0] for r in rows],
                    )
                return str(rows[0][0])
        except Exception as e:
            logger.warning("Could not read alembic_version: %s", e)
            return "unknown"

    def _export_table(self, f: IO[str], table_name: str) -> int:
        """Export all rows from a single table to the JSONL file.

        Uses server-side streaming to avoid loading all rows into memory.
        """
        table = self._metadata.tables.get(table_name)
        if table is None:
            logger.warning("Table %s not found in metadata, skipping", table_name)
            return 0

        count = 0
        with self._engine.connect() as conn:
            # Use server-side cursor for streaming
            result = conn.execution_options(stream_results=True).execute(table.select())

            for partition in result.partitions(_STREAM_BATCH_SIZE):
                for row in partition:
                    row_data = _row_to_dict(row._mapping, table)
                    record = SyncRecord(table=table_name, data=row_data)
                    f.write(record.model_dump_json(by_alias=True) + "\n")
                    count += 1

        return count


def _row_to_dict(mapping: Any, table: Table) -> dict[str, Any]:
    """Convert a SQLAlchemy row mapping to a JSON-serializable dict.

    Handles special types:
    - datetime → ISO 8601 string
    - bytes → hex string
    - None → null (preserved)
    """
    result: dict[str, Any] = {}
    for key, value in mapping.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, bytes):
            result[key] = value.hex()
        else:
            result[key] = value
    return result


def _format_size(size_bytes: int) -> str:
    """Format byte count as human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} TB"
