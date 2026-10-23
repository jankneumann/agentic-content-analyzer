#!/usr/bin/env bash
set -euo pipefail

PODMAN_BIN="${GX10_PODMAN_BIN:-/usr/bin/podman}"
CONTAINER_NAME="${GX10_OPENBAO_CONTAINER_NAME:-aca-gx10_openbao_1}"

if [[ "$PODMAN_BIN" != /* || ! -x "$PODMAN_BIN" ]]; then
  echo "gx10 Podman executable must be an absolute executable path" >&2
  exit 64
fi
if [[ ! "$CONTAINER_NAME" =~ ^[A-Za-z0-9_.-]+$ ]]; then
  echo "gx10 OpenBao container name is invalid" >&2
  exit 64
fi

state="$($PODMAN_BIN inspect --format "{{.State.Status}}" "$CONTAINER_NAME" 2>/dev/null)" || {
  echo "gx10 OpenBao container is not running: $CONTAINER_NAME" >&2
  exit 1
}
if [[ "$state" != "running" ]]; then
  echo "gx10 OpenBao container is not running: $CONTAINER_NAME ($state)" >&2
  exit 1
fi
