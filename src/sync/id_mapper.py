"""ID mapping for cross-database FK remapping during sync import.

When importing data into a target database, auto-increment IDs differ
from the source. This module tracks old→new ID mappings as parent table
rows are inserted, then remaps FK columns in child table rows.
"""

from __future__ import annotations

import logging

from src.sync.constants import FK_COLUMNS, SELF_REF_FKS, UUID_PK_TABLES

logger = logging.getLogger(__name__)


class IDMapper:
    """Maps source IDs to target IDs during import.

    As parent table rows are inserted into the target database,
    their old→new ID mappings are recorded. When child table rows
    are processed, FK columns are remapped using these mappings.
    """

    def __init__(self) -> None:
        self._id_map: dict[str, dict[int, int]] = {}
        self._uuid_map: dict[str, dict[str, str]] = {}
        self._deferred_self_refs: dict[str, list[tuple[int, int]]] = {}

    def record_mapping(self, table: str, old_id: int, new_id: int) -> None:
        """Record an old→new integer ID mapping for a table."""
        if table not in self._id_map:
            self._id_map[table] = {}
        self._id_map[table][old_id] = new_id

    def record_uuid_mapping(self, table: str, old_uuid: str, new_uuid: str) -> None:
        """Record an old→new UUID mapping for a table."""
        if table not in self._uuid_map:
            self._uuid_map[table] = {}
        self._uuid_map[table][old_uuid] = new_uuid

    def remap_fk(self, parent_table: str, old_id: int) -> int | None:
        """Look up the new ID for a parent table FK reference.

        Returns None if the old_id is not in the map
        (parent was skipped or failed).
        """
        return self._id_map.get(parent_table, {}).get(old_id)

    def remap_uuid(self, parent_table: str, old_uuid: str) -> str | None:
        """Look up the new UUID for a parent table FK reference."""
        return self._uuid_map.get(parent_table, {}).get(old_uuid)

    def remap_row_fks(self, table: str, data: dict) -> tuple[dict, list[str]]:
        """Remap all FK columns in a row's data dict.

        Skips self-referential FKs (handled in two-pass).
        Sets unmappable FKs to None rather than leaving stale IDs.

        Args:
            table: Table name
            data: Row data dict (will be mutated)

        Returns:
            Tuple of (remapped data, list of warning messages)
        """
        warnings: list[str] = []
        fk_defs = FK_COLUMNS.get(table, {})

        # Skip self-referential FKs (handled in two-pass)
        self_ref_col = SELF_REF_FKS.get(table)

        for fk_col, parent_table in fk_defs.items():
            if fk_col == self_ref_col:
                continue  # Handled separately in two-pass

            old_value = data.get(fk_col)
            if old_value is None:
                continue  # Nullable FK, nothing to remap

            if parent_table in UUID_PK_TABLES:
                new_value: int | str | None = self.remap_uuid(parent_table, str(old_value))
            else:
                new_value = self.remap_fk(parent_table, old_value)

            if new_value is None:
                warnings.append(
                    f"FK remap failed: {table}.{fk_col}={old_value} -> no mapping in {parent_table}"
                )
                data[fk_col] = None  # Set to NULL rather than leaving stale ID
            else:
                data[fk_col] = new_value

        return data, warnings

    def defer_self_ref(self, table: str, new_id: int, old_parent_id: int) -> None:
        """Record a deferred self-referential FK update.

        Called during first pass when a row has a self-referential FK.
        The FK is set to NULL on insert; the real value is applied
        in the second pass via get_self_ref_updates().
        """
        if table not in self._deferred_self_refs:
            self._deferred_self_refs[table] = []
        self._deferred_self_refs[table].append((new_id, old_parent_id))

    def get_self_ref_updates(self, table: str) -> list[tuple[int, int]]:
        """Get pending self-referential FK updates for a table.

        Returns list of (new_row_id, new_parent_id) tuples for batch UPDATE.
        Called after all rows in the table are inserted and id_map is complete.
        """
        self_ref_col = SELF_REF_FKS.get(table)
        if not self_ref_col or table not in self._deferred_self_refs:
            return []

        updates: list[tuple[int, int]] = []
        for new_id, old_parent_id in self._deferred_self_refs[table]:
            new_parent_id = self.remap_fk(table, old_parent_id)
            if new_parent_id is not None:
                updates.append((new_id, new_parent_id))
            else:
                logger.warning(
                    "Self-ref FK remap failed: %s.%s old_parent=%d for row new_id=%d",
                    table,
                    self_ref_col,
                    old_parent_id,
                    new_id,
                )
        return updates

    @property
    def id_map(self) -> dict[str, dict[int, int]]:
        """Read-only access to the integer ID mapping."""
        return self._id_map

    @property
    def uuid_map(self) -> dict[str, dict[str, str]]:
        """Read-only access to the UUID mapping."""
        return self._uuid_map
