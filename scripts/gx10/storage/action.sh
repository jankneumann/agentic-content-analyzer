#!/usr/bin/env bash
set -euo pipefail
umask 077

action="${1:-}"
COMPOSE=(/usr/bin/docker compose -f /opt/aca/docker-compose.gx10.yml)
payload="$(mktemp)"
trap 'rm -f -- "$payload"' EXIT
head -c 16385 >"$payload"
[[ "$(wc -c <"$payload")" -le 16384 ]] || { echo "storage action payload exceeds limit" >&2; exit 1; }
jq -e 'type == "object" and (.operation_id | type == "string") and (.trace_id | test("^[0-9a-f]{32}$"))' "$payload" >/dev/null

case "$action" in
  throttle)
    jq -e 'has("scheduled_ingestion_concurrency") and has("pause_nonessential_ingestion") and has("suppress_success_excerpts")' "$payload" >/dev/null
    if [[ "$(jq -r '.pause_nonessential_ingestion' "$payload")" == "true" ]]; then
      "${COMPOSE[@]}" stop --timeout 45 scheduler >&2
    else
      "${COMPOSE[@]}" up -d --no-deps scheduler >&2
    fi
    ;;
  cleanup)
    jq -e 'has("retention")' "$payload" >/dev/null
    if [[ "$(jq -r '.retention.mode' "$payload")" == "outcome_specific" ]]; then
      "${COMPOSE[@]}" exec -T maintenance python /srv/aca/scripts/backup_retention.py --apply >&2
    fi
    ;;
  alert)
    diagnostic="$(jq -r '.diagnostic_code // "storage_watermark"' "$payload")"
    outcome="$(jq -r '.outcome // "partial"' "$payload")"
    /usr/bin/logger -p daemon.err -t aca-gx10-storage "operation_id=$(jq -r .operation_id "$payload") trace_id=$(jq -r .trace_id "$payload") outcome=$outcome diagnostic_code=$diagnostic"
    ;;
  *) echo "unsupported storage action" >&2; exit 64 ;;
esac
