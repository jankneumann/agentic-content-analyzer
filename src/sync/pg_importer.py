"""PostgreSQL JSONL importer for database sync.

Reads a JSONL export file and imports rows into a target PostgreSQL
database. Handles FK remapping, natural key deduplication, enum
validation, and self-referential FK two-pass resolution.

The importer accepts an explicit SQLAlchemy Engine (not the global
singleton) to support profile-based sync.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, Table, text
from sqlalchemy.engine import Engine

from src.sync.constants import (
    NATURAL_KEYS,
    SELF_REF_FKS,
    TABLE_LEVELS,
    UUID_PK_TABLES,
    get_enum_catalog,
)
from src.sync.id_mapper import IDMapper
from src.sync.models import ImportStats, SyncError, SyncManifest

logger = logging.getLogger(__name__)


class PGImporter:
    """Import PostgreSQL data from a JSONL export file.

    Reads the manifest, validates schema compatibility, then imports
    rows table-by-table in topological order. FK columns are remapped
    using IDMapper, enum values are validated, and natural keys are
    checked for deduplication.

    Args:
        engine: SQLAlchemy Engine connected to the target database.
        mode: Import mode — 'merge' (skip existing), 'replace' (upsert),
              or 'clean' (truncate + insert).
    """

    def __init__(self, engine: Engine, mode: str = "merge") -> None:
        self._engine = engine
        self._mode = mode
        self._metadata = MetaData()
        self._mapper = IDMapper()
        self._stats: dict[str, ImportStats] = {}
        self._errors: list[SyncError] = []

    @property
    def stats(self) -> dict[str, ImportStats]:
        """Per-table import statistics."""
        return self._stats

    @property
    def errors(self) -> list[SyncError]:
        """Non-fatal import errors."""
        return self._errors

    def import_file(
        self,
        input_path: Path,
        tables: list[str] | None = None,
        dry_run: bool = False,
    ) -> dict[str, ImportStats]:
        """Import data from a JSONL file into the target database.

        Args:
            input_path: Path to the JSONL export file.
            tables: Optional table filter. If None, imports all tables
                    found in the export.
            dry_run: If True, parse and validate without writing.

        Returns:
            Dict mapping table names to ImportStats.

        Raises:
            FileNotFoundError: If input_path doesn't exist.
            ValueError: If manifest is invalid or missing.
        """
        if not input_path.exists():
            raise FileNotFoundError(f"Import file not found: {input_path}")

        # Parse JSONL into manifest + grouped records
        manifest, records_by_table = self._parse_jsonl(input_path)

        # Schema compatibility check
        self._check_schema_compatibility(manifest)

        # Determine which tables to import
        import_tables = self._resolve_import_tables(list(records_by_table.keys()), tables)

        # Reflect target database metadata
        self._metadata.reflect(bind=self._engine, only=import_tables)

        # Clean mode: truncate tables
        if self._mode == "clean" and not dry_run:
            self._truncate_tables(import_tables)

        # Import in topological order (level by level)
        for level in TABLE_LEVELS:
            for table_name in level:
                if table_name not in import_tables:
                    continue
                rows = records_by_table.get(table_name, [])
                if not rows:
                    continue

                self._import_table(table_name, rows, dry_run)

                # Self-referential FK two-pass: apply deferred updates
                if table_name in SELF_REF_FKS and not dry_run:
                    self._apply_self_ref_updates(table_name)

        # Summary
        total_inserted = sum(s.inserted for s in self._stats.values())
        total_skipped = sum(s.skipped for s in self._stats.values())
        total_updated = sum(s.updated for s in self._stats.values())
        total_failed = sum(s.failed for s in self._stats.values())
        logger.info(
            "Import complete: inserted=%d, skipped=%d, updated=%d, failed=%d, errors=%d",
            total_inserted,
            total_skipped,
            total_updated,
            total_failed,
            len(self._errors),
        )

        return self._stats

    def _parse_jsonl(self, path: Path) -> tuple[SyncManifest, dict[str, list[dict]]]:
        """Parse JSONL file into manifest and grouped records.

        Returns:
            Tuple of (manifest, {table_name: [row_data_dicts]})
        """
        manifest: SyncManifest | None = None
        records: dict[str, list[dict]] = {}

        with open(path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError as e:
                    self._errors.append(
                        SyncError(
                            table="__parse__",
                            row_index=line_num,
                            message=f"Malformed JSON on line {line_num}: {e}",
                        )
                    )
                    logger.warning("Skipping malformed line %d: %s", line_num, e)
                    continue

                record_type = data.get("_type")

                if record_type == "manifest":
                    if manifest is not None:
                        logger.warning("Duplicate manifest on line %d, using first", line_num)
                        continue
                    manifest = SyncManifest.model_validate(data)

                elif record_type == "row":
                    table = data.get("table")
                    row_data = data.get("data")
                    if not table or not isinstance(row_data, dict):
                        self._errors.append(
                            SyncError(
                                table="__parse__",
                                row_index=line_num,
                                message=f"Invalid row record on line {line_num}",
                            )
                        )
                        continue
                    records.setdefault(table, []).append(row_data)

                elif record_type in ("neo4j_manifest", "neo4j_node", "neo4j_relationship"):
                    # Skip Neo4j records in PG importer
                    continue

                else:
                    logger.debug("Unknown record type on line %d: %s", line_num, record_type)

        if manifest is None:
            raise ValueError(
                "No manifest found in JSONL file. Expected first line with _type='manifest'."
            )

        return manifest, records

    def _check_schema_compatibility(self, manifest: SyncManifest) -> None:
        """Check that the target database schema is compatible.

        Compares the Alembic revision from the manifest against
        the target database's alembic_version table.
        """
        source_rev = manifest.alembic_rev
        if source_rev == "unknown":
            logger.warning("Export has unknown Alembic revision, skipping schema check")
            return

        try:
            with self._engine.connect() as conn:
                result = conn.execute(text("SELECT version_num FROM alembic_version"))
                rows = result.fetchall()
        except Exception as e:
            logger.warning(
                "Could not read alembic_version from target: %s. Proceeding without schema check.",
                e,
            )
            return

        if not rows:
            logger.warning(
                "Target database has no Alembic revision. "
                "Run 'alembic upgrade head' to initialize schema."
            )
            return

        if len(rows) > 1:
            revisions = [r[0] for r in rows]
            raise ValueError(
                f"Target database has multiple Alembic heads: {revisions}. "
                f"Run 'alembic merge heads' to linearize migrations before importing."
            )

        target_rev = rows[0][0]

        if target_rev == source_rev:
            logger.info("Schema versions match: %s", source_rev)
        else:
            # We can't easily determine ordering without walking the revision chain.
            # Log a warning and proceed — the import may still work if schemas are
            # compatible (new columns are typically nullable with defaults).
            logger.warning(
                "Schema version mismatch: export=%s, target=%s. "
                "If import fails, run 'alembic upgrade head' on the target.",
                source_rev,
                target_rev,
            )

    def _resolve_import_tables(
        self,
        available: list[str],
        requested: list[str] | None,
    ) -> list[str]:
        """Determine which tables to import."""
        if requested is None:
            # Import all tables present in the export, in topological order
            ordered = [t for level in TABLE_LEVELS for t in level if t in available]
            return ordered

        # Filter to requested tables (must be in export)
        missing = set(requested) - set(available)
        if missing:
            logger.warning("Requested tables not in export: %s", ", ".join(sorted(missing)))

        return [t for level in TABLE_LEVELS for t in level if t in requested and t in available]

    def _truncate_tables(self, tables: list[str]) -> None:
        """Truncate tables in reverse dependency order for clean mode."""
        # Reverse topological order: children first, then parents
        reverse_order = list(reversed(tables))
        with self._engine.begin() as conn:
            for table_name in reverse_order:
                conn.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))
                logger.info("Truncated table: %s", table_name)

    def _import_table(
        self,
        table_name: str,
        rows: list[dict],
        dry_run: bool,
    ) -> None:
        """Import all rows for a single table.

        Processing pipeline per row:
        1. Remap FK columns via IDMapper
        2. Validate enum values
        3. Natural key dedup lookup
        4. Skip/update/insert based on mode
        5. Record old→new ID mapping
        """
        stats = ImportStats()
        self._stats[table_name] = stats

        table = self._metadata.tables.get(table_name)
        if table is None:
            logger.warning("Table %s not found in target database, skipping", table_name)
            stats.failed = len(rows)
            return

        enum_catalog = get_enum_catalog()
        is_uuid_table = table_name in UUID_PK_TABLES
        self_ref_col = SELF_REF_FKS.get(table_name)

        with self._engine.begin() as conn:
            for row_idx, data in enumerate(rows):
                try:
                    # Save original ID for mapping
                    old_id = data.get("id")

                    # Step 0: Handle self-referential FK — defer to two-pass
                    if self_ref_col and data.get(self_ref_col) is not None:
                        old_self_ref = data[self_ref_col]
                        data[self_ref_col] = None  # Insert with NULL
                    else:
                        old_self_ref = None

                    # Step 1: Remap FK columns
                    data, fk_warnings = self._mapper.remap_row_fks(table_name, data)
                    for warning in fk_warnings:
                        logger.warning(warning)

                    # Step 2: Validate enum values
                    if not self._validate_enums(table_name, data, row_idx, enum_catalog):
                        stats.failed += 1
                        continue

                    # Step 3: Natural key dedup lookup
                    # Remove 'id' before insert — let the target DB assign new IDs
                    # (except for UUID PK tables where id IS the natural key)
                    if not is_uuid_table:
                        data.pop("id", None)

                    existing_id = self._find_by_natural_key(conn, table, table_name, data)

                    if dry_run:
                        if existing_id is not None:
                            stats.skipped += 1
                        else:
                            stats.inserted += 1
                        continue

                    # Step 4: Skip/update/insert based on mode
                    if existing_id is not None:
                        if self._mode == "merge":
                            stats.skipped += 1
                            # Record mapping even for skipped rows
                            if old_id is not None:
                                if is_uuid_table:
                                    self._mapper.record_uuid_mapping(
                                        table_name, str(old_id), str(existing_id)
                                    )
                                else:
                                    self._mapper.record_mapping(table_name, old_id, existing_id)
                            continue

                        elif self._mode == "replace":
                            # Update existing row
                            natural_keys = NATURAL_KEYS.get(table_name, [])
                            update_data = {k: v for k, v in data.items() if k not in natural_keys}
                            if update_data:
                                nk_filter = {k: data[k] for k in natural_keys if k in data}
                                where_clause = " AND ".join(f"{k} = :{k}" for k in nk_filter)
                                set_clause = ", ".join(f"{k} = :set_{k}" for k in update_data)
                                params = {f"set_{k}": v for k, v in update_data.items()}
                                params.update(nk_filter)
                                conn.execute(
                                    text(
                                        f"UPDATE {table_name} SET {set_clause} "  # noqa: S608
                                        f"WHERE {where_clause}"
                                    ),
                                    params,
                                )
                            stats.updated += 1
                            if old_id is not None:
                                if is_uuid_table:
                                    self._mapper.record_uuid_mapping(
                                        table_name, str(old_id), str(existing_id)
                                    )
                                else:
                                    self._mapper.record_mapping(table_name, old_id, existing_id)
                            continue

                    # Step 5: Insert new row
                    result = conn.execute(table.insert().values(**data))
                    if is_uuid_table:
                        new_id = data.get("id")
                        if old_id is not None and new_id is not None:
                            self._mapper.record_uuid_mapping(table_name, str(old_id), str(new_id))
                    else:
                        pk = result.inserted_primary_key
                        new_id = pk[0] if pk is not None else None
                        if old_id is not None and new_id is not None:
                            self._mapper.record_mapping(table_name, old_id, new_id)

                    stats.inserted += 1

                    # Record deferred self-ref FK
                    if old_self_ref is not None and new_id is not None:
                        self._mapper.defer_self_ref(table_name, new_id, old_self_ref)

                except Exception as e:
                    self._errors.append(
                        SyncError(
                            table=table_name,
                            row_index=row_idx,
                            message=str(e),
                        )
                    )
                    stats.failed += 1
                    logger.warning("Failed to import %s row %d: %s", table_name, row_idx, e)

        logger.info(
            "Imported %s: inserted=%d, skipped=%d, updated=%d, failed=%d",
            table_name,
            stats.inserted,
            stats.skipped,
            stats.updated,
            stats.failed,
        )

    def _validate_enums(
        self,
        table_name: str,
        data: dict,
        row_idx: int,
        enum_catalog: dict[str, set[str]],
    ) -> bool:
        """Validate enum column values against the catalog.

        Returns True if all enums are valid, False if any are invalid.
        """
        for col_key, valid_values in enum_catalog.items():
            cat_table, cat_col = col_key.split(".", 1)
            if cat_table != table_name:
                continue
            value = data.get(cat_col)
            if value is not None and value not in valid_values:
                self._errors.append(
                    SyncError(
                        table=table_name,
                        row_index=row_idx,
                        message=(
                            f"Invalid enum value for {cat_col}: '{value}'. "
                            f"Valid values: {sorted(valid_values)}"
                        ),
                    )
                )
                logger.warning(
                    "Skipping %s row %d: invalid enum %s='%s'",
                    table_name,
                    row_idx,
                    cat_col,
                    value,
                )
                return False
        return True

    def _find_by_natural_key(
        self,
        conn: Any,
        table: Table,
        table_name: str,
        data: dict,
    ) -> Any:
        """Look up an existing row by natural key.

        Returns the existing row's primary key (id) if found, None otherwise.
        """
        natural_keys = NATURAL_KEYS.get(table_name)
        if not natural_keys:
            return None

        # Build WHERE clause from natural key columns
        conditions = {}
        for nk_col in natural_keys:
            value = data.get(nk_col)
            if value is None:
                return None  # Can't match if natural key component is NULL
            conditions[nk_col] = value

        where_parts = [f"{col} = :{col}" for col in conditions]
        where_clause = " AND ".join(where_parts)

        pk_col = "id"
        result = conn.execute(
            text(f"SELECT {pk_col} FROM {table_name} WHERE {where_clause}"),  # noqa: S608
            conditions,
        )
        row = result.fetchone()
        return row[0] if row else None

    def _apply_self_ref_updates(self, table_name: str) -> None:
        """Apply deferred self-referential FK updates (two-pass step 2)."""
        self_ref_col = SELF_REF_FKS.get(table_name)
        if not self_ref_col:
            return

        updates = self._mapper.get_self_ref_updates(table_name)
        if not updates:
            return

        logger.info(
            "Applying %d self-referential FK updates for %s.%s",
            len(updates),
            table_name,
            self_ref_col,
        )

        with self._engine.begin() as conn:
            for new_id, new_parent_id in updates:
                conn.execute(
                    text(
                        f"UPDATE {table_name} SET {self_ref_col} = :parent_id "  # noqa: S608
                        f"WHERE id = :row_id"
                    ),
                    {"parent_id": new_parent_id, "row_id": new_id},
                )

        logger.info(
            "Self-ref FK updates complete for %s: %d rows updated",
            table_name,
            len(updates),
        )
