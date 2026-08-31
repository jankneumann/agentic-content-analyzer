#!/usr/bin/env bash
set -euo pipefail
umask 077

mode="${1:-}"
component="${2:-}"
target="${3:-}"
COMPOSE=(/opt/aca/scripts/gx10/podman-compose.sh)
POSTGRES_IMAGE="postgres:17@sha256:67f41722b7a8cbdb868a44a4995c846eddfdc2973bccb291ce937dce88ad5675"

offline_tar() {
  local service="$1" source="$2" status=0
  "${COMPOSE[@]}" stop --timeout 120 "$service" >&2
  /usr/bin/tar -C "$source" -cf - . || status=$?
  "${COMPOSE[@]}" up -d --no-deps "$service" >&2 || status=$?
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
    neo4j) offline_tar neo4j /srv/aca/neo4j ;;
    clickhouse) offline_tar clickhouse /srv/aca/clickhouse ;;
    minio) offline_tar minio /srv/aca/minio ;;
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
    neo4j|clickhouse|minio|configuration_metadata)
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
    neo4j|clickhouse|minio|configuration_metadata) [[ -d "$target/data" && -n "$(find "$target/data" -mindepth 1 -print -quit)" ]] ;;
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
