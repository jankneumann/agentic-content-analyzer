from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.clients.operational_observability import validate_frozen_entrypoint_inventory


def _minimal_inventory(**overrides: object) -> dict[str, object]:
    inventory: dict[str, object] = {
        "schema_version": 1,
        "shared_boundaries": {},
        "domain_operations": [],
        "operational_services": [],
        "operational_scripts": [],
        "bootstrap_operations": {"paths": []},
        "provider_boundaries": [],
        "explicit_exclusions": [],
    }
    inventory.update(overrides)
    return inventory


def test_inventory_discovers_meaningful_scripts_recursively(tmp_path: Path) -> None:
    nested = tmp_path / "scripts" / "nested" / "run.py"
    nested.parent.mkdir(parents=True)
    nested.write_text("def main():\n    return 0\n\nif __name__ == '__main__':\n    main()\n")
    inventory = tmp_path / "inventory.yaml"
    inventory.write_text(yaml.safe_dump(_minimal_inventory()))

    report = validate_frozen_entrypoint_inventory(tmp_path, inventory, require_declared_paths=False)
    assert report.unlisted == ("scripts/nested/run.py",)


@pytest.mark.parametrize(
    ("section", "relative_path"),
    [
        ("shared_boundaries", "src/cli/app.py"),
        ("domain_operations", "src/workflows/job.py"),
        ("operational_services", "src/services/backup/run.py"),
        ("operational_scripts", "scripts/run.py"),
        ("bootstrap_operations", "scripts/bootstrap.sh"),
        ("provider_boundaries", "src/clients/provider.py"),
    ],
)
def test_inventory_structurally_rejects_false_markers_for_every_boundary_class(
    tmp_path: Path,
    section: str,
    relative_path: str,
) -> None:
    candidate = tmp_path / relative_path
    candidate.parent.mkdir(parents=True, exist_ok=True)
    if candidate.suffix == ".sh":
        candidate.write_text(
            "#!/usr/bin/env bash\n# bootstrap_audit trap EXIT operational_entrypoint\nexit 0\n"
        )
    else:
        candidate.write_text(
            "# operational_entrypoint operational_stage bind_operation_context "
            "install_cli_telemetry bootstrap_entrypoint\n"
            "def main():\n    return 0\n"
        )
    if section == "shared_boundaries":
        value: object = {"cli": [relative_path]}
    elif section == "bootstrap_operations":
        value = {"paths": [relative_path]}
    else:
        value = [relative_path]
    inventory = tmp_path / "inventory.yaml"
    inventory.write_text(yaml.safe_dump(_minimal_inventory(**{section: value})))

    report = validate_frozen_entrypoint_inventory(tmp_path, inventory)
    assert relative_path in report.uninstrumented
