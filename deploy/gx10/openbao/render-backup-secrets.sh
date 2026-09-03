#!/usr/bin/env bash
set -euo pipefail
umask 077
RUNTIME_DIR="${GX10_RUNTIME_DIR:-/run/aca/gx10}/backup"
BAO_ADDR="${GX10_BAO_ADDR:-http://10.89.0.250:8200/v1}"
BACKUP_PATH="${GX10_BAO_BACKUP_PATH:-secret/newsletter/gx10/backup}"
TOKEN_FILE="$RUNTIME_DIR/backup-openbao-token"
[[ -s "$TOKEN_FILE" ]] || { echo "backup OpenBao token unavailable" >&2; exit 1; }
config="$(mktemp)"; response="$(mktemp)"; trap 'rm -f -- "$config" "$response"' EXIT
printf 'header = "X-Vault-Token: %s"\n' "$(<"$TOKEN_FILE")" >"$config"; chmod 0600 "$config"
endpoint="${BAO_ADDR%/}/${BACKUP_PATH/secret\//secret/data/}"
curl -fsS --config "$config" "$endpoint" >"$response"
jq -e '.data.data as $d | ($d.backup_age_recipient | type == "string" and test("^age1[0-9a-z]{20,100}$")) and ($d.backup_age_retained_recipients | type == "array" and all(type == "string" and test("^age1[0-9a-z]{20,100}$"))) and ($d.backup_age_identities | type == "object") and ([ $d.backup_age_recipient ] + $d.backup_age_retained_recipients | all(. as $r | $d.backup_age_identities[$r] | type == "string" and startswith("AGE-SECRET-KEY-")))' "$response" >/dev/null || { echo "backup age material missing, rotated, or invalid" >&2; exit 1; }
backup_tmp="$(mktemp "$RUNTIME_DIR/backup-age.json.XXXXXX")"; restore_tmp="$(mktemp "$RUNTIME_DIR/restore-age.json.XXXXXX")"; trap 'rm -f -- "$config" "$response" "$backup_tmp" "$restore_tmp"' EXIT
jq '{active_recipient:.data.data.backup_age_recipient,retained_recipients:.data.data.backup_age_retained_recipients,identities:{}}' "$response" >"$backup_tmp"
jq '{active_recipient:.data.data.backup_age_recipient,retained_recipients:.data.data.backup_age_retained_recipients,identities:.data.data.backup_age_identities}' "$response" >"$restore_tmp"
install -m 0600 "$backup_tmp" "$RUNTIME_DIR/backup-age.json.new"; mv -f "$RUNTIME_DIR/backup-age.json.new" "$RUNTIME_DIR/backup-age.json"
install -m 0600 "$restore_tmp" "$RUNTIME_DIR/restore-age.json.new"; mv -f "$RUNTIME_DIR/restore-age.json.new" "$RUNTIME_DIR/restore-age.json"
