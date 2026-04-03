"""Tests for obsidian_manifest module.

Covers: SyncManifest load/save, needs_update, stale detection,
corrupt manifest recovery, atomic writes.
"""

import json
from pathlib import Path

import pytest

from src.sync.obsidian_manifest import ManifestEntry, SyncManifest


@pytest.fixture()
def vault_dir(tmp_path: Path) -> Path:
    """Create a temporary vault directory."""
    vault = tmp_path / "test-vault"
    vault.mkdir()
    return vault


class TestSyncManifestLoad:
    """Manifest loading and creation."""

    def test_load_creates_empty_when_no_file(self, vault_dir: Path) -> None:
        manifest = SyncManifest.load(vault_dir)
        assert manifest.version == 1
        assert len(manifest.entries) == 0

    def test_load_reads_existing(self, vault_dir: Path) -> None:
        manifest_path = vault_dir / ".obsidian-sync-manifest.json"
        data = {
            "version": 1,
            "last_sync": "2026-04-03T10:00:00Z",
            "entries": {
                "digest-1": {
                    "filename": "Digests/2026-04-03-daily.md",
                    "aca_type": "digest",
                    "content_hash": "sha256:abc123",
                    "exported_at": "2026-04-03T10:00:00Z",
                },
            },
        }
        manifest_path.write_text(json.dumps(data))

        manifest = SyncManifest.load(vault_dir)
        assert "digest-1" in manifest.entries
        assert manifest.entries["digest-1"].filename == "Digests/2026-04-03-daily.md"
        assert manifest.entries["digest-1"].content_hash == "sha256:abc123"

    def test_load_recovers_from_corrupt_json(self, vault_dir: Path) -> None:
        manifest_path = vault_dir / ".obsidian-sync-manifest.json"
        manifest_path.write_text("{invalid json!!!")

        manifest = SyncManifest.load(vault_dir)

        # Should return empty manifest
        assert len(manifest.entries) == 0
        # Corrupt file should be renamed to .bak
        assert (vault_dir / ".obsidian-sync-manifest.json.bak").exists()
        assert not manifest_path.exists()


class TestSyncManifestNeedsUpdate:
    """Incremental sync change detection."""

    def test_new_item_needs_update(self, vault_dir: Path) -> None:
        manifest = SyncManifest.load(vault_dir)
        assert manifest.needs_update("new-item", "sha256:abc") is True

    def test_unchanged_item_skipped(self, vault_dir: Path) -> None:
        manifest = SyncManifest.load(vault_dir)
        manifest.record("item-1", "Digests/file.md", "digest", "sha256:abc")
        assert manifest.needs_update("item-1", "sha256:abc") is False

    def test_changed_item_needs_update(self, vault_dir: Path) -> None:
        manifest = SyncManifest.load(vault_dir)
        manifest.record("item-1", "Digests/file.md", "digest", "sha256:old")
        assert manifest.needs_update("item-1", "sha256:new") is True


class TestSyncManifestStaleDetection:
    """Detection of items no longer in the database."""

    def test_get_stale_entries(self, vault_dir: Path) -> None:
        manifest = SyncManifest.load(vault_dir)
        manifest.record("item-1", "Digests/a.md", "digest", "sha256:a")
        manifest.record("item-2", "Digests/b.md", "digest", "sha256:b")

        # Simulate a new export session — reset current_ids, then only mark item-1
        manifest._current_ids = set()
        manifest.mark_current("item-1")

        stale = manifest.get_stale_entries()
        assert len(stale) == 1
        assert stale[0].aca_id == "item-2"

    def test_no_stale_when_all_current(self, vault_dir: Path) -> None:
        manifest = SyncManifest.load(vault_dir)
        manifest.record("item-1", "Digests/a.md", "digest", "sha256:a")

        # Record already marks as current
        stale = manifest.get_stale_entries()
        assert len(stale) == 0


class TestSyncManifestSave:
    """Atomic manifest persistence."""

    def test_save_creates_manifest_file(self, vault_dir: Path) -> None:
        manifest = SyncManifest.load(vault_dir)
        manifest.record("item-1", "Digests/a.md", "digest", "sha256:a")
        manifest.save()

        manifest_path = vault_dir / ".obsidian-sync-manifest.json"
        assert manifest_path.exists()

        data = json.loads(manifest_path.read_text())
        assert data["version"] == 1
        assert "item-1" in data["entries"]
        assert data["entries"]["item-1"]["content_hash"] == "sha256:a"

    def test_save_roundtrip(self, vault_dir: Path) -> None:
        manifest = SyncManifest.load(vault_dir)
        manifest.record("d-1", "Digests/x.md", "digest", "sha256:x1")
        manifest.record("s-1", "Summaries/y.md", "summary", "sha256:y1")
        manifest.save()

        reloaded = SyncManifest.load(vault_dir)
        assert "d-1" in reloaded.entries
        assert "s-1" in reloaded.entries
        assert reloaded.entries["d-1"].content_hash == "sha256:x1"

    def test_save_overwrites_atomically(self, vault_dir: Path) -> None:
        manifest = SyncManifest.load(vault_dir)
        manifest.record("item-1", "Digests/a.md", "digest", "sha256:v1")
        manifest.save()

        # Update and save again
        manifest.record("item-1", "Digests/a.md", "digest", "sha256:v2")
        manifest.save()

        reloaded = SyncManifest.load(vault_dir)
        assert reloaded.entries["item-1"].content_hash == "sha256:v2"


class TestSyncManifestFilename:
    """Filename tracking for wikilink stability."""

    def test_get_filename_returns_none_for_unknown(self, vault_dir: Path) -> None:
        manifest = SyncManifest.load(vault_dir)
        assert manifest.get_filename("unknown") is None

    def test_get_filename_returns_tracked(self, vault_dir: Path) -> None:
        manifest = SyncManifest.load(vault_dir)
        manifest.record("d-1", "Digests/2026-04-03-daily.md", "digest", "sha256:x")
        assert manifest.get_filename("d-1") == "Digests/2026-04-03-daily.md"

    def test_remove_clears_entry(self, vault_dir: Path) -> None:
        manifest = SyncManifest.load(vault_dir)
        manifest.record("d-1", "Digests/a.md", "digest", "sha256:x")
        manifest.remove("d-1")
        assert manifest.get_filename("d-1") is None
        assert "d-1" not in manifest.entries
