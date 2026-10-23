#!/usr/bin/env bash
# One-time operator step: store the off-site bucket credentials and re-upload
# the backup policy that grants the off-site renderer read access to them.
#
# The provisioning ceremony writes policies once, so a policy edit after first
# install reaches OpenBao only through a step like this one.
#
# Values are read from the terminal, never argv: argv is world-readable in
# /proc and lands in shell history. jq takes them from its environment.
#
#   sudo /opt/aca/deploy/gx10/openbao/seed-offsite-secret.sh
set -euo pipefail
umask 077
BAO_ADDR="${GX10_BAO_ADDR:-http://10.89.0.250:8200/v1}"
TOKEN_FILE="${GX10_BAO_TOKEN_FILE:-/etc/aca/gx10/bao-bootstrap-token}"
OFFSITE_ENDPOINT="/secret/data/newsletter/gx10/backup-offsite"
POLICY_FILE="$(dirname "$0")/aca-gx10-backup.hcl"
[[ -s "$TOKEN_FILE" ]] || { echo "OpenBao admin token unavailable at $TOKEN_FILE" >&2; exit 1; }

read -rp "R2 account id: " account_id
read -rp "Bucket [aca-gx10-backups]: " bucket
read -rp "Access Key ID: " access_key_id
read -rsp "Secret Access Key (hidden): " secret_access_key; echo
[[ "$account_id" =~ ^[0-9a-f]{32}$ ]] || { echo "account id must be 32 hex characters" >&2; exit 1; }
[[ -n "$access_key_id" && -n "$secret_access_key" ]] || { echo "both keys are required" >&2; exit 1; }

work="$(mktemp -d)"; trap 'rm -rf -- "$work"' EXIT
printf 'header = "X-Vault-Token: %s"\n' "$(<"$TOKEN_FILE")" >"$work/curl"
ENDPOINT="https://$account_id.r2.cloudflarestorage.com" BUCKET="${bucket:-aca-gx10-backups}" \
  KEY_ID="$access_key_id" KEY_SECRET="$secret_access_key" \
  jq -n '{data: {endpoint: env.ENDPOINT, bucket: env.BUCKET, access_key_id: env.KEY_ID,
                 secret_access_key: env.KEY_SECRET, prefix: "aca", region: "auto"}}' >"$work/secret.json"
curl -fsS --config "$work/curl" -X POST --data-binary "@$work/secret.json" "$BAO_ADDR$OFFSITE_ENDPOINT" >/dev/null
jq -n --rawfile policy "$POLICY_FILE" '{policy:$policy}' >"$work/policy.json"
curl -fsS --config "$work/curl" -X PUT --data-binary "@$work/policy.json" "$BAO_ADDR/sys/policies/acl/aca-gx10-backup" >/dev/null
echo "stored off-site credentials and re-uploaded the aca-gx10-backup policy"
