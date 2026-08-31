#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${GX10_COMPOSE_FILE:-$ROOT_DIR/docker-compose.gx10.yml}"
RUNTIME_DIR="${GX10_RUNTIME_DIR:-/run/aca/gx10}"
VALIDATOR="$ROOT_DIR/scripts/gx10/validate_runtime.py"
FAILURE_HARNESS="$ROOT_DIR/scripts/gx10/policy_failure_harness.sh"
DEPENDENCY_RECOVERY="$ROOT_DIR/scripts/gx10/verify_dependency_recovery.sh"
PERSISTENCE_SENTINELS="$ROOT_DIR/scripts/gx10/persistence_sentinels.sh"
NATIVE_PERSISTENCE="$ROOT_DIR/scripts/gx10/native_persistence_evidence.sh"
WORK_DIR="$(mktemp -d)"
VALIDATION_DIR="${GX10_VALIDATION_DIR:-/srv/aca/validation}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
EVIDENCE="${GX10_CLEAN_STACK_EVIDENCE:-$VALIDATION_DIR/clean-stack-$RUN_ID.json}"
STACK_RUNNING=false

case "$(realpath -m "$EVIDENCE")" in
  "$WORK_DIR"/*) echo "gx10 clean-stack evidence must survive WORK_DIR cleanup" >&2; exit 1 ;;
esac

cleanup() {
  if [[ "$STACK_RUNNING" == true ]]; then
    "$ROOT_DIR/scripts/gx10/podman-runtime.sh" down >/dev/null 2>&1 || true
  fi
  [[ -z "${WORK_DIR:-}" ]] || rm -rf -- "$WORK_DIR"
}
trap cleanup EXIT

compose() {
  "$ROOT_DIR/scripts/gx10/podman-compose.sh" "$@"
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
"$ROOT_DIR/scripts/gx10/podman-runtime.sh" down
prepare_runtime
uv run python "$VALIDATOR" --runtime-dir "$RUNTIME_DIR"
require_root_owned_runtime

"$ROOT_DIR/scripts/gx10/podman-runtime.sh" up
STACK_RUNNING=true
compose exec -T caddy caddy validate --config /etc/caddy/Caddyfile
compose exec -T openbao bao status -address=http://127.0.0.1:8200
uv run python "$VALIDATOR" --failure-harness "$FAILURE_HARNESS"
"$DEPENDENCY_RECOVERY"
"$PERSISTENCE_SENTINELS" seed
"$NATIVE_PERSISTENCE" seed

# A real down/up cycle exercises and verifies every required persistent mount.
"$ROOT_DIR/scripts/gx10/podman-runtime.sh" down
STACK_RUNNING=false
prepare_runtime
"$ROOT_DIR/scripts/gx10/podman-runtime.sh" up
STACK_RUNNING=true
"$PERSISTENCE_SENTINELS" verify
"$NATIVE_PERSISTENCE" verify
for role in api worker scheduler maintenance; do
  compose exec -T "$role" gx10-role-ready --role "$role"
done
uv run python "$VALIDATOR" --failure-harness "$FAILURE_HARNESS"
"$DEPENDENCY_RECOVERY"

EVIDENCE_PAYLOAD='{"live":true,"registry_verified":true,"cold_restart_passed":true,"direct_routes_denied":true,"persistence_sentinels_verified":true,"native_persistence_verified":true,"dependency_recovery_verified":true,"cleanup_completed":true}'
"$ROOT_DIR/scripts/gx10/podman-runtime.sh" down
STACK_RUNNING=false
rm -rf -- "$WORK_DIR"
WORK_DIR=""
install -d -m 0700 "$(dirname "$EVIDENCE")"
printf '%s\n' "$EVIDENCE_PAYLOAD" | install -m 0600 /dev/stdin "$EVIDENCE.new"
mv -f "$EVIDENCE.new" "$EVIDENCE"
sha256sum "$EVIDENCE" >"$EVIDENCE.sha256"
chmod 0600 "$EVIDENCE" "$EVIDENCE.sha256"
sha256sum -c "$EVIDENCE.sha256"
uv run python "$VALIDATOR" --clean-stack-evidence "$EVIDENCE"
trap - EXIT
printf 'GX-10 clean-stack evidence: %s\n' "$EVIDENCE"
