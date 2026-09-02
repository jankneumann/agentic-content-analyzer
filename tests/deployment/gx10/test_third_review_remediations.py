"""Regression contracts for the third GX-10 runtime review."""

from __future__ import annotations

import json
import os
import runpy
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
DEPLOY = ROOT / "deploy/gx10"
SCRIPTS = ROOT / "scripts/gx10"


def _compose() -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load((ROOT / "docker-compose.gx10.yml").read_text()))


def test_dependency_recovery_covers_every_runtime_dependency_and_real_worker_health() -> None:
    compose = _compose()
    services = compose["services"]
    recovery = (SCRIPTS / "verify_dependency_recovery.sh").read_text()
    dependents = ("api", "worker", "scheduler", "maintenance", "langfuse-web", "langfuse-worker")
    expected = {
        f"{dependent}:{dependency}"
        for dependent in dependents
        for dependency in services[dependent].get("depends_on", {})
    }
    assert {
        "langfuse-web:langfuse-postgres",
        "langfuse-web:clickhouse",
        "langfuse-web:minio",
        "api:openbao",
        "api:squid",
    } <= expected
    assert all(f'"{mapping}"' in recovery for mapping in expected)
    assert "wait_for_unhealthy" in recovery
    assert "wait_for_healthy" in recovery

    worker = services["langfuse-worker"]
    assert worker["image"] == (
        "langfuse/langfuse-worker:3@sha256:"
        "${GX10_LANGFUSE_WORKER_DIGEST:?set the reviewed worker manifest digest}"
    )
    health = " ".join(worker["healthcheck"]["test"])
    assert "http://127.0.0.1:3030/api/health" in health
    assert "process.exit(0)" not in health

    readiness = runpy.run_path(str(SCRIPTS / "check_role_readiness.py"))
    role_dependencies = readiness["ROLE_DEPENDENCIES"]
    for role in ("api", "worker", "scheduler", "maintenance"):
        assert {host for host, _port in role_dependencies[role]} == set(
            services[role]["depends_on"]
        )


def test_every_srv_bind_and_native_datastore_record_is_verified_across_restart(
    tmp_path: Path,
) -> None:
    compose = _compose()
    mounted = {
        str(volume).split(":", 1)[0].removeprefix("/srv/aca/")
        for service in compose["services"].values()
        for volume in service.get("volumes", [])
        if str(volume).startswith("/srv/aca/")
    }
    persistent_root = tmp_path / "srv-aca"
    runtime = tmp_path / "runtime"
    result = subprocess.run(
        [SCRIPTS / "persistence_sentinels.sh", "seed"],
        env=os.environ
        | {
            "GX10_PERSIST_ROOT": str(persistent_root),
            "GX10_RUNTIME_DIR": str(runtime),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert mounted == {path.name for path in persistent_root.iterdir()}

    native = SCRIPTS / "native_persistence_evidence.sh"
    assert native.is_file() and native.stat().st_mode & 0o111
    native_source = native.read_text()
    for token in (
        "OperationService",
        "operation_id",
        "/api/public/traces/",
        "clickhouse",
        "seed)",
        "verify)",
    ):
        assert token in native_source

    clean_stack = (SCRIPTS / "verify_clean_stack.sh").read_text()
    seed_at = clean_stack.index('"$NATIVE_PERSISTENCE" seed')
    restart_at = clean_stack.index('podman-runtime.sh" down', seed_at)
    verify_at = clean_stack.index('"$NATIVE_PERSISTENCE" verify', restart_at)
    assert seed_at < restart_at < verify_at


def test_first_install_rejects_missing_secret_field_before_ready_marker(tmp_path: Path) -> None:
    credential_dir = tmp_path / "credentials"
    credential_dir.mkdir()
    operator_dir = tmp_path / "operator"
    operator_dir.mkdir()
    (operator_dir / "bao-bootstrap-token").write_text("root-token\n")
    (operator_dir / "bao-unseal-key").write_text("unseal-key\n")

    runtime = {
        "database_url": "postgresql://newsletter_user:pass@app-postgres/newsletters",
        "app_secret_key": "a" * 48,
        "configured_source_key_secret": "b" * 48,
        "operation_cursor_signing_key": "c" * 48,
        "admin_api_key": "d" * 48,
        "langfuse_public_key": "pk-lf-test",
        "langfuse_secret_key": "e" * 48,
        "neo4j_password": "f" * 48,
        "release_revision": "1" * 40,
        "authority_fingerprint": "2" * 64,
        "app_postgres_password": "g" * 48,
        "langfuse_postgres_password": "h" * 48,
        "redis_password": "i" * 48,
        "clickhouse_password": "j" * 48,
        "minio_root_user": "gx10-minio",
        "minio_root_password": "k" * 48,
        "langfuse_nextauth_secret": "l" * 48,
        "langfuse_salt": "m" * 48,
        # langfuse_encryption_key is deliberately absent.
        "caddy_username": "operator",
        "caddy_password_hash": "bcrypt-fixture",
    }
    seed = {
        "runtime": runtime,
        "operator": {"operator_api_key": "n" * 48, "rotation_generation": "1"},
        "proxy": {
            "username": "aca-egress",
            "password": "p" * 48,
            "rotation_generation": "1",
        },
    }
    (credential_dir / "bao-seed").write_text(json.dumps(seed))

    tools = tmp_path / "bin"
    tools.mkdir()
    curl = tools / "curl"
    curl.write_text(
        """#!/usr/bin/env bash
url="${!#}"
case "$url" in
  *sys/health*) printf '{"initialized":true,"sealed":false}\n' ;;
  *sys/mounts) printf '{"data":{"secret/":{"type":"kv","options":{"version":"2"}}}}\n' ;;
  *sys/auth) printf '{"data":{"approle/":{"type":"approle"}}}\n' ;;
  *) printf '{}\n' ;;
esac
"""
    )
    curl.chmod(0o700)

    result = subprocess.run(
        [DEPLOY / "openbao/provision-first-install.sh"],
        env=os.environ
        | {
            "PATH": f"{tools}:{os.environ['PATH']}",
            "CREDENTIALS_DIRECTORY": str(credential_dir),
            "GX10_BAO_OPERATOR_DIR": str(operator_dir),
            "GX10_BAO_ADDR": "http://openbao.test/v1",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "seed credential is invalid" in result.stderr
    assert not (operator_dir / "openbao-provisioned.ready").exists()


def _valid_first_install_seed() -> dict[str, Any]:
    return {
        "runtime": {
            "database_url": "postgresql://newsletter_user:pass@app-postgres/newsletters",
            "app_secret_key": "a" * 48,
            "configured_source_key_secret": "b" * 48,
            "operation_cursor_signing_key": "c" * 48,
            "admin_api_key": "d" * 48,
            "langfuse_public_key": "pk-lf-test",
            "langfuse_secret_key": "e" * 48,
            "langfuse_init_org_id": "aca-gx10",
            "langfuse_init_org_name": "ACA GX-10",
            "langfuse_init_project_id": "aca-gx10-observability",
            "langfuse_init_project_name": "ACA GX-10 Observability",
            "langfuse_init_user_email": "operator@example.test",
            "langfuse_init_user_name": "GX-10 Operator",
            "langfuse_init_user_password": "q" * 48,
            "neo4j_password": "f" * 48,
            "release_revision": "1" * 40,
            "authority_fingerprint": "2" * 64,
            "app_postgres_password": "g" * 48,
            "langfuse_postgres_password": "h" * 48,
            "redis_password": "i" * 48,
            "clickhouse_password": "j" * 48,
            "minio_root_user": "gx10-minio",
            "minio_root_password": "k" * 48,
            "langfuse_nextauth_secret": "l" * 48,
            "langfuse_salt": "m" * 48,
            "langfuse_encryption_key": "3" * 64,
            "caddy_username": "operator",
            "caddy_password_hash": "$2a$14$" + "A" * 53,
        },
        "operator": {"operator_api_key": "n" * 48, "rotation_generation": "1"},
        "proxy": {
            "username": "aca-egress",
            "password": "p" * 48,
            "rotation_generation": "1",
        },
        "backup": {
            "backup_age_recipient": "age1" + "a" * 58,
            "backup_age_retained_recipients": ["age1" + "b" * 58],
            "backup_age_identities": {
                "age1" + "a" * 58: "AGE-SECRET-KEY-ACTIVE",
                "age1" + "b" * 58: "AGE-SECRET-KEY-RETAINED",
            },
        },
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("langfuse_postgres_password", "g" * 48),
        ("redis_password", "i" * 47 + "!"),
        ("proxy.password", "p" * 47 + ":"),
        ("caddy_password_hash", "bcrypt-fixture"),
    ],
)
def test_first_install_rejects_incompatible_secret_values_before_ready_marker(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    credential_dir = tmp_path / "credentials"
    credential_dir.mkdir()
    operator_dir = tmp_path / "operator"
    operator_dir.mkdir()
    (operator_dir / "bao-bootstrap-token").write_text("root-token\n")
    (operator_dir / "bao-unseal-key").write_text("unseal-key\n")
    tools = tmp_path / "bin"
    tools.mkdir()
    curl = tools / "curl"
    curl.write_text(
        """#!/usr/bin/env bash
url="${!#}"
case "$url" in
  *sys/health*) printf '{"initialized":true,"sealed":false}\n' ;;
  *sys/mounts) printf '{"data":{"secret/":{"type":"kv","options":{"version":"2"}}}}\n' ;;
  *sys/auth) printf '{"data":{"approle/":{"type":"approle"}}}\n' ;;
  *) printf '{}\n' ;;
esac
"""
    )
    curl.chmod(0o700)
    seed = _valid_first_install_seed()
    if field == "proxy.password":
        seed["proxy"]["password"] = value
    else:
        seed["runtime"][field] = value
    (credential_dir / "bao-seed").write_text(json.dumps(seed))

    result = subprocess.run(
        [DEPLOY / "openbao/provision-first-install.sh"],
        env=os.environ
        | {
            "PATH": f"{tools}:{os.environ['PATH']}",
            "CREDENTIALS_DIRECTORY": str(credential_dir),
            "GX10_BAO_OPERATOR_DIR": str(operator_dir),
            "GX10_BAO_ADDR": "http://openbao.test/v1",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "seed credential is invalid" in result.stderr
    assert not (operator_dir / "openbao-provisioned.ready").exists()


def test_first_install_accepts_complete_seed_and_records_ready_marker(tmp_path: Path) -> None:
    credential_dir = tmp_path / "credentials"
    credential_dir.mkdir()
    operator_dir = tmp_path / "operator"
    operator_dir.mkdir()
    (operator_dir / "bao-bootstrap-token").write_text("root-token\\n")
    (operator_dir / "bao-unseal-key").write_text("unseal-key\\n")
    (credential_dir / "bao-seed").write_text(json.dumps(_valid_first_install_seed()))

    tools = tmp_path / "bin"
    tools.mkdir()
    curl = tools / "curl"
    curl.write_text(
        """#!/usr/bin/env bash
url="${!#}"
case "$url" in
  *sys/health*) printf '{"initialized":true,"sealed":false}\n' ;;
  *sys/mounts) printf '{"data":{"secret/":{"type":"kv","options":{"version":"2"}}}}\n' ;;
  *sys/auth) printf '{"data":{"approle/":{"type":"approle"}}}\n' ;;
  *) printf '{}\n' ;;
esac
"""
    )
    curl.chmod(0o700)

    result = subprocess.run(
        [DEPLOY / "openbao/provision-first-install.sh"],
        env=os.environ
        | {
            "PATH": f"{tools}:{os.environ['PATH']}",
            "CREDENTIALS_DIRECTORY": str(credential_dir),
            "GX10_BAO_OPERATOR_DIR": str(operator_dir),
            "GX10_BAO_ADDR": "http://openbao.test/v1",
        },
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (operator_dir / "openbao-provisioned.ready").is_file()


def test_public_environment_is_optional_and_renderer_defaults_remain_protected() -> None:
    unit = (DEPLOY / "systemd/aca-gx10-secrets.service").read_text()
    assert "EnvironmentFile=-/etc/aca/gx10-public.env" in unit
    renderer = (DEPLOY / "openbao/render-secrets.sh").read_text()
    assert "${GX10_PUBLIC_LANGFUSE_URL:-https://gx10.local/langfuse}" in renderer
    assert "${GX10_PUBLIC_ORIGIN:-${PUBLIC_LANGFUSE_URL%/langfuse}}" in renderer


def test_clean_stack_evidence_survives_cleanup_with_checksum() -> None:
    source = (SCRIPTS / "verify_clean_stack.sh").read_text()
    assert "${GX10_VALIDATION_DIR:-/srv/aca/validation}" in source
    assert "$WORK_DIR/clean-stack.json" not in source
    cleanup_at = source.index('podman-runtime.sh" down', source.index("cold_restart_passed"))
    evidence_at = source.index("sha256sum", cleanup_at)
    assert cleanup_at < evidence_at
    assert 'chmod 0600 "$EVIDENCE" "$EVIDENCE.sha256"' in source
    assert 'sha256sum -c "$EVIDENCE.sha256"' in source
