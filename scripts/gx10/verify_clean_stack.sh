#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${GX10_COMPOSE_FILE:-$ROOT_DIR/docker-compose.gx10.yml}"
RUNTIME_DIR="${GX10_RUNTIME_DIR:-/run/aca/gx10}"
VALIDATOR="$ROOT_DIR/scripts/gx10/validate_runtime.py"
FAILURE_HARNESS="$ROOT_DIR/scripts/gx10/policy_failure_harness.sh"
DEPENDENCY_RECOVERY="$ROOT_DIR/scripts/gx10/verify_dependency_recovery.sh"
PERSISTENCE_SENTINELS="$ROOT_DIR/scripts/gx10/persistence_sentinels.sh"
WORK_DIR="$(mktemp -d)"
EVIDENCE="${GX10_CLEAN_STACK_EVIDENCE:-$WORK_DIR/clean-stack.json}"

cleanup() {
  docker compose -f "$COMPOSE_FILE" down --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

require_root_owned_runtime() {
  test "$(stat -c %a "$RUNTIME_DIR")" = 700
  test "$(stat -c %u "$RUNTIME_DIR")" = 0
  find "$RUNTIME_DIR" -type f ! -perm 0600 -print -quit | grep -q '^$'
}

prepare_runtime() {
  systemctl restart aca-gx10-secrets.service
  systemctl restart aca-gx10-proxy-policy.service
  systemctl restart aca-gx10-firewall.service
}

"$ROOT_DIR/scripts/gx10/verify_image_pins.sh"
compose config --no-env-resolution >"$WORK_DIR/rendered-compose.yml"
uv run python "$VALIDATOR" \
  --rendered-compose "$WORK_DIR/rendered-compose.yml" \
  --image-pins-evidence "$RUNTIME_DIR/image-pins.ready"
compose down --remove-orphans
prepare_runtime
uv run python "$VALIDATOR" --runtime-dir "$RUNTIME_DIR"
require_root_owned_runtime

compose up -d --wait
compose exec -T caddy caddy validate --config /etc/caddy/Caddyfile
compose exec -T openbao bao status -address=http://127.0.0.1:8200
uv run python "$VALIDATOR" --failure-harness "$FAILURE_HARNESS"
"$DEPENDENCY_RECOVERY"
"$PERSISTENCE_SENTINELS" seed

# A real down/up cycle exercises and verifies every required persistent mount.
compose down --remove-orphans
prepare_runtime
compose up -d --wait
"$PERSISTENCE_SENTINELS" verify
for role in api worker scheduler maintenance; do
  compose exec -T "$role" gx10-role-ready --role "$role"
done
uv run python "$VALIDATOR" --failure-harness "$FAILURE_HARNESS"
"$DEPENDENCY_RECOVERY"

printf '%s\n' \
  '{"live":true,"registry_verified":true,"cold_restart_passed":true,"direct_routes_denied":true,"persistence_sentinels_verified":true,"dependency_recovery_verified":true}' \
  >"$EVIDENCE"
chmod 0600 "$EVIDENCE"
uv run python "$VALIDATOR" --clean-stack-evidence "$EVIDENCE"
printf 'GX-10 clean-stack evidence: %s\n' "$EVIDENCE"
