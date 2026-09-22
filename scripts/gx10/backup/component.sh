#!/usr/bin/env bash
set -euo pipefail
umask 077

mode="${1:-}"
component="${2:-}"
target="${3:-}"
# Absolute defaults in production; the overrides exist so the stop-copy-start
# sequence can be exercised by a test instead of only read.
COMPOSE=("${GX10_COMPOSE_BIN:-/opt/aca/scripts/gx10/podman-compose.sh}")
PODMAN="${GX10_PODMAN_BIN:-/usr/bin/podman}"
PERSIST_ROOT="${GX10_PERSIST_ROOT:-/srv/aca}"
POSTGRES_IMAGE="docker.io/library/postgres:17.11@sha256:67f41722b7a8cbdb868a44a4995c846eddfdc2973bccb291ce937dce88ad5675"

# Freeze the store, copy it, thaw it.
#
# Stopping was the original design and it cannot work here: the container
# carries `restart: on-failure:5`, and Podman brought ClickHouse back up 0.45
# seconds after the stop, so the copy ran against a live store and tar exited
# with "file changed as we read it". MinIO fared worse, failing in Podman's
# own namespace teardown while the stop and the restart raced.
#
# `podman pause` freezes the container's processes through the cgroup freezer.
# No "died" event means no restart policy fires, nothing races the copy, and
# the container keeps its identity, its network, and its dependents' handles.
# The copy is crash-consistent rather than clean-shutdown consistent: it is
# what these stores see after a power cut, which both are built to recover
# from, and it is the same guarantee a filesystem snapshot gives.
#
# A refused pause aborts before the copy. Copying a running store yields an
# artifact that looks fine and restores torn.
paused_tar() {
  local service="$1" source="$2" status=0 name
  name="${COMPOSE_PROJECT_NAME:-aca-gx10}_${service}_1"
  "$PODMAN" pause "$name" >&2 || return "$?"
  /usr/bin/tar -C "$source" -cf - . || status=$?
  # Thaw even when the copy failed; a store left frozen is an outage.
  "$PODMAN" unpause "$name" >&2 || status=$?
  return "$status"
}

produce() {
  case "$component" in
    application_postgresql)
      exec "${COMPOSE[@]}" exec -T app-postgres sh -ec 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_dump --format=custom --dbname=newsletters --username=newsletter_user'
      ;;
    langfuse_postgresql)
      exec "${COMPOSE[@]}" exec -T langfuse-postgres sh -ec 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_dump --format=custom --dbname=langfuse --username=langfuse'
      ;;
    falkordb) paused_tar falkordb "$PERSIST_ROOT/falkordb" ;;
    clickhouse) paused_tar clickhouse "$PERSIST_ROOT/clickhouse" ;;
    minio) paused_tar minio "$PERSIST_ROOT/minio" ;;
    configuration_metadata)
      exec /usr/bin/tar -C /opt/aca -cf - docker-compose.gx10.yml deploy/gx10
      ;;
    *) echo "unsupported backup component" >&2; exit 64 ;;
  esac
}

safe_target() {
  [[ "$target" == /run/aca/gx10/restore-drill/* && -d "$target" && ! -L "$target" ]] || {
    echo "restore target is outside the dedicated isolation root" >&2
    exit 1
  }
}

safe_tar() {
  local archive="$1"
  /usr/bin/tar -tf "$archive" | while IFS= read -r name; do
    [[ "$name" != /* && "$name" != "../"* && "$name" != *"/../"* ]] || exit 1
  done
}

restore() {
  safe_target
  artifact="$target/$component.backup"
  /usr/bin/cat >"$artifact"
  chmod 0600 "$artifact"
  [[ -s "$artifact" ]] || { echo "empty component artifact" >&2; exit 1; }
  case "$component" in
    application_postgresql|langfuse_postgresql)
      /usr/bin/podman run --rm --network none -v "$target:/restore:rw" "$POSTGRES_IMAGE" pg_restore --file="/restore/$component.sql" "/restore/$component.backup" >/dev/null
      ;;
    falkordb|clickhouse|minio|configuration_metadata)
      safe_tar "$artifact"
      install -d -m 0700 "$target/data"
      /usr/bin/tar -xf "$artifact" -C "$target/data"
      ;;
    *) echo "unsupported restore component" >&2; exit 64 ;;
  esac
}

validate() {
  safe_target
  artifact="$target/$component.backup"
  [[ -s "$artifact" ]] || exit 1
  case "$component" in
    application_postgresql|langfuse_postgresql) [[ -s "$target/$component.sql" ]] ;;
    falkordb|clickhouse|minio|configuration_metadata) [[ -d "$target/data" && -n "$(find "$target/data" -mindepth 1 -print -quit)" ]] ;;
    *) exit 64 ;;
  esac
}

probe() {
  case "$component" in
    application_operation_rows)
      exec "${COMPOSE[@]}" exec -T app-postgres sh -ec 'export PGPASSWORD="$POSTGRES_PASSWORD"; test "$(psql -At --dbname=newsletters --username=newsletter_user --command="SELECT count(*) FROM operation_observation_attempts")" -ge 1'
      ;;
    langfuse_trace_metadata)
      exec "${COMPOSE[@]}" exec -T clickhouse sh -ec 'test "$(clickhouse-client --user langfuse --password "$CLICKHOUSE_PASSWORD" --query="SELECT count() FROM langfuse.traces WHERE length(toString(metadata)) > 2")" -ge 1'
      ;;
    *) echo "unsupported metadata probe" >&2; exit 64 ;;
  esac
}

case "$mode" in
  produce) produce ;;
  restore) restore ;;
  validate) validate ;;
  probe) probe ;;
  *) echo "usage: component.sh produce|restore|validate|probe name [target]" >&2; exit 64 ;;
esac
