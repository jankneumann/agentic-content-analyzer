"""deploy/gx10/Makefile only sequences tested scripts and units, and cannot drift."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
MAKEFILE = ROOT / "deploy/gx10/Makefile"
MAKE = shutil.which("make")
TARGETS = (
    "install",
    "ownership",
    "preflight",
    "provision",
    "secrets",
    "image",
    "image-pins",
    "start",
    "stop",
    "status",
    "logs",
    "verify",
)


def _dry_run(target: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [MAKE, "-n", "-C", str(MAKEFILE.parent), target, f"ROOT={ROOT}", "UNIT_DIR=/tmp/units"],
        capture_output=True,
        text=True,
    )


@pytest.mark.skipif(MAKE is None, reason="GNU make is not installed")
def test_every_target_dry_runs_and_is_documented() -> None:
    source = MAKEFILE.read_text(encoding="utf-8")
    assert ".SHELLFLAGS := -euo pipefail -c" in source
    for target in TARGETS:
        assert re.search(rf"^{target}:.*## ", source, re.MULTILINE), f"{target} lacks help text"
        result = _dry_run(target)
        assert result.returncode == 0, f"{target}: {result.stderr}"
    recipes = [line for line in source.splitlines() if line.startswith("\t")]
    assert not any("git pull" in line for line in recipes), "start must never pull"


def test_recipes_only_call_scripts_and_units_that_exist() -> None:
    source = MAKEFILE.read_text(encoding="utf-8")
    for script in re.findall(r"\$\(SCRIPTS\)/([a-z_]+\.(?:sh|py))", source):
        path = ROOT / "scripts/gx10" / script
        assert path.is_file() and path.stat().st_mode & 0o111, script
    units = {p.stem for p in (ROOT / "deploy/gx10/systemd").glob("*.service")}
    for unit in re.findall(r"systemctl (?:start|restart|stop) (aca-gx10[a-z-]*)\.service", source):
        assert unit in units, unit


def test_ownership_recipe_matches_compose_users() -> None:
    """The install -d lines must agree with every service's user: entry."""
    source = MAKEFILE.read_text(encoding="utf-8")
    recipe = source.split("ownership:", 1)[1].split("\n\n", 1)[0]
    declared: dict[str, tuple[int, int]] = {}
    for uid, gid, paths in re.findall(r"install -d -o (\w+) -g (\w+) -m 0700 ([^\n]+)", recipe):
        owner = (0, 0) if uid == "root" else (int(uid), int(gid))
        for path in paths.split():
            declared[path] = owner

    compose = yaml.safe_load((ROOT / "docker-compose.gx10.yml").read_text(encoding="utf-8"))
    expected: dict[str, tuple[int, int]] = {}
    for name, service in compose["services"].items():
        user = service.get("user")
        owner = tuple(int(x) for x in str(user).split(":")) if user else (0, 0)
        for volume in service.get("volumes", []):
            host = volume.split(":", 1)[0]
            if host.startswith("/srv/aca/"):
                assert expected.setdefault(host, owner) == owner, (
                    f"{host} shared by differing users"
                )
    assert declared == expected
