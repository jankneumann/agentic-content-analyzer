"""Baseline production artifacts required by D8 and PROFILE-001/002."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_gx10_baseline_includes_compose_systemd_caddy_and_openbao() -> None:
    required = {
        "docker-compose.gx10.yml",
        "deploy/gx10/Caddyfile",
        "deploy/gx10/openbao/aca-gx10.hcl",
        "deploy/gx10/openbao/render-secrets.sh",
        "deploy/gx10/systemd/aca-gx10.service",
        "deploy/gx10/systemd/aca-gx10-secrets.service",
        "deploy/gx10/systemd/aca-gx10-proxy-policy.service",
        "deploy/gx10/systemd/aca-gx10-firewall.service",
        "deploy/gx10/squid/squid.conf",
        "deploy/gx10/squid/allowed-domains.txt",
        "scripts/gx10/validate_runtime.py",
    }

    assert {path for path in required if not (ROOT / path).is_file()} == set()


def test_openbao_policy_separates_runtime_operator_and_proxy_rotation() -> None:
    policy = (ROOT / "deploy/gx10/openbao/aca-gx10.hcl").read_text(encoding="utf-8")
    renderer = (ROOT / "deploy/gx10/openbao/render-secrets.sh").read_text(encoding="utf-8")

    assert 'path "secret/data/newsletter/gx10/runtime"' in policy
    assert 'path "secret/data/newsletter/gx10/operator"' in policy
    assert 'path "secret/data/newsletter/gx10/proxy"' in policy
    assert 'capabilities = ["read"]' in policy
    assert "umask 077" in renderer
    assert "install -m 0600" in renderer
    assert "OPERATOR_API_KEY" in renderer
    assert "GX10_PROXY_PASSWORD" in renderer
    assert "ROTATION_GENERATION" in renderer


def test_squid_policy_is_pinned_fail_closed_and_masks_connect_logs() -> None:
    compose = (ROOT / "docker-compose.gx10.yml").read_text(encoding="utf-8")
    policy = (ROOT / "deploy/gx10/squid/squid.conf").read_text(encoding="utf-8")
    reload_script = (ROOT / "scripts/gx10/reload_proxy_policy.sh").read_text(encoding="utf-8")

    assert "ubuntu/squid:6.13-25.10_beta@sha256:" in compose
    assert "acl allowed_domains dstdomain" in policy
    assert "acl SSL_ports port 443" in policy
    assert "http_access deny all" in policy
    assert "logformat gx10_connect" in policy
    assert "%>a" not in policy
    assert "%ru" not in policy
    assert "squid -k parse" in reload_script
    assert "squid -k reconfigure" in reload_script
    assert "stale" in reload_script.lower()
