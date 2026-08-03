"""Deterministic, bounded temporary-vault data for Obsidian ingestion tiers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def _clip(url: str, body: str, *, captured_at: str) -> str:
    return (
        "---\n"
        f"source_url: {url}\n"
        f"captured_at: {captured_at}\n"
        "capture_client: obsidian-web-clipper\n"
        "content_type_hint: article\n"
        "---\n"
        f"{body.rstrip()}\n"
    )


@dataclass(frozen=True)
class TemporaryObsidianVault:
    """Paths and mutations for one private, network-free filesystem fixture."""

    approved_root: Path
    vault_path: Path
    ingest_folder: str
    valid_clip: Path
    changed_clip: Path
    invalid_clip: Path
    duplicate_clip: Path

    def source_config(self) -> dict[str, object]:
        """Return bounded server-owned config suitable for the real descriptor."""

        return {
            "type": "obsidian_vault",
            "vault_id": "real-ingestion-fixture",
            "vault_path": str(self.vault_path),
            "ingest_folder": self.ingest_folder,
            "max_files": 8,
            "max_entries": 16,
            "max_total_bytes": 65_536,
            "max_depth": 2,
            "max_duration_seconds": 5.0,
            "max_note_bytes": 16_384,
            "settle_seconds": 0.0,
            "max_concurrency": 1,
        }

    def write_changed_version(self) -> None:
        """Replace one note with a second deterministic file version."""

        self.changed_clip.write_text(
            _clip(
                "https://fixture.invalid/changed",
                "# Changed clip\n\nsecond deterministic version",
                captured_at="2026-08-02T13:00:00Z",
            ),
            encoding="utf-8",
        )


def create_temporary_obsidian_vault(root: Path) -> TemporaryObsidianVault:
    """Create valid, invalid, mutable, and duplicate clips under one tiny vault."""

    approved_root = root / "approved"
    vault_path = approved_root / "fixture-vault"
    ingest_folder = "Clips/Inbox"
    inbox = vault_path / ingest_folder
    inbox.mkdir(parents=True)

    valid = inbox / "valid.md"
    changed = inbox / "changed.md"
    invalid = inbox / "invalid.md"
    duplicate = inbox / "duplicate.md"
    valid.write_text(
        _clip(
            "https://fixture.invalid/shared?utm_source=clipper",
            "# Valid clip\n\nprimary annotation",
            captured_at="2026-08-02T11:00:00Z",
        ),
        encoding="utf-8",
    )
    changed.write_text(
        _clip(
            "https://fixture.invalid/changed",
            "# Changed clip\n\nfirst deterministic version",
            captured_at="2026-08-02T12:00:00Z",
        ),
        encoding="utf-8",
    )
    invalid.write_text(
        "---\ncaptured_at: not-a-time\n---\n# Invalid clip\n",
        encoding="utf-8",
    )
    duplicate.write_text(
        _clip(
            "https://fixture.invalid/shared?utm_medium=duplicate",
            "# Duplicate canonical URL\n\ndistinct annotation",
            captured_at="2026-08-02T11:05:00Z",
        ),
        encoding="utf-8",
    )
    return TemporaryObsidianVault(
        approved_root=approved_root,
        vault_path=vault_path,
        ingest_folder=ingest_folder,
        valid_clip=valid,
        changed_clip=changed,
        invalid_clip=invalid,
        duplicate_clip=duplicate,
    )
