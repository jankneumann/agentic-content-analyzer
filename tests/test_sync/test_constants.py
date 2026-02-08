"""Unit tests for src.sync.constants."""

from __future__ import annotations

from src.sync.constants import (
    EXCLUDED_TABLES,
    FK_COLUMNS,
    NATURAL_KEYS,
    SELF_REF_FKS,
    SYNC_TABLES,
    TABLE_DEPENDENCIES,
    TABLE_LEVELS,
    UUID_PK_TABLES,
    compute_table_closure,
)


class TestTableDependencies:
    """Test the table dependency DAG and topological ordering."""

    def test_sync_tables_matches_levels(self) -> None:
        """SYNC_TABLES should be the flat version of TABLE_LEVELS."""
        from_levels = [t for level in TABLE_LEVELS for t in level]
        assert from_levels == SYNC_TABLES

    def test_all_tables_have_natural_keys(self) -> None:
        """Every syncable table must have a natural key defined."""
        for table in SYNC_TABLES:
            assert table in NATURAL_KEYS, f"Missing natural key for {table}"

    def test_fk_parents_in_sync_tables(self) -> None:
        """All FK parent references must point to syncable tables."""
        for child_table, parent_tables in TABLE_DEPENDENCIES.items():
            assert child_table in SYNC_TABLES, f"{child_table} not in SYNC_TABLES"
            for parent in parent_tables:
                assert parent in SYNC_TABLES, (
                    f"FK parent {parent} (from {child_table}) not in SYNC_TABLES"
                )

    def test_fk_columns_reference_valid_parents(self) -> None:
        """FK_COLUMNS parent table references must be in SYNC_TABLES."""
        for child, fk_defs in FK_COLUMNS.items():
            for fk_col, parent in fk_defs.items():
                assert parent in SYNC_TABLES, f"FK {child}.{fk_col} → {parent} not in SYNC_TABLES"

    def test_self_ref_tables_in_level_0(self) -> None:
        """Self-referential FK tables must be in Level 0."""
        level_0 = set(TABLE_LEVELS[0])
        for table in SELF_REF_FKS:
            assert table in level_0, f"{table} has self-ref FK but is not in Level 0"

    def test_excluded_tables_not_in_sync(self) -> None:
        """Excluded tables must not appear in SYNC_TABLES."""
        for table in EXCLUDED_TABLES:
            assert table not in SYNC_TABLES, f"{table} is both excluded and syncable"

    def test_topological_order_parents_before_children(self) -> None:
        """In SYNC_TABLES, every FK parent must appear before its child."""
        positions = {t: i for i, t in enumerate(SYNC_TABLES)}
        for child, parents in TABLE_DEPENDENCIES.items():
            if child not in positions:
                continue
            for parent in parents:
                assert positions[parent] <= positions[child], (
                    f"Parent {parent} (pos {positions[parent]}) appears after "
                    f"child {child} (pos {positions[child]})"
                )


class TestComputeTableClosure:
    """Test transitive FK parent closure."""

    def test_leaf_table_includes_all_ancestors(self) -> None:
        """Requesting 'podcasts' should include podcast_scripts and digests."""
        result = compute_table_closure(["podcasts"])
        assert "podcast_scripts" in result
        assert "digests" in result
        assert "podcasts" in result

    def test_table_with_no_parents(self) -> None:
        """Requesting a Level 0 table returns just that table."""
        result = compute_table_closure(["contents"])
        assert result == ["contents"]

    def test_multiple_tables_union(self) -> None:
        """Multiple requested tables merge their parent closures."""
        result = compute_table_closure(["summaries", "chat_messages"])
        assert "contents" in result  # parent of summaries
        assert "conversations" in result  # parent of chat_messages
        assert "summaries" in result
        assert "chat_messages" in result

    def test_result_is_topologically_ordered(self) -> None:
        """Result must be in topological order (parents before children)."""
        result = compute_table_closure(["images"])
        positions = {t: i for i, t in enumerate(result)}
        # images depends on contents, summaries, digests
        assert positions["contents"] < positions["images"]
        assert positions["summaries"] < positions["images"]
        assert positions["digests"] < positions["images"]

    def test_empty_input(self) -> None:
        result = compute_table_closure([])
        assert result == []


class TestUUIDPKTables:
    """Test UUID primary key table configuration."""

    def test_uuid_tables_are_syncable(self) -> None:
        for table in UUID_PK_TABLES:
            assert table in SYNC_TABLES, f"UUID PK table {table} not in SYNC_TABLES"

    def test_uuid_tables_have_id_natural_key(self) -> None:
        """UUID PK tables should use 'id' as their natural key."""
        for table in UUID_PK_TABLES:
            nk = NATURAL_KEYS.get(table, [])
            assert "id" in nk, f"UUID PK table {table} missing 'id' in natural keys"
