#!/usr/bin/env bash
# Ensure one compose service's container exists and runs, without ever
# stopping a running one.
#
# podman-compose 1.0.6 `up` recreates every container whose compose hash is
# stale by stopping and removing it. That is never acceptable for a unit that
# fires on a timer while the runtime owns the stack, and Podman records
# depends_on by container ID, so replacing a single container strands its
# dependents. This helper therefore only creates what is missing or starts
# what is stopped; the runtime's own start performs full recreation.
set -euo pipefail

ROOT_DIR="${GX10_ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
PODMAN="${GX10_PODMAN_BIN:-/usr/bin/podman}"
PROJECT="${COMPOSE_PROJECT_NAME:-aca-gx10}"
SERVICE="${1:?usage: ensure_service.sh <service>}"

[[ "$SERVICE" =~ ^[a-z0-9-]+$ ]] || { echo "gx10 invalid service name" >&2; exit 64; }
[[ "$PODMAN" == /* && -x "$PODMAN" ]] || { echo "gx10 Podman executable must be an absolute executable path" >&2; exit 64; }
NAME="${PROJECT}_${SERVICE}_1"

if "$PODMAN" container exists "$NAME"; then
  state="$("$PODMAN" inspect --format '{{.State.Status}}' "$NAME")"
  case "$state" in
    running)
      echo "gx10 $SERVICE already running" >&2
      exit 0
      ;;
    created|exited|stopped)
      "$PODMAN" start "$NAME" >/dev/null
      exit 0
      ;;
    *)
      echo "gx10 $SERVICE container is in state '$state'; remove it first: podman rm -f --depend $NAME" >&2
      exit 1
      ;;
  esac
fi

exec "$ROOT_DIR/scripts/gx10/podman-compose.sh" up -d "$SERVICE"
