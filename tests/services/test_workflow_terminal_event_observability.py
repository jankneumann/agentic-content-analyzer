"""Attempt-aware terminal-event correlation contract tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from src.services.workflow_terminal_event_service import (
    WorkflowTerminalEventService,
    _CLASSIFICATION_UPDATE_QUERY,
    _EVENT_QUERY,
    _event_from_row,
)

EVENT_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TRACE_ONE = "1" * 32
TRACE_TWO = "2" * 32


def _row(*, claim_generation: int, status: str, trace_id: str) -> dict[str, object]:
    return {
        "id": EVENT_ID,
        "event_key": f"operation:42:claim:{claim_generation}:status:{status}",
        "source_kind": "operation",
        "operation_id": 42,
        "claim_generation": claim_generation,
        "terminal_status": status,
        "reconciliation_action_id": None,
        "reconciliation_run_id": None,
        "reconciliation_content_id": None,
        "classification_status": "pending",
        "occurred_at": datetime(2026, 8, 29, tzinfo=UTC),
        "trace_id": trace_id,
    }


def test_terminal_event_reads_trace_from_matching_operation_attempt() -> None:
    assert "operation_observation_attempts" in _EVENT_QUERY
    assert "event.claim_generation" in _EVENT_QUERY
    event = _event_from_row(_row(claim_generation=0, status="completed", trace_id=TRACE_ONE))
    assert event.operation_id == 42
    assert event.claim_generation == 0
    assert event.trace_id == TRACE_ONE


def test_retried_terminal_claims_retain_independent_trace_correlation() -> None:
    first = _event_from_row(_row(claim_generation=0, status="failed", trace_id=TRACE_ONE))
    retry = _event_from_row(_row(claim_generation=1, status="completed", trace_id=TRACE_TWO))
    assert (first.claim_generation, first.trace_id) == (0, TRACE_ONE)
    assert (retry.claim_generation, retry.trace_id) == (1, TRACE_TWO)
    assert first.trace_id != retry.trace_id


def test_terminal_classification_update_persists_resolved_trace() -> None:
    assert "trace_id" in _CLASSIFICATION_UPDATE_QUERY


@pytest.mark.asyncio
async def test_terminal_service_binds_trace_when_classifying_successful_claim() -> None:
    class Connection:
        def __init__(self) -> None:
            self.updates: list[tuple[object, ...]] = []

        async def fetchrow(self, query: str, *args):
            if query == _EVENT_QUERY:
                return _row(claim_generation=0, status="completed", trace_id=TRACE_ONE)
            if "WITH RECURSIVE lineage" in query:
                return {
                    "operation_type": "ingestion.execute",
                    "operation_status": "completed",
                    "result": {
                        "schema_version": 2,
                        "command_key": "rss",
                        "outcome": "success",
                        "items_ingested": 1,
                        "items_skipped": 0,
                        "items_failed": 0,
                        "source_outcomes": [],
                    },
                    "pipeline_root_id": None,
                    "pipeline_root_status": None,
                    "pipeline_root_result": None,
                }
            if query == _CLASSIFICATION_UPDATE_QUERY:
                self.updates.append(args)
                return {"id": EVENT_ID}
            raise AssertionError(query)

        async def execute(self, *_args):
            return "UPDATE 1"

    connection = Connection()
    service = WorkflowTerminalEventService(
        connection,
        telemetry_emitter=lambda **_kwargs: False,
    )
    result = await service.process_pending_event(EVENT_ID)
    assert result is not None
    assert result.event is not None
    assert result.event.trace_id == TRACE_ONE
    assert connection.updates[-1][-1] == TRACE_ONE
