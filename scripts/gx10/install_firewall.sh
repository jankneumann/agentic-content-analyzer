#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${GX10_ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
COMPOSE_FILE="${GX10_COMPOSE_FILE:-$ROOT_DIR/docker-compose.gx10.yml}"
PYTHON="${GX10_PYTHON:-/usr/bin/python3}"

# podman-compose 1.0.6 cannot render without resolving the image environment
# and has no JSON output, so this guard reads the reviewed overlay directly,
# exactly as validate_runtime.py does. It fails closed on any policy drift.
"$PYTHON" - "$COMPOSE_FILE" <<'PY'
import sys

import yaml

compose = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
services = compose["services"]
errors = []

# Compose internal networks have no default gateway. Refuse activation if the
# application or stateful network changes to routed.
for network in ("application", "stateful"):
    if compose["networks"][network].get("internal") is not True:
        errors.append(f"gx10 {network} network permits direct routing")

# No application role may join the egress network.
for service in ("api", "worker", "scheduler", "maintenance"):
    attached = services[service].get("networks") or []
    if "egress" in list(attached):
        errors.append(f"gx10 {service} has a forbidden direct egress route")

# Internal networks cannot publish host ports at all (netavark installs no
# forwarding for them); ingress and management use fixed bridge addresses.
for name, service in services.items():
    for port in service.get("ports") or []:
        errors.append(f"gx10 {name} publishes a host port: {port}")

for error in errors:
    print(error, file=sys.stderr)
sys.exit(1 if errors else 0)
PY

echo "gx10 private-network and host-binding policy verified" >&2
