#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${GX10_ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
COMPOSE=(docker compose -f "$ROOT_DIR/docker-compose.gx10.yml")
POLICY="$ROOT_DIR/deploy/gx10/squid/squid.conf"
DOMAINS="$ROOT_DIR/deploy/gx10/squid/allowed-domains.txt"
RUNTIME_DIR="${GX10_RUNTIME_DIR:-/run/aca/gx10}"
READY="$RUNTIME_DIR/proxy/policy.ready"
MAX_AGE="${GX10_PROXY_POLICY_MAX_AGE_SECONDS:-300}"

install -d -m 0700 "$RUNTIME_DIR/proxy"
rm -f -- "$READY"

if [[ ! -s "$POLICY" || ! -s "$DOMAINS" ]]; then
  echo "gx10 proxy policy missing; refusing reload" >&2
  exit 1
fi
if find "$POLICY" "$DOMAINS" -mmin "+$(( (MAX_AGE + 59) / 60 ))" -print -quit | grep -q .; then
  echo "gx10 proxy policy is stale; refusing reload" >&2
  exit 1
fi
if [[ ! -s "$RUNTIME_DIR/proxy/squid.passwd" ]]; then
  echo "gx10 proxy credentials missing; refusing reload" >&2
  exit 1
fi

"${COMPOSE[@]}" exec -T squid squid -k parse -f /etc/squid/squid.conf
"${COMPOSE[@]}" exec -T squid squid -k reconfigure
install -m 0600 /dev/null "$READY"
printf 'validated_at=%(%s)T\n' -1 >"$READY"
