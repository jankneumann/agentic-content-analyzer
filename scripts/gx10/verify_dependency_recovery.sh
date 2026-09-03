#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${GX10_COMPOSE_FILE:-$ROOT_DIR/docker-compose.gx10.yml}"
FAILURE_HARNESS="$ROOT_DIR/scripts/gx10/policy_failure_harness.sh"
declare -a RUNTIME_DEPENDENCIES=(
  "api:app-postgres"
  "api:redis"
  "api:falkordb"
  "api:openbao"
  "api:squid"
  "api:langfuse-web"
  "worker:app-postgres"
  "worker:redis"
  "worker:falkordb"
  "worker:openbao"
  "worker:squid"
  "worker:langfuse-web"
  "scheduler:app-postgres"
  "scheduler:redis"
  "scheduler:falkordb"
  "scheduler:openbao"
  "scheduler:squid"
  "scheduler:langfuse-web"
  "maintenance:app-postgres"
  "maintenance:redis"
  "maintenance:falkordb"
  "maintenance:openbao"
  "maintenance:squid"
  "maintenance:langfuse-web"
  "langfuse-web:langfuse-postgres"
  "langfuse-web:clickhouse"
  "langfuse-web:redis"
  "langfuse-web:minio"
  "langfuse-worker:langfuse-postgres"
  "langfuse-worker:clickhouse"
  "langfuse-worker:redis"
  "langfuse-worker:minio"
  "langfuse-worker:langfuse-web"
)

compose() {
  "$ROOT_DIR/scripts/gx10/podman-compose.sh" "$@"
}

probe_dependency() {
  local role="$1" dependency="$2" port self_health
  case "$role" in
    api|worker|scheduler|maintenance)
      compose exec -T "$role" gx10-role-ready --role "$role"
      ;;
    langfuse-web|langfuse-worker)
      if [[ "$role" == "langfuse-web" ]]; then
        self_health="http://127.0.0.1:3000/api/public/health"
      else
        self_health="http://127.0.0.1:3030/api/health"
      fi
      compose exec -T "$role" wget --spider -q "$self_health" || return 1
      case "$dependency" in
        langfuse-postgres) port=5432 ;;
        redis) port=6379 ;;
        clickhouse)
          compose exec -T "$role" wget --spider -q http://clickhouse:8123/ping
          return
          ;;
        minio)
          compose exec -T "$role" wget --spider -q http://minio:9000/minio/health/live
          return
          ;;
        langfuse-web)
          compose exec -T "$role" wget --spider -q http://langfuse-web:3000/api/public/health
          return
          ;;
        *) echo "unsupported GX-10 dependency mapping: $role -> $dependency" >&2; return 64 ;;
      esac
      compose exec -T "$role" node -e \
        'const n=require("net");const s=n.createConnection(Number(process.argv[2]),process.argv[1]);s.setTimeout(3000);s.on("connect",()=>{s.end();process.exit(0)});s.on("timeout",()=>process.exit(1));s.on("error",()=>process.exit(1));' \
        "$dependency" "$port"
      ;;
    *) echo "unsupported GX-10 dependent: $role" >&2; return 64 ;;
  esac
}

wait_for_unhealthy() {
  local role="$1" dependency="$2"
  for _attempt in {1..45}; do
    if ! probe_dependency "$role" "$dependency"; then
      return 0
    fi
    sleep 2
  done
  echo "gx10 dependent remained ready after dependency loss: $role -> $dependency" >&2
  return 1
}

wait_for_healthy() {
  local role="$1" dependency="$2"
  for _attempt in {1..60}; do
    if probe_dependency "$role" "$dependency"; then
      return 0
    fi
    sleep 2
  done
  echo "gx10 dependent did not recover: $role -> $dependency" >&2
  return 1
}

for mapping in "${RUNTIME_DEPENDENCIES[@]}"; do
  role="${mapping%%:*}"
  dependency="${mapping#*:}"
  compose stop "$dependency"
  if probe_dependency "$role" "$dependency"; then
    echo "gx10 role remained ready after dependency loss: $role -> $dependency" >&2
    exit 1
  fi
  wait_for_unhealthy "$role" "$dependency"
  diagnostic_role="$role"
  [[ "$role" == langfuse-* ]] && diagnostic_role=api
  GX10_DIAGNOSTIC_ROLE="$diagnostic_role" "$FAILURE_HARNESS" diagnostics dependency_loss
  compose start "$dependency"
  compose up -d --wait "$role"
  wait_for_healthy "$role" "$dependency"
done

echo "gx10 dependency-loss readiness and recovery verified" >&2
