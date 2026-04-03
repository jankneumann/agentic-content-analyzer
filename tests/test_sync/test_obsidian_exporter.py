"""Tests for obsidian_exporter module.

Covers: validate_vault_path(), ObsidianExporter export methods,
ExportSummary, dry-run mode, cleanup, incremental sync.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.sync.obsidian_exporter import (
    ExportOptions,
    ExportSummary,
    ObsidianExporter,
    validate_vault_path,
)


class TestValidateVaultPath:
    """Vault path safety validation."""

    def test_accepts_normal_path(self, tmp_path: Path) -> None:
        vault = tmp_path / "my-vault"
        vault.mkdir()
        result = validate_vault_path(str(vault))
        assert result.is_absolute()

    def test_accepts_nonexistent_path(self, tmp_path: Path) -> None:
        vault = tmp_path / "new-vault"
        result = validate_vault_path(str(vault))
        assert result.is_absolute()

    def test_rejects_traversal(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="traversal"):
            validate_vault_path(str(tmp_path / ".." / "escape"))

    def test_resolves_to_absolute(self, tmp_path: Path) -> None:
        result = validate_vault_path(str(tmp_path / "vault"))
        assert result.is_absolute()


class TestExportSummary:
    """ExportSummary dataclass and serialization."""

    def test_to_dict_structure(self) -> None:
        summary = ExportSummary()
        summary.digests.created = 3
        summary.digests.updated = 1
        summary.summaries.skipped = 5
        summary.elapsed_seconds = 1.234

        d = summary.to_dict()
        assert d["digests"] == {"created": 3, "updated": 1, "skipped": 0}
        assert d["summaries"] == {"created": 0, "updated": 0, "skipped": 5}
        assert d["elapsed_seconds"] == 1.23

    def test_to_dict_includes_warnings(self) -> None:
        summary = ExportSummary()
        summary.warnings = ["Neo4j unavailable"]
        d = summary.to_dict()
        assert d["warnings"] == ["Neo4j unavailable"]

    def test_to_dict_omits_warnings_when_empty(self) -> None:
        summary = ExportSummary()
        d = summary.to_dict()
        assert "warnings" not in d


class TestObsidianExporterWriteNote:
    """Tests for the _write_note helper and incremental sync."""

    @pytest.fixture()
    def exporter(self, tmp_path: Path) -> ObsidianExporter:
        vault = tmp_path / "vault"
        vault.mkdir()
        engine = MagicMock()
        return ObsidianExporter(engine=engine, vault_path=vault)

    def test_creates_new_file(self, exporter: ObsidianExporter) -> None:
        result = exporter._write_note(
            "Digests", "d-1", "digest", None, "Test Digest",
            "---\ngenerator: aca\n---\n# Test", "sha256:abc", ["ai"],
        )
        assert result == "created"
        assert (exporter._vault_path / "Digests").exists()

    def test_skips_unchanged(self, exporter: ObsidianExporter) -> None:
        # Write once
        exporter._write_note(
            "Digests", "d-1", "digest", None, "Test",
            "content", "sha256:abc", [],
        )
        # Write again with same hash
        result = exporter._write_note(
            "Digests", "d-1", "digest", None, "Test",
            "content", "sha256:abc", [],
        )
        assert result == "skipped"

    def test_updates_changed(self, exporter: ObsidianExporter) -> None:
        exporter._write_note(
            "Digests", "d-1", "digest", None, "Test",
            "content v1", "sha256:v1", [],
        )
        result = exporter._write_note(
            "Digests", "d-1", "digest", None, "Test",
            "content v2", "sha256:v2", [],
        )
        assert result == "updated"

    def test_dry_run_no_file_written(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        engine = MagicMock()
        options = ExportOptions(dry_run=True)
        exporter = ObsidianExporter(engine=engine, vault_path=vault, options=options)

        result = exporter._write_note(
            "Digests", "d-1", "digest", None, "Test",
            "content", "sha256:abc", [],
        )
        assert result == "created"
        # File should NOT exist in dry-run mode
        assert not (vault / "Digests").exists()

    def test_tracks_tags_for_mocs(self, exporter: ObsidianExporter) -> None:
        exporter._write_note(
            "Digests", "d-1", "digest", None, "Test",
            "content", "sha256:abc", ["ai", "ml"],
        )
        assert "ai" in exporter._all_tags
        assert "ml" in exporter._all_tags

    def test_tracks_id_to_filename(self, exporter: ObsidianExporter) -> None:
        exporter._write_note(
            "Digests", "d-1", "digest", None, "Test",
            "content", "sha256:abc", [],
        )
        assert "d-1" in exporter._id_to_filename


class TestObsidianExporterThemeMocs:
    """Theme MOC generation."""

    @pytest.fixture()
    def exporter(self, tmp_path: Path) -> ObsidianExporter:
        vault = tmp_path / "vault"
        vault.mkdir()
        engine = MagicMock()
        return ObsidianExporter(engine=engine, vault_path=vault)

    def test_generates_moc_files(self, exporter: ObsidianExporter) -> None:
        # Simulate tags collected during export
        exporter._all_tags = {
            "AI": [("Digests/d1.md", "digest"), ("Summaries/s1.md", "summary")],
            "ML": [("Digests/d2.md", "digest")],
        }

        stats = exporter.export_theme_mocs()
        assert stats.created == 2

        themes_dir = exporter._vault_path / "Themes"
        assert themes_dir.exists()
        moc_files = list(themes_dir.glob("*.md"))
        assert len(moc_files) == 2

        # Find the AI MOC file (filename is slugified)
        ai_moc = [f for f in moc_files if "ai" in f.name.lower()]
        assert len(ai_moc) == 1
        content = ai_moc[0].read_text()
        assert "generator: aca" in content
        assert "[[d1]]" in content
        assert "[[s1]]" in content

    def test_no_mocs_when_no_tags(self, exporter: ObsidianExporter) -> None:
        stats = exporter.export_theme_mocs()
        assert stats.created == 0


class TestObsidianExporterCleanup:
    """Stale file cleanup."""

    @pytest.fixture()
    def exporter(self, tmp_path: Path) -> ObsidianExporter:
        vault = tmp_path / "vault"
        vault.mkdir()
        engine = MagicMock()
        options = ExportOptions(clean=True)
        return ObsidianExporter(engine=engine, vault_path=vault, options=options)

    def test_removes_stale_managed_files(self, exporter: ObsidianExporter) -> None:
        # Create a managed file
        digests_dir = exporter._vault_path / "Digests"
        digests_dir.mkdir()
        stale_file = digests_dir / "old-digest.md"
        stale_file.write_text("---\ngenerator: aca\naca_id: \"d-old\"\n---\n# Old")

        # Record it in manifest but don't mark as current
        exporter._manifest.record("d-old", "Digests/old-digest.md", "digest", "sha256:old")
        # Reset current_ids — simulate it not being seen in this export
        exporter._manifest._current_ids = set()

        summary = ExportSummary()
        exporter._cleanup_stale_files(summary)

        assert not stale_file.exists()

    def test_preserves_unmanaged_files(self, exporter: ObsidianExporter) -> None:
        # Create a user file without generator: aca
        digests_dir = exporter._vault_path / "Digests"
        digests_dir.mkdir()
        user_file = digests_dir / "my-notes.md"
        user_file.write_text("# My Personal Notes\nSome thoughts")

        # Even if somehow in manifest, should not delete without generator: aca
        exporter._manifest.record("user-1", "Digests/my-notes.md", "digest", "sha256:x")
        exporter._manifest._current_ids = set()

        summary = ExportSummary()
        exporter._cleanup_stale_files(summary)

        assert user_file.exists()
