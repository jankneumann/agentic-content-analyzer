"""Regression contracts for the GX-10 independent-review findings."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from src.config.profiles import load_profile
from src.config.settings import Settings, _flatten_profile_to_settings

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "deploy/gx10"


def _read_env(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if line)


def _mock_secret_tools(tmp_path: Path) -> Path:
    tools = tmp_path / "bin"
    tools.mkdir()
    curl = tools / "curl"
    curl.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
url="${!#}"
common='{"database_url":"postgresql://newsletter_user:pass@app-postgres:5432/newsletters","app_secret_key":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","configured_source_key_secret":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","operation_cursor_signing_key":"cccccccccccccccccccccccccccccccccccccccccccccccc","admin_api_key":"dddddddddddddddddddddddddddddddddddddddddddddddd","langfuse_public_key":"pk-lf-fixture","langfuse_secret_key":"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee","neo4j_password":"ffffffffffffffffffffffffffffffffffffffffffffffff","release_revision":"1111111111111111111111111111111111111111","authority_fingerprint":"2222222222222222222222222222222222222222222222222222222222222222","app_postgres_password":"gggggggggggggggggggggggggggggggggggggggggggggggg","langfuse_postgres_password":"hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh","redis_password":"iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii","clickhouse_password":"jjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjjj","minio_root_user":"gx10-minio","minio_root_password":"kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk","langfuse_nextauth_secret":"llllllllllllllllllllllllllllllllllllllllllllllll","langfuse_salt":"mmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmm","langfuse_encryption_key":"3333333333333333333333333333333333333333333333333333333333333333","caddy_username":"operator","caddy_password_hash":"bcrypt-fixture"}'
case "$url" in
  */runtime) printf '{"data":{"data":%s}}\n' "$common" ;;
  */operator) printf '{"data":{"data":{"operator_api_key":"nnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnnn","rotation_generation":"8"}}}\n' ;;
  */proxy) printf '{"data":{"data":{"username":"aca-egress","password":"proxycanaryproxycanaryproxycanary1234","rotation_generation":"9"}}}\n' ;;
  *) exit 22 ;;
esac
""",
        encoding="utf-8",
    )
    openssl = tools / "openssl"
    openssl.write_text(
        """#!/usr/bin/env bash
printf '%s\n' "$*" >"$GX10_OPENSSL_ARGS"
IFS= read -r secret
printf '%s\n' "$secret" >"$GX10_OPENSSL_STDIN"
printf '$apr1$fixture$hash\n'
""",
        encoding="utf-8",
    )
    curl.chmod(0o700)
    openssl.chmod(0o700)
    return tools


def test_renderer_outputs_profile_compatible_least_privilege_role_envs(tmp_path: Path) -> None:
    tools = _mock_secret_tools(tmp_path)
    runtime = tmp_path / "runtime"
    token = tmp_path / "token"
    token.write_text("fixture-token", encoding="utf-8")
    env = os.environ | {
        "PATH": f"{tools}:{os.environ['PATH']}",
        "GX10_RUNTIME_DIR": str(runtime),
        "GX10_BAO_ADDR": "http://openbao.test/v1",
        "GX10_BAO_TOKEN_FILE": str(token),
        "GX10_OPENSSL_ARGS": str(tmp_path / "openssl.args"),
        "GX10_OPENSSL_STDIN": str(tmp_path / "openssl.stdin"),
    }
    result = subprocess.run(
        [RUNTIME / "openbao/render-secrets.sh"], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr

    expected = {
        "common.env",
        "api.env",
        "worker.env",
        "scheduler.env",
        "maintenance.env",
        "proxy.env",
        "app-postgres.env",
        "langfuse-postgres.env",
        "redis.env",
        "neo4j.env",
        "clickhouse.env",
        "minio.env",
        "langfuse.env",
        "caddy.env",
    }
    assert expected <= {path.name for path in runtime.glob("*.env")}
    assert "GX10_OPERATOR_API_KEY" in _read_env(runtime / "api.env")
    assert "GX10_ADMIN_API_KEY" in _read_env(runtime / "api.env")
    for role in ("worker", "scheduler", "maintenance"):
        values = _read_env(runtime / f"{role}.env")
        assert "GX10_OPERATOR_API_KEY" not in values
        assert "GX10_ADMIN_API_KEY" not in values
        assert values["GX10_PROCESS_ROLE"] == role
        assert values["OTEL_SERVICE_NAME"] == f"aca-gx10-{role}"

    assert _read_env(runtime / "app-postgres.env").keys() == {"POSTGRES_PASSWORD"}
    assert _read_env(runtime / "langfuse-postgres.env").keys() == {"POSTGRES_PASSWORD"}
    assert _read_env(runtime / "app-postgres.env") != _read_env(
        runtime / "langfuse-postgres.env"
    )

    args = (tmp_path / "openssl.args").read_text()
    stdin = (tmp_path / "openssl.stdin").read_text()
    assert "proxycanary" not in args
    assert "-stdin" in args
    assert "proxycanary" in stdin

    api_environment = (
        _read_env(runtime / "common.env")
        | _read_env(runtime / "api.env")
        | _read_env(runtime / "proxy.env")
        | {
            "GX10_PUBLIC_ORIGIN": "https://gx10.example.com",
            "GX10_PUBLIC_LANGFUSE_URL": "https://gx10.example.com/langfuse",
        }
    )
    profile = load_profile("gx10", profiles_dir=ROOT / "profiles", env_vars=api_environment)
    settings = Settings(_env_file=None, **_flatten_profile_to_settings(profile.model_dump()))
    assert settings.gx10_runtime_enabled is True
    assert settings.gx10_process_role == "api"
    assert settings.otel_service_name == "aca-gx10-api"
    assert settings.operator_api_key is not None


def test_systemd_sources_protected_pins_and_verifies_registry_provenance() -> None:
    units = "\n".join(path.read_text() for path in (RUNTIME / "systemd").glob("*.service"))
    assert "EnvironmentFile=/etc/aca/gx10-images.env" in units
    assert "aca-gx10-image-pins.service" in units
    verifier = (ROOT / "scripts/gx10/verify_image_pins.sh").read_text()
    assert "imagetools inspect" in verifier
    assert "image-pins.ready" in verifier
    assert "0000000000000000000000000000000000000000000000000000000000000000" not in verifier


def test_rendered_validator_rejects_sentinel_or_unverified_digests(tmp_path: Path) -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.gx10.yml").read_text())
    for service in compose["services"].values():
        image = service["image"]
        if "${GX10_APP_IMAGE" in image:
            service["image"] = "example/aca:review@sha256:" + "0" * 64
        elif "${GX10_SQUID_DIGEST" in image:
            service["image"] = "ubuntu/squid:6.13-25.10_beta@sha256:" + "0" * 64
    rendered = tmp_path / "rendered.yml"
    rendered.write_text(yaml.safe_dump(compose), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, ROOT / "scripts/gx10/validate_runtime.py", "--rendered-compose", rendered],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "sentinel" in result.stdout or "verified" in result.stdout


def test_openbao_lifecycle_is_reachable_authenticated_initialized_and_unsealed() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.gx10.yml").read_text())
    openbao = compose["services"]["openbao"]
    assert openbao["ports"] == ["127.0.0.1:18200:8200"]
    health = " ".join(openbao["healthcheck"]["test"])
    assert "test $$? -eq 0" in health
    bootstrap = (RUNTIME / "openbao/bootstrap-approle.sh").read_text()
    assert "sys/policies/acl/aca-gx10" in bootstrap
    assert "auth/approle/role/aca-gx10" in bootstrap
    assert "CREDENTIALS_DIRECTORY" in bootstrap
    login = (RUNTIME / "openbao/login-approle.sh").read_text()
    assert "initialized" in login and "sealed" in login
    assert "auth/approle/login" in login


def test_internal_hosts_bypass_proxy_and_roles_have_distinct_exporters() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.gx10.yml").read_text())
    internal = {"app-postgres", "redis", "neo4j", "openbao", "squid", "langfuse-web"}
    for role in ("api", "worker", "scheduler", "maintenance"):
        service = compose["services"][role]
        no_proxy = set(service["environment"]["NO_PROXY"].split(","))
        assert internal <= no_proxy
        assert service["environment"]["OTEL_SERVICE_NAME"] == f"aca-gx10-{role}"
        assert service["environment"]["OTEL_EXPORTER_OTLP_ENDPOINT"].startswith(
            "http://langfuse-web:3000/"
        )
        assert "gx10-role-ready" in " ".join(service["healthcheck"]["test"])


def test_proxy_readiness_requires_fresh_marker_and_authenticated_connect_probe() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.gx10.yml").read_text())
    command = " ".join(compose["services"]["squid"]["healthcheck"]["test"])
    assert "gx10-proxy-ready" in command
    probe = (ROOT / "scripts/gx10/check_proxy_ready.sh").read_text()
    for token in ("policy.ready", "stat", "proxy-user", "connect-timeout", "max-time"):
        assert token in probe
    assert "https://api.github.com/" in probe


def test_public_langfuse_path_and_generated_trace_url_are_aligned(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = yaml.safe_load((ROOT / "profiles/gx10.yaml").read_text())
    assert profile["settings"]["observability"]["langfuse_public_url"].endswith("/langfuse}")
    caddy = (RUNTIME / "Caddyfile").read_text()
    renderer = (RUNTIME / "openbao/render-secrets.sh").read_text()
    assert "path /langfuse/*" in caddy
    assert "strip_prefix /langfuse" in caddy
    assert "NEXTAUTH_URL=https://gx10.local/langfuse" in renderer

    from src.api import operation_routes

    monkeypatch.setattr(
        operation_routes,
        "get_settings",
        lambda: type("S", (), {"langfuse_public_url": "https://gx10.example.com/langfuse"})(),
    )
    assert operation_routes._langfuse_url("trace-123", authorized=True) == (
        "https://gx10.example.com/langfuse/trace/trace-123"
    )


def test_validator_runs_executable_failure_harness_and_rejects_claimed_cold_restart(
    tmp_path: Path,
) -> None:
    harness = tmp_path / "harness.py"
    harness.write_text(
        """#!/usr/bin/env python3
import sys
raise SystemExit(23 if sys.argv[1] == 'external' else 0)
""",
        encoding="utf-8",
    )
    harness.chmod(0o700)
    result = subprocess.run(
        [
            sys.executable,
            ROOT / "scripts/gx10/validate_runtime.py",
            "--failure-harness",
            harness,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "executed" in result.stdout
    assert "--simulate-cold-restart" not in (
        ROOT / "scripts/gx10/validate_runtime.py"
    ).read_text()


def test_real_clean_stack_gate_is_executable_and_evidence_stays_incomplete() -> None:
    failure_harness = ROOT / "scripts/gx10/policy_failure_harness.sh"
    clean_stack = ROOT / "scripts/gx10/verify_clean_stack.sh"
    validation = RUNTIME / "VALIDATION.md"

    assert failure_harness.stat().st_mode & 0o111
    assert clean_stack.stat().st_mode & 0o111
    harness_source = failure_harness.read_text()
    gate_source = clean_stack.read_text()
    evidence = validation.read_text()

    assert "docker compose" in harness_source
    assert "exec" in harness_source
    assert "validate_runtime.py" in gate_source
    assert "--failure-harness" in gate_source
    assert "docker compose" in gate_source
    assert "restart" in gate_source
