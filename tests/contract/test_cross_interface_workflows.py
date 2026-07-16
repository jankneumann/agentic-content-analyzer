"""Cross-interface conformance for canonical durable workflow operations."""

from __future__ import annotations

import importlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from mcp.shared.exceptions import McpError
from pydantic import TypeAdapter, ValidationError
from typer.testing import CliRunner

from src.api.app import app
from src.api.workflow_dependencies import get_operation_service, get_sources_config
from src.cli.app import app as cli_app
from src.config.sources import SourcesConfig
from src.contracts.workflow_models import (
    DigestCreateRequest,
    IngestCommand,
    OperationHandle,
)
from src.ingestion.registry import SOURCE_REGISTRY, SourceRegistry
from src.ingestion.service import IngestionService
from src.mcp_tools import (
    ingestion as mcp_ingestion,
    runtime as mcp_runtime,
    workflows as mcp_workflows,
)
from src.models.jobs import JobRecord, JobStatus, OperationType
from src.services.operation_service import OperationService

DIGEST_INPUT = {
    "digest_type": "daily",
    "period_start": "2026-07-15T00:00:00Z",
    "period_end": "2026-07-16T00:00:00Z",
    "include_historical_context": False,
}
NORMALIZED_DIGEST_INPUT = DigestCreateRequest.model_validate(DIGEST_INPUT).model_dump(
    mode="json", exclude_none=True
)
IDEMPOTENCY_KEY = "digest-parity-1"
CREATED_AT = datetime(2026, 7, 16, tzinfo=UTC)


def _completed_digest_handle() -> OperationHandle:
    return OperationHandle.model_validate(
        {
            "operation_id": "701",
            "operation_type": "digest.create",
            "status": "completed",
            "progress": 100,
            "message": "Digest persisted",
            "cancellable": False,
            "retry_count": 0,
            "status_url": "/api/v1/operations/701",
            "events_url": "/api/v1/operations/701/events",
            "resource": {
                "type": "digest",
                "id": "17",
                "url": "/api/v1/digests/17",
            },
            "result": {"digest_id": 17},
            "created_at": CREATED_AT,
            "started_at": CREATED_AT,
            "completed_at": CREATED_AT,
        }
    )


class _CapturingClient:
    """Validate like WorkflowApiClient while replacing only HTTP transport."""

    def __init__(self, captures: dict[str, tuple[str, dict[str, Any], str | None]], key: str):
        self.captures = captures
        self.key = key
        self.ingestion_enqueues = 0
        self.closed = False

    def __enter__(self) -> _CapturingClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self.closed = True

    def submit_digest(
        self,
        request: DigestCreateRequest | dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> OperationHandle:
        normalized = DigestCreateRequest.model_validate(request).model_dump(
            mode="json", exclude_none=True
        )
        self.captures[self.key] = ("digest.create", normalized, idempotency_key)
        return _completed_digest_handle()

    def submit_ingestion(
        self,
        command: IngestCommand | dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> OperationHandle:
        TypeAdapter(IngestCommand).validate_python(command)
        self.ingestion_enqueues += 1
        return _completed_digest_handle()


@pytest.fixture
def canonical_api_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("APP_SECRET_KEY", "")
    monkeypatch.setenv("ADMIN_API_KEY", "")
    monkeypatch.setenv("WORKER_ENABLED", "false")
    from src.config.settings import get_settings

    get_settings.cache_clear()
    service = AsyncMock()
    service.submit.return_value = _completed_digest_handle()
    app.dependency_overrides[get_operation_service] = lambda: service
    app.dependency_overrides[get_sources_config] = lambda: SourcesConfig(sources=[])
    try:
        with TestClient(app) as client:
            yield client, service
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_completed_digest_contract_matches_every_python_interface(
    monkeypatch: pytest.MonkeyPatch,
    canonical_api_client: tuple[TestClient, AsyncMock],
) -> None:
    captures: dict[str, tuple[str, dict[str, Any], str | None]] = {}
    enqueued_payload: dict[str, Any] = {}

    async def enqueue(
        entrypoint: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        **_kwargs: Any,
    ) -> tuple[int, bool]:
        enqueued_payload.update(payload)
        captures["application"] = (entrypoint, payload["input"], idempotency_key)
        return 701, True

    async def get_job(_job_id: int, **_kwargs: Any) -> JobRecord:
        return JobRecord(
            id=701,
            entrypoint="digest.create",
            status=JobStatus.COMPLETED,
            payload=enqueued_payload
            | {
                "progress": 100,
                "message": "Digest persisted",
                "cancellable": False,
                "resource": {
                    "type": "digest",
                    "id": "17",
                    "url": "/api/v1/digests/17",
                },
                "result": {"digest_id": 17},
            },
            created_at=CREATED_AT,
            started_at=CREATED_AT,
            completed_at=CREATED_AT,
        )

    monkeypatch.setattr("src.services.operation_service.queue_setup.enqueue_queue_job", enqueue)
    monkeypatch.setattr("src.services.operation_service.queue_setup.get_job_status", get_job)
    application_handle = await OperationService().submit(
        OperationType.DIGEST_CREATE,
        NORMALIZED_DIGEST_INPUT,
        idempotency_key=IDEMPOTENCY_KEY,
    )

    cli_client = _CapturingClient(captures, "cli")
    cli_module = importlib.import_module("src.cli.app")
    monkeypatch.setattr(cli_module, "default_client_factory", lambda: cli_client)
    cli_result = CliRunner().invoke(
        cli_app,
        [
            "--json",
            "digest",
            "create",
            "--type",
            "daily",
            "--period-start",
            DIGEST_INPUT["period_start"],
            "--period-end",
            DIGEST_INPUT["period_end"],
            "--no-historical-context",
            "--idempotency-key",
            IDEMPOTENCY_KEY,
        ],
    )
    assert cli_result.exit_code == 0, cli_result.output
    cli_handle = OperationHandle.model_validate_json(cli_result.stdout)

    http_client, http_service = canonical_api_client
    http_response = http_client.post(
        "/api/v1/digests",
        json=DIGEST_INPUT,
        headers={"Idempotency-Key": IDEMPOTENCY_KEY},
    )
    assert http_response.status_code == 202, http_response.text
    http_call = http_service.submit.await_args
    captures["http"] = (
        http_call.args[0].value,
        http_call.args[1],
        http_call.kwargs["idempotency_key"],
    )
    http_handle = OperationHandle.model_validate(http_response.json())

    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("ACA_ADMIN_KEY", "secret")
    mcp_http_client = _CapturingClient(captures, "mcp_http")
    monkeypatch.setattr(mcp_runtime, "create_workflow_client", lambda: mcp_http_client)
    mcp_http_handle = await mcp_workflows.create_digest(
        **DIGEST_INPUT,
        idempotency_key=IDEMPOTENCY_KEY,
    )

    monkeypatch.delenv("ACA_API_BASE_URL")
    monkeypatch.delenv("ACA_ADMIN_KEY")
    mcp_in_process_service = AsyncMock()
    mcp_in_process_service.submit.return_value = _completed_digest_handle()
    monkeypatch.setattr(mcp_workflows, "OperationService", lambda: mcp_in_process_service)
    mcp_in_process_handle = await mcp_workflows.create_digest(
        **DIGEST_INPUT,
        idempotency_key=IDEMPOTENCY_KEY,
    )
    in_process_call = mcp_in_process_service.submit.await_args
    captures["mcp_in_process"] = (
        in_process_call.args[0].value,
        in_process_call.args[1],
        in_process_call.kwargs["idempotency_key"],
    )

    expected_submission = (
        "digest.create",
        NORMALIZED_DIGEST_INPUT,
        IDEMPOTENCY_KEY,
    )
    assert captures == dict.fromkeys(
        ("application", "cli", "http", "mcp_http", "mcp_in_process"), expected_submission
    )
    for raw_handle in (
        application_handle,
        cli_handle,
        http_handle,
        mcp_http_handle,
        mcp_in_process_handle,
    ):
        handle = OperationHandle.model_validate(raw_handle.model_dump(mode="json"))
        assert handle.status == "completed"
        assert handle.resource is not None
        assert handle.resource.type == "digest"
        assert handle.resource.id == "17"
        assert handle.resource.url == "/api/v1/digests/17"
    assert cli_client.closed
    assert mcp_http_client.closed


def _error_signature(error: dict[str, Any]) -> tuple[tuple[str | int, ...], str]:
    path = error.get("path", error.get("loc"))
    code = error.get("code", error.get("type"))
    assert isinstance(path, (list, tuple))
    assert isinstance(code, str)
    return tuple(path), code


@pytest.mark.contract
@pytest.mark.asyncio
async def test_invalid_ingestion_is_rejected_before_enqueue_with_matching_semantics(
    monkeypatch: pytest.MonkeyPatch,
    canonical_api_client: tuple[TestClient, AsyncMock],
) -> None:
    invalid = {"kind": "x_search", "prompt": "agents", "max_threads": 0}
    expected = (("x_search", "max_threads"), "greater_than_equal")
    signatures: dict[str, tuple[tuple[str | int, ...], str]] = {}

    orchestrator = MagicMock()
    descriptor = SOURCE_REGISTRY.get("x_search")
    registry = SourceRegistry([replace(descriptor, orchestrator=orchestrator)])
    with pytest.raises(ValidationError) as application_error:
        typed_command = TypeAdapter(IngestCommand).validate_python(invalid)
        IngestionService(registry=registry).execute(typed_command)
    signatures["application"] = _error_signature(application_error.value.errors()[0])
    orchestrator.assert_not_called()

    cli_client = _CapturingClient({}, "cli")
    cli_module = importlib.import_module("src.cli.app")
    monkeypatch.setattr(cli_module, "default_client_factory", lambda: cli_client)
    cli_result = CliRunner().invoke(
        cli_app,
        [
            "--json",
            "ingest",
            "x-search",
            "--prompt",
            "agents",
            "--max-threads",
            "0",
        ],
    )
    assert cli_result.exit_code == 2
    cli_problem = json.loads(cli_result.stdout)
    assert cli_problem["code"] == "validation_error"
    signatures["cli"] = _error_signature(cli_problem["errors"][0])
    assert cli_client.ingestion_enqueues == 0

    http_client, http_service = canonical_api_client
    http_response = http_client.post("/api/v1/ingestions", json=invalid)
    assert http_response.status_code == 422
    assert http_response.headers["content-type"].startswith("application/problem+json")
    http_problem = http_response.json()
    assert http_problem["code"] == "validation_error"
    signatures["http"] = _error_signature(http_problem["errors"][0])
    http_service.submit.assert_not_awaited()

    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("ACA_ADMIN_KEY", "secret")
    http_factory = MagicMock()
    monkeypatch.setattr(mcp_runtime, "create_workflow_client", http_factory)
    with pytest.raises(McpError) as mcp_http_error:
        await mcp_ingestion.ingest_x_search(prompt="agents", max_threads=0)
    mcp_http_problem = mcp_http_error.value.error.data["problem"]
    assert mcp_http_problem["code"] == "validation_error"
    signatures["mcp_http"] = _error_signature(mcp_http_problem["errors"][0])
    http_factory.assert_not_called()

    monkeypatch.delenv("ACA_API_BASE_URL")
    monkeypatch.delenv("ACA_ADMIN_KEY")
    operation_factory = MagicMock()
    monkeypatch.setattr(mcp_ingestion, "OperationService", operation_factory)
    with pytest.raises(McpError) as mcp_in_process_error:
        await mcp_ingestion.ingest_x_search(prompt="agents", max_threads=0)
    mcp_in_process_problem = mcp_in_process_error.value.error.data["problem"]
    assert mcp_in_process_problem["code"] == "validation_error"
    signatures["mcp_in_process"] = _error_signature(mcp_in_process_problem["errors"][0])
    operation_factory.assert_not_called()

    assert signatures == dict.fromkeys(
        ("application", "cli", "http", "mcp_http", "mcp_in_process"), expected
    )
