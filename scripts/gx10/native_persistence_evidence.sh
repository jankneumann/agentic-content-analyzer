#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${GX10_COMPOSE_FILE:-$ROOT_DIR/docker-compose.gx10.yml}"
RUNTIME_DIR="${GX10_RUNTIME_DIR:-/run/aca/gx10}"
MANIFEST="$RUNTIME_DIR/native-persistence.env"
MODE="${1:?usage: native_persistence_evidence.sh seed|verify}"

compose() {
  "$ROOT_DIR/scripts/gx10/podman-compose.sh" "$@"
}

seed() {
  local record operation_id trace_id temporary
  record="$(compose exec -T api python - <<'PY'
import asyncio
import os
import uuid

from langfuse import Langfuse

from src.models.jobs import OperationType
from src.services.operation_service import OperationService


async def queue_native_operation(marker: str) -> str:
    handle = await OperationService().submit(
        OperationType.THEME_ANALYSIS_CREATE,
        {"query": {"gx10_persistence_marker": marker}},
        idempotency_key=marker,
    )
    return handle.operation_id


marker = f"gx10-persistence-{uuid.uuid4().hex}"
operation_id = asyncio.run(queue_native_operation(marker))
client = Langfuse(
    public_key=os.environ["GX10_LANGFUSE_PUBLIC_KEY"],
    secret_key=os.environ["GX10_LANGFUSE_SECRET_KEY"],
    host="http://langfuse-web:3000",
)
trace_id = client.create_trace_id(seed=marker)
with client.start_as_current_observation(
    name="gx10.persistence.native",
    as_type="span",
    trace_context={"trace_id": trace_id},
) as observation:
    observation.update(metadata={"operation_id": operation_id, "marker": marker})
client.flush()
print(f"operation_id={operation_id}")
print(f"trace_id={trace_id}")
PY
)"
  operation_id="$(sed -n 's/^operation_id=//p' <<<"$record")"
  trace_id="$(sed -n 's/^trace_id=//p' <<<"$record")"
  [[ "$operation_id" =~ ^[1-9][0-9]*$ ]] || { echo "gx10 native operation id missing" >&2; return 1; }
  [[ "$trace_id" =~ ^[0-9a-f]{32}$ ]] || { echo "gx10 Langfuse trace id missing" >&2; return 1; }
  install -d -m 0700 "$RUNTIME_DIR"
  temporary="$(mktemp "$RUNTIME_DIR/native-persistence.XXXXXX")"
  printf 'operation_id=%s\ntrace_id=%s\n' "$operation_id" "$trace_id" >"$temporary"
  chmod 0600 "$temporary"
  mv -f "$temporary" "$MANIFEST"
}

verify() {
  local operation_id trace_id
  [[ -s "$MANIFEST" && "$(stat -c %a "$MANIFEST")" == "600" ]] || {
    echo "gx10 native persistence manifest missing or unsafe" >&2
    return 1
  }
  operation_id="$(sed -n 's/^operation_id=//p' "$MANIFEST")"
  trace_id="$(sed -n 's/^trace_id=//p' "$MANIFEST")"
  [[ "$operation_id" =~ ^[1-9][0-9]*$ && "$trace_id" =~ ^[0-9a-f]{32}$ ]] || {
    echo "gx10 native persistence manifest invalid" >&2
    return 1
  }
  compose exec -T \
    -e GX10_PERSISTED_OPERATION_ID="$operation_id" \
    -e GX10_PERSISTED_TRACE_ID="$trace_id" \
    api python - <<'PY'
import asyncio
import base64
import json
import os
import time
from urllib.request import Request, urlopen

from src.services.operation_service import OperationService


async def verify_operation() -> None:
    handle = await OperationService().get(os.environ["GX10_PERSISTED_OPERATION_ID"])
    assert handle.operation_id == os.environ["GX10_PERSISTED_OPERATION_ID"]


asyncio.run(verify_operation())
trace_id = os.environ["GX10_PERSISTED_TRACE_ID"]
credentials = base64.b64encode(
    f'{os.environ["GX10_LANGFUSE_PUBLIC_KEY"]}:{os.environ["GX10_LANGFUSE_SECRET_KEY"]}'.encode()
).decode()
request = Request(  # noqa: S310 - fixed internal GX-10 endpoint
    f"http://langfuse-web:3000/api/public/traces/{trace_id}",
    headers={"Authorization": f"Basic {credentials}"},
)
for attempt in range(60):
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310
            payload = json.load(response)
        assert payload.get("id") == trace_id
        break
    except Exception:
        if attempt == 59:
            raise
        time.sleep(2)
PY
  compose exec -T -e GX10_PERSISTED_TRACE_ID="$trace_id" clickhouse sh -ec '
    for attempt in $(seq 1 60); do
      count="$(clickhouse-client --user langfuse --password "$CLICKHOUSE_PASSWORD" \
        --query "SELECT count() FROM langfuse.traces WHERE id = '\''${GX10_PERSISTED_TRACE_ID}'\''")"
      test "$count" -ge 1 && exit 0
      test "$attempt" -eq 60 && exit 1
      sleep 2
    done
  '
}

case "$MODE" in
  seed) seed ;;
  verify) verify ;;
  *) echo "usage: native_persistence_evidence.sh seed|verify" >&2; exit 64 ;;
esac
