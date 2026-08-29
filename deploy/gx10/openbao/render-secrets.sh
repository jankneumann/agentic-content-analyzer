#!/usr/bin/env bash
set -euo pipefail

# Runtime files are intentionally outside the repository and are atomically
# replaced with owner-only permissions after every independent secret rotation.
umask 077

RUNTIME_DIR="${GX10_RUNTIME_DIR:-/run/aca/gx10}"
RUNTIME_PATH="${GX10_BAO_RUNTIME_PATH:-secret/newsletter/gx10/runtime}"
OPERATOR_PATH="${GX10_BAO_OPERATOR_PATH:-secret/newsletter/gx10/operator}"
PROXY_PATH="${GX10_BAO_PROXY_PATH:-secret/newsletter/gx10/proxy}"

install -d -m 0700 "$RUNTIME_DIR"
APP_TMP="$(mktemp "$RUNTIME_DIR/application.env.XXXXXX")"
PROXY_TMP="$(mktemp "$RUNTIME_DIR/proxy.env.XXXXXX")"

cleanup() {
  rm -f -- "$APP_TMP" "$PROXY_TMP"
}
trap cleanup EXIT

fetch() {
  local path="$1"
  local field="$2"
  bao kv get -field="$field" "$path"
}

emit() {
  local target="$1"
  local key="$2"
  local path="$3"
  local field="$4"
  local value
  value="$(fetch "$path" "$field")"
  if [[ -z "$value" || "$value" == *$'\n'* || "$value" == *$'\r'* ]]; then
    echo "gx10 secret field is missing or not env-file safe: $field" >&2
    exit 1
  fi
  printf '%s=%s\n' "$key" "$value" >>"$target"
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

emit "$PROXY_TMP" GX10_PROXY_USERNAME "$PROXY_PATH" username
emit "$PROXY_TMP" GX10_PROXY_PASSWORD "$PROXY_PATH" password
emit "$PROXY_TMP" ROTATION_GENERATION "$PROXY_PATH" rotation_generation

ROTATION_GENERATION="$(fetch "$PROXY_PATH" rotation_generation)"
if [[ ! "$ROTATION_GENERATION" =~ ^[1-9][0-9]*$ ]]; then
  echo "gx10 proxy ROTATION_GENERATION is invalid" >&2
  exit 1
fi
printf 'GX10_ROTATION_GENERATION=%s\n' "$ROTATION_GENERATION" >>"$APP_TMP"

chmod 0600 "$APP_TMP" "$PROXY_TMP"
install -m 0600 "$APP_TMP" "$RUNTIME_DIR/application.env.new"
install -m 0600 "$PROXY_TMP" "$RUNTIME_DIR/proxy.env.new"
mv -f "$RUNTIME_DIR/application.env.new" "$RUNTIME_DIR/application.env"
mv -f "$RUNTIME_DIR/proxy.env.new" "$RUNTIME_DIR/proxy.env"

# Only non-secret metadata is logged.
echo "gx10 runtime secret files rotated generation=$ROTATION_GENERATION" >&2
