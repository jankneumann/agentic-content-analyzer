#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${GX10_ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

# bootstrap_audit: durable terminal evidence while PostgreSQL may be unavailable.
gx10_proxy_policy_audit_exit() {
  local command_status=$?
  trap - EXIT
  local outcome="succeeded"
  local diagnostic_args=()
  if [[ $command_status -ne 0 ]]; then
    outcome="permanent_failure"
    diagnostic_args=(--diagnostic-code gx10.proxy_policy_reload_failed)
  fi
  local python_bin="python3"
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    python_bin="$ROOT_DIR/.venv/bin/python"
  fi
  local audit_status=0
  PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
    "$python_bin" -m src.clients.operational_observability \
    "gx10.reload_proxy_policy" "$outcome" "${diagnostic_args[@]}" \
    >/dev/null || audit_status=$?
  if [[ $command_status -eq 0 && $audit_status -ne 0 ]]; then
    command_status=$audit_status
  fi
  exit "$command_status"
}
trap gx10_proxy_policy_audit_exit EXIT
COMPOSE=(docker compose -f "$ROOT_DIR/docker-compose.gx10.yml")
POLICY="$ROOT_DIR/deploy/gx10/squid/squid.conf"
DOMAINS="$ROOT_DIR/deploy/gx10/squid/allowed-domains.txt"
RUNTIME_DIR="${GX10_RUNTIME_DIR:-/run/aca/gx10}"
READY="$RUNTIME_DIR/proxy/policy.ready"

install -d -m 0700 "$RUNTIME_DIR/proxy"
rm -f -- "$READY"

if [[ ! -s "$POLICY" || ! -s "$DOMAINS" ]]; then
  echo "gx10 proxy policy missing; refusing reload" >&2
  exit 1
fi
# A stale readiness marker is intentionally recoverable after a fresh parse and probe.
if [[ ! -s "$RUNTIME_DIR/proxy/squid.passwd" ]]; then
  echo "gx10 proxy credentials missing; refusing reload" >&2
  exit 1
fi

"${COMPOSE[@]}" exec -T squid squid -k parse -f /etc/squid/squid.conf
"${COMPOSE[@]}" exec -T squid squid -k reconfigure
"${COMPOSE[@]}" exec -T squid /usr/local/bin/gx10-proxy-ready --probe-only
install -m 0600 /dev/null "$READY"
printf 'validated_at=%(%s)T\n' -1 >"$READY"
