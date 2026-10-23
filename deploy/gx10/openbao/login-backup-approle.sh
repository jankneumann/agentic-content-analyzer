#!/usr/bin/env bash
set -euo pipefail
umask 077
RUNTIME_DIR="${GX10_RUNTIME_DIR:-/run/aca/gx10}/backup"
BAO_ADDR="${GX10_BAO_ADDR:-http://10.89.0.250:8200/v1}"
[[ -s "$RUNTIME_DIR/backup-openbao-role-id" && -s "$RUNTIME_DIR/backup-openbao-secret-id" ]] || { echo "backup OpenBao AppRole material missing" >&2; exit 1; }
payload="$(mktemp)"; token_tmp="$(mktemp "$RUNTIME_DIR/backup-openbao-token.XXXXXX")"; trap 'rm -f -- "$payload" "$token_tmp"' EXIT
jq -n --arg role_id "$(<"$RUNTIME_DIR/backup-openbao-role-id")" --arg secret_id "$(<"$RUNTIME_DIR/backup-openbao-secret-id")" '{role_id:$role_id,secret_id:$secret_id}' >"$payload"
curl -fsS -X POST --data-binary "@$payload" "$BAO_ADDR/auth/approle/login" | jq -er '.auth.client_token' >"$token_tmp"
chmod 0600 "$token_tmp"; mv -f "$token_tmp" "$RUNTIME_DIR/backup-openbao-token"
