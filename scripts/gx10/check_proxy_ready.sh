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
# The ubuntu/squid image ships no curl. OpenSSL performs the same authenticated
# CONNECT through the local proxy and then a verified TLS handshake with an
# allowed egress host. The username is a non-secret identifier; the password is
# read from the environment by OpenSSL itself and never appears in argv.
PROBE_HOST="${GX10_PROXY_PROBE_HOST:-api.github.com:443}"
timeout "${GX10_PROXY_PROBE_TIMEOUT_SECONDS:-10}" openssl s_client \
  -proxy 127.0.0.1:3128 \
  -proxy_user "$GX10_PROXY_USERNAME" \
  -proxy_pass env:GX10_PROXY_PASSWORD \
  -connect "$PROBE_HOST" \
  -verify_return_error -brief </dev/null >/dev/null 2>&1
