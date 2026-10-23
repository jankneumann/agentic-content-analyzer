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


def test_start_keeps_openbao_and_unseals_before_the_runtime() -> None:
    source = MAKEFILE.read_text(encoding="utf-8")
    recipe = source.split("\nstart:", 1)[1].split("\n\n", 1)[0]
    assert '$$2 != "$(PROJECT)_openbao_1"' in recipe
    order = [
        recipe.index("podman rm -f --depend"),
        recipe.index("systemctl restart aca-gx10-openbao-container.service"),
        recipe.index("systemctl restart aca-gx10-secrets.service"),
        recipe.index("systemctl start aca-gx10.service"),
    ]
    assert order == sorted(order)


SYSTEMD_DIR = ROOT / "deploy/gx10/systemd"
TMPFILES = ROOT / "deploy/gx10/tmpfiles/aca-gx10.conf"


def _directives(unit: Path, key: str) -> list[str]:
    values: list[str] = []
    for line in unit.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            values.extend(line.split("=", 1)[1].split())
    return values


def test_every_run_path_a_unit_writes_is_recreated_at_boot() -> None:
    """/run is a tmpfs; a missing ReadWritePaths= entry fails the unit with 226/NAMESPACE.

    After the 2026-10-12 reboot /run/aca/gx10 was gone, image-pins failed before
    ExecStart, and OpenBao (Requires= it) never started.
    """
    created = {
        fields[1]
        for line in TMPFILES.read_text(encoding="utf-8").splitlines()
        if (fields := line.split()) and fields[0] == "d"
    }
    for unit in sorted(SYSTEMD_DIR.glob("*.service")):
        runtime_dirs = {f"/run/{d}" for d in _directives(unit, "RuntimeDirectory")}
        for path in _directives(unit, "ReadWritePaths"):
            if path.startswith("-") or not path.startswith("/run/"):
                continue
            assert path in created | runtime_dirs, (
                f"{unit.name}: {path} is not created by tmpfiles or RuntimeDirectory="
            )


def test_every_output_file_directory_exists_before_the_unit_starts() -> None:
    """systemd opens StandardOutput= files before creating StateDirectory=.

    The restore drill appended to a file inside its own StateDirectory=, so it
    failed with "Failed to set up standard output" on every run from first install.
    """
    created = {
        fields[1]
        for line in TMPFILES.read_text(encoding="utf-8").splitlines()
        if (fields := line.split()) and fields[0] == "d"
    }
    for unit in sorted(SYSTEMD_DIR.glob("*.service")):
        for key in ("StandardOutput", "StandardError"):
            for value in _directives(unit, key):
                mode, _, path = value.partition(":")
                if mode in {"file", "append", "truncate"}:
                    assert str(Path(path).parent) in created, (
                        f"{unit.name}: {key} directory {Path(path).parent} is not in tmpfiles"
                    )


def test_install_enables_every_unit_meant_to_survive_a_reboot() -> None:
    """Installing without enabling left the stack down for 8 days after a reboot."""
    boot_units = {
        unit.name for unit in SYSTEMD_DIR.iterdir() if "\n[Install]\n" in unit.read_text()
    }
    assert boot_units, "no unit declares [Install]"
    source = MAKEFILE.read_text(encoding="utf-8")
    recipe = source.split("\ninstall:", 1)[1].split("\n\n", 1)[0]
    assert "systemd-tmpfiles --create" in recipe
    assert recipe.index("systemd-tmpfiles --create") < recipe.index("systemctl daemon-reload")
    assert recipe.index("systemctl daemon-reload") < recipe.index("systemctl enable $(BOOT_UNITS)")


@pytest.mark.skipif(MAKE is None, reason="GNU make is not installed")
def test_install_dry_run_enables_exactly_the_installable_units() -> None:
    result = _dry_run("install")
    assert result.returncode == 0, result.stderr
    enable = next(line for line in result.stdout.splitlines() if "systemctl enable" in line)
    enabled = set(enable.split("systemctl enable", 1)[1].split())
    expected = {u.name for u in SYSTEMD_DIR.iterdir() if "\n[Install]\n" in u.read_text()}
    assert enabled == expected
