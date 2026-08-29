#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${GX10_ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
COMPOSE=(docker compose -f "$ROOT_DIR/docker-compose.gx10.yml")

# Compose internal networks have no default gateway. Refuse activation if the
# application or stateful network changes to routed, or an app joins egress.
for network in application stateful; do
  internal="$("${COMPOSE[@]}" config --no-env-resolution --format json | jq -r ".networks.${network}.internal")"
  [[ "$internal" == "true" ]] || {
    echo "gx10 ${network} network permits direct routing" >&2
    exit 1
  }
done
for service in api worker scheduler maintenance; do
  if "${COMPOSE[@]}" config --no-env-resolution --format json | jq -e ".services.${service}.networks.egress" >/dev/null; then
    echo "gx10 ${service} has a forbidden direct egress route" >&2
    exit 1
  fi
done

# Host ingress is loopback-only; persistent/stateful ports remain unbound.
if "${COMPOSE[@]}" config --no-env-resolution --format json | jq -e '[.services[] | .ports[]? | select(.host_ip != "127.0.0.1")] | length > 0' >/dev/null; then
  echo "gx10 exposes a non-loopback host port" >&2
  exit 1
fi

echo "gx10 private-network and host-binding policy verified" >&2
