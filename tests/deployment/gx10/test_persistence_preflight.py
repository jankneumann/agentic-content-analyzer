"""The ownership preflight fails closed before any hardened container starts."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/gx10/check_persistence_ownership.py"
ME = f"{os.getuid()}:{os.getgid()}"
OTHER = f"{os.getuid() + 1}:{os.getgid()}"


def _run(compose: dict, tmp_path: Path, *services: str) -> subprocess.CompletedProcess[str]:
    overlay = tmp_path / "overlay.yml"
    overlay.write_text(yaml.safe_dump(compose), encoding="utf-8")
    argv = [
        sys.executable,
        str(SCRIPT),
        "--compose",
        str(overlay),
        "--persist-root",
        str(tmp_path / "srv"),
        "--runtime-root",
        str(tmp_path / "run"),
    ]
    for service in services:
        argv += ["--service", service]
    return subprocess.run(argv, capture_output=True, text=True)


def test_preflight_is_wired_before_every_hardened_start() -> None:
    assert SCRIPT.stat().st_mode & 0o111
    runtime = (ROOT / "scripts/gx10/podman-runtime.sh").read_text(encoding="utf-8")
    assert runtime.index("check_persistence_ownership.py") < runtime.index("compose up -d")
    openbao = (ROOT / "deploy/gx10/systemd/aca-gx10-openbao-container.service").read_text()
    assert (
        "ExecStartPre=/opt/aca/scripts/gx10/check_persistence_ownership.py --service openbao"
        in openbao
    )
    proxy = (ROOT / "deploy/gx10/systemd/aca-gx10-proxy-policy.service").read_text()
    assert proxy.index("check_persistence_ownership.py --service squid") < proxy.index(
        "ensure_service.sh squid"
    )


def test_preflight_passes_when_owners_match_and_reports_every_mismatch(tmp_path: Path) -> None:
    (tmp_path / "srv/good").mkdir(parents=True)
    (tmp_path / "srv/wrong").mkdir(parents=True)
    (tmp_path / "run/redis").mkdir(parents=True)
    (tmp_path / "run/redis/users.acl").write_text("user default on\n")
    compose = {
        "services": {
            "good": {
                "user": ME,
                "volumes": ["/srv/aca/good:/data:rw", "/run/aca/gx10/redis/users.acl:/x:ro"],
            },
            "wrong": {"user": OTHER, "volumes": ["/srv/aca/wrong:/data:rw"]},
            "missing": {"user": ME, "volumes": ["/srv/aca/missing:/data:rw"]},
            "rootish": {"volumes": ["/srv/aca/good:/data:rw"]},
        }
    }
    ok = _run(compose, tmp_path, "good")
    assert ok.returncode == 0, ok.stderr
    assert "verified for 1 service" in ok.stderr

    failed = _run(compose, tmp_path)
    assert failed.returncode == 1
    assert f"wrong: /srv/aca/wrong is owned by {ME}" in failed.stderr
    assert (
        f"fix: install -d -o {OTHER.replace(':', ' -g ')} -m 0700 /srv/aca/wrong" in failed.stderr
    )
    assert "missing: /srv/aca/missing is missing" in failed.stderr
    if os.getuid() != 0:
        assert "rootish: /srv/aca/good is owned by" in failed.stderr


def test_preflight_requires_read_only_inputs_to_be_reachable(tmp_path: Path) -> None:
    proxy = tmp_path / "run/proxy"
    proxy.mkdir(parents=True)
    (proxy / "squid.passwd").write_text("u:x\n")
    (proxy / "squid.passwd").chmod(0o600)
    proxy.chmod(0o700)
    compose = {
        "services": {
            "squid": {"user": OTHER, "volumes": ["/run/aca/gx10/proxy:/run/aca/gx10/proxy:ro"]}
        }
    }
    if os.getuid() != 0:
        sealed = _run(compose, tmp_path)
        assert sealed.returncode == 1
        assert "not traversable" in sealed.stderr
        assert "-m 0710 /run/aca/gx10/proxy" in sealed.stderr

    compose["services"]["squid"]["user"] = ME
    assert _run(compose, tmp_path).returncode == 0


def test_renderer_and_reload_make_the_proxy_directory_reachable_for_squid() -> None:
    renderer = (ROOT / "deploy/gx10/openbao/render-secrets.sh").read_text(encoding="utf-8")
    reload_script = (ROOT / "scripts/gx10/reload_proxy_policy.sh").read_text(encoding="utf-8")
    for source in (renderer, reload_script):
        assert "PROXY_DIR_OWNER=(-o 0 -g 13); PROXY_DIR_MODE=0710" in source
        assert (
            'install -d "${PROXY_DIR_OWNER[@]}" -m "$PROXY_DIR_MODE" "$RUNTIME_DIR/proxy"' in source
        )
    assert "READY_OWNER=(-o 13 -g 13)" in reload_script
    assert 'install "${READY_OWNER[@]}" -m 0600 /dev/null "$READY"' in reload_script
