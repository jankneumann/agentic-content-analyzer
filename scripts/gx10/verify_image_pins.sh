#!/usr/bin/env bash
set -euo pipefail
RUNTIME_DIR="${GX10_RUNTIME_DIR:-/run/aca/gx10}"
APP_REF="${GX10_APP_IMAGE:?protected GX10_APP_IMAGE is required}"
SQUID_DIGEST="${GX10_SQUID_DIGEST:?protected GX10_SQUID_DIGEST is required}"
LANGFUSE_WORKER_DIGEST="${GX10_LANGFUSE_WORKER_DIGEST:?protected GX10_LANGFUSE_WORKER_DIGEST is required}"
PIN='^[^[:space:]@]+:[^[:space:]@]+@sha256:([0-9a-f]{64})$'
[[ "$APP_REF" =~ $PIN ]] || { echo "application image is not tag@sha256 pinned" >&2; exit 1; }
APP_DIGEST="${BASH_REMATCH[1]}"
[[ "$SQUID_DIGEST" =~ ^[0-9a-f]{64}$ ]] || { echo "Squid digest invalid" >&2; exit 1; }
[[ "$LANGFUSE_WORKER_DIGEST" =~ ^[0-9a-f]{64}$ ]] || { echo "Langfuse worker digest invalid" >&2; exit 1; }
for digest in "$APP_DIGEST" "$SQUID_DIGEST" "$LANGFUSE_WORKER_DIGEST"; do
  [[ "$digest" != "$(printf '0%.0s' {1..64})" && "$digest" != "$(printf 'f%.0s' {1..64})" ]] || { echo "sentinel image digest denied" >&2; exit 1; }
done
APP_TAG="${APP_REF%@sha256:*}"
SQUID_TAG="docker.io/ubuntu/squid:6.6-24.04_beta"
LANGFUSE_WORKER_TAG="docker.io/langfuse/langfuse-worker:3.225.5"
inspect() { /usr/bin/skopeo inspect --override-os linux --override-arch arm64 --format '{{.Digest}}' "docker://$1"; }
[[ "$(inspect "$APP_TAG")" == "sha256:$APP_DIGEST" ]] || { echo "application tag provenance mismatch" >&2; exit 1; }
[[ "$(inspect "$SQUID_TAG")" == "sha256:$SQUID_DIGEST" ]] || { echo "Squid tag provenance mismatch or unpublished tag" >&2; exit 1; }
[[ "$(inspect "$LANGFUSE_WORKER_TAG")" == "sha256:$LANGFUSE_WORKER_DIGEST" ]] || { echo "Langfuse worker tag provenance mismatch" >&2; exit 1; }
install -d -m 0700 "$RUNTIME_DIR"
tmp="$(mktemp "$RUNTIME_DIR/image-pins.ready.XXXXXX")"; trap 'rm -f -- "$tmp"' EXIT
printf 'verified_at=%(%s)T\napp=%s\nsquid=%s@sha256:%s\nlangfuse_worker=%s@sha256:%s\n' \
  -1 "$APP_REF" "$SQUID_TAG" "$SQUID_DIGEST" "$LANGFUSE_WORKER_TAG" "$LANGFUSE_WORKER_DIGEST" >"$tmp"
chmod 0600 "$tmp"; mv -f "$tmp" "$RUNTIME_DIR/image-pins.ready"
