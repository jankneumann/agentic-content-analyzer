#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${GX10_ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
COMPOSE=("$ROOT_DIR/scripts/gx10/podman-compose.sh")
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
      container="$(compose ps -q "$service" | head -n 1)"
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
    compose up -d
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
