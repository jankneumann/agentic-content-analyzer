#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${GX10_ROOT_DIR:-/opt/aca}"
COMPOSE_FILE="${GX10_COMPOSE_FILE:-$ROOT_DIR/docker-compose.gx10.yml}"

if [[ ! -x /usr/bin/podman-compose ]]; then
  echo "gx10 requires the rootful /usr/bin/podman-compose provider" >&2
  exit 127
fi

exec /usr/bin/podman-compose -p aca-gx10 -f "$COMPOSE_FILE" "$@"
