from pathlib import Path

import pytest

from scripts.validate_openspec_inventory import validate_inventory


def _create_change(root: Path, name: str, *, archived: bool = False) -> None:
    changes = root / "openspec" / "changes"
    target = changes / "archive" / name if archived else changes / name
    target.mkdir(parents=True)


def _manifest() -> dict[str, object]:
    return {
        "reconciliation_change": "reconcile-openspec-inventory",
        "final_active": ["retained-change", "successor-change"],
        "dated_archives": [
            "2026-07-23-historical-change",
            "2026-07-23-reconcile-openspec-inventory",
        ],
        "successors": ["successor-change"],
        "entries": [
            {
                "name": "retained-change",
                "disposition": "retain-actionable",
                "next_action": "Implement the retained change.",
                "final_location": "active",
            },
            {
                "name": "successor-change",
                "disposition": "retain-successor",
                "next_action": "Implement the focused successor.",
                "final_location": "active",
            },
            {
                "name": "historical-change",
                "disposition": "archive-complete",
                "next_action": "Use the durable main specification.",
                "final_location": "2026-07-23-historical-change",
            },
            {
                "name": "reconcile-openspec-inventory",
                "disposition": "self-archive",
                "next_action": "Run final inventory validation.",
                "final_location": "2026-07-23-reconcile-openspec-inventory",
            },
        ],
    }


def test_transitional_inventory_allows_only_reconciliation_extra(
    tmp_path: Path,
) -> None:
    for name in (
        "retained-change",
        "successor-change",
        "reconcile-openspec-inventory",
    ):
        _create_change(tmp_path, name)
    _create_change(
        tmp_path,
        "2026-07-23-historical-change",
        archived=True,
    )

    assert validate_inventory(tmp_path, _manifest(), mode="transitional") == []


def test_transitional_inventory_rejects_unexpected_active_change(
    tmp_path: Path,
) -> None:
    for name in (
        "retained-change",
        "successor-change",
        "reconcile-openspec-inventory",
        "untracked-change",
    ):
        _create_change(tmp_path, name)
    _create_change(
        tmp_path,
        "2026-07-23-historical-change",
        archived=True,
    )

    errors = validate_inventory(tmp_path, _manifest(), mode="transitional")

    assert errors == ["unexpected active changes: untracked-change"]


def test_final_inventory_requires_exact_active_and_archive_sets(
    tmp_path: Path,
) -> None:
    for name in ("retained-change", "successor-change"):
        _create_change(tmp_path, name)
    for name in (
        "2026-07-23-historical-change",
        "2026-07-23-reconcile-openspec-inventory",
    ):
        _create_change(tmp_path, name, archived=True)

    assert validate_inventory(tmp_path, _manifest(), mode="final") == []


def test_final_inventory_reports_transient_change_and_missing_self_archive(
    tmp_path: Path,
) -> None:
    for name in (
        "retained-change",
        "successor-change",
        "reconcile-openspec-inventory",
    ):
        _create_change(tmp_path, name)
    _create_change(
        tmp_path,
        "2026-07-23-historical-change",
        archived=True,
    )

    errors = validate_inventory(tmp_path, _manifest(), mode="final")

    assert errors == [
        "unexpected active changes: reconcile-openspec-inventory",
        "missing dated archives: 2026-07-23-reconcile-openspec-inventory",
    ]


def test_inventory_requires_successor_to_remain_active(tmp_path: Path) -> None:
    _create_change(tmp_path, "retained-change")
    _create_change(tmp_path, "reconcile-openspec-inventory")
    _create_change(
        tmp_path,
        "2026-07-23-historical-change",
        archived=True,
    )

    errors = validate_inventory(tmp_path, _manifest(), mode="transitional")

    assert errors == [
        "missing active changes: successor-change",
        "missing active successors: successor-change",
    ]


def test_inventory_rejects_unexpected_archive_on_manifest_date(
    tmp_path: Path,
) -> None:
    for name in (
        "retained-change",
        "successor-change",
        "reconcile-openspec-inventory",
    ):
        _create_change(tmp_path, name)
    for name in (
        "2026-07-23-historical-change",
        "2026-07-23-unexpected-change",
        "2026-07-22-unrelated-history",
    ):
        _create_change(tmp_path, name, archived=True)

    errors = validate_inventory(tmp_path, _manifest(), mode="transitional")

    assert errors == ["unexpected dated archives: 2026-07-23-unexpected-change"]


def test_inventory_requires_disposition_for_every_final_entry(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    entries = manifest["entries"]
    assert isinstance(entries, list)
    manifest["entries"] = entries[:-1]

    with pytest.raises(
        ValueError,
        match="entries must exactly cover active and archived changes",
    ):
        validate_inventory(tmp_path, manifest, mode="transitional")
