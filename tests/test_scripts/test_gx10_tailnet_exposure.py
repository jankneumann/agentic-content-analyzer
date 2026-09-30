"""Tailnet exposure baseline for the gx-10 host.

OpenBao holds every credential the worker uses, and the API accepts the admin
key. On gx-10 neither may listen on ``0.0.0.0``: the only path in from another
machine is ``tailscale serve`` on the Tailscale address, gated by the tailnet
policy. These tests pin the shipped configuration to that rule, because a
wrong bind is silent — everything keeps working, it is just also reachable
from the LAN.

The container entrypoint is exercised for real (with ``alembic`` and
``uvicorn`` replaced by recorders on ``PATH``) so the argv uvicorn receives is
asserted, not inferred from the script text.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = REPO_ROOT / "docker-entrypoint.sh"
GX10_DIR = REPO_ROOT / "deploy" / "gx10"
COMPOSE_FILE = GX10_DIR / "docker-compose.gx10.yml"
OPENBAO_HCL = GX10_DIR / "openbao.hcl"
API_UNIT = GX10_DIR / "aca-api.service"
ENV_TEMPLATE = GX10_DIR / "aca-gx10.env.example"
TAILNET_DOC = REPO_ROOT / "docs" / "TAILNET.md"

_BASH = shutil.which("bash")
# The value this suite forbids on gx-10 and expects as the in-container default.
ALL_INTERFACES = "0.0.0.0"  # noqa: S104 — asserted against, never bound


def _directives(text: str) -> str:
    """Non-comment, non-blank lines: the rationale comments may name 0.0.0.0."""
    return "\n".join(
        line for line in text.splitlines() if line.strip() and not line.strip().startswith("#")
    )


def _write_recorder(path: Path, body: str) -> None:
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _run_entrypoint(tmp_path: Path, extra_env: dict[str, str]) -> list[str]:
    """Run docker-entrypoint.sh with recorders standing in for alembic/uvicorn.

    Returns the argv uvicorn was exec'd with (excluding the program name).
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    argv_file = tmp_path / "uvicorn-argv"
    _write_recorder(bin_dir / "alembic", "exit 0")
    _write_recorder(
        bin_dir / "uvicorn",
        f'for a in "$@"; do printf "%s\\n" "$a"; done > "{argv_file}"',
    )
    env = {
        "PATH": f"{bin_dir}{os.pathsep}/usr/bin{os.pathsep}/bin",
        "HOME": str(tmp_path),
        **extra_env,
    }
    assert _BASH is not None
    result = subprocess.run(
        [_BASH, str(ENTRYPOINT)],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return argv_file.read_text().splitlines()


def _flag_value(argv: list[str], flag: str) -> str:
    for i, arg in enumerate(argv):
        if arg == flag:
            return argv[i + 1]
        if arg.startswith(f"{flag}="):
            return arg.split("=", 1)[1]
    raise AssertionError(f"{flag} not passed to uvicorn: {argv}")


@pytest.mark.skipif(_BASH is None, reason="bash is required to run the entrypoint")
class TestEntrypointBinding:
    def test_container_default_is_unchanged(self, tmp_path: Path) -> None:
        """Railway and plain `docker run` keep binding every in-container interface;
        exposure there is decided by the published port, not the bind."""
        argv = _run_entrypoint(tmp_path, {})
        assert argv[0] == "src.api.app:app"
        assert _flag_value(argv, "--host") == ALL_INTERFACES
        assert _flag_value(argv, "--port") == "8000"
        assert _flag_value(argv, "--forwarded-allow-ips") == "*"
        assert "--proxy-headers" in argv

    def test_host_port_and_forwarded_trust_are_configurable(self, tmp_path: Path) -> None:
        argv = _run_entrypoint(
            tmp_path,
            {
                "ACA_API_HOST": "127.0.0.1",
                "PORT": "8123",
                "ACA_FORWARDED_ALLOW_IPS": "127.0.0.1",
            },
        )
        assert _flag_value(argv, "--host") == "127.0.0.1"
        assert _flag_value(argv, "--port") == "8123"
        assert _flag_value(argv, "--forwarded-allow-ips") == "127.0.0.1"

    def test_forwarded_default_is_not_glob_expanded(self, tmp_path: Path) -> None:
        """An unquoted `*` would expand to the files in the working directory."""
        (tmp_path / "decoy-file").write_text("")
        argv = _run_entrypoint(tmp_path, {})
        assert _flag_value(argv, "--forwarded-allow-ips") == "*"


@pytest.fixture(scope="module")
def compose() -> dict:
    loaded = yaml.safe_load(COMPOSE_FILE.read_text())
    assert isinstance(loaded, dict)
    return loaded


class TestGx10Compose:
    def test_every_published_port_is_bound_to_a_configurable_loopback_default(
        self, compose: dict
    ) -> None:
        published = [
            (name, port)
            for name, service in compose["services"].items()
            for port in service.get("ports", [])
        ]
        assert published, "the gx-10 compose file must publish OpenBao"
        for name, port in published:
            assert isinstance(port, str), f"{name}: use the short string form"
            assert re.fullmatch(r"\$\{ACA_[A-Z_]+_BIND_ADDR:-127\.0\.0\.1\}:\d+:\d+", port), (
                f"{name} publishes {port!r}; it must bind a configurable address "
                "that defaults to loopback"
            )

    def test_openbao_publishes_only_the_api_port(self, compose: dict) -> None:
        ports = compose["services"]["openbao"]["ports"]
        assert ports == ["${ACA_BAO_BIND_ADDR:-127.0.0.1}:8200:8200"]

    def test_openbao_is_not_dev_mode(self, compose: dict) -> None:
        service = compose["services"]["openbao"]
        assert "-dev" not in str(service.get("command", ""))
        assert not any("BAO_DEV" in key for key in service.get("environment", {}) or {})

    def test_openbao_uses_raft_storage_for_backup_snapshots(self) -> None:
        """`aca backup run` captures OpenBao with `bao operator raft snapshot save`."""
        hcl = _directives(OPENBAO_HCL.read_text())
        assert 'storage "raft"' in hcl
        assert "cluster_addr" in hcl


@pytest.fixture(scope="module")
def api_unit() -> str:
    return API_UNIT.read_text()


class TestApiUnit:
    def test_unit_binds_loopback_and_trusts_only_local_proxy(self, api_unit: str) -> None:
        directives = _directives(api_unit)
        assert "Environment=ACA_API_HOST=127.0.0.1" in directives
        assert "Environment=ACA_FORWARDED_ALLOW_IPS=127.0.0.1" in directives
        assert ALL_INTERFACES not in directives

    def test_unit_reuses_the_container_entrypoint(self, api_unit: str) -> None:
        """One launch contract (migrate, then uvicorn) for Railway, Docker, and gx-10.

        Invoked through bash: git tracks the script as 0644 (the Dockerfile adds
        the exec bit), so a checkout under /opt/aca is not directly executable.
        """
        assert "ExecStart=/bin/bash /opt/aca/docker-entrypoint.sh" in _directives(api_unit)

    def test_unit_is_unprivileged_and_reads_an_environment_file(self, api_unit: str) -> None:
        directives = _directives(api_unit)
        assert "User=aca" in directives
        assert "User=root" not in directives
        assert "EnvironmentFile=" in directives

    def test_unit_contains_no_literal_secret(self, api_unit: str) -> None:
        for marker in ("SECRET_ID=", "ROLE_ID=", "TOKEN=", "PASSWORD=", "ADMIN_API_KEY="):
            assert marker not in _directives(api_unit)


class TestEnvTemplate:
    def test_template_defaults_to_loopback(self) -> None:
        settings = dict(
            line.split("=", 1)
            for line in _directives(ENV_TEMPLATE.read_text()).splitlines()
            if "=" in line
        )
        assert settings["ACA_API_HOST"] == "127.0.0.1"
        assert settings["ACA_BAO_BIND_ADDR"] == "127.0.0.1"
        assert settings["ACA_FORWARDED_ALLOW_IPS"] == "127.0.0.1"
        assert settings["BAO_ADDR"] == "http://127.0.0.1:8200"

    def test_template_ships_no_real_credential(self) -> None:
        for line in _directives(ENV_TEMPLATE.read_text()).splitlines():
            key, _, value = line.partition("=")
            if any(marker in key for marker in ("SECRET", "TOKEN", "KEY", "PASSWORD", "ROLE_ID")):
                assert value.startswith("<") and value.endswith(">"), key


class TestRunbookLinks:
    def test_tailnet_doc_is_linked_from_the_entry_points(self) -> None:
        assert TAILNET_DOC.exists()
        assert "docs/TAILNET.md" in (REPO_ROOT / "CLAUDE.md").read_text()
        assert "TAILNET.md" in (REPO_ROOT / "docs" / "SETUP.md").read_text()

    def test_tailnet_doc_records_the_required_facts(self) -> None:
        doc = TAILNET_DOC.read_text()
        for needle in (
            "tailscale serve",
            "BAO_ADDR=https://gx-10.<tailnet>.ts.net:8200",
            "tag:gx10",
            "ss -ltn",
            "ALLOWED_ORIGINS",
        ):
            assert needle in doc, needle

    def test_extension_readme_names_the_tailnet_api_url(self) -> None:
        readme = (REPO_ROOT / "extension" / "README.md").read_text()
        assert "https://gx-10.<tailnet>.ts.net" in readme
        assert "host_permissions" in readme
