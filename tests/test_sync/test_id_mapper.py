"""Unit tests for src.sync.id_mapper.IDMapper."""

from __future__ import annotations

from src.sync.id_mapper import IDMapper


class TestRecordMapping:
    """Test integer ID mapping."""

    def test_record_and_remap(self) -> None:
        mapper = IDMapper()
        mapper.record_mapping("contents", old_id=10, new_id=100)
        assert mapper.remap_fk("contents", 10) == 100

    def test_remap_missing_returns_none(self) -> None:
        mapper = IDMapper()
        assert mapper.remap_fk("contents", 999) is None

    def test_remap_missing_table_returns_none(self) -> None:
        mapper = IDMapper()
        assert mapper.remap_fk("nonexistent", 1) is None

    def test_multiple_tables(self) -> None:
        mapper = IDMapper()
        mapper.record_mapping("contents", 1, 100)
        mapper.record_mapping("digests", 1, 200)
        assert mapper.remap_fk("contents", 1) == 100
        assert mapper.remap_fk("digests", 1) == 200


class TestUUIDMapping:
    """Test UUID string mapping."""

    def test_record_and_remap_uuid(self) -> None:
        mapper = IDMapper()
        mapper.record_uuid_mapping("images", "old-uuid-1", "new-uuid-1")
        assert mapper.remap_uuid("images", "old-uuid-1") == "new-uuid-1"

    def test_remap_uuid_missing_returns_none(self) -> None:
        mapper = IDMapper()
        assert mapper.remap_uuid("images", "nonexistent") is None


class TestRemapRowFKs:
    """Test remap_row_fks method."""

    def test_remap_single_fk(self) -> None:
        mapper = IDMapper()
        mapper.record_mapping("contents", 10, 100)
        data = {"content_id": 10, "text": "hello"}
        remapped, warnings = mapper.remap_row_fks("summaries", data)
        assert remapped["content_id"] == 100
        assert not warnings

    def test_nullable_fk_skipped(self) -> None:
        mapper = IDMapper()
        data = {"content_id": None, "text": "hello"}
        remapped, warnings = mapper.remap_row_fks("summaries", data)
        assert remapped["content_id"] is None
        assert not warnings

    def test_unmappable_fk_set_to_none(self) -> None:
        mapper = IDMapper()
        # No mapping recorded for contents
        data = {"content_id": 999, "text": "hello"}
        remapped, warnings = mapper.remap_row_fks("summaries", data)
        assert remapped["content_id"] is None
        assert len(warnings) == 1
        assert "FK remap failed" in warnings[0]

    def test_self_ref_fk_skipped(self) -> None:
        """Self-referential FKs are handled in two-pass, not by remap_row_fks."""
        mapper = IDMapper()
        data = {"canonical_id": 5, "content_hash": "abc"}
        remapped, warnings = mapper.remap_row_fks("contents", data)
        # canonical_id should NOT be remapped (it's a self-ref)
        assert remapped["canonical_id"] == 5
        assert not warnings

    def test_uuid_fk_remap(self) -> None:
        mapper = IDMapper()
        mapper.record_uuid_mapping("conversations", "old-conv", "new-conv")
        data = {"conversation_id": "old-conv", "content": "msg"}
        remapped, warnings = mapper.remap_row_fks("chat_messages", data)
        assert remapped["conversation_id"] == "new-conv"
        assert not warnings

    def test_multiple_fks_in_images(self) -> None:
        mapper = IDMapper()
        mapper.record_mapping("contents", 1, 100)
        mapper.record_mapping("summaries", 2, 200)
        mapper.record_mapping("digests", 3, 300)
        data = {
            "source_content_id": 1,
            "source_summary_id": 2,
            "source_digest_id": 3,
        }
        remapped, warnings = mapper.remap_row_fks("images", data)
        assert remapped["source_content_id"] == 100
        assert remapped["source_summary_id"] == 200
        assert remapped["source_digest_id"] == 300
        assert not warnings

    def test_table_without_fks(self) -> None:
        mapper = IDMapper()
        data = {"key": "test", "value": "hello"}
        remapped, warnings = mapper.remap_row_fks("prompt_overrides", data)
        assert remapped == data
        assert not warnings


class TestSelfRefDeferred:
    """Test self-referential FK deferred two-pass handling."""

    def test_defer_and_resolve(self) -> None:
        mapper = IDMapper()
        # Record mappings: old 1→new 100, old 2→new 200
        mapper.record_mapping("contents", 1, 100)
        mapper.record_mapping("contents", 2, 200)

        # Row with new_id=200 has self-ref to old_parent_id=1
        mapper.defer_self_ref("contents", new_id=200, old_parent_id=1)

        updates = mapper.get_self_ref_updates("contents")
        assert len(updates) == 1
        assert updates[0] == (200, 100)  # (new_row_id, new_parent_id)

    def test_defer_unresolvable_logged(self) -> None:
        mapper = IDMapper()
        mapper.record_mapping("contents", 1, 100)
        # Parent 999 doesn't exist in id_map
        mapper.defer_self_ref("contents", new_id=100, old_parent_id=999)

        updates = mapper.get_self_ref_updates("contents")
        assert len(updates) == 0  # Unresolvable, logged as warning

    def test_no_deferred_returns_empty(self) -> None:
        mapper = IDMapper()
        updates = mapper.get_self_ref_updates("contents")
        assert updates == []

    def test_non_self_ref_table_returns_empty(self) -> None:
        mapper = IDMapper()
        updates = mapper.get_self_ref_updates("summaries")
        assert updates == []


class TestProperties:
    """Test read-only property access."""

    def test_id_map_property(self) -> None:
        mapper = IDMapper()
        mapper.record_mapping("contents", 1, 100)
        assert mapper.id_map == {"contents": {1: 100}}

    def test_uuid_map_property(self) -> None:
        mapper = IDMapper()
        mapper.record_uuid_mapping("images", "a", "b")
        assert mapper.uuid_map == {"images": {"a": "b"}}
