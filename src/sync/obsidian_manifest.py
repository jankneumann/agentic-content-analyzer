"""Obsidian sync manifest for incremental vault exports.

Tracks which content items have been exported, their content hashes,
and filenames. Supports atomic writes and corrupt manifest recovery.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


@dataclass
class ManifestEntry:
    """A single entry in the sync manifest."""

    filename: str
    aca_id: str
    aca_type: str
    content_hash: str
    exported_at: str  # ISO 8601


@dataclass
class SyncManifest:
    """Tracks exported Obsidian vault files for incremental sync.

    The manifest is stored as ``.obsidian-sync-manifest.json`` in the
    vault root. Uses atomic writes (tempfile + rename) to prevent
    corruption on interrupted exports.
    """

    vault_path: Path
    version: int = 1
    last_sync: str = ""
    entries: dict[str, ManifestEntry] = field(default_factory=dict)
    _current_ids: set[str] = field(default_factory=set, repr=False)

    MANIFEST_FILENAME: ClassVar[str] = ".obsidian-sync-manifest.json"

    @classmethod
    def load(cls, vault_path: Path) -> SyncManifest:
        """Load manifest from vault, or create empty one.

        If the manifest file exists but is corrupt (invalid JSON),
        it is renamed to ``.bak`` and a fresh manifest is created.

        Args:
            vault_path: Root path of the Obsidian vault.

        Returns:
            Loaded or fresh SyncManifest instance.
        """
        manifest_path = vault_path / cls.MANIFEST_FILENAME
        manifest = cls(vault_path=vault_path)

        if not manifest_path.exists():
            return manifest

        try:
            raw = manifest_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Corrupt manifest — back up and start fresh
            backup_path = manifest_path.with_suffix(".json.bak")
            logger.warning(
                "Corrupt manifest at %s — renaming to %s and rebuilding",
                manifest_path,
                backup_path,
            )
            manifest_path.rename(backup_path)
            return manifest

        manifest.version = data.get("version", 1)
        manifest.last_sync = data.get("last_sync", "")

        for aca_id, entry_data in data.get("entries", {}).items():
            manifest.entries[aca_id] = ManifestEntry(
                filename=entry_data["filename"],
                aca_id=aca_id,
                aca_type=entry_data.get("aca_type", ""),
                content_hash=entry_data.get("content_hash", ""),
                exported_at=entry_data.get("exported_at", ""),
            )

        return manifest

    def needs_update(self, aca_id: str, content_hash: str) -> bool:
        """Check if an item needs to be (re-)exported.

        Args:
            aca_id: Unique content identifier.
            content_hash: Current content hash.

        Returns:
            True if the item is new or has changed.
        """
        existing = self.entries.get(aca_id)
        if existing is None:
            return True
        return existing.content_hash != content_hash

    def get_filename(self, aca_id: str) -> str | None:
        """Get the previously assigned filename for a content item.

        Used to preserve filenames across runs (keeps wikilinks stable).

        Args:
            aca_id: Unique content identifier.

        Returns:
            Previously assigned filename, or None if not tracked.
        """
        entry = self.entries.get(aca_id)
        return entry.filename if entry else None

    def record(
        self,
        aca_id: str,
        filename: str,
        aca_type: str,
        content_hash: str,
    ) -> None:
        """Record an exported item in the manifest.

        Args:
            aca_id: Unique content identifier.
            filename: Relative path within vault (e.g., ``Digests/2026-04-03-daily.md``).
            aca_type: Content type string.
            content_hash: SHA-256 hash of the exported content.
        """
        self.entries[aca_id] = ManifestEntry(
            filename=filename,
            aca_id=aca_id,
            aca_type=aca_type,
            content_hash=content_hash,
            exported_at=datetime.now(UTC).isoformat(),
        )
        self._current_ids.add(aca_id)

    def mark_current(self, aca_id: str) -> None:
        """Mark an item as current (exists in DB, even if unchanged).

        Call this for items that exist but were skipped (unchanged).
        Used by get_stale_entries() to find items no longer in the DB.
        """
        self._current_ids.add(aca_id)

    def get_stale_entries(self) -> list[ManifestEntry]:
        """Find manifest entries for items no longer in the database.

        Returns entries that were previously exported but not seen
        during the current export run (not in _current_ids).

        Returns:
            List of stale ManifestEntry objects.
        """
        stale = []
        for aca_id, entry in self.entries.items():
            if aca_id not in self._current_ids:
                stale.append(entry)
        return stale

    def remove(self, aca_id: str) -> None:
        """Remove an entry from the manifest.

        Args:
            aca_id: Unique content identifier to remove.
        """
        self.entries.pop(aca_id, None)
        self._current_ids.discard(aca_id)

    def save(self) -> None:
        """Write manifest to disk atomically.

        Writes to a temporary file in the same directory, then
        uses ``os.replace()`` for an atomic rename. This prevents
        corruption if the process is interrupted mid-write.
        """
        self.last_sync = datetime.now(UTC).isoformat()

        data: dict[str, Any] = {
            "version": self.version,
            "last_sync": self.last_sync,
            "entries": {},
        }

        for aca_id, entry in self.entries.items():
            data["entries"][aca_id] = {
                "filename": entry.filename,
                "aca_type": entry.aca_type,
                "content_hash": entry.content_hash,
                "exported_at": entry.exported_at,
            }

        manifest_path = self.vault_path / self.MANIFEST_FILENAME

        # Atomic write: tempfile + os.replace
        fd, tmp_path = tempfile.mkstemp(
            dir=self.vault_path,
            prefix=".manifest-tmp-",
            suffix=".json",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, manifest_path)
        except BaseException:
            # Clean up temp file on any error
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
