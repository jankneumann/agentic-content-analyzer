from __future__ import annotations

from pathlib import Path

import pytest

from src.clients.operational_observability import validate_frozen_entrypoint_inventory


ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "openspec/changes/gx10-full-operation-observability/contracts/operation-entrypoints.yaml"


def test_frozen_non_http_inventory_is_complete_and_instrumented() -> None:
    report = validate_frozen_entrypoint_inventory(ROOT, INVENTORY)

    assert report.unlisted == ()
    assert report.missing == ()
    assert report.uninstrumented == ()
    assert report.explicit_exclusions_only is True


def test_inventory_rejects_new_unallowlisted_meaningful_script(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "unexpected_operation.py").write_text(
        "def main():\n    return 0\n\nif __name__ == '__main__':\n    main()\n"
    )

    report = validate_frozen_entrypoint_inventory(
        tmp_path,
        INVENTORY,
        require_declared_paths=False,
    )

    assert report.unlisted == ("scripts/unexpected_operation.py",)


def test_inventory_parser_rejects_undocumented_exclusion(tmp_path: Path) -> None:
    bad_inventory = tmp_path / "inventory.yaml"
    bad_inventory.write_text(
        "schema_version: 1\n"
        "shared_boundaries: {}\n"
        "domain_operations: []\n"
        "operational_services: []\n"
        "operational_scripts: []\n"
        "bootstrap_operations: {paths: []}\n"
        "provider_boundaries: []\n"
        "explicit_exclusions:\n"
        "  - pattern: scripts/ignored.py\n"
    )

    with pytest.raises(ValueError, match="reason"):
        validate_frozen_entrypoint_inventory(tmp_path, bad_inventory)
