"""Regression contracts for the second GX-10 runtime review."""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import yaml

from .test_review_remediations import _mock_secret_tools, _read_env

ROOT = Path(__file__).resolve().parents[3]
DEPLOY = ROOT / "deploy/gx10"
SCRIPTS = ROOT / "scripts/gx10"
SQUID_PROBE_TMPFS = "/tmp:rw,noexec,nosuid,nodev,size=8m"  # noqa: S108


def _compose() -> dict[str, object]:
    return yaml.safe_load((ROOT / "docker-compose.gx10.yml").read_text())


def test_redis_credentials_never_appear_in_server_or_healthcheck_argv() -> None:
    redis = _compose()["services"]["redis"]
    command = " ".join(redis["command"])
    health = " ".join(redis["healthcheck"]["test"])
    assert "REDIS_PASSWORD" not in command
    assert "requirepass" not in command
    assert "REDIS_PASSWORD" not in health
    assert " -a " not in health
    assert "redis-server /etc/redis/gx10.conf" in command
    assert "redis-cli ping" in health
    assert any("users.acl:/run/aca/gx10/redis/users.acl:ro" in mount for mount in redis["volumes"])

    renderer = (DEPLOY / "openbao/render-secrets.sh").read_text()
    assert "REDISCLI_AUTH" in renderer
    assert "user default on >" in renderer


def test_read_only_squid_has_only_a_bounded_writable_probe_tmpfs() -> None:
    squid = _compose()["services"]["squid"]
    assert squid["read_only"] is True
    assert squid["tmpfs"] == [SQUID_PROBE_TMPFS]


def test_proxy_policy_refreshes_before_expiry_and_recovers_from_stale_marker(
    tmp_path: Path,
) -> None:
    timer = DEPLOY / "systemd/aca-gx10-proxy-policy.timer"
    assert timer.is_file()
    timer_source = timer.read_text()
    assert "OnUnitActiveSec=180s" in timer_source
    assert "Persistent=true" in timer_source
    assert "aca-gx10-proxy-policy.service" in timer_source
    runtime_unit = (DEPLOY / "systemd/aca-gx10.service").read_text()
    assert "aca-gx10-proxy-policy.timer" in runtime_unit

    marker = tmp_path / "policy.ready"
    marker.write_text(f"validated_at={int(time.time()) - 301}\n")
    squid = tmp_path / "squid"
    squid.write_text("#!/usr/bin/env bash\nexit 0\n")
    squid.chmod(0o700)
    curl = tmp_path / "curl"
    curl.write_text("#!/usr/bin/env bash\nexit 0\n")
    curl.chmod(0o700)
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "GX10_PROXY_READY_FILE": str(marker),
        "GX10_PROXY_POLICY_MAX_AGE_SECONDS": "300",
        "GX10_PROXY_USERNAME": "operator",
        "GX10_PROXY_PASSWORD": "credential",
        "GX10_SQUID_BIN": str(squid),
    }
    check = SCRIPTS / "check_proxy_ready.sh"
    stale = subprocess.run([check], env=env, capture_output=True, text=True)
    assert stale.returncode != 0
    marker.write_text(f"validated_at={int(time.time())}\n")
    fresh = subprocess.run([check], env=env, capture_output=True, text=True)
    assert fresh.returncode == 0, fresh.stderr


def test_stale_policy_harness_uses_supported_real_age_control() -> None:
    source = (SCRIPTS / "policy_failure_harness.sh").read_text()
    stale_case = source.split("stale_policy)", 1)[1].split(";;", 1)[0]
    assert "GX10_PROXY_POLICY_MAX_AGE_SECONDS=0" in stale_case
    assert "--max-age-seconds" not in stale_case


def test_clean_stack_exercises_dependency_loss_diagnostics_and_recovery() -> None:
    clean_stack = (SCRIPTS / "verify_clean_stack.sh").read_text()
    recovery = SCRIPTS / "verify_dependency_recovery.sh"
    assert recovery.is_file() and recovery.stat().st_mode & 0o111
    source = recovery.read_text()
    for token in (
        'compose stop "$dependency"',
        'gx10-role-ready --role "$role"',
        "diagnostics dependency_loss",
        'compose start "$dependency"',
        'compose up -d --wait "$role"',
    ):
        assert token in source
    assert "verify_dependency_recovery.sh" in clean_stack


def test_every_stateful_mount_has_a_verified_persistence_sentinel(tmp_path: Path) -> None:
    script = SCRIPTS / "persistence_sentinels.sh"
    assert script.is_file() and script.stat().st_mode & 0o111
    persistent_root = tmp_path / "srv-aca"
    runtime = tmp_path / "runtime"
    env = os.environ | {
        "GX10_PERSIST_ROOT": str(persistent_root),
        "GX10_RUNTIME_DIR": str(runtime),
    }
    seed = subprocess.run([script, "seed"], env=env, capture_output=True, text=True)
    assert seed.returncode == 0, seed.stderr
    required_mounts = {
        "application",
        "postgres",
        "langfuse-postgres",
        "redis",
        "neo4j",
        "neo4j-logs",
        "clickhouse",
        "clickhouse-logs",
        "minio",
        "openbao",
        "squid-logs",
        "caddy-data",
        "caddy-config",
    }
    assert required_mounts == {path.name for path in persistent_root.iterdir()}
    verify = subprocess.run([script, "verify"], env=env, capture_output=True, text=True)
    assert verify.returncode == 0, verify.stderr
    (persistent_root / "redis/.gx10-persistence-sentinel").write_text("tampered\n")
    rejected = subprocess.run([script, "verify"], env=env, capture_output=True, text=True)
    assert rejected.returncode != 0

    clean_stack = (SCRIPTS / "verify_clean_stack.sh").read_text()
    seed_at = clean_stack.index('"$PERSISTENCE_SENTINELS" seed')
    restart_at = clean_stack.index('podman-runtime.sh" down', seed_at)
    verify_at = clean_stack.index('"$PERSISTENCE_SENTINELS" verify', restart_at)
    evidence_at = clean_stack.index('"cold_restart_passed":true', verify_at)
    assert seed_at < restart_at < verify_at < evidence_at


def test_first_install_openbao_provisioning_is_explicit_protected_and_separate() -> None:
    provision = DEPLOY / "openbao/provision-first-install.sh"
    unit = DEPLOY / "systemd/aca-gx10-openbao-provision.service"
    assert provision.is_file() and provision.stat().st_mode & 0o111
    assert unit.is_file()
    source = provision.read_text()
    for token in (
        "CREDENTIALS_DIRECTORY",
        "/sys/init",
        "/sys/auth/approle",
        "/secret/data/newsletter/gx10/runtime",
        "/secret/data/newsletter/gx10/operator",
        "/secret/data/newsletter/gx10/proxy",
        "install -m 0600",
    ):
        assert token in source
    unit_source = unit.read_text()
    assert "LoadCredential=bao-seed:" in unit_source
    assert "provision-first-install.sh" in unit_source
    assert "ProtectSystem=strict" in unit_source
    assert "podman-compose.sh" not in unit_source
    assert "aca-gx10-openbao-container.service" in unit_source

    secrets_unit_source = (DEPLOY / "systemd/aca-gx10-secrets.service").read_text()
    assert "ProtectSystem=strict" in secrets_unit_source
    assert "podman-compose.sh" not in secrets_unit_source
    assert "aca-gx10-openbao-container.service" in secrets_unit_source

    container_unit = DEPLOY / "systemd/aca-gx10-openbao-container.service"
    assert container_unit.is_file()
    container_source = container_unit.read_text()
    assert container_source.startswith("[Unit]\n")
    assert "\n[Service]\n" in container_source
    assert "ExecStart=/opt/aca/scripts/gx10/podman-compose.sh up -d openbao" in container_source
    assert "ProtectSystem=full" in container_source
    assert "LoadCredential=" not in container_source
    assert "provision-first-install.sh" not in container_source
    assert "render-secrets.sh" not in container_source

    normal_units = "\n".join(
        (DEPLOY / f"systemd/{name}").read_text()
        for name in ("aca-gx10.service", "aca-gx10-secrets.service")
    )
    assert "aca-gx10-openbao-provision.service" not in normal_units


def test_non_default_public_langfuse_url_drives_nextauth_renderer(tmp_path: Path) -> None:
    tools = _mock_secret_tools(tmp_path)
    runtime = tmp_path / "runtime"
    token = tmp_path / "token"
    token.write_text("fixture-token")
    public_url = "https://observability.example.test/langfuse"
    env = os.environ | {
        "PATH": f"{tools}:{os.environ['PATH']}",
        "GX10_RUNTIME_DIR": str(runtime),
        "GX10_BAO_ADDR": "http://openbao.test/v1",
        "GX10_BAO_TOKEN_FILE": str(token),
        "GX10_OPENSSL_ARGS": str(tmp_path / "openssl.args"),
        "GX10_OPENSSL_STDIN": str(tmp_path / "openssl.stdin"),
        "GX10_PUBLIC_LANGFUSE_URL": public_url,
    }
    result = subprocess.run(
        [DEPLOY / "openbao/render-secrets.sh"], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert _read_env(runtime / "langfuse.env")["NEXTAUTH_URL"] == public_url
    assert _read_env(runtime / "common.env")["GX10_PUBLIC_LANGFUSE_URL"] == public_url
