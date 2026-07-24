#!/usr/bin/env python3
"""Validate the exact active and dated-archive OpenSpec inventory."""

from __future__ import annotations

import argparse
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, cast

import yaml

Mode = Literal["transitional", "final"]
DATED_ARCHIVE_PATTERN = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<name>.+)")


def _string_set(manifest: Mapping[str, object], key: str) -> set[str]:
    value = manifest.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"manifest field {key!r} must be a list of strings")
    return set(cast(list[str], value))


def _validate_disposition_entries(
    manifest: Mapping[str, object],
    final_active: set[str],
    dated_archives: set[str],
) -> None:
    raw_entries = manifest.get("entries")
    if not isinstance(raw_entries, list):
        raise ValueError("manifest field 'entries' must be a list")

    archive_locations: dict[str, str] = {}
    for archive in dated_archives:
        match = DATED_ARCHIVE_PATTERN.match(archive)
        if not match:
            raise ValueError(f"invalid dated archive name: {archive}")
        archive_locations[match.group("name")] = archive

    expected_names = final_active | set(archive_locations)
    actual_names: set[str] = set()
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            raise ValueError("each disposition entry must be a mapping")
        entry = cast(dict[object, object], raw_entry)
        values: dict[str, str] = {}
        for key in ("name", "disposition", "next_action", "final_location"):
            value = entry.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"disposition entry field {key!r} must be a non-empty string")
            values[key] = value

        name = values["name"]
        if name in actual_names:
            raise ValueError(f"duplicate disposition entry: {name}")
        actual_names.add(name)
        expected_location = "active" if name in final_active else archive_locations.get(name)
        if values["final_location"] != expected_location:
            raise ValueError(f"disposition entry {name!r} has an invalid final_location")

    if actual_names != expected_names:
        raise ValueError("entries must exactly cover active and archived changes")


def load_manifest(path: Path) -> dict[str, object]:
    """Load and minimally validate an inventory disposition manifest."""
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError("inventory manifest must be a mapping")
    manifest = cast(dict[str, object], raw)
    reconciliation_change = manifest.get("reconciliation_change")
    if not isinstance(reconciliation_change, str):
        raise ValueError("manifest field 'reconciliation_change' must be a string")
    for key in ("final_active", "dated_archives", "successors"):
        _string_set(manifest, key)
    _validate_disposition_entries(
        manifest,
        _string_set(manifest, "final_active"),
        _string_set(manifest, "dated_archives"),
    )
    return manifest


def _directory_names(path: Path) -> set[str]:
    if not path.is_dir():
        return set()
    return {entry.name for entry in path.iterdir() if entry.is_dir()}


def _format_error(label: str, values: set[str]) -> str:
    return f"{label}: {', '.join(sorted(values))}"


def validate_inventory(
    repo_root: Path,
    manifest: Mapping[str, object],
    *,
    mode: Mode,
) -> list[str]:
    """Return deterministic errors for inventory drift."""
    changes_root = repo_root / "openspec" / "changes"
    archive_root = changes_root / "archive"
    actual_active = _directory_names(changes_root) - {"archive"}
    actual_archives = _directory_names(archive_root)

    final_active = _string_set(manifest, "final_active")
    dated_archives = _string_set(manifest, "dated_archives")
    successors = _string_set(manifest, "successors")
    _validate_disposition_entries(manifest, final_active, dated_archives)
    reconciliation_change = manifest.get("reconciliation_change")
    if not isinstance(reconciliation_change, str):
        raise ValueError("manifest field 'reconciliation_change' must be a string")

    expected_active = set(final_active)
    expected_archives = set(dated_archives)
    if mode == "transitional":
        expected_active.add(reconciliation_change)
        self_archives = {
            name for name in expected_archives if name.endswith(f"-{reconciliation_change}")
        }
        if len(self_archives) != 1:
            raise ValueError("dated_archives must contain exactly one reconciliation archive")
        expected_archives -= self_archives
    elif mode != "final":
        raise ValueError(f"unsupported inventory validation mode: {mode}")

    errors: list[str] = []
    missing_active = expected_active - actual_active
    unexpected_active = actual_active - expected_active
    missing_archives = expected_archives - actual_archives
    manifest_dates = {
        match.group("date")
        for name in dated_archives
        if (match := DATED_ARCHIVE_PATTERN.match(name))
    }
    if not manifest_dates:
        raise ValueError("dated_archives must contain dated archive names")
    actual_archives_on_manifest_dates = {
        name
        for name in actual_archives
        if ((match := DATED_ARCHIVE_PATTERN.match(name)) and match.group("date") in manifest_dates)
    }
    unexpected_archives = actual_archives_on_manifest_dates - expected_archives
    missing_successors = successors - actual_active

    if missing_active:
        errors.append(_format_error("missing active changes", missing_active))
    if unexpected_active:
        errors.append(_format_error("unexpected active changes", unexpected_active))
    if missing_archives:
        errors.append(_format_error("missing dated archives", missing_archives))
    if unexpected_archives:
        errors.append(_format_error("unexpected dated archives", unexpected_archives))
    if missing_successors:
        errors.append(_format_error("missing active successors", missing_successors))
    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--transitional", action="store_true")
    mode.add_argument("--final", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    mode: Mode = "transitional" if args.transitional else "final"
    manifest = load_manifest(args.manifest)
    errors = validate_inventory(args.repo_root, manifest, mode=mode)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OpenSpec inventory is exact for {mode} state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
