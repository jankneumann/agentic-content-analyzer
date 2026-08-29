#!/usr/bin/env bash
set -euo pipefail
umask 077

BAO_ADDR="${GX10_BAO_ADDR:-http://127.0.0.1:18200/v1}"
KEY_FILE="${CREDENTIALS_DIRECTORY:?systemd credentials required}/bao-unseal-key"
[[ -s "$KEY_FILE" ]] || { echo "OpenBao unseal credential missing" >&2; exit 1; }

health=""
for _attempt in {1..60}; do
  if health="$(curl -sS --connect-timeout 2 --max-time 3 "$BAO_ADDR/sys/health?standbyok=true&perfstandbyok=true")"; then
    break
  fi
  sleep 1
done
jq -e '.initialized == true' <<<"$health" >/dev/null || { echo "OpenBao is unreachable or uninitialized" >&2; exit 1; }

if jq -e '.sealed == true' <<<"$health" >/dev/null; then
  while IFS= read -r unseal_key; do
    [[ -n "$unseal_key" ]] || continue
    payload="$(mktemp)"
    trap 'rm -f -- "$payload"' EXIT
    jq -n --arg key "$unseal_key" '{key:$key}' >"$payload"
    curl -fsS -X POST --data-binary "@$payload" "$BAO_ADDR/sys/unseal" >/dev/null
    rm -f -- "$payload"
    trap - EXIT
    health="$(curl -sS "$BAO_ADDR/sys/health?standbyok=true&perfstandbyok=true")"
    if jq -e '.sealed == false' <<<"$health" >/dev/null; then
      break
    fi
  done <"$KEY_FILE"
fi

jq -e '.initialized == true and .sealed == false' <<<"$health" >/dev/null || { echo "OpenBao remains sealed" >&2; exit 1; }
