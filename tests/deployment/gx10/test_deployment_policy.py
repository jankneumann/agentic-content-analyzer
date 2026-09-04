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
    "falkordb",
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
        "docker.io/ubuntu/squid:6.6-24.04_beta@sha256:"
        "${GX10_SQUID_DIGEST:?set the reviewed published manifest digest}"
    )
    assert _service(compose, "langfuse-worker")["image"] == (
        "docker.io/langfuse/langfuse-worker:3.225.5@sha256:"
        "${GX10_LANGFUSE_WORKER_DIGEST:?set the reviewed worker manifest digest}"
    )


def test_stateful_ports_are_private_and_ingress_is_loopback_bound() -> None:
    compose = _compose()
    for name in STATEFUL_SERVICES | {
        "langfuse-web",
        "langfuse-worker",
        "squid",
    }:
        service = _service(compose, name)
        assert "ports" not in service, f"{name} must not publish a host port"

    assert "ports" not in _service(compose, "caddy"), "caddy must not publish a host port"


def test_openbao_runs_as_image_user_without_capabilities() -> None:
    """The pinned OpenBao image drops root via su-exec, which needs CAP_SETGID.

    The stack drops every capability, so the container must start directly as
    the image's own ``openbao`` user (uid 100, gid 1000 in the pinned digest)
    and the entrypoint's privilege drop never runs. OpenBao 2.2 also refuses to
    boot when ``disable_mlock`` appears in the config at all, so the config must
    not mention it and ``IPC_LOCK`` is not required.
    """
    service = _service(_compose(), "openbao")
    assert service.get("user") == "100:1000"
    assert "cap_add" not in service, "openbao must not add capabilities"
    config = (ROOT / "deploy/gx10/openbao/openbao.hcl").read_text(encoding="utf-8")
    assert re.search(r"^\s*disable_mlock\s*=", config, re.MULTILINE) is None


OPENBAO_STATEFUL_ADDRESS = "10.89.0.250"
OPENBAO_HOST_ADDR = f"http://{OPENBAO_STATEFUL_ADDRESS}:8200/v1"
OPENBAO_HOST_UNITS = (
    "deploy/gx10/systemd/aca-gx10-openbao-provision.service",
    "deploy/gx10/systemd/aca-gx10-secrets.service",
    "deploy/gx10/systemd/aca-gx10-backup-secrets.service",
)


def test_openbao_is_reached_on_a_fixed_stateful_address_not_a_host_port() -> None:
    """netavark does not port-forward for ``internal: true`` networks.

    Podman still binds the published host port as a reservation and hands the
    socket to conmon, so a loopback publish on the internal stateful network
    accepts TCP and then hangs forever. Host-side units therefore talk to
    OpenBao on a fixed bridge address inside an explicitly declared subnet, and
    the service publishes nothing on the host.
    """
    compose = _compose()
    stateful = compose["networks"]["stateful"]
    assert stateful["internal"] is True
    assert stateful["ipam"]["config"] == [{"subnet": "10.89.0.0/24", "ip_range": "10.89.0.0/25"}]

    openbao = _service(compose, "openbao")
    assert "ports" not in openbao
    assert openbao["networks"] == {"stateful": {"ipv4_address": OPENBAO_STATEFUL_ADDRESS}}

    for unit in OPENBAO_HOST_UNITS:
        text = (ROOT / unit).read_text(encoding="utf-8")
        assert f"Environment=GX10_BAO_ADDR={OPENBAO_HOST_ADDR}" in text, unit
        assert "18200" not in text, unit

    for script in sorted((ROOT / "deploy/gx10/openbao").glob("*.sh")):
        text = script.read_text(encoding="utf-8")
        if "GX10_BAO_ADDR" not in text:
            continue
        assert f'"${{GX10_BAO_ADDR:-{OPENBAO_HOST_ADDR}}}"' in text, script.name
        assert "18200" not in text, script.name


IMAGE_USERS = {
    # Verified from the pinned digests: each image's own service account, so the
    # entrypoint never needs CAP_SETUID/SETGID/CHOWN to drop root itself.
    "app-postgres": "999:999",
    "langfuse-postgres": "999:999",
    "redis": "999:1000",
    "falkordb": "999:999",
    "clickhouse": "101:101",
    "minio": "60001:60001",
    "openbao": "100:1000",
    "squid": "13:13",
}
CADDY_APPLICATION_ADDRESS = "10.89.1.250"


def test_stateful_services_start_as_their_image_users_with_no_capabilities() -> None:
    """Every image here drops root via gosu/su-exec/setpriv when started as root.

    With ``cap_drop: ALL`` that drop fails, so each service starts directly as
    the image's own user. Redis previously chowned and gosu'd inside its
    command; both are impossible without capabilities and are gone.
    """
    compose = _compose()
    for name, user in IMAGE_USERS.items():
        service = _service(compose, name)
        assert service.get("user") == user, name
        assert "cap_add" not in service, name
        assert service.get("cap_drop") == ["ALL"], name
    redis_command = " ".join(_service(compose, "redis")["command"])
    for forbidden in ("chown", "gosu", "su-exec", "setpriv"):
        assert forbidden not in redis_command


def test_caddy_ingress_sits_on_a_fixed_application_address() -> None:
    """The application network is internal, so a loopback publish would hang
    exactly like OpenBao's did. Caddy holds a fixed bridge address instead.

    The caddy binary carries file capabilities; with every capability dropped
    the kernel refuses to exec it at all, so NET_BIND_SERVICE is the one grant
    in the stack, and it is exactly what binding 443 needs.
    """
    compose = _compose()
    application = compose["networks"]["application"]
    assert application["internal"] is True
    assert application["ipam"]["config"] == [{"subnet": "10.89.1.0/24", "ip_range": "10.89.1.0/25"}]
    caddy = _service(compose, "caddy")
    assert "ports" not in caddy
    assert caddy["networks"] == {"application": {"ipv4_address": CADDY_APPLICATION_ADDRESS}}
    assert caddy["cap_add"] == ["NET_BIND_SERVICE"]
    for name, service in compose["services"].items():
        if name != "caddy":
            assert "cap_add" not in service, name


def test_squid_runs_unprivileged_on_a_read_only_root() -> None:
    config = (ROOT / "deploy/gx10/squid/squid.conf").read_text(encoding="utf-8")
    assert re.search(r"^pid_filename /tmp/squid\.pid$", config, re.MULTILINE)
    domains = [
        line.strip()
        for line in (ROOT / "deploy/gx10/squid/allowed-domains.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    for domain in domains:
        parents = [other for other in domains if other != domain and domain.endswith(other)]
        assert not parents, f"squid 6 rejects {domain}: already covered by {parents}"


def test_renderer_hands_container_read_secrets_to_the_consuming_image_user() -> None:
    renderer = (ROOT / "deploy/gx10/openbao/render-secrets.sh").read_text(encoding="utf-8")
    assert "REDIS_ACL_OWNER=(-o 999 -g 1000)" in renderer
    assert "PASSWD_OWNER=(-o 13 -g 13)" in renderer
    assert 'install "${REDIS_ACL_OWNER[@]}" -m 0600 "$REDIS_ACL_TMP"' in renderer
    assert 'install "${PASSWD_OWNER[@]}" -m 0600 "$PASSWD_TMP"' in renderer


def test_firewall_guard_parses_the_overlay_without_unsupported_compose_flags(
    tmp_path: Path,
) -> None:
    """podman-compose 1.0.6 has no ``--no-env-resolution``/``--format`` on
    ``config``; the guard must read the overlay itself and still fail closed."""
    script = ROOT / "scripts/gx10/install_firewall.sh"
    source = script.read_text(encoding="utf-8")
    assert "--no-env-resolution" not in source
    assert "--format json" not in source

    import subprocess

    env = {"PATH": "/usr/bin:/bin", "GX10_ROOT_DIR": str(ROOT)}
    ok = subprocess.run([str(script)], env=env, capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr

    compose = _compose()
    compose["services"]["caddy"]["ports"] = ["0.0.0.0:8443:8443"]
    broken = tmp_path / "broken.yml"
    broken.write_text(yaml.safe_dump(compose), encoding="utf-8")
    rejected = subprocess.run(
        [str(script)], env={**env, "GX10_COMPOSE_FILE": str(broken)}, capture_output=True, text=True
    )
    assert rejected.returncode != 0
    assert "host port" in rejected.stderr

    compose = _compose()
    compose["networks"]["stateful"]["internal"] = False
    broken.write_text(yaml.safe_dump(compose), encoding="utf-8")
    rejected = subprocess.run(
        [str(script)], env={**env, "GX10_COMPOSE_FILE": str(broken)}, capture_output=True, text=True
    )
    assert rejected.returncode != 0
    assert "direct routing" in rejected.stderr


def test_clean_stack_gate_renders_compose_with_supported_config_command() -> None:
    source = (ROOT / "scripts/gx10/verify_clean_stack.sh").read_text(encoding="utf-8")
    assert "--no-env-resolution" not in source
    assert 'compose config >"$WORK_DIR/rendered-compose.yml"' in source


def test_env_file_entries_are_plain_paths_for_podman_compose_1_0_6() -> None:
    """podman-compose 1.0.6 joins each env_file entry as a path string and
    crashes with a TypeError on the ``{path, required}`` long form. Podman
    fails closed on a missing ``--env-file``, so nothing is lost."""
    for name, service in _compose()["services"].items():
        for entry in service.get("env_file", []):
            assert isinstance(entry, str), f"{name}: {entry!r}"
            assert entry.startswith("/run/aca/gx10/"), f"{name}: {entry}"


GX10_SURFACE = (
    "docker-compose.gx10.yml",
    "profiles/gx10.yaml",
    "docs/GX10_PODMAN_SETUP.md",
    "deploy/gx10",
    "scripts/gx10",
)


def test_graph_backend_is_falkordb_end_to_end() -> None:
    """GX-10 runs FalkorDB, the backend production already uses on Railway.

    Every Neo4j touchpoint must be gone: the profile, the compose service and
    its dependents, the secret seed and renderer, readiness, the persistence
    sentinels, backup/restore plans, storage budgets, and the setup doc.
    """
    profile = yaml.safe_load((ROOT / "profiles/gx10.yaml").read_text(encoding="utf-8"))
    assert profile["providers"]["graphdb"] == "falkordb"
    assert "neo4j" not in profile["providers"]
    assert "neo4j" not in profile["settings"]
    graph = profile["settings"]["graphdb"]
    assert graph["graphdb_mode"] == "local"
    assert graph["falkordb_host"] == "falkordb"
    assert graph["falkordb_port"] == 6379
    assert graph["falkordb_password"] == "${GX10_FALKORDB_PASSWORD}"
    assert graph["falkordb_database"] == "newsletter_graph"
    assert graph["semaphore_limit"] == 1
    assert "falkordb" in profile["settings"]["gx10"]["component_budgets_percent"]

    compose = _compose()
    assert "neo4j" not in compose["services"]
    falkordb = _service(compose, "falkordb")
    assert falkordb["image"].startswith("docker.io/falkordb/falkordb:v4.18.1@sha256:")
    assert DIGEST_PIN.match(falkordb["image"])
    assert falkordb["user"] == "999:999"
    assert falkordb["environment"]["BROWSER"] == "0"
    assert "--aclfile /tmp/falkordb/users.acl" in falkordb["environment"]["REDIS_ARGS"]
    assert falkordb["env_file"] == ["/run/aca/gx10/falkordb.env"]
    assert "/srv/aca/falkordb:/var/lib/falkordb/data:rw" in falkordb["volumes"]
    assert any(m.endswith("falkordb/users.acl:ro") for m in falkordb["volumes"])
    entrypoint = " ".join(falkordb["entrypoint"])
    for forbidden in ("chown", "gosu", "su-exec", "setpriv", "requirepass"):
        assert forbidden not in entrypoint
    assert "exec /var/lib/falkordb/bin/run.sh" in entrypoint
    assert "redis-cli ping" in " ".join(falkordb["healthcheck"]["test"])
    for role in APPLICATION_SERVICES:
        assert _service(compose, role)["depends_on"]["falkordb"]["condition"] == "service_healthy"

    for relative in GX10_SURFACE:
        path = ROOT / relative
        files = [path] if path.is_file() else sorted(path.rglob("*"))
        for file in files:
            if not file.is_file() or (
                file.suffix in {".age", ".json"} and "evidence" in file.parts
            ):
                continue
            text = file.read_text(encoding="utf-8", errors="ignore")
            assert "neo4j" not in text.lower(), file.relative_to(ROOT)


def test_every_image_names_its_registry_explicitly() -> None:
    """Rootful Podman on the GX-10 host has no unqualified-search registries,
    so a short name such as ``ubuntu/squid@sha256:...`` is refused at pull
    time. Short-name aliases do not apply to digested references either, so
    every reviewed image carries its registry host."""
    for name, service in _compose()["services"].items():
        image = service["image"]
        if name in APPLICATION_SERVICES:
            continue
        registry = image.split("/", 1)[0]
        assert "." in registry or registry == "localhost", (
            f"{name}: {image} is not registry-qualified"
        )
        # The pin gate verifies that the tag still resolves to the recorded
        # digest, so a moving tag such as ``:3`` fails on every upstream patch
        # release. Every tag must therefore be an exact release.
        tag = image.split("@", 1)[0].rsplit(":", 1)[1]
        assert not re.fullmatch(r"\d+", tag), f"{name}: bare major tag {tag} is a moving target"
    pins = (ROOT / "scripts/gx10/verify_image_pins.sh").read_text(encoding="utf-8")
    assert 'SQUID_TAG="docker.io/ubuntu/squid:6.6-24.04_beta"' in pins
    assert 'LANGFUSE_WORKER_TAG="docker.io/langfuse/langfuse-worker:3.225.5"' in pins
    component = (ROOT / "scripts/gx10/backup/component.sh").read_text(encoding="utf-8")
    assert 'POSTGRES_IMAGE="docker.io/library/postgres:17.11@sha256:' in component


def test_squid_is_pid_one_and_stops_within_its_grace_period() -> None:
    """The image entrypoint (bash at PID 1) never forwards SIGTERM, so every
    stop hit the kill timeout and podman-compose's stop-then-rm left the
    container stuck in "stopping". Squid itself as PID 1 exits cleanly."""
    squid = _service(_compose(), "squid")
    assert squid["entrypoint"] == ["/usr/sbin/squid"]
    assert squid["command"] == ["-f", "/etc/squid/squid.conf", "-NYC"]
    assert squid["stop_grace_period"] == "20s"


def test_fixed_addresses_sit_outside_the_dynamic_pools_and_networks_are_recreated() -> None:
    """Podman's allocator cursor eventually reaches any address inside the
    dynamic range, and an application container took Caddy's .250 on a real
    start. Fixed addresses live above the ip_range, and the runtime recreates
    project networks on cold start so stale leases and options cannot persist."""
    compose = _compose()
    for network, fixed in (
        ("application", CADDY_APPLICATION_ADDRESS),
        ("stateful", OPENBAO_STATEFUL_ADDRESS),
    ):
        config = compose["networks"][network]["ipam"]["config"][0]
        assert config["ip_range"].endswith("/25")
        assert int(fixed.rsplit(".", 1)[1]) >= 128
    runtime = (ROOT / "scripts/gx10/podman-runtime.sh").read_text(encoding="utf-8")
    assert runtime.index("recreate_project_networks\n    compose up -d") > 0
    assert "network rm" in runtime


def test_langfuse_runs_against_a_single_clickhouse_node() -> None:
    compose = _compose()
    for name in ("langfuse-web", "langfuse-worker"):
        assert _service(compose, name)["environment"]["CLICKHOUSE_CLUSTER_ENABLED"] == "false"


def test_public_origin_is_required_and_never_an_internal_host() -> None:
    """The application rejects LANGFUSE_PUBLIC_URL hosts under localhost,
    .local and .internal; the old gx10.local default could never boot."""
    renderer = (ROOT / "deploy/gx10/openbao/render-secrets.sh").read_text(encoding="utf-8")
    assert "gx10 public origin is unset" in renderer
    assert "localhost|*.localhost|*.local|*.internal)" in renderer
    assert "gx10.local" not in renderer
    assert "gx10.local" not in (ROOT / "deploy/gx10/Caddyfile").read_text(encoding="utf-8")
    profile = (ROOT / "profiles/gx10.yaml").read_text(encoding="utf-8")
    assert "gx10.local" not in profile
    assert '"${GX10_PUBLIC_ORIGIN}"' in profile and '"${GX10_PUBLIC_LANGFUSE_URL}"' in profile


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
            "falkordb",
            "openbao",
            "squid",
            "langfuse-web",
        } <= set(environment["NO_PROXY"].split(","))
        env_files = service["env_file"]
        assert {
            "/run/aca/gx10/common.env",
            f"/run/aca/gx10/{name}.env",
            "/run/aca/gx10/proxy.env",
        } == set(env_files)

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
