"""Unit tests for src.sync.pg_exporter.PGExporter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.sync.pg_exporter import PGExporter, _format_size, _row_to_dict


class TestFormatSize:
    """Test human-readable file size formatting."""

    def test_bytes(self) -> None:
        assert _format_size(500) == "500.0 B"

    def test_kilobytes(self) -> None:
        assert _format_size(2048) == "2.0 KB"

    def test_megabytes(self) -> None:
        assert _format_size(5 * 1024 * 1024) == "5.0 MB"


class TestRowToDict:
    """Test row serialization for JSONL output."""

    def test_basic_types(self) -> None:
        mapping = {"id": 1, "name": "test", "count": None}
        result = _row_to_dict(mapping, MagicMock())
        assert result == {"id": 1, "name": "test", "count": None}

    def test_datetime_serialized(self) -> None:
        from datetime import UTC, datetime

        dt = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
        mapping = {"created_at": dt}
        result = _row_to_dict(mapping, MagicMock())
        assert result["created_at"] == "2025-06-15T12:00:00+00:00"

    def test_bytes_serialized(self) -> None:
        mapping = {"data": b"\x01\x02\x03"}
        result = _row_to_dict(mapping, MagicMock())
        assert result["data"] == "010203"


class TestPGExporterResolveTable:
    """Test table resolution and validation."""

    def test_resolve_all_tables(self) -> None:
        engine = MagicMock()
        exporter = PGExporter(engine)
        result = exporter._resolve_tables(None)
        from src.sync.constants import SYNC_TABLES

        assert result == list(SYNC_TABLES)

    def test_resolve_with_closure(self) -> None:
        engine = MagicMock()
        exporter = PGExporter(engine)
        result = exporter._resolve_tables(["summaries"])
        assert "contents" in result  # FK parent auto-included
        assert "summaries" in result

    def test_resolve_unknown_table_raises(self) -> None:
        engine = MagicMock()
        exporter = PGExporter(engine)
        with pytest.raises(ValueError, match="Unknown tables"):
            exporter._resolve_tables(["nonexistent_table"])


class TestPGExporterFileHandling:
    """Test file overwrite behavior."""

    def test_export_raises_if_file_exists(self, tmp_path: Path) -> None:
        output = tmp_path / "export.jsonl"
        output.touch()

        engine = MagicMock()
        exporter = PGExporter(engine)
        with pytest.raises(FileExistsError, match="already exists"):
            exporter.export(output, force=False)

    def test_export_overwrites_with_force(self, tmp_path: Path) -> None:
        """Force mode should not raise for existing files."""
        output = tmp_path / "export.jsonl"
        output.write_text("old data")

        engine = MagicMock()
        exporter = PGExporter(engine)

        # Mock out the actual DB operations
        exporter._count_rows = MagicMock(return_value={})  # type: ignore[method-assign]
        exporter._get_alembic_revision = MagicMock(return_value="abc123")  # type: ignore[method-assign]

        result = exporter.export(output, tables=[], force=True)
        # Should succeed without raising
        assert isinstance(result, dict)
