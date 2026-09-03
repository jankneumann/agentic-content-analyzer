#!/usr/bin/env python3
"""Fail-closed static, rendered, and executable-evidence validator for GX-10."""

from __future__ import annotations

import argparse
import json
import re
import stat
import subprocess
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = ROOT / "docker-compose.gx10.yml"
DIGEST_PIN = re.compile(r"^[^\s@]+:[^\s@]+@sha256:([0-9a-f]{64})$")
APPLICATION_SERVICES = ("api", "worker", "scheduler", "maintenance")
SQUID_PROBE_TMPFS = "/tmp:rw,noexec,nosuid,nodev,size=8m"  # noqa: S108
STATEFUL_SERVICES = (
    "app-postgres",
    "langfuse-postgres",
    "redis",
    "falkordb",
    "clickhouse",
    "minio",
    "openbao",
)
OPENBAO_STATEFUL_ADDRESS = "10.89.0.250"
STATEFUL_SUBNET = "10.89.0.0/24"
CADDY_APPLICATION_ADDRESS = "10.89.1.250"
APPLICATION_SUBNET = "10.89.1.0/24"
FAILURE_SCENARIOS = (
    "unknown_destination",
    "stale_policy",
    "invalid_policy",
    "dns_failure",
    "credential_failure",
    "proxy_failure",
    "direct_route",
)
RUNTIME_FILES = (
    "common.env",
    "api.env",
    "worker.env",
    "scheduler.env",
    "maintenance.env",
    "proxy.env",
    "app-postgres.env",
    "langfuse-postgres.env",
    "redis.env",
    "falkordb.env",
    "clickhouse.env",
    "minio.env",
    "langfuse.env",
    "caddy.env",
    "proxy/squid.passwd",
    "redis/users.acl",
    "proxy/policy.ready",
    "image-pins.ready",
)


def load(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


def sentinel(digest: str) -> bool:
    return len(set(digest)) <= 1 or digest in {"deadbeef" * 8, "0123456789abcdef" * 4}


def check_images(compose: dict[str, Any], errors: list[str]) -> None:
    for name, service in compose["services"].items():
        image = service.get("image", "")
        if name in APPLICATION_SERVICES:
            if image != "${GX10_APP_IMAGE:?set a reviewed application tag@sha256 digest}":
                errors.append(f"{name}: protected application image input required")
        elif name == "squid":
            expected = "docker.io/ubuntu/squid:6.6-24.04_beta@sha256:${GX10_SQUID_DIGEST:?set the reviewed published manifest digest}"
            if image != expected:
                errors.append("squid: frozen tag plus protected digest input required")
        elif name == "langfuse-worker":
            expected = "docker.io/langfuse/langfuse-worker:3.225.5@sha256:${GX10_LANGFUSE_WORKER_DIGEST:?set the reviewed worker manifest digest}"
            if image != expected:
                errors.append("langfuse-worker: dedicated protected worker image required")
        elif not DIGEST_PIN.fullmatch(image):
            errors.append(f"{name}: image is not immutable")
        if name not in APPLICATION_SERVICES:
            registry = image.split("/", 1)[0]
            if "." not in registry and registry != "localhost":
                errors.append(f"{name}: image must name its registry explicitly")


def check_topology(compose: dict[str, Any], errors: list[str]) -> None:
    services = compose["services"]
    networks = compose["networks"]
    for network in ("application", "stateful"):
        if networks.get(network, {}).get("internal") is not True:
            errors.append(f"{network}: must be internal")
    for name in APPLICATION_SERVICES:
        attached = services[name].get("networks", [])
        if "application" not in attached or "egress" in attached:
            errors.append(f"{name}: direct route present")
        command = " ".join(services[name].get("healthcheck", {}).get("test", []))
        if "gx10-role-ready" not in command:
            errors.append(f"{name}: active dependency readiness missing")
    for name in (*STATEFUL_SERVICES, "langfuse-web", "langfuse-worker", "squid"):
        ports = services[name].get("ports", [])
        if ports:
            errors.append(f"{name}: internal port published")
    openbao_nets = services["openbao"].get("networks")
    if (
        not isinstance(openbao_nets, dict)
        or openbao_nets.get("stateful", {}).get("ipv4_address") != OPENBAO_STATEFUL_ADDRESS
    ):
        errors.append("openbao: management API must sit on the fixed stateful address")
    stateful_ipam = compose["networks"]["stateful"].get("ipam", {}).get("config", [])
    if stateful_ipam != [{"subnet": STATEFUL_SUBNET}]:
        errors.append("stateful: subnet must be declared for the fixed OpenBao address")
    caddy_nets = services["caddy"].get("networks")
    if services["caddy"].get("ports"):
        errors.append("caddy: internal network cannot publish a host port")
    if (
        not isinstance(caddy_nets, dict)
        or caddy_nets.get("application", {}).get("ipv4_address") != CADDY_APPLICATION_ADDRESS
    ):
        errors.append("caddy: ingress must sit on the fixed application address")
    application_ipam = compose["networks"]["application"].get("ipam", {}).get("config", [])
    if application_ipam != [{"subnet": APPLICATION_SUBNET}]:
        errors.append("application: subnet must be declared for the fixed Caddy address")
    for name, service in services.items():
        if service.get("cap_drop") != ["ALL"]:
            errors.append(f"{name}: must drop all capabilities")
        expected_caps = ["NET_BIND_SERVICE"] if name == "caddy" else None
        if service.get("cap_add") != expected_caps:
            errors.append(f"{name}: unexpected capability grant")
    redis = services["redis"]
    redis_command = " ".join(redis.get("command", []))
    redis_health = " ".join(redis.get("healthcheck", {}).get("test", []))
    if any(token in redis_command for token in ("REDIS_PASSWORD", "requirepass")):
        errors.append("redis: credential present in server argv")
    if "REDIS_PASSWORD" in redis_health or " -a " in redis_health:
        errors.append("redis: credential present in healthcheck argv")
    if "redis-server /etc/redis/gx10.conf" not in redis_command:
        errors.append("redis: protected ACL configuration is not loaded")
    if services["squid"].get("tmpfs") != [SQUID_PROBE_TMPFS]:
        errors.append("squid: bounded writable readiness tmpfs required")


def check_runtime(runtime: Path, errors: list[str]) -> None:
    for relative in RUNTIME_FILES:
        path = runtime / relative
        if not path.is_file():
            errors.append(f"runtime file missing: {relative}")
            continue
        if stat.S_IMODE(path.stat().st_mode) != 0o600:
            errors.append(f"runtime file mode must be 600: {relative}")


def static_validate(runtime: Path | None) -> list[str]:
    errors = []
    required = (
        COMPOSE_PATH,
        ROOT / "deploy/gx10/Caddyfile",
        ROOT / "deploy/gx10/egress-policy.yaml",
        ROOT / "deploy/gx10/squid/squid.conf",
        ROOT / "deploy/gx10/openbao/bootstrap-approle.sh",
        ROOT / "deploy/gx10/openbao/provision-first-install.sh",
        ROOT / "deploy/gx10/openbao/unseal.sh",
        ROOT / "deploy/gx10/openbao/login-approle.sh",
        ROOT / "deploy/gx10/openbao/render-secrets.sh",
        ROOT / "deploy/gx10/redis/gx10.conf",
        ROOT / "deploy/gx10/systemd/aca-gx10-openbao-container.service",
        ROOT / "deploy/gx10/systemd/aca-gx10-openbao-provision.service",
        ROOT / "deploy/gx10/systemd/aca-gx10-image-pins.service",
        ROOT / "scripts/gx10/verify_image_pins.sh",
        ROOT / "scripts/gx10/check_openbao_container_started.sh",
        ROOT / "scripts/gx10/check_persistence_ownership.py",
        ROOT / "deploy/gx10/systemd/aca-gx10-proxy-policy.timer",
        ROOT / "scripts/gx10/check_proxy_ready.sh",
        ROOT / "scripts/gx10/persistence_sentinels.sh",
        ROOT / "scripts/gx10/native_persistence_evidence.sh",
        ROOT / "scripts/gx10/verify_dependency_recovery.sh",
        ROOT / "scripts/gx10/check_role_readiness.py",
    )
    for path in required:
        if not path.is_file():
            errors.append(f"required artifact missing: {path.relative_to(ROOT)}")
    if not errors:
        compose = load(COMPOSE_PATH)
        check_images(compose, errors)
        check_topology(compose, errors)
    if runtime is not None:
        check_runtime(runtime, errors)
    return errors


def rendered_validate(path: Path, evidence: Path | None) -> list[str]:
    errors = []
    compose = load(path)
    for name, service in compose["services"].items():
        match = DIGEST_PIN.fullmatch(service.get("image", ""))
        if not match:
            errors.append(f"rendered {name}: image is not tag@sha256 pinned")
        elif sentinel(match.group(1)):
            errors.append(f"rendered {name}: sentinel digest denied")
    squid = compose["services"]["squid"]["image"]
    if not squid.startswith("docker.io/ubuntu/squid:6.6-24.04_beta@sha256:"):
        errors.append("rendered Squid tag provenance changed")
    if evidence is None or not evidence.is_file():
        errors.append("registry verified image-pins evidence required")
    else:
        proof = evidence.read_text()
        if (
            f"app={compose['services']['api']['image']}" not in proof
            or f"squid={squid}" not in proof
            or f"langfuse_worker={compose['services']['langfuse-worker']['image']}" not in proof
        ):
            errors.append("rendered images do not match verified registry evidence")
    return errors


def run_harness(path: Path) -> list[str]:
    errors = []
    for scenario in FAILURE_SCENARIOS:
        external = subprocess.run(
            [str(path), "external", scenario],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        diagnostics = subprocess.run(
            [str(path), "diagnostics", scenario],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if external.returncode == 0:
            errors.append(f"{scenario}: external call was not denied")
        if diagnostics.returncode != 0:
            errors.append(f"{scenario}: local diagnostics unavailable")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--rendered-compose", type=Path)
    group.add_argument("--failure-harness", type=Path)
    group.add_argument("--clean-stack-evidence", type=Path)
    parser.add_argument("--image-pins-evidence", type=Path)
    parser.add_argument("--runtime-dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.failure_harness:
        errors = run_harness(args.failure_harness)
        executed = True
    elif args.clean_stack_evidence:
        evidence = json.loads(args.clean_stack_evidence.read_text())
        required = {
            "live": True,
            "registry_verified": True,
            "cold_restart_passed": True,
            "direct_routes_denied": True,
            "persistence_sentinels_verified": True,
            "native_persistence_verified": True,
            "dependency_recovery_verified": True,
            "cleanup_completed": True,
        }
        errors = (
            []
            if all(evidence.get(k) == v for k, v in required.items())
            else ["actual clean-stack evidence is incomplete"]
        )
        executed = True
    elif args.rendered_compose:
        errors = rendered_validate(args.rendered_compose, args.image_pins_evidence)
        executed = False
    else:
        errors = static_validate(args.runtime_dir)
        executed = False
    if errors:
        print(json.dumps({"errors": errors, "result": "denied"}, sort_keys=True))
        return 1
    result = {"result": "ready"}
    if executed:
        result["evidence"] = "executed"
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
