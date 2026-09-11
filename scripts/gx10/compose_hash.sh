#!/usr/bin/env bash
# Print podman-compose's config hash for the current overlay (`current`), or
# the hash a container was created from (`container <name>`). podman-compose
# hashes the merged, env-resolved document, so the only faithful source is
# podman-compose itself: a --dry-run `up` prints the label without creating
# anything (its read-only `podman ps`/`network exists` calls still run).
set -euo pipefail

ROOT_DIR="${GX10_ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
PODMAN="${GX10_PODMAN_BIN:-/usr/bin/podman}"

case "${1:-}" in
  current)
    service="${2:?usage: compose_hash.sh current <service>}"
    "$ROOT_DIR/scripts/gx10/podman-compose.sh" --dry-run up -d "$service" 2>&1 \
      | grep -oE 'io\.podman\.compose\.config-hash=[0-9a-f]{64}' | head -n 1 | cut -d= -f2
    ;;
  container)
    name="${2:?usage: compose_hash.sh container <name>}"
    "$PODMAN" inspect --format '{{index .Config.Labels "io.podman.compose.config-hash"}}' "$name"
    ;;
  *)
    echo "usage: compose_hash.sh current <service> | container <name>" >&2
    exit 64
    ;;
esac
