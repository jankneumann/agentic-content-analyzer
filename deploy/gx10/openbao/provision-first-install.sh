#!/usr/bin/env bash
set -euo pipefail
umask 077

BAO_ADDR="${GX10_BAO_ADDR:-http://127.0.0.1:18200/v1}"
OPERATOR_DIR="${GX10_BAO_OPERATOR_DIR:-/etc/aca/gx10}"
SEED_FILE="${CREDENTIALS_DIRECTORY:?systemd credentials required}/bao-seed"
BOOTSTRAP_TOKEN_FILE="$OPERATOR_DIR/bao-bootstrap-token"
UNSEAL_KEY_FILE="$OPERATOR_DIR/bao-unseal-key"
RUNTIME_ENDPOINT="/secret/data/newsletter/gx10/runtime"
OPERATOR_ENDPOINT="/secret/data/newsletter/gx10/operator"
PROXY_ENDPOINT="/secret/data/newsletter/gx10/proxy"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf -- "$WORK_DIR"' EXIT

[[ -s "$SEED_FILE" ]] || { echo "gx10 OpenBao seed credential missing" >&2; exit 1; }
jq -e '
  (.runtime | type == "object") and
  (.operator | type == "object") and
  (.proxy | type == "object")
' "$SEED_FILE" >/dev/null || { echo "gx10 OpenBao seed credential is invalid" >&2; exit 1; }
install -d -m 0700 "$OPERATOR_DIR"

health=""
for _attempt in {1..60}; do
  if health="$(curl -sS --connect-timeout 2 --max-time 3 "$BAO_ADDR/sys/health?standbyok=true&perfstandbyok=true")"; then
    [[ -n "$health" ]] && break
  fi
  sleep 1
done
jq -e 'has("initialized") and has("sealed")' <<<"$health" >/dev/null || {
  echo "gx10 OpenBao is unreachable during first-install ceremony" >&2
  exit 1
}

if jq -e '.initialized == false' <<<"$health" >/dev/null; then
  init_payload="$WORK_DIR/init.json"
  init_response="$WORK_DIR/init-response.json"
  printf '{"secret_shares":1,"secret_threshold":1}\n' >"$init_payload"
  curl -fsS -X POST --data-binary "@$init_payload" "$BAO_ADDR/sys/init" >"$init_response"
  jq -er '.root_token' "$init_response" | install -m 0600 /dev/stdin "$BOOTSTRAP_TOKEN_FILE.new"
  jq -er '.keys_base64[]' "$init_response" | install -m 0600 /dev/stdin "$UNSEAL_KEY_FILE.new"
  mv -f "$BOOTSTRAP_TOKEN_FILE.new" "$BOOTSTRAP_TOKEN_FILE"
  mv -f "$UNSEAL_KEY_FILE.new" "$UNSEAL_KEY_FILE"
elif [[ ! -s "$BOOTSTRAP_TOKEN_FILE" || ! -s "$UNSEAL_KEY_FILE" ]]; then
  echo "gx10 initialized OpenBao requires protected operator recovery material" >&2
  exit 1
fi

health="$(curl -sS "$BAO_ADDR/sys/health?standbyok=true&perfstandbyok=true")"
if jq -e '.sealed == true' <<<"$health" >/dev/null; then
  while IFS= read -r key; do
    [[ -n "$key" ]] || continue
    jq -n --arg key "$key" '{key:$key}' >"$WORK_DIR/unseal.json"
    curl -fsS -X POST --data-binary "@$WORK_DIR/unseal.json" "$BAO_ADDR/sys/unseal" >/dev/null
  done <"$UNSEAL_KEY_FILE"
fi
health="$(curl -sS "$BAO_ADDR/sys/health?standbyok=true&perfstandbyok=true")"
jq -e '.initialized == true and .sealed == false' <<<"$health" >/dev/null || {
  echo "gx10 OpenBao first-install unseal failed" >&2
  exit 1
}

curl_config="$WORK_DIR/curl.conf"
printf 'header = "X-Vault-Token: %s"\n' "$(<"$BOOTSTRAP_TOKEN_FILE")" >"$curl_config"
chmod 0600 "$curl_config"

curl -fsS --config "$curl_config" "$BAO_ADDR/sys/mounts" >"$WORK_DIR/mounts.json"
if jq -e '.data["secret/"].type == "kv" and .data["secret/"].options.version == "2"' "$WORK_DIR/mounts.json" >/dev/null; then
  :
elif jq -e '.data["secret/"]' "$WORK_DIR/mounts.json" >/dev/null; then
  echo "gx10 secret/ exists but is not KV v2" >&2
  exit 1
else
  printf '{"type":"kv","options":{"version":"2"}}\n' >"$WORK_DIR/kv.json"
  curl -fsS --config "$curl_config" -X POST --data-binary "@$WORK_DIR/kv.json" "$BAO_ADDR/sys/mounts/secret" >/dev/null
fi

curl -fsS --config "$curl_config" "$BAO_ADDR/sys/auth" >"$WORK_DIR/auth.json"
if jq -e '.data["approle/"].type == "approle"' "$WORK_DIR/auth.json" >/dev/null; then
  :
elif jq -e '.data["approle/"]' "$WORK_DIR/auth.json" >/dev/null; then
  echo "gx10 approle/ exists with the wrong auth type" >&2
  exit 1
else
  printf '{"type":"approle"}\n' >"$WORK_DIR/approle.json"
  curl -fsS --config "$curl_config" -X POST --data-binary "@$WORK_DIR/approle.json" "$BAO_ADDR/sys/auth/approle" >/dev/null
fi

jq -n --rawfile policy "$(dirname "$0")/aca-gx10.hcl" '{policy:$policy}' >"$WORK_DIR/policy.json"
printf '{"token_policies":["aca-gx10"],"token_ttl":"15m","token_max_ttl":"1h","secret_id_ttl":"24h"}\n' >"$WORK_DIR/role.json"
curl -fsS --config "$curl_config" -X PUT --data-binary "@$WORK_DIR/policy.json" "$BAO_ADDR/sys/policies/acl/aca-gx10" >/dev/null
curl -fsS --config "$curl_config" -X POST --data-binary "@$WORK_DIR/role.json" "$BAO_ADDR/auth/approle/role/aca-gx10" >/dev/null

seed_path() {
  local key="$1" endpoint="$2" payload="$WORK_DIR/seed-$1.json"
  jq --arg key "$key" '{data: .[$key]}' "$SEED_FILE" >"$payload"
  curl -fsS --config "$curl_config" -X PUT --data-binary "@$payload" "$BAO_ADDR$endpoint" >/dev/null
}
seed_path runtime "$RUNTIME_ENDPOINT"
seed_path operator "$OPERATOR_ENDPOINT"
seed_path proxy "$PROXY_ENDPOINT"

printf 'provisioned_at=%(%s)T\n' -1 | install -m 0600 /dev/stdin "$OPERATOR_DIR/openbao-provisioned.ready.new"
mv -f "$OPERATOR_DIR/openbao-provisioned.ready.new" "$OPERATOR_DIR/openbao-provisioned.ready"
echo "gx10 OpenBao first-install operator ceremony completed" >&2
