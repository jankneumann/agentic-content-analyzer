#!/usr/bin/env bash
set -euo pipefail
umask 077

RUNTIME_DIR="${GX10_RUNTIME_DIR:-/run/aca/gx10}"
RUNTIME_PATH="${GX10_BAO_RUNTIME_PATH:-secret/newsletter/gx10/runtime}"
OPERATOR_PATH="${GX10_BAO_OPERATOR_PATH:-secret/newsletter/gx10/operator}"
PROXY_PATH="${GX10_BAO_PROXY_PATH:-secret/newsletter/gx10/proxy}"
BAO_ADDR="${GX10_BAO_ADDR:-http://10.89.0.250:8200/v1}"
BAO_TOKEN_FILE="${GX10_BAO_TOKEN_FILE:-$RUNTIME_DIR/openbao-token}"

[[ -s "$BAO_TOKEN_FILE" ]] || { echo "gx10 OpenBao token is unavailable" >&2; exit 1; }
PUBLIC_LANGFUSE_URL="${GX10_PUBLIC_LANGFUSE_URL:-https://gx10.local/langfuse}"
PUBLIC_ORIGIN="${GX10_PUBLIC_ORIGIN:-${PUBLIC_LANGFUSE_URL%/langfuse}}"
[[ "$PUBLIC_ORIGIN" =~ ^https://[A-Za-z0-9.-]+(:[0-9]{1,5})?$ ]] || { echo "gx10 public origin is invalid" >&2; exit 1; }
[[ "$PUBLIC_LANGFUSE_URL" == "$PUBLIC_ORIGIN/langfuse" ]] || { echo "gx10 public Langfuse URL must be the public origin plus /langfuse" >&2; exit 1; }
install -d -m 0700 "$RUNTIME_DIR" "$RUNTIME_DIR/proxy" "$RUNTIME_DIR/redis" "$RUNTIME_DIR/falkordb"
CURL_CONFIG="$(mktemp "$RUNTIME_DIR/bao-curl.XXXXXX")"
printf 'header = "X-Vault-Token: %s"\n' "$(<"$BAO_TOKEN_FILE")" >"$CURL_CONFIG"
chmod 0600 "$CURL_CONFIG"

declare -a TEMPS=()
new_env() { local name="$1"; local path; path="$(mktemp "$RUNTIME_DIR/$name.XXXXXX")"; TEMPS+=("$path"); printf '%s' "$path"; }
COMMON_TMP="$(new_env common.env)"; API_TMP="$(new_env api.env)"; WORKER_TMP="$(new_env worker.env)"
SCHEDULER_TMP="$(new_env scheduler.env)"; MAINTENANCE_TMP="$(new_env maintenance.env)"
PROXY_TMP="$(new_env proxy.env)"; APP_POSTGRES_TMP="$(new_env app-postgres.env)"
LANGFUSE_POSTGRES_TMP="$(new_env langfuse-postgres.env)"; REDIS_TMP="$(new_env redis.env)"
FALKORDB_TMP="$(new_env falkordb.env)"; CLICKHOUSE_TMP="$(new_env clickhouse.env)"
MINIO_TMP="$(new_env minio.env)"; LANGFUSE_TMP="$(new_env langfuse.env)"; CADDY_TMP="$(new_env caddy.env)"
PASSWD_TMP="$(mktemp "$RUNTIME_DIR/proxy/squid.passwd.XXXXXX")"; TEMPS+=("$PASSWD_TMP")
REDIS_ACL_TMP="$(mktemp "$RUNTIME_DIR/redis/users.acl.XXXXXX")"; TEMPS+=("$REDIS_ACL_TMP")
FALKORDB_ACL_TMP="$(mktemp "$RUNTIME_DIR/falkordb/users.acl.XXXXXX")"; TEMPS+=("$FALKORDB_ACL_TMP")
cleanup() { rm -f -- "$CURL_CONFIG" "${TEMPS[@]}"; }
trap cleanup EXIT

kv_endpoint() { printf '%s/%s' "${BAO_ADDR%/}" "${1/secret\//secret/data/}"; }
fetch() {
  local path="$1" field="$2" value
  value="$(curl --silent --show-error --fail --config "$CURL_CONFIG" "$(kv_endpoint "$path")" | jq -er --arg field "$field" '.data.data[$field]')"
  [[ -n "$value" && "$value" != *$'\n'* && "$value" != *$'\r'* ]] || { echo "gx10 secret field is missing or unsafe: $field" >&2; exit 1; }
  printf '%s' "$value"
}
emit() { printf '%s=%s\n' "$2" "$(fetch "$3" "$4")" >>"$1"; }

emit "$COMMON_TMP" GX10_APP_DATABASE_URL "$RUNTIME_PATH" database_url
emit "$COMMON_TMP" GX10_APP_SECRET_KEY "$RUNTIME_PATH" app_secret_key
emit "$COMMON_TMP" GX10_CONFIGURED_SOURCE_KEY_SECRET "$RUNTIME_PATH" configured_source_key_secret
emit "$COMMON_TMP" GX10_OPERATION_CURSOR_SIGNING_KEY "$RUNTIME_PATH" operation_cursor_signing_key
emit "$COMMON_TMP" GX10_LANGFUSE_PUBLIC_KEY "$RUNTIME_PATH" langfuse_public_key
emit "$COMMON_TMP" GX10_LANGFUSE_SECRET_KEY "$RUNTIME_PATH" langfuse_secret_key
emit "$COMMON_TMP" GX10_FALKORDB_PASSWORD "$RUNTIME_PATH" falkordb_password
emit "$COMMON_TMP" GX10_RELEASE_REVISION "$RUNTIME_PATH" release_revision
emit "$COMMON_TMP" GX10_AUTHORITY_FINGERPRINT "$RUNTIME_PATH" authority_fingerprint
printf 'GX10_PUBLIC_ORIGIN=%s\nGX10_PUBLIC_LANGFUSE_URL=%s\n' "$PUBLIC_ORIGIN" "$PUBLIC_LANGFUSE_URL" >>"$COMMON_TMP"
emit "$API_TMP" GX10_ADMIN_API_KEY "$RUNTIME_PATH" admin_api_key
emit "$API_TMP" GX10_OPERATOR_API_KEY "$OPERATOR_PATH" operator_api_key

OPERATOR_GENERATION="$(fetch "$OPERATOR_PATH" rotation_generation)"; PROXY_GENERATION="$(fetch "$PROXY_PATH" rotation_generation)"
for generation in "$OPERATOR_GENERATION" "$PROXY_GENERATION"; do [[ "$generation" =~ ^[1-9][0-9]*$ ]] || { echo "gx10 rotation generation invalid" >&2; exit 1; }; done
printf 'GX10_OPERATOR_ROTATION_GENERATION=%s\nGX10_PROCESS_ROLE=api\nOTEL_SERVICE_NAME=aca-gx10-api\nTELEMETRY_SERVICE_INSTANCE_ID=aca-gx10-api\n' "$OPERATOR_GENERATION" >>"$API_TMP"
printf 'GX10_PROCESS_ROLE=worker\nOTEL_SERVICE_NAME=aca-gx10-worker\nTELEMETRY_SERVICE_INSTANCE_ID=aca-gx10-worker\n' >>"$WORKER_TMP"
printf 'GX10_PROCESS_ROLE=scheduler\nOTEL_SERVICE_NAME=aca-gx10-scheduler\nTELEMETRY_SERVICE_INSTANCE_ID=aca-gx10-scheduler\n' >>"$SCHEDULER_TMP"
printf 'GX10_PROCESS_ROLE=maintenance\nOTEL_SERVICE_NAME=aca-gx10-maintenance\nTELEMETRY_SERVICE_INSTANCE_ID=aca-gx10-maintenance\n' >>"$MAINTENANCE_TMP"
printf 'GX10_ROTATION_GENERATION=%s\n' "$PROXY_GENERATION" >>"$COMMON_TMP"

PROXY_USERNAME="$(fetch "$PROXY_PATH" username)"; PROXY_PASSWORD="$(fetch "$PROXY_PATH" password)"
[[ "$PROXY_USERNAME" =~ ^[A-Za-z0-9._~-]+$ && "$PROXY_PASSWORD" =~ ^[A-Za-z0-9._~-]{32,}$ ]] || { echo "gx10 proxy credentials invalid" >&2; exit 1; }
printf 'GX10_PROXY_USERNAME=%s\nGX10_PROXY_PASSWORD=%s\n' "$PROXY_USERNAME" "$PROXY_PASSWORD" >>"$PROXY_TMP"
printf 'HTTP_PROXY=http://%s:%s@squid:3128\nHTTPS_PROXY=http://%s:%s@squid:3128\nALL_PROXY=http://%s:%s@squid:3128\n' "$PROXY_USERNAME" "$PROXY_PASSWORD" "$PROXY_USERNAME" "$PROXY_PASSWORD" "$PROXY_USERNAME" "$PROXY_PASSWORD" >>"$PROXY_TMP"
PROXY_HASH="$(printf '%s\n' "$PROXY_PASSWORD" | openssl passwd -apr1 -stdin)"
printf '%s:%s\n' "$PROXY_USERNAME" "$PROXY_HASH" >"$PASSWD_TMP"

APP_DB="$(fetch "$RUNTIME_PATH" app_postgres_password)"; LF_DB="$(fetch "$RUNTIME_PATH" langfuse_postgres_password)"
REDIS="$(fetch "$RUNTIME_PATH" redis_password)"; FALKORDB="$(fetch "$RUNTIME_PATH" falkordb_password)"
CLICKHOUSE="$(fetch "$RUNTIME_PATH" clickhouse_password)"; MINIO_USER="$(fetch "$RUNTIME_PATH" minio_root_user)"; MINIO_PASSWORD="$(fetch "$RUNTIME_PATH" minio_root_password)"
printf 'POSTGRES_PASSWORD=%s\n' "$APP_DB" >"$APP_POSTGRES_TMP"; printf 'POSTGRES_PASSWORD=%s\n' "$LF_DB" >"$LANGFUSE_POSTGRES_TMP"
[[ "$REDIS" =~ ^[A-Za-z0-9._~-]{32,}$ ]] || { echo "gx10 Redis credential is unsafe for ACL configuration" >&2; exit 1; }
printf 'REDISCLI_AUTH=%s\n' "$REDIS" >"$REDIS_TMP"
printf 'user default on >%s ~* +@all\n' "$REDIS" >"$REDIS_ACL_TMP"
printf 'REDISCLI_AUTH=%s\n' "$FALKORDB" >"$FALKORDB_TMP"
printf 'user default on >%s ~* +@all\n' "$FALKORDB" >"$FALKORDB_ACL_TMP"
printf 'CLICKHOUSE_PASSWORD=%s\n' "$CLICKHOUSE" >"$CLICKHOUSE_TMP"; printf 'MINIO_ROOT_USER=%s\nMINIO_ROOT_PASSWORD=%s\n' "$MINIO_USER" "$MINIO_PASSWORD" >"$MINIO_TMP"
printf 'DATABASE_URL=postgresql://langfuse:%s@langfuse-postgres:5432/langfuse\nNEXTAUTH_URL=%s\n' "$LF_DB" "$PUBLIC_LANGFUSE_URL" >"$LANGFUSE_TMP"
emit "$LANGFUSE_TMP" NEXTAUTH_SECRET "$RUNTIME_PATH" langfuse_nextauth_secret; emit "$LANGFUSE_TMP" SALT "$RUNTIME_PATH" langfuse_salt; emit "$LANGFUSE_TMP" ENCRYPTION_KEY "$RUNTIME_PATH" langfuse_encryption_key
emit "$LANGFUSE_TMP" LANGFUSE_INIT_ORG_ID "$RUNTIME_PATH" langfuse_init_org_id
emit "$LANGFUSE_TMP" LANGFUSE_INIT_ORG_NAME "$RUNTIME_PATH" langfuse_init_org_name
emit "$LANGFUSE_TMP" LANGFUSE_INIT_PROJECT_ID "$RUNTIME_PATH" langfuse_init_project_id
emit "$LANGFUSE_TMP" LANGFUSE_INIT_PROJECT_NAME "$RUNTIME_PATH" langfuse_init_project_name
emit "$LANGFUSE_TMP" LANGFUSE_INIT_PROJECT_PUBLIC_KEY "$RUNTIME_PATH" langfuse_public_key
emit "$LANGFUSE_TMP" LANGFUSE_INIT_PROJECT_SECRET_KEY "$RUNTIME_PATH" langfuse_secret_key
emit "$LANGFUSE_TMP" LANGFUSE_INIT_USER_EMAIL "$RUNTIME_PATH" langfuse_init_user_email
emit "$LANGFUSE_TMP" LANGFUSE_INIT_USER_NAME "$RUNTIME_PATH" langfuse_init_user_name
emit "$LANGFUSE_TMP" LANGFUSE_INIT_USER_PASSWORD "$RUNTIME_PATH" langfuse_init_user_password
printf 'CLICKHOUSE_URL=http://clickhouse:8123\nCLICKHOUSE_MIGRATION_URL=clickhouse://clickhouse:9000\nCLICKHOUSE_USER=langfuse\nCLICKHOUSE_PASSWORD=%s\nREDIS_HOST=redis\nREDIS_PORT=6379\nREDIS_AUTH=%s\nLANGFUSE_S3_EVENT_UPLOAD_ENABLED=true\nLANGFUSE_S3_EVENT_UPLOAD_ENDPOINT=http://minio:9000\nLANGFUSE_S3_EVENT_UPLOAD_BUCKET=langfuse-events\nLANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID=%s\nLANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY=%s\nLANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE=true\nLANGFUSE_S3_EVENT_UPLOAD_REGION=us-east-1\n' "$CLICKHOUSE" "$REDIS" "$MINIO_USER" "$MINIO_PASSWORD" >>"$LANGFUSE_TMP"
emit "$CADDY_TMP" CADDY_USERNAME "$RUNTIME_PATH" caddy_username; emit "$CADDY_TMP" CADDY_PASSWORD_HASH "$RUNTIME_PATH" caddy_password_hash
printf 'GX10_PUBLIC_ORIGIN=%s\n' "$PUBLIC_ORIGIN" >>"$CADDY_TMP"

for pair in "$COMMON_TMP:common.env" "$API_TMP:api.env" "$WORKER_TMP:worker.env" "$SCHEDULER_TMP:scheduler.env" "$MAINTENANCE_TMP:maintenance.env" "$PROXY_TMP:proxy.env" "$APP_POSTGRES_TMP:app-postgres.env" "$LANGFUSE_POSTGRES_TMP:langfuse-postgres.env" "$REDIS_TMP:redis.env" "$FALKORDB_TMP:falkordb.env" "$CLICKHOUSE_TMP:clickhouse.env" "$MINIO_TMP:minio.env" "$LANGFUSE_TMP:langfuse.env" "$CADDY_TMP:caddy.env"; do source_file="${pair%%:*}"; destination="${pair#*:}"; install -m 0600 "$source_file" "$RUNTIME_DIR/$destination.new"; mv -f "$RUNTIME_DIR/$destination.new" "$RUNTIME_DIR/$destination"; done
# Files the containers read directly are owned by the image user that reads
# them (squid proxy 13:13, redis 999:1000, falkordb 999:999); mode stays 0600. Only root can
# assign ownership; unprivileged test runs keep the invoking user.
if [[ "$(id -u)" == 0 ]]; then PASSWD_OWNER=(-o 13 -g 13); REDIS_ACL_OWNER=(-o 999 -g 1000); FALKORDB_ACL_OWNER=(-o 999 -g 999); else PASSWD_OWNER=(); REDIS_ACL_OWNER=(); FALKORDB_ACL_OWNER=(); fi
install "${PASSWD_OWNER[@]}" -m 0600 "$PASSWD_TMP" "$RUNTIME_DIR/proxy/squid.passwd.new"; mv -f "$RUNTIME_DIR/proxy/squid.passwd.new" "$RUNTIME_DIR/proxy/squid.passwd"
install "${REDIS_ACL_OWNER[@]}" -m 0600 "$REDIS_ACL_TMP" "$RUNTIME_DIR/redis/users.acl.new"; mv -f "$RUNTIME_DIR/redis/users.acl.new" "$RUNTIME_DIR/redis/users.acl"
install "${FALKORDB_ACL_OWNER[@]}" -m 0600 "$FALKORDB_ACL_TMP" "$RUNTIME_DIR/falkordb/users.acl.new"; mv -f "$RUNTIME_DIR/falkordb/users.acl.new" "$RUNTIME_DIR/falkordb/users.acl"
echo "gx10 secrets rotated operator_generation=$OPERATOR_GENERATION proxy_generation=$PROXY_GENERATION" >&2
