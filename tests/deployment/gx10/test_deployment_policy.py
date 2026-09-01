"""Executable deployment policy contract for the GX-10 production runtime."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
COMPOSE_PATH = ROOT / "docker-compose.gx10.yml"
DIGEST_PIN = re.compile(r"^[^\s@]+:[^\s@]+@sha256:[0-9a-f]{64}$")
APPLICATION_SERVICES = {"api", "worker", "scheduler", "maintenance"}
STATEFUL_SERVICES = {
    "app-postgres",
    "langfuse-postgres",
    "redis",
    "neo4j",
    "clickhouse",
    "minio",
    "openbao",
}
REQUIRED_SERVICES = (
    STATEFUL_SERVICES
    | APPLICATION_SERVICES
    | {
        "langfuse-web",
        "langfuse-worker",
        "squid",
        "caddy",
    }
)


def _compose() -> dict[str, object]:
    assert COMPOSE_PATH.is_file(), "GX-10 Compose overlay is required"
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def _service(compose: dict[str, object], name: str) -> dict[str, object]:
    services = compose["services"]
    assert isinstance(services, dict)
    value = services[name]
    assert isinstance(value, dict)
    return value


def test_all_runtime_images_are_immutable_and_squid_uses_reviewed_release() -> None:
    compose = _compose()
    services = compose["services"]
    assert isinstance(services, dict)
    assert services.keys() >= REQUIRED_SERVICES

    for name, value in services.items():
        assert isinstance(value, dict)
        image = value.get("image")
        assert isinstance(image, str), f"{name} must declare a rendered image"
        if name not in APPLICATION_SERVICES | {"squid", "langfuse-worker"}:
            assert DIGEST_PIN.fullmatch(image), (
                f"{name} image must include tag and immutable digest"
            )

    for name in APPLICATION_SERVICES:
        assert _service(compose, name)["image"] == (
            "${GX10_APP_IMAGE:?set a reviewed application tag@sha256 digest}"
        )

    squid_image = _service(compose, "squid")["image"]
    assert isinstance(squid_image, str)
    assert squid_image == (
        "ubuntu/squid:6.6-24.04_beta@sha256:"
        "${GX10_SQUID_DIGEST:?set the reviewed published manifest digest}"
    )
    assert _service(compose, "langfuse-worker")["image"] == (
        "langfuse/langfuse-worker:3@sha256:"
        "${GX10_LANGFUSE_WORKER_DIGEST:?set the reviewed worker manifest digest}"
    )


def test_stateful_ports_are_private_and_ingress_is_loopback_bound() -> None:
    compose = _compose()
    for name in (STATEFUL_SERVICES - {"openbao"}) | {
        "langfuse-web",
        "langfuse-worker",
        "squid",
    }:
        service = _service(compose, name)
        assert "ports" not in service, f"{name} must not publish a host port"

    assert _service(compose, "openbao")["ports"] == ["127.0.0.1:18200:8200"]
    caddy_ports = _service(compose, "caddy").get("ports")
    assert caddy_ports == ["127.0.0.1:8443:443"]


def test_application_namespaces_have_no_direct_internet_route() -> None:
    compose = _compose()
    networks = compose["networks"]
    assert isinstance(networks, dict)
    assert networks["application"]["internal"] is True
    assert networks["stateful"]["internal"] is True
    assert networks["egress"]["internal"] is False

    for name in APPLICATION_SERVICES:
        service_networks = _service(compose, name)["networks"]
        assert "application" in service_networks
        assert "egress" not in service_networks
        service = _service(compose, name)
        environment = service["environment"]
        assert {
            "localhost",
            "127.0.0.1",
            "app-postgres",
            "redis",
            "neo4j",
            "openbao",
            "squid",
            "langfuse-web",
        } <= set(environment["NO_PROXY"].split(","))
        env_files = service["env_file"]
        assert {
            "/run/aca/gx10/common.env",
            f"/run/aca/gx10/{name}.env",
            "/run/aca/gx10/proxy.env",
        } == {entry["path"] for entry in env_files if entry["required"] is True}

    assert {"application", "egress"} <= set(_service(compose, "squid")["networks"])


def test_proxy_policy_is_read_only_authenticated_masked_and_fail_closed() -> None:
    compose = _compose()
    squid = _service(compose, "squid")
    mounts = squid["volumes"]
    assert any("squid.conf:/etc/squid/squid.conf:ro" in mount for mount in mounts)
    assert any("allowed-domains.txt:/etc/squid/allowed-domains.txt:ro" in mount for mount in mounts)
    assert any("/run/aca/gx10/proxy" in mount and mount.endswith(":ro") for mount in mounts)

    config = (ROOT / "deploy/gx10/squid/squid.conf").read_text(encoding="utf-8")
    assert "auth_param basic" in config
    assert "acl authenticated proxy_auth REQUIRED" in config
    assert "acl allowed_domains dstdomain" in config
    assert "acl SSL_ports port 443" in config
    assert "http_access allow authenticated allowed_domains SSL_ports CONNECT" in config
    assert config.rstrip().endswith("http_access deny all")
    assert "logformat gx10_connect" in config
    assert "%>a" not in config and "%ru" not in config


def test_egress_exceptions_and_failure_matrix_are_explicit_and_bounded() -> None:
    policy = yaml.safe_load((ROOT / "deploy/gx10/egress-policy.yaml").read_text(encoding="utf-8"))
    assert policy["default"] == "deny"
    assert policy["application_direct_route"] == "deny"
    assert set(policy["bounded_exceptions"]) == {
        "dns",
        "ntp",
        "certificate_bootstrap",
        "proxy_health",
    }
    assert all(
        entry["targets"] and entry["timeout_seconds"] <= 30
        for entry in policy["bounded_exceptions"].values()
    )

    failures = policy["fail_closed"]
    assert set(failures) == {
        "unknown_destination",
        "stale_policy",
        "invalid_policy",
        "dns_failure",
        "credential_failure",
        "proxy_failure",
    }
    assert all(value["external_calls"] == "deny" for value in failures.values())
    assert all(value["local_diagnostics"] == "allow" for value in failures.values())


def test_health_order_persistence_restart_backoff_and_quotas_are_bounded() -> None:
    compose = _compose()
    for name in REQUIRED_SERVICES:
        service = _service(compose, name)
        assert "healthcheck" in service, f"{name} must be health checked"
        assert service.get("restart") == "on-failure:5"
        limits = service.get("deploy", {}).get("resources", {}).get("limits", {})
        assert limits.get("cpus") and limits.get("memory")

    for name in STATEFUL_SERVICES:
        mounts = _service(compose, name).get("volumes", [])
        assert any(str(mount).startswith("/srv/aca/") for mount in mounts), name

    for name in APPLICATION_SERVICES:
        depends = _service(compose, name)["depends_on"]
        assert depends["squid"]["condition"] == "service_healthy"
        assert depends["openbao"]["condition"] == "service_healthy"
        assert depends["langfuse-web"]["condition"] == "service_healthy"

    unit = (ROOT / "deploy/gx10/systemd/aca-gx10.service").read_text(encoding="utf-8")
    requires = next(line for line in unit.splitlines() if line.startswith("Requires="))
    after = next(line for line in unit.splitlines() if line.startswith("After="))
    dependencies = {
        "aca-gx10-image-pins.service",
        "aca-gx10-secrets.service",
        "aca-gx10-proxy-policy.service",
        "aca-gx10-firewall.service",
    }
    assert dependencies <= set(requires.removeprefix("Requires=").split())
    assert dependencies <= set(after.removeprefix("After=").split())
    assert "Restart=on-failure" in unit
    assert "RestartSec=15s" in unit
    assert "StartLimitBurst=5" in unit


def test_runtime_validator_accepts_the_reviewed_squid_source_contract() -> None:
    """The static and rendered image gates must share the approved Squid tag."""
    from scripts.gx10 import validate_runtime

    errors: list[str] = []
    validate_runtime.check_images(_compose(), errors)
    assert errors == []
