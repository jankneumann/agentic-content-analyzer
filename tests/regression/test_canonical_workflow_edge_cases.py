"""Cross-boundary regression coverage for canonical workflow edge cases."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from src.ingestion.registry import SOURCE_REGISTRY
from src.ingestion.result import IngestionError, IngestionResponse
from src.models.content import ContentSource, ContentStatus
from src.models.jobs import (
    LEGACY_OPERATION_TYPES,
    JobRecord,
    JobStatus,
    OperationStatus,
    OperationType,
)
from src.models.query import ContentQuery, DateBasis, SelectionExclusionReason
from src.services.content_set_resolver import ContentSetResolver
from src.services.operation_service import OperationService
from tests.factories.content import ContentFactory
from tests.factories.summary import SummaryFactory

START = datetime(2026, 7, 1, tzinfo=UTC)
END = START + timedelta(days=1)


def _summary(content) -> None:
    SummaryFactory(content=content, content_id=content.id)


def _job(
    *,
    status: JobStatus = JobStatus.QUEUED,
    payload: dict | None = None,
    entrypoint: str = OperationType.INGESTION_EXECUTE.value,
    retry_count: int = 0,
) -> JobRecord:
    return JobRecord(
        id=9123,
        entrypoint=entrypoint,
        status=status,
        payload=payload
        or {
            "schema_version": 2,
            "operation_type": OperationType.INGESTION_EXECUTE.value,
            "input": {"command": {"kind": "rss", "force_reprocess": True}},
            "progress": 0,
            "message": "Queued",
            "cancel_requested": False,
            "cancellable": True,
            "resource": None,
            "result": None,
            "problem": None,
        },
        priority=0,
        retry_count=retry_count,
        created_at=START,
    )


class _MutationConnection:
    def __init__(self, returned: JobRecord) -> None:
        class _Transaction:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

        self.returned = returned
        self.fetchrow = AsyncMock(side_effect=self._fetchrow)
        self.fetchval = AsyncMock(side_effect=[returned.id, None, returned.id, returned.id])
        self.execute = AsyncMock(return_value="SELECT 1")
        self.transaction = lambda: _Transaction()

    async def _fetchrow(self, query: str, *_args):
        job = self.returned
        return {
            "id": job.id,
            "entrypoint": job.entrypoint,
            "status": job.status.value,
            "payload": job.payload,
            "priority": job.priority,
            "error": job.error,
            "retry_count": job.retry_count,
            "parent_job_id": job.parent_job_id,
            "heartbeat_at": job.heartbeat_at,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
        }


def test_selection_edge_cases_keep_structured_exclusions_and_explicit_date_basis(
    db_session,
) -> None:
    canonical = ContentFactory(
        source_type=ContentSource.RSS,
        published_date=START + timedelta(hours=1),
        ingested_at=START + timedelta(hours=1),
    )
    _summary(canonical)
    alias = ContentFactory(
        source_type=ContentSource.GMAIL,
        canonical_id=canonical.id,
        published_date=START + timedelta(hours=2),
        ingested_at=START + timedelta(hours=2),
    )
    _summary(alias)
    null_date = ContentFactory(
        source_type=ContentSource.SUBSTACK,
        published_date=None,
        ingested_at=START + timedelta(hours=3),
    )
    _summary(null_date)
    filtered = ContentFactory(
        status=ContentStatus.FILTERED_OUT,
        published_date=START + timedelta(hours=4),
        ingested_at=START + timedelta(hours=4),
    )
    _summary(filtered)
    failed = ContentFactory(
        status=ContentStatus.FAILED,
        published_date=START + timedelta(hours=5),
        ingested_at=START + timedelta(hours=5),
    )
    _summary(failed)
    missing_summary = ContentFactory(
        published_date=START + timedelta(hours=6),
        ingested_at=START + timedelta(hours=6),
    )

    resolver = ContentSetResolver()
    published = resolver.resolve(ContentQuery(start_date=START, end_date=END), session=db_session)
    ingested = resolver.resolve(
        ContentQuery(
            start_date=START,
            end_date=END,
            date_basis=DateBasis.INGESTED_AT,
        ),
        session=db_session,
    )

    assert published.content_ids == (canonical.id,)
    assert set(ingested.content_ids) == {canonical.id, null_date.id}
    assert published.exclusion_counts == {
        SelectionExclusionReason.DUPLICATE_ALIAS: 1,
        SelectionExclusionReason.FAILED: 1,
        SelectionExclusionReason.FILTERED_OUT: 1,
        SelectionExclusionReason.MISSING_SUMMARY: 1,
        SelectionExclusionReason.OUTSIDE_PERIOD: 1,
    }
    assert null_date.id in ingested.content_ids
    assert missing_summary.id in {
        item.content_id
        for item in ingested.exclusions_by_reason[SelectionExclusionReason.MISSING_SUMMARY]
    }


@pytest.mark.asyncio
async def test_forced_ingestion_is_idempotently_submitted_and_partial_results_are_typed(
    monkeypatch,
) -> None:
    command = SOURCE_REGISTRY.parse_command(
        {"kind": "rss", "force_reprocess": True, "max_items": 2}
    )
    enqueue = AsyncMock(return_value=(9123, True))
    get_status = AsyncMock(return_value=_job())
    monkeypatch.setattr("src.services.operation_service.queue_setup.enqueue_queue_job", enqueue)
    monkeypatch.setattr("src.services.operation_service.queue_setup.get_job_status", get_status)
    service = OperationService()
    normalized = {"command": command.model_dump(mode="json", exclude_none=True)}

    await service.submit(OperationType.INGESTION_EXECUTE, normalized)
    await service.submit(
        OperationType.INGESTION_EXECUTE,
        {"command": dict(reversed(list(normalized["command"].items())))},
    )

    assert (
        enqueue.await_args_list[0].kwargs["idempotency_key"]
        == enqueue.await_args_list[1].kwargs["idempotency_key"]
    )
    first_payload = enqueue.await_args_list[0].args[1]
    assert first_payload["input"]["command"]["force_reprocess"] is True

    partial = IngestionResponse(
        command="ingest.rss",
        source="rss",
        status="partial",
        items_ingested=1,
        items_failed=1,
        errors=[IngestionError(code="feed_unavailable", message="one feed failed")],
    )
    assert partial.status == "partial"
    assert partial.items_ingested == 1
    assert partial.items_failed == 1


@pytest.mark.asyncio
async def test_cancel_and_retry_preserve_normalized_input_and_reset_only_control_state() -> None:
    cancelled = _job(status=JobStatus.CANCELLED)
    cancelled.payload["cancel_requested"] = True
    cancelled.payload["message"] = "Cancelled"
    cancel_connection = _MutationConnection(cancelled)

    cancel_handle = await OperationService(connection=cancel_connection).cancel("9123")

    assert cancel_handle.status is OperationStatus.CANCELLED
    assert cancel_handle.cancellable is False

    retried = _job(status=JobStatus.QUEUED, retry_count=2)
    retry_connection = _MutationConnection(retried)
    retry_handle = await OperationService(connection=retry_connection).retry("9123")
    query, reset_json, operation_id = retry_connection.fetchrow.await_args.args

    assert operation_id == 9123
    assert "retry_count = retry_count + 1" in query
    assert json.loads(reset_json) == {
        "progress": 0,
        "message": "Queued",
        "cancel_requested": False,
        "resource": None,
        "result": None,
        "problem": None,
    }
    assert retry_handle.retry_count == 2
    assert retry_handle.operation_type is OperationType.INGESTION_EXECUTE
    assert retried.payload["input"]["command"]["force_reprocess"] is True


def test_every_supported_version_one_entrypoint_drains_through_canonical_projection() -> None:
    for entrypoint, operation_type in LEGACY_OPERATION_TYPES.items():
        handle = OperationService.project(
            _job(
                entrypoint=entrypoint,
                payload={
                    "schema_version": 1,
                    "progress": 25,
                    "message": "Draining legacy work",
                    "legacy_argument": "preserved",
                },
            )
        )

        assert handle.schema_version == 2
        assert handle.operation_type is operation_type
        assert handle.progress == 25
        assert handle.message == "Draining legacy work"
