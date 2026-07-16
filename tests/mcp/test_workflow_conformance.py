"""Conformance tests for the canonical MCP workflow surface."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from inspect import signature
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.shared.exceptions import McpError

from src.contracts.workflow_models import (
    COMMAND_FIELD_SCHEMAS,
    CapabilityDocument,
    OperationHandle,
    Problem,
    UploadReference,
)
from src.mcp_tools import content, ingestion, operations, review, runtime, workflows
from src.mcp_tools.toolsets import CANONICAL_TOOL_NAMES, register_toolsets


def _handle(operation_type: str = "ingestion.execute") -> OperationHandle:
    return OperationHandle.model_validate(
        {
            "schema_version": 2,
            "operation_id": "42",
            "operation_type": operation_type,
            "status": "queued",
            "progress": 0,
            "message": "Queued",
            "cancellable": True,
            "retry_count": 0,
            "status_url": "/api/v1/operations/42",
            "events_url": "/api/v1/operations/42/events",
            "created_at": datetime.now(UTC),
        }
    )


@pytest.fixture(autouse=True)
def _clean_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ACA_API_BASE_URL", raising=False)
    monkeypatch.delenv("ACA_ADMIN_KEY", raising=False)
    monkeypatch.delenv("ACA_MCP_STRICT_HTTP", raising=False)


def test_registered_ingestion_tools_match_every_registry_command() -> None:
    assert set(ingestion.INGESTION_TOOL_BY_SOURCE) == set(COMMAND_FIELD_SCHEMAS)


def test_ingestion_tool_signatures_expose_every_public_contract_field() -> None:
    for source, tool in ingestion.INGESTION_TOOL_BY_SOURCE.items():
        expected = set(COMMAND_FIELD_SCHEMAS[source]["properties"]) - {
            "kind",
            "configured_sources",
        }
        assert expected <= set(signature(tool).parameters), source


def test_composition_root_registers_stable_unique_tool_names() -> None:
    server = MagicMock()
    registered: list[str] = []
    server.tool.side_effect = lambda: lambda function: registered.append(function.__name__)

    register_toolsets(server)

    assert registered == list(CANONICAL_TOOL_NAMES)
    assert len(registered) == len(set(registered))


@pytest.mark.asyncio
async def test_ingestion_http_mode_uses_shared_workflow_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("ACA_ADMIN_KEY", "secret")
    client = MagicMock()
    client.submit_ingestion.return_value = _handle()
    monkeypatch.setattr(runtime, "create_workflow_client", lambda: client)

    result = await ingestion.ingest_url("https://example.test/article", tags=["ai"])

    client.submit_ingestion.assert_called_once_with(
        {
            "kind": "url",
            "url": "https://example.test/article",
            "tags": ["ai"],
            "routing_mode": "auto",
            "force_reprocess": False,
        },
        idempotency_key=None,
    )
    client.close.assert_called_once()
    assert result.operation_id == "42"


@pytest.mark.asyncio
async def test_workflow_result_is_native_not_json_encoded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("ACA_ADMIN_KEY", "secret")
    client = MagicMock()
    client.submit_digest.return_value = _handle("digest.create")
    monkeypatch.setattr(runtime, "create_workflow_client", lambda: client)

    result = await workflows.create_digest("daily", "2026-07-15T00:00:00Z", "2026-07-16T00:00:00Z")

    assert result.operation_type == "digest.create"


@pytest.mark.asyncio
async def test_problem_is_preserved_as_typed_mcp_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("ACA_ADMIN_KEY", "secret")
    client = MagicMock()
    client.get_operation.side_effect = runtime.ProblemError(
        Problem(
            type="https://aca.example/problems/not-found",
            title="Operation not found",
            status=404,
            detail="Operation 999 does not exist",
            instance="/api/v1/operations/999",
            code="operation_not_found",
            errors=[{"path": ["operation_id"], "code": "missing", "message": "Not found"}],
        )
    )
    monkeypatch.setattr(runtime, "create_workflow_client", lambda: client)

    with pytest.raises(McpError) as exc_info:
        await operations.get_operation_status("999")

    data = exc_info.value.error.data
    assert data["code"] == "operation_not_found"
    assert data["problem"]["status"] == 404
    assert data["problem"]["instance"] == "/api/v1/operations/999"
    assert data["problem"]["errors"][0]["path"] == ["operation_id"]


@pytest.mark.asyncio
async def test_strict_http_mode_fails_closed_without_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ACA_MCP_STRICT_HTTP", "true")

    with pytest.raises(McpError) as exc_info:
        await operations.get_capabilities()

    assert exc_info.value.error.data["code"] == "mcp_http_configuration_error"


@pytest.mark.asyncio
async def test_partial_config_warns_to_stderr_and_uses_in_process(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.example.test")
    expected = CapabilityDocument(
        contract_version="2.0.0",
        source_commands=[],
        operation_types=[],
        resource_types=[],
    )
    monkeypatch.setattr(operations, "_in_process_capabilities", lambda **_: expected)

    result = await operations.get_capabilities()

    assert result == expected
    captured = capsys.readouterr()
    assert "ACA_ADMIN_KEY" in captured.err
    assert captured.out == ""


def test_upload_tool_accepts_bytes_not_server_local_paths() -> None:
    parameters = signature(ingestion.upload_content).parameters
    assert {"filename", "content_base64", "media_type"}.issubset(parameters)
    assert "path" not in parameters


@pytest.mark.asyncio
async def test_upload_http_mode_sends_caller_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("ACA_ADMIN_KEY", "secret")
    client = MagicMock()
    client.upload_bytes.return_value = UploadReference(
        id="up_1", filename="note.md", media_type="text/markdown", size_bytes=5
    )
    monkeypatch.setattr(runtime, "create_workflow_client", lambda: client)

    result = await ingestion.upload_content(
        "note.md", base64.b64encode(b"hello").decode(), "text/markdown"
    )

    client.upload_bytes.assert_called_once_with(
        "note.md", b"hello", "text/markdown", title=None, publication=None
    )
    assert result.id == "up_1"
    client.close.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "client_method"),
    [
        (operations.retry_operation, "retry_operation"),
        (operations.cancel_operation, "cancel_operation"),
    ],
)
async def test_operation_controls_use_shared_http_client(
    monkeypatch: pytest.MonkeyPatch, tool, client_method: str
) -> None:
    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("ACA_ADMIN_KEY", "secret")
    client = MagicMock()
    getattr(client, client_method).return_value = _handle()
    monkeypatch.setattr(runtime, "create_workflow_client", lambda: client)

    result = await tool("42")

    getattr(client, client_method).assert_called_once_with("42")
    assert result.operation_id == "42"


@pytest.mark.asyncio
async def test_wait_uses_agent_level_bounded_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("ACA_ADMIN_KEY", "secret")
    client = MagicMock()
    client.wait_operation.return_value = _handle()
    monkeypatch.setattr(runtime, "create_workflow_client", lambda: client)

    await operations.wait_for_operation("42", timeout_seconds=12, poll_interval=0.2)

    client.wait_operation.assert_called_once_with("42", timeout_seconds=12, poll_interval=0.2)


@pytest.mark.asyncio
async def test_in_process_workflow_uses_operation_application_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = MagicMock()
    service.submit = AsyncMock(return_value=_handle("summarization.run"))
    monkeypatch.setattr(workflows, "OperationService", lambda: service)

    result = await workflows.summarize_pending(content_ids=[1, 2])

    service.submit.assert_awaited_once()
    assert result.operation_type == "summarization.run"


@pytest.mark.asyncio
async def test_workflow_http_and_in_process_results_have_contract_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _handle("digest.create")
    client = MagicMock()
    client.submit_digest.return_value = expected
    monkeypatch.setattr(runtime, "create_workflow_client", lambda: client)
    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("ACA_ADMIN_KEY", "secret")
    http_result = await workflows.create_digest(
        "daily", "2026-07-15T00:00:00Z", "2026-07-16T00:00:00Z"
    )

    monkeypatch.delenv("ACA_API_BASE_URL")
    monkeypatch.delenv("ACA_ADMIN_KEY")
    service = MagicMock()
    service.submit = AsyncMock(return_value=expected)
    monkeypatch.setattr(workflows, "OperationService", lambda: service)
    local_result = await workflows.create_digest(
        "daily", "2026-07-15T00:00:00Z", "2026-07-16T00:00:00Z"
    )

    assert http_result.model_dump(mode="json") == local_result.model_dump(mode="json")


@pytest.mark.asyncio
async def test_http_content_tool_never_opens_local_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("ACA_ADMIN_KEY", "secret")
    request = MagicMock(return_value={"items": [], "total": 0})
    monkeypatch.setattr(runtime, "request_json", request)

    result = await content.search_content("agents", source_types="rss", limit=5)

    request.assert_called_once()
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_search_http_and_in_process_results_have_projection_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {"items": [{"content_id": 7, "score": 0.9}], "total": 1}
    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("ACA_ADMIN_KEY", "secret")
    monkeypatch.setattr(runtime, "request_json", MagicMock(return_value=expected))
    http_result = await content.search_content("agents", source_types="rss,blog", limit=5)

    monkeypatch.delenv("ACA_API_BASE_URL")
    monkeypatch.delenv("ACA_ADMIN_KEY")
    import src.services.search as search_module
    import src.storage.database as database_module

    search_service = MagicMock()
    search_service.search = AsyncMock(return_value=expected)
    monkeypatch.setattr(search_module, "HybridSearchService", lambda **_: search_service)
    context = MagicMock()
    context.__enter__.return_value = MagicMock()
    monkeypatch.setattr(database_module, "get_db", lambda: context)
    local_result = await content.search_content("agents", source_types="rss,blog", limit=5)

    assert http_result == local_result == expected


@pytest.mark.asyncio
async def test_review_http_and_in_process_results_have_projection_parity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewed_at = datetime(2026, 7, 16, tzinfo=UTC)
    expected = {
        "digest_id": 9,
        "status": "approved",
        "reviewed_by": "agent",
        "reviewed_at": reviewed_at.isoformat(),
    }
    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("ACA_ADMIN_KEY", "secret")
    monkeypatch.setattr(runtime, "request_json", MagicMock(return_value=expected))
    http_result = await review.finalize_review(9, "approve", reviewer="agent")

    monkeypatch.delenv("ACA_API_BASE_URL")
    monkeypatch.delenv("ACA_ADMIN_KEY")
    import src.services.review_service as review_module

    service = MagicMock()
    service.finalize_review = AsyncMock(
        return_value=SimpleNamespace(
            id=9,
            status=SimpleNamespace(value="approved"),
            reviewed_by="agent",
            reviewed_at=reviewed_at,
        )
    )
    monkeypatch.setattr(review_module, "ReviewService", lambda: service)
    local_result = await review.finalize_review(9, "approve", reviewer="agent")

    assert http_result == local_result == expected


@pytest.mark.asyncio
async def test_unmapped_http_tool_fails_closed_without_local_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ACA_API_BASE_URL", "https://api.example.test")
    monkeypatch.setenv("ACA_ADMIN_KEY", "secret")

    assert "ingest_reference" not in CANONICAL_TOOL_NAMES


@pytest.mark.asyncio
async def test_fastmcp_advertises_generated_contract_schemas() -> None:
    from src.mcp_server import mcp

    tools = {tool.name: tool for tool in await mcp.list_tools()}
    assert "operation_id" in tools["create_digest"].outputSchema["properties"]
    assert "operation_id" in tools["ingest_url"].outputSchema["properties"]
    assert "contract_version" in tools["get_capabilities"].outputSchema["properties"]
    query_schema = tools["create_digest"].inputSchema["properties"]["query"]
    assert "$ref" in str(query_schema)


@pytest.mark.asyncio
async def test_fastmcp_protocol_call_returns_structured_content() -> None:
    from src.mcp_server import mcp

    content_blocks, structured = await mcp.call_tool("get_capabilities", {})

    assert content_blocks
    assert structured["contract_version"]
    assert isinstance(structured["source_commands"], list)


@pytest.mark.asyncio
async def test_in_process_wait_uses_the_requested_agent_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = MagicMock()
    service.wait = AsyncMock(return_value=_handle())
    constructor = MagicMock(return_value=service)
    monkeypatch.setattr(operations, "OperationService", constructor)

    await operations.wait_for_operation("42", timeout_seconds=180, poll_interval=0.25)

    constructor.assert_called_once_with(poll_interval=0.25, max_wait_seconds=180)
    service.wait.assert_awaited_once_with("42", timeout_seconds=180)


@pytest.mark.asyncio
async def test_operation_status_rejects_unbounded_http_wait() -> None:
    with pytest.raises(McpError) as exc_info:
        await operations.get_operation_status("42", wait_seconds=31)

    assert exc_info.value.error.data["problem"]["status"] == 422
