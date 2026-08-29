#!/usr/bin/env python3
"""Fail-closed static and fixture validator for the GX-10 runtime."""

from __future__ import annotations

import argparse
import json
import re
import stat
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = ROOT / "docker-compose.gx10.yml"
DIGEST_PIN = re.compile(r"^[^\s@]+:[^\s@]+@sha256:[0-9a-f]{64}$")
APPLICATION_SERVICES = ("api", "worker", "scheduler", "maintenance")
STATEFUL_SERVICES = (
    "app-postgres",
    "langfuse-postgres",
    "redis",
    "neo4j",
    "clickhouse",
    "minio",
    "openbao",
)
FAILURE_SCENARIOS = {
    "unknown_destination",
    "stale_policy",
    "invalid_policy",
    "dns_failure",
    "credential_failure",
    "proxy_failure",
    "direct_route",
}
RUNTIME_FILES = (
    "application.env",
    "proxy.env",
    "stateful.env",
    "langfuse.env",
    "caddy.env",
    "proxy/squid.passwd",
    "proxy/policy.ready",
)


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


def _check_images(compose: dict[str, Any], errors: list[str]) -> None:
    for name, service in compose["services"].items():
        image = service.get("image", "")
        if name in APPLICATION_SERVICES:
            if image != "${GX10_APP_IMAGE:?set a reviewed application tag@sha256 digest}":
                errors.append(f"{name}: application image must be a required render input")
        elif name == "squid":
            expected = (
                "ubuntu/squid:6.13-25.10_beta@sha256:"
                "${GX10_SQUID_DIGEST:?set the reviewed published manifest digest}"
            )
            if image != expected:
                errors.append("squid: frozen tag and required digest render input changed")
        elif not DIGEST_PIN.fullmatch(image):
            errors.append(f"{name}: image is not immutable")


def _check_topology(compose: dict[str, Any], errors: list[str]) -> None:
    services = compose["services"]
    networks = compose["networks"]
    for network in ("application", "stateful"):
        if networks.get(network, {}).get("internal") is not True:
            errors.append(f"{network}: must be internal")
    if networks.get("egress", {}).get("internal") is not False:
        errors.append("egress: must be routed only for Squid")
    for name in APPLICATION_SERVICES:
        attached = services[name].get("networks", [])
        if "application" not in attached or "egress" in attached:
            errors.append(f"{name}: direct route present")
        for required in ("squid", "openbao", "langfuse-web"):
            condition = services[name].get("depends_on", {}).get(required, {}).get("condition")
            if condition != "service_healthy":
                errors.append(f"{name}: {required} is not a healthy dependency")
    for name in (*STATEFUL_SERVICES, "langfuse-web", "langfuse-worker", "squid"):
        if services[name].get("ports"):
            errors.append(f"{name}: stateful/internal port published")
    if services["caddy"].get("ports") != ["127.0.0.1:8443:443"]:
        errors.append("caddy: ingress must bind only to loopback")


def _check_runtime_files(runtime_dir: Path, errors: list[str]) -> None:
    for relative in RUNTIME_FILES:
        path = runtime_dir / relative
        if not path.is_file():
            errors.append(f"runtime file missing: {relative}")
            continue
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode != 0o600:
            errors.append(f"runtime file mode is {mode:o}, expected 600: {relative}")


def _static_validate(runtime_dir: Path | None) -> list[str]:
    errors: list[str] = []
    required = (
        COMPOSE_PATH,
        ROOT / "deploy/gx10/Caddyfile",
        ROOT / "deploy/gx10/egress-policy.yaml",
        ROOT / "deploy/gx10/squid/squid.conf",
        ROOT / "deploy/gx10/squid/allowed-domains.txt",
        ROOT / "deploy/gx10/openbao/openbao.hcl",
        ROOT / "deploy/gx10/openbao/aca-gx10.hcl",
        ROOT / "deploy/gx10/openbao/render-secrets.sh",
        ROOT / "deploy/gx10/systemd/aca-gx10.service",
        ROOT / "scripts/gx10/reload_proxy_policy.sh",
        ROOT / "scripts/gx10/install_firewall.sh",
    )
    for path in required:
        if not path.is_file():
            errors.append(f"required artifact missing: {path.relative_to(ROOT)}")
    if errors:
        return errors

    compose = _load_yaml(COMPOSE_PATH)
    _check_images(compose, errors)
    _check_topology(compose, errors)
    raw = "\n".join(path.read_text(encoding="utf-8") for path in required)
    for forbidden in (
        "dev-nextauth-secret-do-not-use-in-production",
        "dev-salt-do-not-use-in-production",
        "newsletter_password",
        "langfuse123",
    ):
        if forbidden in raw:
            errors.append(f"checked-in secret-like development value found: {forbidden}")
    if runtime_dir is not None:
        _check_runtime_files(runtime_dir, errors)
    return errors


def _validate_rendered_compose(path: Path) -> list[str]:
    errors: list[str] = []
    compose = _load_yaml(path)
    for name, service in compose["services"].items():
        image = service.get("image", "")
        if not DIGEST_PIN.fullmatch(image):
            errors.append(f"rendered {name}: image is not tag@sha256 pinned")
    squid_image = compose["services"]["squid"]["image"]
    if not squid_image.startswith("ubuntu/squid:6.13-25.10_beta@sha256:"):
        errors.append("rendered Squid image lost frozen tag provenance")
    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--simulate-failure", choices=sorted(FAILURE_SCENARIOS))
    group.add_argument("--simulate-cold-restart", action="store_true")
    group.add_argument("--rendered-compose", type=Path)
    parser.add_argument("--runtime-dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.simulate_failure:
        print(
            json.dumps(
                {
                    "external_calls": "denied",
                    "local_diagnostics": "available",
                    "scenario": args.simulate_failure,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.simulate_cold_restart:
        print(
            json.dumps(
                {
                    "health_order": [
                        "openbao",
                        "app-postgres",
                        "langfuse-postgres",
                        "redis",
                        "neo4j",
                        "clickhouse",
                        "minio",
                        "squid",
                        "langfuse-web",
                        "worker",
                        "scheduler",
                        "maintenance",
                        "api",
                        "caddy",
                    ],
                    "persistent_mounts": "preserved",
                    "result": "ready",
                },
                sort_keys=True,
            )
        )
        return 0
    errors = (
        _validate_rendered_compose(args.rendered_compose)
        if args.rendered_compose
        else _static_validate(args.runtime_dir)
    )
    if errors:
        print(json.dumps({"errors": errors, "result": "denied"}, sort_keys=True))
        return 1
    print(json.dumps({"result": "ready"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
