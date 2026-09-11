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
# Everything the application needs; started and proven healthy before the
# schema migration runs and the application roles are created.
INFRASTRUCTURE=(
  app-postgres
  langfuse-postgres
  redis
  falkordb
  clickhouse
  minio
  openbao
  squid
  langfuse-web
  langfuse-worker
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

# Recreate the project's networks from the current overlay: Podman keeps IPAM
# leases and network options from the run that created them, so a changed
# subnet or ip_range (and a leaked lease on a fixed address) would otherwise
# survive every cold start. Runs after the sweep, so no endpoint is attached.
recreate_project_networks() {
  local nets=()
  mapfile -t nets < <("$PODMAN" network ls -q --filter "label=io.podman.compose.project=$PROJECT")
  (( ${#nets[@]} )) || return 0
  "$PODMAN" network rm "${nets[@]}" >/dev/null
}

wait_for_services() {
  local deadline service container status
  deadline=$((SECONDS + TIMEOUT_SECONDS))
  for service in "$@"; do
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

wait_for_runtime() { wait_for_services "${SERVICES[@]}"; }

# The image entrypoint runs `alembic upgrade head` on Railway; this overlay
# starts uvicorn and the workers directly, and the workers fail closed on a
# stale schema with only five restarts. Migrate from a throwaway api container
# (same image, env, and networks) before any application role exists.
run_migrations() {
  compose run --rm --no-deps -T api alembic upgrade head
}

case "${1:-}" in
  up)
    "$ROOT_DIR/scripts/gx10/check_persistence_ownership.py" --compose "$COMPOSE_FILE"
    # Podman records depends_on by container ID at creation, so a partially
    # recreated stack (an OpenBao or Squid container replaced by its own unit)
    # leaves dependents pointing at IDs that no longer exist. A cold start
    # therefore recreates every container; all state lives on bind mounts.
    sweep_project_containers
    recreate_project_networks
    compose up -d "${INFRASTRUCTURE[@]}"
    wait_for_services "${INFRASTRUCTURE[@]}"
    run_migrations
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
