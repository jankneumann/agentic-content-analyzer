#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${GX10_ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
COMPOSE=("$ROOT_DIR/scripts/gx10/podman-compose.sh")
COMPOSE_FILE="${GX10_COMPOSE_FILE:-$ROOT_DIR/docker-compose.gx10.yml}"
PROJECT="${COMPOSE_PROJECT_NAME:-aca-gx10}"
TIMEOUT_SECONDS="${GX10_RUNTIME_WAIT_SECONDS:-300}"
SERVICES=(
  app-postgres
  langfuse-postgres
  redis
  falkordb
  clickhouse
  minio
  openbao
  langfuse-web
  langfuse-worker
  squid
  caddy
  api
  worker
  scheduler
  maintenance
)

compose() { "${COMPOSE[@]}" "$@"; }

wait_for_runtime() {
  local deadline service container status
  deadline=$((SECONDS + TIMEOUT_SECONDS))
  for service in "${SERVICES[@]}"; do
    while true; do
      # podman-compose 1.0.6 has no per-service `ps -q`; resolve through labels.
      container="$(/usr/bin/podman ps -a --filter "label=io.podman.compose.project=$PROJECT" --filter "label=com.docker.compose.service=$service" --format '{{.ID}}' | head -n 1)"
      if [[ -n "$container" ]]; then
        status="$(/usr/bin/podman inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container")"
        if [[ "$status" == "healthy" ]]; then
          break
        fi
      fi
      if (( SECONDS >= deadline )); then
        echo "gx10 runtime service did not become healthy: $service" >&2
        return 1
      fi
      sleep 2
    done
  done
}

case "${1:-}" in
  up)
    "$ROOT_DIR/scripts/gx10/check_persistence_ownership.py" --compose "$COMPOSE_FILE"
    # Podman records depends_on by container ID at creation, so a partially
    # recreated stack (an OpenBao or Squid container replaced by its own unit)
    # leaves dependents pointing at IDs that no longer exist. A cold start
    # therefore recreates every container; all state lives on bind mounts.
    compose up -d --force-recreate
    wait_for_runtime
    ;;
  down)
    compose down --timeout "${GX10_RUNTIME_DOWN_TIMEOUT_SECONDS:-45}"
    ;;
  *)
    echo "usage: podman-runtime.sh up|down" >&2
    exit 64
    ;;
esac
