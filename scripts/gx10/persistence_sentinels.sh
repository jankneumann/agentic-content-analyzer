#!/usr/bin/env bash
set -euo pipefail
umask 077

MODE="${1:?usage: persistence_sentinels.sh seed|verify}"
PERSIST_ROOT="${GX10_PERSIST_ROOT:-/srv/aca}"
RUNTIME_DIR="${GX10_RUNTIME_DIR:-/run/aca/gx10}"
MANIFEST="$RUNTIME_DIR/persistence-sentinels.manifest"
declare -A COMPONENT_PATHS=(
  [app-postgres]="postgres"
  [langfuse-postgres]="langfuse-postgres"
  [redis]="redis"
  [neo4j]="neo4j"
  [clickhouse]="clickhouse"
  [minio]="minio"
  [openbao]="openbao"
)
declare -a COMPONENTS=(
  app-postgres
  langfuse-postgres
  redis
  neo4j
  clickhouse
  minio
  openbao
)

if [[ "$PERSIST_ROOT" == "/srv/aca" && "$EUID" -ne 0 ]]; then
  echo "gx10 production persistence sentinel ceremony requires root" >&2
  exit 1
fi

seed() {
  local component directory token manifest_tmp
  install -d -m 0700 "$RUNTIME_DIR"
  manifest_tmp="$(mktemp "$RUNTIME_DIR/persistence-sentinels.XXXXXX")"
  for component in "${COMPONENTS[@]}"; do
    directory="$PERSIST_ROOT/${COMPONENT_PATHS[$component]}"
    if [[ "$PERSIST_ROOT" == "/srv/aca" ]]; then
      [[ -d "$directory" ]] || { echo "gx10 persistent mount missing: $component" >&2; return 1; }
    else
      install -d -m 0700 "$directory"
    fi
    token="$(tr -d - </proc/sys/kernel/random/uuid)"
    printf '%s\n' "$token" | install -m 0600 /dev/stdin "$directory/.gx10-persistence-sentinel"
    printf '%s=%s\n' "$component" "$token" >>"$manifest_tmp"
  done
  install -m 0600 "$manifest_tmp" "$MANIFEST.new"
  mv -f "$MANIFEST.new" "$MANIFEST"
  rm -f -- "$manifest_tmp"
}

verify() {
  local component directory expected actual
  [[ -s "$MANIFEST" ]] || { echo "gx10 persistence sentinel manifest missing" >&2; return 1; }
  [[ "$(stat -c %a "$MANIFEST")" == "600" ]] || { echo "gx10 persistence sentinel manifest mode invalid" >&2; return 1; }
  for component in "${COMPONENTS[@]}"; do
    directory="$PERSIST_ROOT/${COMPONENT_PATHS[$component]}"
    expected="$(sed -n "s/^$component=//p" "$MANIFEST")"
    actual="$(<"$directory/.gx10-persistence-sentinel")"
    [[ -n "$expected" && "$actual" == "$expected" ]] || { echo "gx10 persistence sentinel mismatch: $component" >&2; return 1; }
    [[ "$(stat -c %a "$directory/.gx10-persistence-sentinel")" == "600" ]] || { echo "gx10 persistence sentinel mode invalid: $component" >&2; return 1; }
  done
}

case "$MODE" in
  seed) seed ;;
  verify) verify ;;
  *) echo "usage: persistence_sentinels.sh seed|verify" >&2; exit 64 ;;
esac
