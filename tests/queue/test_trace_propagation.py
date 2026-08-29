"""Queue claim trace propagation tests (CORR-001/005/006, JOB-001/002)."""
from __future__ import annotations
import json
import pytest
from src.contracts.operation_context import get_current_operation_context
from src.queue import worker

def _submission_context() -> dict[str, object]:
    return {"schema_version":1,"operation_id":"41","root_operation_id":"41","parent_operation_id":None,
        "traceparent":"00-11111111111111111111111111111111-2222222222222222-01","tracestate":None,
        "trace_id":"11111111111111111111111111111111","span_id":"2222222222222222","claim_generation":"0",
        "attempt_number":None,"entrypoint":"pipeline.run","service_name":"aca-api","service_instance_id":"api-1",
        "environment":"test","release_revision":"test-revision","stage":"submit","resource_kind":None,"resource_key":None}

def test_restart_reconstructs_attempt_only_from_persisted_context() -> None:
    stored = _submission_context()
    job = {"id":41,"entrypoint":"pipeline.run","claim_generation":2,"claim_protocol_version":2,
        "submission_context":json.dumps(stored),"submission_traceparent":stored["traceparent"],
        "submission_tracestate":None,"trace_id":stored["trace_id"],"root_operation_id":41}
    context = worker._attempt_context_from_job(job)
    assert context.operation_id == "41" and context.trace_id == stored["trace_id"]
    assert context.claim_generation == "2" and context.attempt_number == "3"
    assert context.stage == "claim" and context.service_instance_id != "api-1"

@pytest.mark.asyncio
async def test_handler_receives_bound_attempt_context(monkeypatch) -> None:
    seen: list[object] = []
    async def handler(_job_id: int, _payload: dict[str, object]) -> None: seen.append(get_current_operation_context())
    async def false(*args: object, **kwargs: object) -> bool: return False
    async def true(*args: object, **kwargs: object) -> bool: return True
    class _Connection:
        async def fetchval(self, *_args: object) -> object: return None
    monkeypatch.setitem(worker._handlers, "pipeline.run", handler)
    monkeypatch.setattr(worker, "_checkpoint_job_cancellation", false)
    monkeypatch.setattr(worker, "_complete_job", true)
    monkeypatch.setattr(worker, "_emit_job_notification", false)
    monkeypatch.setattr("src.queue.setup.touch_job_heartbeat", true)
    monkeypatch.setattr(worker, "_start_attempt_evidence", true)
    monkeypatch.setattr(worker, "_complete_attempt_evidence", true)
    stored = _submission_context()
    await worker._process_job(_Connection(), {"id":41,"entrypoint":"pipeline.run","payload":{},
        "claim_generation":0,"claim_protocol_version":2,"submission_context":stored,
        "submission_traceparent":stored["traceparent"],"submission_tracestate":None,
        "trace_id":stored["trace_id"],"root_operation_id":41})
    assert len(seen) == 1 and seen[0] is not None
    assert seen[0].attempt_number == "1"
    assert get_current_operation_context() is None
