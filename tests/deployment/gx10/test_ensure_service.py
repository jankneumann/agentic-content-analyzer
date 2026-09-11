"""ensure_service.sh never stops a running container and only fills gaps."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/gx10/ensure_service.sh"


def _fixture(tmp_path: Path, exists: bool, state: str) -> dict[str, str]:
    log = tmp_path / "calls.log"
    podman = tmp_path / "podman"
    podman.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "podman $*" >> "{log}"\n'
        f'case "$1" in container) exit {0 if exists else 1};; inspect) echo "{state}";; start) exit 0;; esac\n'
    )
    podman.chmod(0o700)
    fake_root = tmp_path / "root"
    (fake_root / "scripts/gx10").mkdir(parents=True)
    compose = fake_root / "scripts/gx10/podman-compose.sh"
    compose.write_text(f'#!/usr/bin/env bash\necho "compose $*" >> "{log}"\n')
    compose.chmod(0o700)
    return {
        "PATH": os.environ["PATH"],
        "GX10_PODMAN_BIN": str(podman),
        "GX10_ROOT_DIR": str(fake_root),
        "COMPOSE_PROJECT_NAME": "aca-gx10",
    }


def _calls(env: dict[str, str]) -> str:
    return (Path(env["GX10_ROOT_DIR"]).parent / "calls.log").read_text()


def test_units_delegate_container_ownership_to_ensure_service() -> None:
    assert SCRIPT.stat().st_mode & 0o111
    openbao = (ROOT / "deploy/gx10/systemd/aca-gx10-openbao-container.service").read_text()
    proxy = (ROOT / "deploy/gx10/systemd/aca-gx10-proxy-policy.service").read_text()
    assert "ExecStart=/opt/aca/scripts/gx10/ensure_service.sh openbao" in openbao
    assert "ExecStartPre=/opt/aca/scripts/gx10/ensure_service.sh squid" in proxy
    assert "podman-compose.sh up" not in openbao
    assert "podman-compose.sh up" not in proxy


def test_running_container_is_left_alone(tmp_path: Path) -> None:
    env = _fixture(tmp_path, exists=True, state="running")
    result = subprocess.run([SCRIPT, "squid"], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "compose" not in _calls(env)
    assert "podman start" not in _calls(env)


def test_stopped_container_is_started_not_recreated(tmp_path: Path) -> None:
    env = _fixture(tmp_path, exists=True, state="exited")
    result = subprocess.run([SCRIPT, "openbao"], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "podman start aca-gx10_openbao_1" in _calls(env)
    assert "compose" not in _calls(env)


def test_missing_container_is_created_through_compose(tmp_path: Path) -> None:
    env = _fixture(tmp_path, exists=False, state="")
    result = subprocess.run([SCRIPT, "squid"], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "compose up -d squid" in _calls(env)


def test_stuck_container_fails_closed_with_the_fix(tmp_path: Path) -> None:
    env = _fixture(tmp_path, exists=True, state="stopping")
    result = subprocess.run([SCRIPT, "squid"], env=env, capture_output=True, text=True)
    assert result.returncode == 1
    assert "podman rm -f --depend aca-gx10_squid_1" in result.stderr


def test_openbao_container_unit_stays_active_and_operator_flows_restart_it() -> None:
    """systemd terminates a oneshot's cgroup when it goes inactive, and the
    container's conmon lives there, so the unit must stay active. Because the
    runtime's sweep can remove the container while the unit stays active, the
    secrets and provision targets restart it explicitly before depending on it."""
    openbao = (ROOT / "deploy/gx10/systemd/aca-gx10-openbao-container.service").read_text()
    assert "Type=oneshot\nRemainAfterExit=yes\n" in openbao
    makefile = (ROOT / "deploy/gx10/Makefile").read_text()
    for target, follow in (
        ("secrets", "aca-gx10-secrets.service"),
        ("provision", "aca-gx10-openbao-provision.service"),
    ):
        recipe = makefile.split(f"\n{target}:", 1)[1].split("\n\n", 1)[0]
        assert "systemctl restart aca-gx10-openbao-container.service" in recipe, target
        assert recipe.index("aca-gx10-openbao-container.service") < recipe.index(follow), target


def test_openbao_unit_recreates_a_stale_container_and_nothing_else_does(tmp_path: Path) -> None:
    """Only the OpenBao unit opts into stale recreation; it runs before any
    dependent exists. The compose hash comes from podman-compose's own dry-run."""
    openbao = (ROOT / "deploy/gx10/systemd/aca-gx10-openbao-container.service").read_text()
    assert "Environment=GX10_ENSURE_RECREATE_STALE=1" in openbao
    proxy = (ROOT / "deploy/gx10/systemd/aca-gx10-proxy-policy.service").read_text()
    assert "GX10_ENSURE_RECREATE_STALE" not in proxy

    env = _fixture(tmp_path, exists=True, state="running")
    compose = Path(env["GX10_ROOT_DIR"]) / "scripts/gx10/podman-compose.sh"
    compose.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "compose $*" >> "{tmp_path / "calls.log"}"\n'
        '[[ "$1" == --dry-run ]] && echo "--label io.podman.compose.config-hash=' + "b" * 64 + '"\n'
        "exit 0\n"
    )
    podman = Path(env["GX10_PODMAN_BIN"])
    podman.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "podman $*" >> "{tmp_path / "calls.log"}"\n'
        'case "$1" in container) exit 0;; inspect) [[ "$*" == *config-hash* ]] && echo "'
        + "a" * 64
        + '" || echo running;; rm) exit 0;; esac\n'
    )
    (ROOT / "scripts/gx10/compose_hash.sh").read_text()
    fake_hash = Path(env["GX10_ROOT_DIR"]) / "scripts/gx10/compose_hash.sh"
    fake_hash.write_text((ROOT / "scripts/gx10/compose_hash.sh").read_text())
    fake_hash.chmod(0o700)

    untouched = subprocess.run([SCRIPT, "openbao"], env=env, capture_output=True, text=True)
    assert untouched.returncode == 0 and "compose up" not in _calls(env)

    stale = subprocess.run(
        [SCRIPT, "openbao"],
        env={**env, "GX10_ENSURE_RECREATE_STALE": "1"},
        capture_output=True,
        text=True,
    )
    assert stale.returncode == 0, stale.stderr
    assert "older overlay" in stale.stderr
    calls = _calls(env)
    assert "podman rm -f --depend -t 15 aca-gx10_openbao_1" in calls
    assert calls.index("podman rm -f --depend") < calls.index("compose up -d openbao")
