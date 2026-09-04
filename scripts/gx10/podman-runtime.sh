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

PODMAN="${GX10_PODMAN_BIN:-/usr/bin/podman}"
DOWN_TIMEOUT="${GX10_RUNTIME_DOWN_TIMEOUT_SECONDS:-45}"

compose() { "${COMPOSE[@]}" "$@"; }

# Remove every container of the project, dependents first, killing after the
# grace period. podman-compose's own down stops with a short grace and then
# removes without --force, which leaves a slow-stopping container stuck in
# "stopping" and every later start failing on it.
sweep_project_containers() {
  local ids=()
  mapfile -t ids < <("$PODMAN" ps -aq --filter "label=io.podman.compose.project=$PROJECT")
  (( ${#ids[@]} )) || return 0
  "$PODMAN" rm -f --depend -t "$DOWN_TIMEOUT" "${ids[@]}" >/dev/null
}

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
    sweep_project_containers
    compose up -d
    wait_for_runtime
    ;;
  down)
    compose down --timeout "$DOWN_TIMEOUT"
    sweep_project_containers
    ;;
  *)
    echo "usage: podman-runtime.sh up|down" >&2
    exit 64
    ;;
esac
