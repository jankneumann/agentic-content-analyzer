#!/usr/bin/env bash
set -euo pipefail
MARKER="${GX10_PROXY_READY_FILE:-/run/aca/gx10/proxy/policy.ready}"
PROBE_ONLY="${1:-}"
MAX_AGE="${GX10_PROXY_POLICY_MAX_AGE_SECONDS:-300}"
SQUID_BIN="${GX10_SQUID_BIN:-/usr/sbin/squid}"
if [[ "$PROBE_ONLY" != "--probe-only" ]]; then
  [[ -s "$MARKER" ]] || exit 1
validated_at="$(sed -n 's/^validated_at=//p' "$MARKER")"
[[ "$validated_at" =~ ^[0-9]+$ ]] || exit 1
now="$(date +%s)"
mtime="$(stat -c %Y "$MARKER")"
(( now - validated_at <= MAX_AGE && now - mtime <= MAX_AGE )) || exit 1
fi
"$SQUID_BIN" -k parse -f /etc/squid/squid.conf >/dev/null 2>&1
[[ -n "${GX10_PROXY_USERNAME:-}" && -n "${GX10_PROXY_PASSWORD:-}" ]] || exit 1
config="$(mktemp)"; trap 'rm -f -- "$config"' EXIT; chmod 0600 "$config"
# Curl config is equivalent to --proxy-user without putting credentials in argv.
printf 'proxy = "http://127.0.0.1:3128"\nproxy-user = "%s:%s"\nconnect-timeout = 5\nmax-time = 10\noutput = "/dev/null"\nsilent\nshow-error\nfail\n' "$GX10_PROXY_USERNAME" "$GX10_PROXY_PASSWORD" >"$config"
curl --config "$config" https://api.github.com/
