#!/usr/bin/env bash
set -euo pipefail
umask 077
BAO_ADDR="${GX10_BAO_ADDR:-http://10.89.0.250:8200/v1}"; RUNTIME_DIR="${GX10_RUNTIME_DIR:-/run/aca/gx10}"
BOOTSTRAP_TOKEN_FILE="${CREDENTIALS_DIRECTORY:?systemd credentials required}/bao-bootstrap-token"
[[ -s "$BOOTSTRAP_TOKEN_FILE" ]] || { echo "OpenBao bootstrap credential missing" >&2; exit 1; }
health="$(curl -fsS "$BAO_ADDR/sys/health?standbyok=true&perfstandbyok=true")"
jq -e '.initialized == true and .sealed == false' <<<"$health" >/dev/null || { echo "OpenBao is uninitialized or sealed" >&2; exit 1; }
config="$(mktemp)"; trap 'rm -f -- "$config"' EXIT; chmod 0600 "$config"; printf 'header = "X-Vault-Token: %s"\n' "$(<"$BOOTSTRAP_TOKEN_FILE")" >"$config"
policy_payload="$(mktemp)"; role_payload="$(mktemp)"; trap 'rm -f -- "$config" "$policy_payload" "$role_payload"' EXIT
jq -n --rawfile policy "$(dirname "$0")/aca-gx10.hcl" '{policy:$policy}' >"$policy_payload"
printf '{"token_policies":["aca-gx10"],"token_ttl":"15m","token_max_ttl":"1h","secret_id_ttl":"24h"}\n' >"$role_payload"
curl -fsS --config "$config" -X PUT --data-binary "@$policy_payload" "$BAO_ADDR/sys/policies/acl/aca-gx10" >/dev/null
curl -fsS --config "$config" -X POST --data-binary "@$role_payload" "$BAO_ADDR/auth/approle/role/aca-gx10" >/dev/null
install -d -m 0700 "$RUNTIME_DIR"
curl -fsS --config "$config" "$BAO_ADDR/auth/approle/role/aca-gx10/role-id" | jq -er '.data.role_id' | install -m 0600 /dev/stdin "$RUNTIME_DIR/openbao-role-id"
curl -fsS --config "$config" -X POST "$BAO_ADDR/auth/approle/role/aca-gx10/secret-id" | jq -er '.data.secret_id' | install -m 0600 /dev/stdin "$RUNTIME_DIR/openbao-secret-id"
