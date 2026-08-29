#!/usr/bin/env bash
set -euo pipefail

# Runtime files are intentionally outside the repository and are atomically
# replaced with owner-only permissions after every independent secret rotation.
umask 077

RUNTIME_DIR="${GX10_RUNTIME_DIR:-/run/aca/gx10}"
RUNTIME_PATH="${GX10_BAO_RUNTIME_PATH:-secret/newsletter/gx10/runtime}"
OPERATOR_PATH="${GX10_BAO_OPERATOR_PATH:-secret/newsletter/gx10/operator}"
PROXY_PATH="${GX10_BAO_PROXY_PATH:-secret/newsletter/gx10/proxy}"

install -d -m 0700 "$RUNTIME_DIR" "$RUNTIME_DIR/proxy"
APP_TMP="$(mktemp "$RUNTIME_DIR/application.env.XXXXXX")"
PROXY_TMP="$(mktemp "$RUNTIME_DIR/proxy.env.XXXXXX")"
STATEFUL_TMP="$(mktemp "$RUNTIME_DIR/stateful.env.XXXXXX")"
LANGFUSE_TMP="$(mktemp "$RUNTIME_DIR/langfuse.env.XXXXXX")"
CADDY_TMP="$(mktemp "$RUNTIME_DIR/caddy.env.XXXXXX")"
PASSWD_TMP="$(mktemp "$RUNTIME_DIR/proxy/squid.passwd.XXXXXX")"

cleanup() {
  rm -f -- "$APP_TMP" "$PROXY_TMP" "$STATEFUL_TMP" "$LANGFUSE_TMP" "$CADDY_TMP" "$PASSWD_TMP"
}
trap cleanup EXIT

fetch() {
  local path="$1"
  local field="$2"
  bao kv get -field="$field" "$path"
}

fetch_safe() {
  local path="$1"
  local field="$2"
  local value
  value="$(fetch "$path" "$field")"
  if [[ -z "$value" || "$value" == *$'\n'* || "$value" == *$'\r'* ]]; then
    echo "gx10 secret field is missing or not env-file safe: $field" >&2
    exit 1
  fi
  printf '%s' "$value"
}

emit() {
  local target="$1"
  local key="$2"
  local path="$3"
  local field="$4"
  printf '%s=%s\n' "$key" "$(fetch_safe "$path" "$field")" >>"$target"
}

emit "$APP_TMP" DATABASE_URL "$RUNTIME_PATH" database_url
emit "$APP_TMP" APP_SECRET_KEY "$RUNTIME_PATH" app_secret_key
emit "$APP_TMP" CONFIGURED_SOURCE_KEY_SECRET "$RUNTIME_PATH" configured_source_key_secret
emit "$APP_TMP" OPERATION_CURSOR_SIGNING_KEY "$RUNTIME_PATH" operation_cursor_signing_key
emit "$APP_TMP" ADMIN_API_KEY "$RUNTIME_PATH" admin_api_key
emit "$APP_TMP" LANGFUSE_PUBLIC_KEY "$RUNTIME_PATH" langfuse_public_key
emit "$APP_TMP" LANGFUSE_SECRET_KEY "$RUNTIME_PATH" langfuse_secret_key
emit "$APP_TMP" NEO4J_PASSWORD "$RUNTIME_PATH" neo4j_password
emit "$APP_TMP" TELEMETRY_RELEASE_REVISION "$RUNTIME_PATH" release_revision
emit "$APP_TMP" GX10_AUTHORITY_FINGERPRINT "$RUNTIME_PATH" authority_fingerprint
emit "$APP_TMP" OPERATOR_API_KEY "$OPERATOR_PATH" operator_api_key

OPERATOR_ROTATION_GENERATION="$(fetch_safe "$OPERATOR_PATH" rotation_generation)"
PROXY_ROTATION_GENERATION="$(fetch_safe "$PROXY_PATH" rotation_generation)"
for generation in "$OPERATOR_ROTATION_GENERATION" "$PROXY_ROTATION_GENERATION"; do
  [[ "$generation" =~ ^[1-9][0-9]*$ ]] || {
    echo "gx10 operator or proxy ROTATION_GENERATION is invalid" >&2
    exit 1
  }
done
printf 'GX10_OPERATOR_ROTATION_GENERATION=%s\n' "$OPERATOR_ROTATION_GENERATION" >>"$APP_TMP"
printf 'GX10_ROTATION_GENERATION=%s\n' "$PROXY_ROTATION_GENERATION" >>"$APP_TMP"

PROXY_USERNAME="$(fetch_safe "$PROXY_PATH" username)"
PROXY_PASSWORD="$(fetch_safe "$PROXY_PATH" password)"
if [[ ! "$PROXY_USERNAME" =~ ^[A-Za-z0-9._~-]+$ || ! "$PROXY_PASSWORD" =~ ^[A-Za-z0-9._~-]{32,}$ ]]; then
  echo "gx10 proxy credentials are not URL-safe or sufficiently long" >&2
  exit 1
fi
printf 'GX10_PROXY_USERNAME=%s\nGX10_PROXY_PASSWORD=%s\n' "$PROXY_USERNAME" "$PROXY_PASSWORD" >>"$PROXY_TMP"
printf 'HTTP_PROXY=http://%s:%s@squid:3128\n' "$PROXY_USERNAME" "$PROXY_PASSWORD" >>"$PROXY_TMP"
printf 'HTTPS_PROXY=http://%s:%s@squid:3128\n' "$PROXY_USERNAME" "$PROXY_PASSWORD" >>"$PROXY_TMP"
printf 'ALL_PROXY=http://%s:%s@squid:3128\n' "$PROXY_USERNAME" "$PROXY_PASSWORD" >>"$PROXY_TMP"
printf '%s:%s\n' "$PROXY_USERNAME" "$(openssl passwd -apr1 "$PROXY_PASSWORD")" >"$PASSWD_TMP"

APP_POSTGRES_PASSWORD="$(fetch_safe "$RUNTIME_PATH" app_postgres_password)"
LANGFUSE_POSTGRES_PASSWORD="$(fetch_safe "$RUNTIME_PATH" langfuse_postgres_password)"
REDIS_PASSWORD="$(fetch_safe "$RUNTIME_PATH" redis_password)"
NEO4J_PASSWORD="$(fetch_safe "$RUNTIME_PATH" neo4j_password)"
CLICKHOUSE_PASSWORD="$(fetch_safe "$RUNTIME_PATH" clickhouse_password)"
MINIO_ROOT_USER="$(fetch_safe "$RUNTIME_PATH" minio_root_user)"
MINIO_ROOT_PASSWORD="$(fetch_safe "$RUNTIME_PATH" minio_root_password)"
printf 'POSTGRES_PASSWORD=%s\n' "$APP_POSTGRES_PASSWORD" >>"$STATEFUL_TMP"
printf 'LANGFUSE_POSTGRES_PASSWORD=%s\n' "$LANGFUSE_POSTGRES_PASSWORD" >>"$STATEFUL_TMP"
printf 'REDIS_PASSWORD=%s\n' "$REDIS_PASSWORD" >>"$STATEFUL_TMP"
printf 'NEO4J_AUTH=neo4j/%s\n' "$NEO4J_PASSWORD" >>"$STATEFUL_TMP"
printf 'CLICKHOUSE_PASSWORD=%s\n' "$CLICKHOUSE_PASSWORD" >>"$STATEFUL_TMP"
printf 'MINIO_ROOT_USER=%s\nMINIO_ROOT_PASSWORD=%s\n' "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >>"$STATEFUL_TMP"

# Langfuse receives no checked-in credentials; every secret is rendered here.
printf 'DATABASE_URL=postgresql://langfuse:%s@langfuse-postgres:5432/langfuse\n' "$LANGFUSE_POSTGRES_PASSWORD" >>"$LANGFUSE_TMP"
printf 'NEXTAUTH_URL=https://gx10.local/observability\n' >>"$LANGFUSE_TMP"
emit "$LANGFUSE_TMP" NEXTAUTH_SECRET "$RUNTIME_PATH" langfuse_nextauth_secret
emit "$LANGFUSE_TMP" SALT "$RUNTIME_PATH" langfuse_salt
emit "$LANGFUSE_TMP" ENCRYPTION_KEY "$RUNTIME_PATH" langfuse_encryption_key
printf 'CLICKHOUSE_URL=http://clickhouse:8123\nCLICKHOUSE_MIGRATION_URL=clickhouse://clickhouse:9000\n' >>"$LANGFUSE_TMP"
printf 'CLICKHOUSE_USER=langfuse\nCLICKHOUSE_PASSWORD=%s\n' "$CLICKHOUSE_PASSWORD" >>"$LANGFUSE_TMP"
printf 'REDIS_HOST=redis\nREDIS_PORT=6379\nREDIS_AUTH=%s\n' "$REDIS_PASSWORD" >>"$LANGFUSE_TMP"
printf 'LANGFUSE_S3_EVENT_UPLOAD_ENABLED=true\nLANGFUSE_S3_EVENT_UPLOAD_ENDPOINT=http://minio:9000\n' >>"$LANGFUSE_TMP"
printf 'LANGFUSE_S3_EVENT_UPLOAD_BUCKET=langfuse-events\nLANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID=%s\n' "$MINIO_ROOT_USER" >>"$LANGFUSE_TMP"
printf 'LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY=%s\nLANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE=true\n' "$MINIO_ROOT_PASSWORD" >>"$LANGFUSE_TMP"
printf 'LANGFUSE_S3_EVENT_UPLOAD_REGION=us-east-1\n' >>"$LANGFUSE_TMP"

emit "$CADDY_TMP" CADDY_USERNAME "$RUNTIME_PATH" caddy_username
emit "$CADDY_TMP" CADDY_PASSWORD_HASH "$RUNTIME_PATH" caddy_password_hash

for pair in \
  "$APP_TMP:application.env" \
  "$PROXY_TMP:proxy.env" \
  "$STATEFUL_TMP:stateful.env" \
  "$LANGFUSE_TMP:langfuse.env" \
  "$CADDY_TMP:caddy.env"; do
  source_file="${pair%%:*}"
  destination="${pair#*:}"
  install -m 0600 "$source_file" "$RUNTIME_DIR/$destination.new"
  mv -f "$RUNTIME_DIR/$destination.new" "$RUNTIME_DIR/$destination"
done
install -m 0600 "$PASSWD_TMP" "$RUNTIME_DIR/proxy/squid.passwd.new"
mv -f "$RUNTIME_DIR/proxy/squid.passwd.new" "$RUNTIME_DIR/proxy/squid.passwd"

# Only independent, non-secret rotation metadata is logged.
echo "gx10 runtime secrets rotated operator_generation=$OPERATOR_ROTATION_GENERATION proxy_generation=$PROXY_ROTATION_GENERATION" >&2
