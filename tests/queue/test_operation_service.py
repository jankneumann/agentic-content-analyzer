"""Contract tests for the durable operation projection."""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest
import yaml
from jsonschema import Draft202012Validator

from src.contracts.workflow_models import OperationSummary
from src.models.jobs import (
    LEGACY_OPERATION_TYPES,
    JobRecord,
    JobStatus,
    OperationPayloadV2,
    OperationProblem,
    OperationProblemError,
    OperationStatus,
    OperationType,
    ResourceReference,
)
from src.queue.execution_claim import ExecutionClaim, bind_execution_claim
from src.services.operation_service import OperationService

NOW = datetime(2026, 7, 13, 10, 0, tzinfo=UTC)
CONTRACTS = Path(__file__).parents[2] / "openspec/contracts/content-workflows"
CONTRACT_MODELS = CONTRACTS / "generated/models.py"
OPENAPI_CONTRACT = CONTRACTS / "openapi/v1.yaml"


def _contract_models() -> ModuleType:
    spec = importlib.util.spec_from_file_location("operation_contract_models", CONTRACT_MODELS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _validate_operation_handle_contract(handle: dict) -> None:
    contract = yaml.safe_load(OPENAPI_CONTRACT.read_text())
    schema = {
        "$ref": "#/components/schemas/OperationHandle",
        "components": contract["components"],
    }
    Draft202012Validator(schema).validate(handle)


def _job(
    *,
    job_id: int = 8123,
    entrypoint: str = "digest.create",
    status: JobStatus = JobStatus.QUEUED,
    payload: dict | None = None,
    error: str | None = None,
) -> JobRecord:
    return JobRecord(
        id=job_id,
        entrypoint=entrypoint,
        status=status,
        payload=payload
        or {
            "schema_version": 2,
            "operation_type": "digest.create",
            "input": {"digest_type": "daily"},
            "progress": 0,
            "message": "Queued",
            "cancel_requested": False,
            "resource": None,
            "result": None,
        },
        priority=0,
        error=error,
        retry_count=0,
        created_at=NOW,
    )


def test_version_2_payload_projects_openapi_operation_handle() -> None:
    handle = OperationService.project(_job())

    assert handle.model_dump(mode="json") == {
        "schema_version": 2,
        "operation_id": "8123",
        "operation_type": "digest.create",
        "status": "queued",
        "progress": 0,
        "message": "Queued",
        "cancellable": True,
        "retry_count": 0,
        "status_url": "/api/v1/operations/8123",
        "events_url": "/api/v1/operations/8123/events",
        "resource": None,
        "result": None,
        "problem": None,
        "created_at": "2026-07-13T10:00:00Z",
        "started_at": None,
        "completed_at": None,
    }
    _contract_models().OperationHandle.model_validate(handle.model_dump(mode="json"))


def test_completed_operation_projects_persisted_resource_and_result() -> None:
    payload = OperationPayloadV2(
        operation_type=OperationType.DIGEST_CREATE,
        input={"digest_type": "daily"},
        progress=100,
        message="Digest created",
        resource=ResourceReference(type="digest", id="42", url="/api/v1/digests/42"),
        result={"selection_fingerprint": "abc123"},
    ).model_dump(mode="json")
    job = _job(status=JobStatus.COMPLETED, payload=payload)
    job.completed_at = NOW

    handle = OperationService.project(job)

    assert handle.status is OperationStatus.COMPLETED
    assert handle.cancellable is False
    assert handle.resource == ResourceReference(type="digest", id="42", url="/api/v1/digests/42")
    assert handle.result == {"selection_fingerprint": "abc123"}


def test_failed_operation_projects_rfc7807_problem() -> None:
    handle = OperationService.project(_job(status=JobStatus.FAILED, error="provider unavailable"))
    serialized = handle.model_dump(mode="json")

    assert handle.status is OperationStatus.FAILED
    assert handle.problem is not None
    assert handle.problem.status == 500
    assert handle.problem.detail == "provider unavailable"
    assert handle.problem.code == "operation_failed"
    assert "errors" not in serialized["problem"]
    _validate_operation_handle_contract(serialized)


@pytest.mark.parametrize(
    ("status", "expected_outcome"),
    [
        (JobStatus.FAILED, "failed"),
        (JobStatus.CANCELLED, "cancelled"),
    ],
)
def test_terminal_pipeline_projection_applies_lifecycle_precedence_without_mutation(
    status: JobStatus,
    expected_outcome: str,
) -> None:
    stored_result = {
        "schema_version": 2,
        "stage": "digest",
        "ingestion_summary": {
            "outcome": "success",
            "sources": [],
            "sources_omitted": 0,
        },
    }
    payload = OperationPayloadV2(
        operation_type=OperationType.PIPELINE_RUN,
        result=stored_result,
    ).model_dump(mode="json")

    handle = OperationService.project(
        _job(entrypoint="pipeline.run", status=status, payload=payload)
    )

    assert handle.result is not stored_result
    assert handle.result is not None
    assert handle.result["stage"] == "digest"
    assert handle.result["ingestion_summary"]["outcome"] == expected_outcome
    assert stored_result["ingestion_summary"]["outcome"] == "success"


@pytest.mark.parametrize(
    ("status", "expected_outcome"),
    [
        (JobStatus.FAILED, "failed"),
        (JobStatus.CANCELLED, "cancelled"),
    ],
)
def test_early_terminal_pipeline_projection_synthesizes_minimal_summary(
    status: JobStatus,
    expected_outcome: str,
) -> None:
    payload = OperationPayloadV2(
        operation_type=OperationType.PIPELINE_RUN,
        result=None,
    ).model_dump(mode="json")

    handle = OperationService.project(
        _job(entrypoint="pipeline.run", status=status, payload=payload)
    )

    assert handle.result == {
        "schema_version": 2,
        "ingestion_summary": {
            "outcome": expected_outcome,
            "sources": [],
            "sources_omitted": 0,
        },
    }


def test_operation_problem_errors_match_openapi_contract() -> None:
    job = _job(status=JobStatus.FAILED)
    job.payload["problem"] = OperationProblem(
        type="https://aca.rotkohl.ai/problems/validation",
        title="Validation failed",
        status=422,
        detail="The request was invalid",
        errors=[
            OperationProblemError(
                path=["input", "url"],
                code="invalid_url",
                message="Must be an absolute URL",
            )
        ],
    ).model_dump(mode="json")

    serialized = OperationService.project(job).model_dump(mode="json")

    assert serialized["problem"]["errors"] == [
        {
            "path": ["input", "url"],
            "code": "invalid_url",
            "message": "Must be an absolute URL",
        }
    ]
    _validate_operation_handle_contract(serialized)


@pytest.mark.parametrize(
    ("entrypoint", "operation_type"),
    [
        ("ingest_content", OperationType.INGESTION_EXECUTE),
        ("summarize_content", OperationType.SUMMARIZATION_RUN),
        ("run_pipeline", OperationType.PIPELINE_RUN),
        ("create_digest", OperationType.DIGEST_CREATE),
    ],
)
def test_version_1_payloads_remain_queryable(
    entrypoint: str, operation_type: OperationType
) -> None:
    job = _job(
        entrypoint=entrypoint,
        payload={"schema_version": 1, "progress": 25, "message": "Working"},
    )

    handle = OperationService.project(job)

    assert handle.schema_version == 2
    assert handle.operation_type is operation_type
    assert handle.progress == 25
    assert handle.message == "Working"


def test_progress_event_matches_shared_event_contract() -> None:
    event = OperationService.event(OperationService.project(_job()), sequence=5, occurred_at=NOW)

    assert event.model_dump(mode="json") == {
        "schema_version": 2,
        "event_id": "8123:5",
        "operation_id": "8123",
        "operation_type": "digest.create",
        "status": "queued",
        "progress": 0,
        "message": "Queued",
        "resource": None,
        "problem": None,
        "occurred_at": "2026-07-13T10:00:00Z",
    }
    _contract_models().OperationEvent.model_validate(event.model_dump(mode="json"))


@pytest.mark.asyncio
async def test_bounded_wait_returns_latest_nonterminal_handle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = OperationService(poll_interval=0.001)
    get_operation = AsyncMock(return_value=OperationService.project(_job()))
    monkeypatch.setattr(service, "get", get_operation)

    handle = await service.wait("8123", timeout_seconds=0.002)

    assert handle.status is OperationStatus.QUEUED
    assert get_operation.await_count >= 1


@pytest.mark.asyncio
async def test_bounded_wait_returns_terminal_handle(monkeypatch: pytest.MonkeyPatch) -> None:
    service = OperationService(poll_interval=0)
    queued = OperationService.project(_job())
    completed_job = _job(status=JobStatus.COMPLETED)
    completed_job.payload["progress"] = 100
    completed_job.payload["message"] = "Done"
    completed = OperationService.project(completed_job)
    get_operation = AsyncMock(side_effect=[queued, completed])
    monkeypatch.setattr(service, "get", get_operation)

    handle = await service.wait("8123", timeout_seconds=1)

    assert handle.status is OperationStatus.COMPLETED
    assert get_operation.await_count == 2


def _row(job_id: int, created_at: datetime) -> dict:
    job = _job(job_id=job_id)
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
        "created_at": created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
    }


def _history_row(
    job_id: int,
    created_at: datetime,
    *,
    status: JobStatus = JobStatus.COMPLETED,
    parent_job_id: int | None = 91,
) -> dict:
    row = _row(job_id, created_at)
    row.update(
        {
            "entrypoint": "ingestion.execute",
            "status": status.value,
            "parent_job_id": parent_job_id,
            "completed_at": created_at,
            "payload": {
                "schema_version": 2,
                "operation_type": "ingestion.execute",
                "input": {"kind": "rss", "configured_sources": [{"url": "private"}]},
                "progress": 100,
                "message": "private lifecycle detail",
                "result": {
                    "schema_version": 2,
                    "command_key": "rss",
                    "resolved_route": "rss",
                    "emitted_sources": ["rss"],
                    "status": "partial",
                    "outcome": "partial",
                    "items_ingested": 3,
                    "items_skipped": 1,
                    "items_failed": 2,
                    "content_ids": [11, 12, 13],
                    "errors": [{"code": "fetch_error", "message": "private error"}],
                    "warnings": [],
                    "errors_omitted": 0,
                    "warnings_omitted": 0,
                    "source_outcomes": [
                        {
                            "source_key": "src_0123456789abcdefabcd",
                            "status": "partial",
                            "items_ingested": 3,
                            "items_failed": 2,
                            "errors": [{"code": "fetch_error", "message": "private source error"}],
                            "warnings": [],
                            "errors_omitted": 0,
                            "warnings_omitted": 0,
                        }
                    ],
                    "source_outcomes_omitted": 0,
                    "details": {},
                    "details_omitted": 0,
                },
                "problem": {
                    "title": "Partial source failure",
                    "status": 500,
                    "detail": "private problem detail",
                    "code": "source_partial",
                },
            },
        }
    )
    return row


@pytest.mark.asyncio
async def test_operation_listing_uses_opaque_keyset_cursor() -> None:
    conn = AsyncMock()
    conn.fetch.return_value = [
        _row(3, NOW),
        _row(2, NOW.replace(minute=1)),
        _row(1, NOW.replace(minute=2)),
    ]
    service = OperationService(connection=conn)

    page = await service.list(limit=2)

    assert [item.operation_id for item in page.data] == ["3", "2"]
    assert page.next_cursor is not None
    decoded_at, decoded_id = service._decode_cursor(page.next_cursor)
    assert decoded_at == NOW.replace(minute=1)
    assert decoded_id == 2
    assert "ORDER BY created_at DESC, id DESC" in conn.fetch.await_args.args[0]


@pytest.mark.asyncio
async def test_operation_listing_projects_sanitized_wire_compatible_summaries() -> None:
    conn = AsyncMock()
    row = _row(3, NOW)
    row["status"] = "failed"
    row["error"] = "private provider detail"
    row["payload"].update(
        {
            "input": {"url": "https://example.test/private?token=input-secret"},
            "result": {"checkpoint": {"content_ids": [1, 2]}},
            "resource": {
                "type": "digest",
                "id": "42",
                "url": "/api/v1/digests/42",
            },
            "problem": {
                "title": "Failed",
                "status": 500,
                "detail": "private problem detail",
            },
            "message": (
                "Fetching https://example.test/private?q=secret\x00 "
                "token=message-secret " + "x" * 600
            ),
        }
    )
    conn.fetch.return_value = [row]

    page = await OperationService(connection=conn).list(limit=1)

    summary = page.data[0]
    assert isinstance(summary, OperationSummary)
    serialized = summary.model_dump(mode="json")
    assert {"input", "result", "checkpoint", "resource", "problem"}.isdisjoint(serialized)
    assert summary.message == "Failed"
    _contract_models().OperationHandle.model_validate(serialized)


@pytest.mark.parametrize(
    ("status", "persisted_message", "expected_message"),
    [
        (JobStatus.QUEUED, "Authorization Bearer topsecret", "Queued"),
        (JobStatus.IN_PROGRESS, "token topsecret", "In progress"),
        (JobStatus.COMPLETED, "Finished for user alice@example.test", "Completed"),
        (JobStatus.FAILED, "Provider Acme returned private account text", "Failed"),
        (JobStatus.CANCELLED, "Cancelled mailbox private@example.test", "Cancelled"),
    ],
)
def test_operation_summary_uses_closed_lifecycle_message_labels(
    status: JobStatus,
    persisted_message: str,
    expected_message: str,
) -> None:
    job = _job(status=status)
    job.payload["message"] = persisted_message

    summary = OperationService.project_summary(job)

    assert summary.message == expected_message
    assert len(summary.message) <= 500


@pytest.mark.asyncio
async def test_operation_listing_filters_by_lifecycle_status() -> None:
    conn = AsyncMock()
    conn.fetch.return_value = []

    await OperationService(connection=conn).list(limit=25, status=OperationStatus.IN_PROGRESS)

    query, *arguments = conn.fetch.await_args.args
    assert "status = $4::text" in query
    assert arguments == [None, 0, list(LEGACY_OPERATION_TYPES), "in_progress", 26]


@pytest.mark.asyncio
async def test_ingestion_history_projects_only_compact_terminal_result_fields() -> None:
    conn = AsyncMock()
    conn.fetch.return_value = [_history_row(17, NOW)]
    service = OperationService(
        connection=conn,
        cursor_signing_key="history-cursor-signing-key-for-tests",
    )

    page = await service.list_ingestion_history(limit=25)

    assert page.model_dump(mode="json") == {
        "data": [
            {
                "operation_id": "17",
                "parent_operation_id": "91",
                "command_key": "rss",
                "operation_status": "completed",
                "outcome": "partial",
                "items_ingested": 3,
                "items_skipped": 1,
                "items_failed": 2,
                "source_outcomes": [
                    {
                        "source_key": "src_0123456789abcdefabcd",
                        "status": "partial",
                        "outcome": "partial",
                        "items_ingested": 3,
                        "items_failed": 2,
                        "error_codes": ["fetch_error"],
                        "warning_codes": None,
                    }
                ],
                "retry_count": 0,
                "problem_code": "source_partial",
                "status_url": "/api/v1/operations/17",
                "created_at": "2026-07-13T10:00:00Z",
                "completed_at": "2026-07-13T10:00:00Z",
            }
        ],
        "next_cursor": None,
    }
    serialized = page.model_dump_json()
    for private_value in (
        "content_ids",
        "configured_sources",
        "private lifecycle detail",
        "private error",
        "private source error",
        "private problem detail",
    ):
        assert private_value not in serialized


@pytest.mark.asyncio
async def test_ingestion_history_omits_untrusted_identifiers_and_machine_codes() -> None:
    completed = _history_row(19, NOW)
    source = completed["payload"]["result"]["source_outcomes"][0]
    source["errors"] = [
        {"code": "safe.code-1", "message": "safe"},
        {"code": "https://private.example/feed?token=secret", "message": "private"},
        {"code": "mailbox@example.test", "message": "private"},
        {"code": "token=private", "message": "private"},
        {"code": "sk-proj-private-token", "message": "private"},
        {"code": "token_private_mailbox", "message": "private"},
    ]
    source["warnings"] = [
        {"code": "feed_redirected", "message": "safe"},
        {"code": "Authorization Bearer private-token", "message": "private"},
    ]
    completed["payload"]["result"]["source_outcomes"].extend(
        [
            {
                "source_key": "https://private.example/feed?token=secret",
                "status": "error",
                "items_ingested": 0,
                "items_failed": 1,
                "errors": [],
                "warnings": [],
            },
            {
                "source_key": "mailbox@example.test",
                "status": "ok",
                "items_ingested": 1,
                "items_failed": 0,
                "errors": [],
                "warnings": [],
            },
        ]
    )
    completed["payload"]["problem"]["code"] = "sk-proj-private-token"
    failed = _history_row(18, NOW - timedelta(minutes=1), status=JobStatus.FAILED)
    failed["payload"]["problem"]["code"] = "token_private_mailbox"
    conn = AsyncMock()
    conn.fetch.return_value = [completed, failed]

    page = await OperationService(
        connection=conn,
        cursor_signing_key="history-cursor-signing-key-for-tests",
    ).list_ingestion_history()

    assert len(page.data[0].source_outcomes) == 1
    assert page.data[0].source_outcomes[0].source_key == "src_0123456789abcdefabcd"
    assert page.data[0].source_outcomes[0].error_codes == ["unexpected_error"]
    assert page.data[0].source_outcomes[0].warning_codes == [
        "feed_redirected",
        "unexpected_error",
    ]
    assert page.data[0].problem_code is None
    assert page.data[1].problem_code == "operation_failed"
    serialized = page.model_dump_json()
    for private_value in (
        "https://private.example",
        "mailbox@example.test",
        "token=private",
        "private-token",
        "token_private_mailbox",
    ):
        assert private_value not in serialized


@pytest.mark.asyncio
async def test_ingestion_history_compact_projection_ignores_unrelated_v2_fields() -> None:
    row = _history_row(21, NOW)
    result = row["payload"]["result"]
    result.update(
        {
            "resolved_route": "",
            "emitted_sources": [],
            "content_ids": "https://private.example/content",
            "errors": "mailbox@example.test",
            "warnings": {"token": "private"},
            "details": {"unsupported_private_field": "private"},
            "errors_omitted": -1,
        }
    )
    conn = AsyncMock()
    conn.fetch.return_value = [row, _history_row(20, NOW - timedelta(minutes=1))]
    service = OperationService(
        connection=conn,
        cursor_signing_key="history-cursor-signing-key-for-tests",
    )

    page = await service.list_ingestion_history(
        command_key="rss",
        configured_source_key="src_0123456789abcdefabcd",
        outcome="partial",
        limit=1,
    )

    assert page.next_cursor is not None
    assert page.data[0].command_key == "rss"
    assert page.data[0].outcome == "partial"
    assert page.data[0].items_ingested == 3
    assert [item.source_key for item in page.data[0].source_outcomes] == [
        "src_0123456789abcdefabcd"
    ]
    query = conn.fetch.await_args.args[0]
    assert "compact_result_eligible" in query
    assert "WITH ORDINALITY" in query
    assert "source_ordinality <= 100" in query
    assert "ORDER BY created_at DESC, id DESC" in query
    assert "(created_at, id) <" in query


@pytest.mark.asyncio
async def test_ingestion_history_rejects_malformed_required_compact_v2_fields() -> None:
    malformed_rows = []
    mutations = (
        ("schema_version", "2"),
        ("command_key", "https://private.example/feed"),
        ("outcome", "mailbox@example.test"),
        ("items_ingested", -1),
        ("items_failed", True),
        ("source_outcomes", {"token": "private"}),
    )
    for offset, (field, value) in enumerate(mutations):
        row = _history_row(40 - offset, NOW - timedelta(minutes=offset))
        row["payload"]["result"][field] = value
        malformed_rows.append(row)
    conn = AsyncMock()
    conn.fetch.return_value = malformed_rows

    page = await OperationService(
        connection=conn,
        cursor_signing_key="history-cursor-signing-key-for-tests",
    ).list_ingestion_history()

    assert [item.command_key for item in page.data] == ["rss"] * len(mutations)
    assert [item.outcome for item in page.data] == ["unknown"] * len(mutations)
    assert all(item.items_ingested is None for item in page.data)
    assert all(item.items_failed is None for item in page.data)
    assert all(not item.source_outcomes for item in page.data)


@pytest.mark.asyncio
async def test_ingestion_history_applies_every_fixed_filter_to_terminal_rows() -> None:
    conn = AsyncMock()
    conn.fetch.return_value = []
    service = OperationService(
        connection=conn,
        cursor_signing_key="history-cursor-signing-key-for-tests",
    )

    await service.list_ingestion_history(
        command_key="rss",
        configured_source_key="src_0123456789abcdefabcd",
        outcome="partial",
        status=OperationStatus.COMPLETED,
        parent_operation_id="91",
        created_after=datetime(2026, 7, 13, 4, tzinfo=UTC),
        created_before=datetime(2026, 7, 14, 4, tzinfo=UTC),
        limit=25,
    )

    query, *arguments = conn.fetch.await_args.args
    assert "status IN ('completed', 'failed', 'cancelled')" in query
    assert "created_at >= $8::timestamptz" in query
    assert "created_at < $9::timestamptz" in query
    assert "jsonb_array_elements" in query
    assert arguments[2:9] == [
        "rss",
        "src_0123456789abcdefabcd",
        "partial",
        "completed",
        91,
        datetime(2026, 7, 13, 4, tzinfo=UTC),
        datetime(2026, 7, 14, 4, tzinfo=UTC),
    ]


@pytest.mark.asyncio
async def test_ingestion_history_cursor_is_signed_and_bound_to_normalized_filters() -> None:
    conn = AsyncMock()
    conn.fetch.return_value = [
        _history_row(17, NOW),
        _history_row(16, NOW - timedelta(minutes=1)),
    ]
    service = OperationService(
        connection=conn,
        cursor_signing_key="history-cursor-signing-key-for-tests",
    )
    eastern = timezone(timedelta(hours=-4))

    first = await service.list_ingestion_history(
        command_key="rss",
        created_after=datetime(2026, 7, 13, 0, tzinfo=eastern),
        limit=1,
    )
    assert first.next_cursor is not None

    conn.fetch.return_value = []
    await service.list_ingestion_history(
        command_key="rss",
        created_after=datetime(2026, 7, 13, 4, tzinfo=UTC),
        cursor=first.next_cursor,
        limit=1,
    )
    with pytest.raises(ValueError, match="Invalid ingestion history cursor"):
        await service.list_ingestion_history(
            command_key="gmail",
            created_after=datetime(2026, 7, 13, 4, tzinfo=UTC),
            cursor=first.next_cursor,
            limit=1,
        )
    tamper_index = len(first.next_cursor) // 2
    tampered = (
        first.next_cursor[:tamper_index]
        + ("A" if first.next_cursor[tamper_index] != "A" else "B")
        + first.next_cursor[tamper_index + 1 :]
    )
    with pytest.raises(ValueError, match="Invalid ingestion history cursor"):
        await service.list_ingestion_history(
            command_key="rss",
            created_after=datetime(2026, 7, 13, 4, tzinfo=UTC),
            cursor=tampered,
            limit=1,
        )


def _signed_history_cursor(payload: dict, key: str) -> str:
    encoded_payload = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    envelope = {
        "payload": payload,
        "signature": hmac.new(key.encode(), encoded_payload, hashlib.sha256).hexdigest(),
    }
    return (
        base64.urlsafe_b64encode(
            json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
        )
        .decode()
        .rstrip("=")
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cursor",
    [
        "a" * 2049,
        _signed_history_cursor(
            {
                "v": 1,
                "position": {"created_at": "2026-07-13T10:00:00Z", "id": "invalid"},
                "filters": {},
            },
            "history-cursor-signing-key-for-tests",
        ),
        _signed_history_cursor(
            {
                "v": 99,
                "position": {"created_at": "2026-07-13T10:00:00Z", "id": "17"},
                "filters": {},
            },
            "history-cursor-signing-key-for-tests",
        ),
    ],
)
async def test_ingestion_history_rejects_oversize_or_invalid_signed_cursors(
    cursor: str,
) -> None:
    service = OperationService(
        connection=AsyncMock(),
        cursor_signing_key="history-cursor-signing-key-for-tests",
    )

    with pytest.raises(ValueError, match="Invalid ingestion history cursor"):
        await service.list_ingestion_history(cursor=cursor)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"limit": 0},
        {"limit": 101},
        {"status": OperationStatus.QUEUED},
        {"status": OperationStatus.IN_PROGRESS},
        {"parent_operation_id": "0"},
        {"parent_operation_id": "invalid"},
        {"parent_operation_id": "99999999999999999999"},
        {"configured_source_key": "https://private.example/feed"},
        {"created_after": datetime(2026, 7, 14, tzinfo=UTC), "created_before": NOW},
        {"created_after": NOW, "created_before": NOW},
        {"created_after": datetime(2026, 7, 13)},
    ],
)
async def test_ingestion_history_rejects_invalid_filters(kwargs: dict) -> None:
    service = OperationService(
        connection=AsyncMock(),
        cursor_signing_key="history-cursor-signing-key-for-tests",
    )

    with pytest.raises(ValueError):
        await service.list_ingestion_history(**kwargs)


@pytest.mark.asyncio
async def test_ingestion_history_fails_closed_without_cursor_signing_material() -> None:
    service = OperationService(connection=AsyncMock(), cursor_signing_key="")

    with pytest.raises(RuntimeError, match="OPERATION_CURSOR_SIGNING_KEY"):
        await service.list_ingestion_history()


@pytest.mark.asyncio
async def test_ingestion_history_legacy_command_precedence_and_nullable_counts() -> None:
    typed_input = _history_row(31, NOW)
    typed_input["payload"]["result"] = None
    typed_input["payload"]["input"] = {"kind": "rss"}
    typed_input["payload"]["source"] = "gmail"
    root_source = _history_row(30, NOW - timedelta(minutes=1))
    root_source["entrypoint"] = "ingest_content"
    root_source["payload"] = {"schema_version": 1, "source": "gmail"}
    entrypoint_only = _history_row(29, NOW - timedelta(minutes=2))
    entrypoint_only["entrypoint"] = "extract_url_content"
    entrypoint_only["payload"] = {}
    failed = _history_row(28, NOW - timedelta(minutes=3), status=JobStatus.FAILED)
    conn = AsyncMock()
    conn.fetch.return_value = [typed_input, root_source, entrypoint_only, failed]
    service = OperationService(
        connection=conn,
        cursor_signing_key="history-cursor-signing-key-for-tests",
    )

    page = await service.list_ingestion_history()

    assert [item.command_key for item in page.data] == ["rss", "gmail", "url", "rss"]
    for item in page.data[:3]:
        assert item.outcome == "unknown"
        assert (item.items_ingested, item.items_skipped, item.items_failed) == (
            None,
            None,
            None,
        )
    assert page.data[3].outcome == "failed"
    assert "NOT COALESCE" in conn.fetch.await_args.args[0]


@pytest.mark.asyncio
async def test_ingestion_history_query_includes_untagged_legacy_row(test_engine) -> None:
    operation_id = 9_108_123
    dsn = test_engine.url.render_as_string(hide_password=False)
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            """
            INSERT INTO pgqueuer_jobs (id, entrypoint, payload, status, completed_at)
            VALUES ($1, 'extract_url_content', '{}'::jsonb, 'completed', NOW())
            """,
            operation_id,
        )

        page = await OperationService(
            connection=conn,
            cursor_signing_key="history-cursor-signing-key-for-tests",
        ).list_ingestion_history(command_key="url", limit=100)

        item = next(item for item in page.data if item.operation_id == str(operation_id))
        assert item.command_key == "url"
        assert item.outcome == "unknown"
        assert item.items_ingested is None
    finally:
        await conn.execute("DELETE FROM pgqueuer_jobs WHERE id = $1", operation_id)
        await conn.close()


def test_invalid_operation_cursor_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid operation cursor"):
        OperationService._decode_cursor("not-a-valid-cursor")


@pytest.mark.asyncio
async def test_defer_atomically_checkpoints_and_requeues_parent() -> None:
    service = OperationService()
    queued = _row(8123, NOW)
    queued["status"] = "queued"
    queued["payload"]["result"] = {"stage": "ingestion"}
    update = AsyncMock(return_value=queued)
    service._update_returning = update  # type: ignore[method-assign]

    with bind_execution_claim(ExecutionClaim(job_id=8123, claim_generation=7)):
        handle = await service.defer(
            "8123",
            checkpoint={"stage": "ingestion"},
            progress=10,
            message="Waiting for source operations",
        )

    query, patch, operation_id, claim_generation = update.await_args.args
    assert "status = 'queued'" in query
    assert "execute_after" in query
    assert "status = 'in_progress'" in query
    assert "priority = LEAST(priority, -1)" in query
    assert operation_id == 8123
    assert claim_generation == 7
    assert "claim_generation = $3" in query
    assert __import__("json").loads(patch) == {
        "result": {"stage": "ingestion"},
        "progress": 10,
        "message": "Waiting for source operations",
    }
    assert handle.status is OperationStatus.QUEUED


@pytest.mark.asyncio
async def test_attach_completion_atomically_persists_result_resource_and_progress() -> None:
    service = OperationService()
    completed = _row(8123, NOW)
    completed["payload"].update(
        {
            "result": {"stage": "completed", "digest_id": 91},
            "resource": {
                "type": "digest",
                "id": "91",
                "url": "/api/v1/digests/91",
            },
            "progress": 100,
            "message": "Pipeline complete",
        }
    )
    update = AsyncMock(return_value=completed)
    service._update_returning = update  # type: ignore[method-assign]
    resource = ResourceReference(type="digest", id="91", url="/api/v1/digests/91")

    with bind_execution_claim(ExecutionClaim(job_id=8123, claim_generation=7)):
        await service.attach_completion(
            "8123",
            result={"stage": "completed", "digest_id": 91},
            resource=resource,
            message="Pipeline complete",
        )

    query, patch, operation_id, claim_generation = update.await_args.args
    assert operation_id == 8123
    assert claim_generation == 7
    assert "claim_generation = $3" in query
    assert __import__("json").loads(patch) == {
        "result": {"stage": "completed", "digest_id": 91},
        "resource": resource.model_dump(mode="json"),
        "progress": 100,
        "message": "Pipeline complete",
    }


@pytest.mark.asyncio
async def test_submit_child_reuses_terminal_parent_scoped_operation(monkeypatch) -> None:
    service = OperationService()
    existing = _job(
        job_id=44,
        entrypoint="ingestion.execute",
        status=JobStatus.COMPLETED,
        payload=OperationPayloadV2(
            operation_type=OperationType.INGESTION_EXECUTE,
            input={"kind": "rss"},
        ).model_dump(mode="json"),
    )
    lookup = AsyncMock(return_value=existing)
    enqueue = AsyncMock()
    monkeypatch.setattr(
        "src.services.operation_service.queue_setup.get_child_job_by_idempotency_key", lookup
    )
    monkeypatch.setattr("src.services.operation_service.queue_setup.enqueue_queue_job", enqueue)

    handle = await service.submit_child(
        "10",
        OperationType.INGESTION_EXECUTE,
        {"kind": "rss"},
        idempotency_key="pipeline:10:source:rss:abc",
    )

    assert handle.operation_id == "44"
    assert handle.status is OperationStatus.COMPLETED
    lookup.assert_awaited_once_with(
        10,
        "ingestion.execute",
        "parent:10:pipeline:10:source:rss:abc",
        conn=None,
    )
    enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_submit_child_namespaces_caller_key_by_parent(monkeypatch) -> None:
    service = OperationService()
    lookup = AsyncMock(return_value=None)
    enqueue = AsyncMock(side_effect=[(51, True), (52, True)])
    get_operation = AsyncMock(
        side_effect=[
            OperationService.project(_job(job_id=51)),
            OperationService.project(_job(job_id=52)),
        ]
    )
    monkeypatch.setattr(
        "src.services.operation_service.queue_setup.get_child_job_by_idempotency_key", lookup
    )
    monkeypatch.setattr("src.services.operation_service.queue_setup.enqueue_queue_job", enqueue)
    monkeypatch.setattr(service, "get", get_operation)

    for parent_id in (10, 11):
        await service.submit_child(
            parent_id,
            OperationType.INGESTION_EXECUTE,
            {"kind": "rss"},
            idempotency_key="source:rss",
        )

    assert [call.kwargs["idempotency_key"] for call in enqueue.await_args_list] == [
        "parent:10:source:rss",
        "parent:11:source:rss",
    ]


@pytest.mark.asyncio
async def test_pipeline_retry_preserves_checkpoint_and_requeues_failed_children() -> None:
    class Transaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    queued = _row(8123, NOW)
    queued["entrypoint"] = OperationType.PIPELINE_RUN.value
    queued["status"] = JobStatus.QUEUED.value
    locked = dict(queued)
    locked["status"] = JobStatus.FAILED.value
    conn = MagicMock()
    conn.transaction.return_value = Transaction()
    conn.fetchval = AsyncMock(side_effect=[8123, None, 8123, 8123, True])
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(side_effect=[locked, queued])
    conn.execute = AsyncMock()
    service = OperationService(connection=conn)

    await service.retry("8123")

    query = conn.fetchrow.await_args_list[-1].args[0]
    assert "pg_advisory_xact_lock" in conn.fetchval.await_args_list[1].args[0]
    assert "FOR UPDATE" in conn.fetchval.await_args_list[3].args[0]
    assert "WITH retried_children AS" in query
    assert query.index("UPDATE pgqueuer_jobs AS child") < query.index(
        "UPDATE pgqueuer_jobs AS parent"
    )
    assert "child.parent_job_id = $2" in query
    assert "retry_child_operation_ids" in query
    assert "child.status IN ('failed', 'cancelled')" in query
    assert "child.id" in query
    assert "parent.entrypoint = 'pipeline.run'" in query
    assert "entrypoint = 'pipeline.run'" in query
    assert "jsonb_build_object('result', parent.payload->'result')" in query


@pytest.mark.asyncio
async def test_pipeline_retry_requeues_only_checkpointed_failed_or_cancelled_children(
    test_engine,
) -> None:
    parent_id = 9_008_123
    tolerated_source_id = parent_id + 1
    failed_summary_id = parent_id + 2
    cancelled_digest_id = parent_id + 3
    dsn = test_engine.url.render_as_string(hide_password=False)
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            """
            INSERT INTO pgqueuer_jobs (id, entrypoint, payload, status, completed_at)
            VALUES ($1, 'pipeline.run', $2::jsonb, 'failed', NOW())
            """,
            parent_id,
            json.dumps(
                OperationPayloadV2(
                    operation_type=OperationType.PIPELINE_RUN,
                    input={"period": "daily"},
                    result={
                        "stage": "failed",
                        "retry_child_operation_ids": [failed_summary_id, cancelled_digest_id],
                    },
                ).model_dump(mode="json")
            ),
        )
        for child_id, operation_type in (
            (tolerated_source_id, OperationType.INGESTION_EXECUTE),
            (failed_summary_id, OperationType.SUMMARIZATION_RUN),
            (cancelled_digest_id, OperationType.DIGEST_CREATE),
        ):
            child_status = "cancelled" if child_id == cancelled_digest_id else "failed"
            await conn.execute(
                """
                INSERT INTO pgqueuer_jobs (
                    id, entrypoint, payload, status, parent_job_id, completed_at
                )
                VALUES (
                    $1,
                    $2,
                    $3::jsonb,
                    $4,
                    $5,
                    NOW()
                )
                """,
                child_id,
                operation_type.value,
                json.dumps(
                    OperationPayloadV2(
                        operation_type=operation_type,
                        input={},
                    ).model_dump(mode="json")
                ),
                child_status,
                parent_id,
            )

        await OperationService(connection=conn).retry(parent_id)

        statuses = {
            int(row["id"]): row["status"]
            for row in await conn.fetch(
                "SELECT id, status FROM pgqueuer_jobs WHERE id = ANY($1::bigint[])",
                [parent_id, tolerated_source_id, failed_summary_id, cancelled_digest_id],
            )
        }
        assert statuses == {
            parent_id: "queued",
            tolerated_source_id: "failed",
            failed_summary_id: "queued",
            cancelled_digest_id: "queued",
        }
    finally:
        await conn.execute(
            "DELETE FROM pgqueuer_jobs WHERE id = ANY($1::bigint[])",
            [tolerated_source_id, failed_summary_id, cancelled_digest_id, parent_id],
        )
        await conn.close()
