#!/usr/bin/env bash
# Render the off-site bucket credentials for exactly one off-site run.
#
# Separate from render-backup-secrets.sh so the local backup never fails on a
# missing off-site secret, and so the process holding the age material never
# sees the bucket keys. The off-site unit removes the file when it stops.
set -euo pipefail
umask 077
RUNTIME_DIR="${GX10_RUNTIME_DIR:-/run/aca/gx10}/backup"
BAO_ADDR="${GX10_BAO_ADDR:-http://10.89.0.250:8200/v1}"
OFFSITE_PATH="${GX10_BAO_OFFSITE_PATH:-secret/newsletter/gx10/backup-offsite}"
TOKEN_FILE="$RUNTIME_DIR/backup-openbao-token"
[[ -s "$TOKEN_FILE" ]] || { echo "backup OpenBao token unavailable" >&2; exit 1; }
config="$(mktemp)"; response="$(mktemp)"; trap 'rm -f -- "$config" "$response"' EXIT
printf 'header = "X-Vault-Token: %s"\n' "$(<"$TOKEN_FILE")" >"$config"; chmod 0600 "$config"
endpoint="${BAO_ADDR%/}/${OFFSITE_PATH/secret\//secret/data/}"
curl -fsS --config "$config" "$endpoint" >"$response" || { echo "off-site backup secret unreadable at $OFFSITE_PATH" >&2; exit 1; }
jq -e '.data.data as $d | ($d.endpoint | type == "string" and startswith("https://")) and ($d.bucket | type == "string" and length > 0) and ($d.access_key_id | type == "string" and length > 0) and ($d.secret_access_key | type == "string" and length > 0)' "$response" >/dev/null || { echo "off-site backup secret missing endpoint, bucket, or key pair" >&2; exit 1; }
tmp="$(mktemp "$RUNTIME_DIR/offsite.json.XXXXXX")"; trap 'rm -f -- "$config" "$response" "$tmp"' EXIT
jq '.data.data | {endpoint, bucket, access_key_id, secret_access_key, prefix: (.prefix // "aca"), region: (.region // "auto")}' "$response" >"$tmp"
install -m 0600 "$tmp" "$RUNTIME_DIR/offsite.json.new"; mv -f "$RUNTIME_DIR/offsite.json.new" "$RUNTIME_DIR/offsite.json"
