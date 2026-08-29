#!/usr/bin/env bash
set -euo pipefail
umask 077
RUNTIME_DIR="${GX10_RUNTIME_DIR:-/run/aca/gx10}"
BAO_ADDR="${GX10_BAO_ADDR:-http://127.0.0.1:18200/v1}"
BOOTSTRAP_TOKEN_FILE="${CREDENTIALS_DIRECTORY:?systemd credentials required}/bao-bootstrap-token"
[[ -s "$BOOTSTRAP_TOKEN_FILE" ]] || { echo "OpenBao bootstrap credential missing" >&2; exit 1; }
config="$(mktemp)"; trap 'rm -f -- "$config"' EXIT
printf 'header = "X-Vault-Token: %s"\n' "$(<"$BOOTSTRAP_TOKEN_FILE")" >"$config"; chmod 0600 "$config"
install -d -m 0700 "$RUNTIME_DIR/backup"
curl -fsS --config "$config" "$BAO_ADDR/auth/approle/role/aca-gx10-backup/role-id" | jq -er '.data.role_id' | install -m 0600 /dev/stdin "$RUNTIME_DIR/backup/backup-openbao-role-id"
curl -fsS --config "$config" -X POST "$BAO_ADDR/auth/approle/role/aca-gx10-backup/secret-id" | jq -er '.data.secret_id' | install -m 0600 /dev/stdin "$RUNTIME_DIR/backup/backup-openbao-secret-id"
