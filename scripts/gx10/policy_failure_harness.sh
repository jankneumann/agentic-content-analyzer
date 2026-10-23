#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${GX10_COMPOSE_FILE:-$ROOT_DIR/docker-compose.gx10.yml}"
MODE="${1:?usage: policy_failure_harness.sh external|diagnostics SCENARIO}"
SCENARIO="${2:?usage: policy_failure_harness.sh external|diagnostics SCENARIO}"

compose() {
  "$ROOT_DIR/scripts/gx10/podman-compose.sh" "$@"
}

diagnostics() {
  local role="${GX10_DIAGNOSTIC_ROLE:-api}"
  compose exec -T "$role" python -c \
    'import os; assert os.environ.get("PROFILE") == "gx10"; print("gx10 local diagnostics available")'
}

external() {
  case "$SCENARIO" in
    unknown_destination)
      compose exec -T api curl --fail --silent --show-error \
        --connect-timeout 3 --max-time 8 https://not-on-gx10-allowlist.invalid/
      ;;
    stale_policy)
      compose exec -T squid env GX10_PROXY_POLICY_MAX_AGE_SECONDS=0 \
        sh -ec 'sleep 1; exec gx10-proxy-ready'
      ;;
    invalid_policy)
      compose exec -T squid squid -k parse -f /tmp/gx10-policy-does-not-exist.conf
      ;;
    dns_failure)
      compose exec -T api curl --fail --silent --show-error \
        --connect-timeout 3 --max-time 8 https://gx10-dns-failure.invalid/
      ;;
    credential_failure)
      compose exec -T api env \
        HTTPS_PROXY=http://invalid:invalid@squid:3128 \
        HTTP_PROXY=http://invalid:invalid@squid:3128 \
        curl --fail --silent --show-error --connect-timeout 3 --max-time 8 \
        https://api.github.com/
      ;;
    proxy_failure)
      compose exec -T api env \
        HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 \
        curl --fail --silent --show-error --connect-timeout 3 --max-time 8 \
        https://api.github.com/
      ;;
    direct_route)
      compose exec -T api env -u HTTPS_PROXY -u HTTP_PROXY -u ALL_PROXY \
        -u https_proxy -u http_proxy -u all_proxy \
        curl --fail --silent --show-error --connect-timeout 3 --max-time 8 \
        https://api.github.com/
      ;;
    *)
      printf 'unknown failure scenario: %s\n' "$SCENARIO" >&2
      return 64
      ;;
  esac
}

case "$MODE" in
  external) external ;;
  diagnostics) diagnostics ;;
  *)
    printf 'unknown harness mode: %s\n' "$MODE" >&2
    exit 64
    ;;
esac
