#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${GX10_COMPOSE_FILE:-$ROOT_DIR/docker-compose.gx10.yml}"
FAILURE_HARNESS="$ROOT_DIR/scripts/gx10/policy_failure_harness.sh"
declare -a ROLE_DEPENDENCIES=(
  "api:neo4j"
  "worker:redis"
  "scheduler:app-postgres"
  "maintenance:langfuse-web"
)

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

wait_for_unhealthy() {
  local role="$1" container_id status
  container_id="$(compose ps -q "$role")"
  [[ -n "$container_id" ]] || { echo "gx10 role container missing: $role" >&2; return 1; }
  for _attempt in {1..45}; do
    status="$(docker inspect --format '{{.State.Health.Status}}' "$container_id")"
    [[ "$status" == "unhealthy" ]] && return 0
    sleep 2
  done
  echo "gx10 role did not become unhealthy after dependency loss: $role" >&2
  return 1
}

for mapping in "${ROLE_DEPENDENCIES[@]}"; do
  role="${mapping%%:*}"
  dependency="${mapping#*:}"
  compose stop "$dependency"
  if compose exec -T "$role" gx10-role-ready --role "$role"; then
    echo "gx10 role remained ready after dependency loss: $role -> $dependency" >&2
    exit 1
  fi
  wait_for_unhealthy "$role"
  GX10_DIAGNOSTIC_ROLE="$role" "$FAILURE_HARNESS" diagnostics dependency_loss
  compose start "$dependency"
  compose up -d --wait "$role"
  compose exec -T "$role" gx10-role-ready --role "$role"
done

echo "gx10 dependency-loss readiness and recovery verified" >&2
