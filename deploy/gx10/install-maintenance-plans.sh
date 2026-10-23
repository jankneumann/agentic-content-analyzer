#!/usr/bin/env bash
set -euo pipefail
umask 077

SOURCE_DIR="${GX10_MAINTENANCE_SOURCE_DIR:-/opt/aca/deploy/gx10/maintenance}"
CONFIG_DIR="${GX10_MAINTENANCE_CONFIG_DIR:-/etc/aca/gx10}"
INSTALL_ROOT="${GX10_INSTALL_ROOT:-/opt/aca}"
COMPONENT_SCRIPT="/opt/aca/scripts/gx10/backup/component.sh"
ACTION_SCRIPT="/opt/aca/scripts/gx10/storage/action.sh"
components='["application_postgresql","falkordb","langfuse_postgresql","clickhouse","minio","configuration_metadata"]'

[[ -d "$SOURCE_DIR" && ! -L "$SOURCE_DIR" ]] || { echo "reviewed maintenance source directory unavailable" >&2; exit 1; }
[[ ! -L "$CONFIG_DIR" ]] || { echo "maintenance configuration directory must not be a symlink" >&2; exit 1; }

storage="$SOURCE_DIR/storage-actions.json"
backup="$SOURCE_DIR/backup-plan.json"
[[ -x "$INSTALL_ROOT/scripts/gx10/storage/action.sh" ]] || { echo "storage action helper unavailable" >&2; exit 1; }
[[ -x "$INSTALL_ROOT/scripts/gx10/backup/component.sh" ]] || { echo "backup component helper unavailable" >&2; exit 1; }


restore="$SOURCE_DIR/restore-plan.json"
jq -e --arg action "$ACTION_SCRIPT" '
  keys == ["alert","cleanup","throttle"] and
  all(to_entries[]; (.value == [$action, .key]))
' "$storage" >/dev/null || { echo "storage action inventory is invalid" >&2; exit 1; }
jq -e --arg component "$COMPONENT_SCRIPT" --argjson names "$components" '
  keys == ["producers"] and
  (.producers | keys == ($names | sort)) and
  (.producers | all(to_entries[]; .value == [$component, "produce", .key]))
' "$backup" >/dev/null || { echo "backup component inventory is invalid" >&2; exit 1; }
jq -e --arg component "$COMPONENT_SCRIPT" --argjson names "$components" '
  keys == ["metadata_probe","production_sources","restore","validate"] and
  (.restore | keys == ($names | sort)) and
  (.validate | keys == ($names | sort)) and
  (.production_sources | keys == ($names | sort)) and
  (.restore | all(to_entries[]; .value == [$component, "restore", .key])) and
  (.validate | all(to_entries[]; .value == [$component, "validate", .key])) and
  .production_sources == {
    application_postgresql:"/srv/aca/postgres",
    falkordb:"/srv/aca/falkordb",
    langfuse_postgresql:"/srv/aca/langfuse-postgres",
    clickhouse:"/srv/aca/clickhouse",
    minio:"/srv/aca/minio",
    configuration_metadata:"/opt/aca/deploy/gx10"
  } and
  .metadata_probe == {
    application_operation_rows:[$component, "probe", "application_operation_rows"],
    langfuse_trace_metadata:[$component, "probe", "langfuse_trace_metadata"]
  }
' "$restore" >/dev/null || { echo "restore component inventory is invalid" >&2; exit 1; }

install -d -m 0700 "$CONFIG_DIR"
for name in storage-actions.json backup-plan.json restore-plan.json; do
  temporary="$(mktemp "$CONFIG_DIR/.$name.XXXXXX")"
  install -m 0600 "$SOURCE_DIR/$name" "$temporary"
  mv -f "$temporary" "$CONFIG_DIR/$name"
done
