"""Unit tests for src.sync.pg_importer.PGImporter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.sync.pg_importer import PGImporter


def _write_jsonl(path: Path, lines: list[dict]) -> None:
    """Write a list of dicts as JSONL lines."""
    with open(path, "w") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")


class TestParseJSONL:
    """Test JSONL parsing and validation."""

    def test_parse_valid_manifest_and_rows(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        path = tmp_path / "test.jsonl"
        _write_jsonl(
            path,
            [
                {
                    "_type": "manifest",
                    "alembic_rev": "abc123",
                    "exported_at": "2025-06-15T12:00:00Z",
                    "tables": {"contents": 2},
                    "version": 1,
                },
                {
                    "_type": "row",
                    "table": "contents",
                    "data": {"id": 1, "content_hash": "hash1"},
                },
                {
                    "_type": "row",
                    "table": "contents",
                    "data": {"id": 2, "content_hash": "hash2"},
                },
            ],
        )

        engine = MagicMock()
        importer = PGImporter(engine)
        manifest, records = importer._parse_jsonl(path)

        assert manifest.alembic_rev == "abc123"
        assert len(records["contents"]) == 2
        assert records["contents"][0]["content_hash"] == "hash1"

    def test_parse_missing_manifest_raises(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        path = tmp_path / "test.jsonl"
        _write_jsonl(
            path,
            [
                {
                    "_type": "row",
                    "table": "contents",
                    "data": {"id": 1},
                },
            ],
        )

        engine = MagicMock()
        importer = PGImporter(engine)
        with pytest.raises(ValueError, match="No manifest found"):
            importer._parse_jsonl(path)

    def test_parse_malformed_line_skipped(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        path = tmp_path / "test.jsonl"
        with open(path, "w") as f:
            f.write(
                json.dumps(
                    {
                        "_type": "manifest",
                        "alembic_rev": "abc",
                        "exported_at": "2025-01-01T00:00:00Z",
                        "tables": {},
                        "version": 1,
                    }
                )
                + "\n"
            )
            f.write("this is not valid json\n")
            f.write(
                json.dumps(
                    {
                        "_type": "row",
                        "table": "contents",
                        "data": {"id": 1},
                    }
                )
                + "\n"
            )

        engine = MagicMock()
        importer = PGImporter(engine)
        manifest, records = importer._parse_jsonl(path)

        assert manifest is not None
        assert len(records.get("contents", [])) == 1
        assert len(importer.errors) == 1
        assert "Malformed JSON" in importer.errors[0].message

    def test_parse_neo4j_records_skipped(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        path = tmp_path / "test.jsonl"
        _write_jsonl(
            path,
            [
                {
                    "_type": "manifest",
                    "alembic_rev": "abc",
                    "exported_at": "2025-01-01T00:00:00Z",
                    "tables": {},
                    "version": 1,
                },
                {
                    "_type": "neo4j_node",
                    "label": "Entity",
                    "uuid": "x",
                    "properties": {},
                },
            ],
        )

        engine = MagicMock()
        importer = PGImporter(engine)
        manifest, records = importer._parse_jsonl(path)

        assert manifest is not None
        assert len(records) == 0  # Neo4j records not included


class TestFileNotFound:
    """Test error handling for missing input files."""

    def test_import_missing_file_raises(self) -> None:
        from unittest.mock import MagicMock

        engine = MagicMock()
        importer = PGImporter(engine)
        with pytest.raises(FileNotFoundError, match="Import file not found"):
            importer.import_file(Path("/nonexistent/file.jsonl"))


class TestEnumValidation:
    """Test enum value validation."""

    def test_valid_enum_passes(self) -> None:
        from unittest.mock import MagicMock

        engine = MagicMock()
        importer = PGImporter(engine)
        catalog = {"contents.source_type": {"rss", "gmail", "file_upload"}}
        data = {"source_type": "rss"}
        assert importer._validate_enums("contents", data, 0, catalog)

    def test_invalid_enum_fails(self) -> None:
        from unittest.mock import MagicMock

        engine = MagicMock()
        importer = PGImporter(engine)
        catalog = {"contents.source_type": {"rss", "gmail"}}
        data = {"source_type": "unknown_source"}
        assert not importer._validate_enums("contents", data, 0, catalog)
        assert len(importer.errors) == 1
        assert "Invalid enum value" in importer.errors[0].message

    def test_null_enum_passes(self) -> None:
        from unittest.mock import MagicMock

        engine = MagicMock()
        importer = PGImporter(engine)
        catalog = {"contents.source_type": {"rss", "gmail"}}
        data = {"source_type": None}
        assert importer._validate_enums("contents", data, 0, catalog)

    def test_unrelated_table_passes(self) -> None:
        from unittest.mock import MagicMock

        engine = MagicMock()
        importer = PGImporter(engine)
        catalog = {"contents.source_type": {"rss", "gmail"}}
        data = {"key": "test"}
        # prompt_overrides doesn't have enum columns
        assert importer._validate_enums("prompt_overrides", data, 0, catalog)
