"""Regression tests for the isolated Railway frontend build boundary."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = REPO_ROOT / "web"


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_railway_frontend_build_is_isolated_and_uses_railpack() -> None:
    railway_config = _read_json(WEB_ROOT / "railway.json")

    assert railway_config["build"]["builder"] == "RAILPACK"
    assert railway_config["build"]["watchPatterns"] == ["web/**"]


def test_frontend_package_declares_node_22_and_a_local_build() -> None:
    package = _read_json(WEB_ROOT / "package.json")
    build_script = package["scripts"]["build"]

    assert package["engines"]["node"] == "22.x"
    assert build_script == "tsc -b && vite build"
    for forbidden_tool in (
        "pnpm",
        "python",
        "uv",
        "contracts:check",
        "generate_workflow_contracts",
    ):
        assert forbidden_tool not in build_script.lower()


def test_frontend_has_an_exact_npm_dependency_graph() -> None:
    package = _read_json(WEB_ROOT / "package.json")
    package_lock = _read_json(WEB_ROOT / "package-lock.json")
    lock_root = package_lock["packages"][""]

    assert package_lock["lockfileVersion"] == 3
    assert lock_root["name"] == package["name"]
    assert lock_root["version"] == package["version"]
    assert lock_root["engines"]["node"] == package["engines"]["node"]
    assert lock_root["dependencies"] == package["dependencies"]
    assert lock_root["devDependencies"] == package["devDependencies"]


def test_frontend_lockfile_is_included_in_railway_uploads() -> None:
    git = shutil.which("git")
    assert git is not None
    result = subprocess.run(
        [
            git,
            "check-ignore",
            "--no-index",
            "--quiet",
            "web/package-lock.json",
        ],
        cwd=REPO_ROOT,
        check=False,
    )

    assert result.returncode == 1


def test_frontend_dependency_graph_uses_audit_safe_protobuf_override() -> None:
    root_package = _read_json(REPO_ROOT / "package.json")
    frontend_package = _read_json(WEB_ROOT / "package.json")
    package_lock = _read_json(WEB_ROOT / "package-lock.json")

    assert root_package["pnpm"]["overrides"]["protobufjs"] == "8.7.1"
    assert frontend_package["overrides"]["protobufjs"] == "8.7.1"
    # The OTel 0.221 bump dropped @opentelemetry/otlp-transformer's protobufjs
    # dependency, so the package may be absent from the graph entirely. Absent
    # is as audit-safe as pinned; what this test forbids is protobufjs PRESENT
    # at any other version. The overrides above stay as defense-in-depth for
    # whenever a dependency reintroduces it.
    protobufjs = package_lock["packages"].get("node_modules/protobufjs")
    assert protobufjs is None or protobufjs["version"] == "8.7.1"
