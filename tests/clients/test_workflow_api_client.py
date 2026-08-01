from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from src.clients.workflow_api_client import ProblemError, WorkflowApiClient


def _handle(operation_type: str = "ingestion.execute", status: str = "queued") -> dict[str, object]:
    return {
        "schema_version": 2,
        "operation_id": "op-1",
        "operation_type": operation_type,
        "status": status,
        "progress": 0 if status == "queued" else 100,
        "message": status,
        "cancellable": status == "queued",
        "retry_count": 0,
        "status_url": "/api/v1/operations/op-1",
        "events_url": "/api/v1/operations/op-1/events",
        "created_at": datetime.now(UTC).isoformat(),
    }


def _history_item(operation_id: str = "17") -> dict[str, object]:
    return {
        "operation_id": operation_id,
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
        "status_url": f"/api/v1/operations/{operation_id}",
        "created_at": "2026-07-13T10:00:00Z",
        "completed_at": "2026-07-13T10:01:00Z",
    }


def test_submissions_preserve_typed_payload_and_idempotency() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(202, json=_handle(), request=request)

    client = WorkflowApiClient("https://aca.test", transport=httpx.MockTransport(handler))
    result = client.submit_ingestion(
        {"kind": "x_search", "prompt": "agents", "max_threads": 4},
        idempotency_key="stable-key",
    )

    assert result.operation_type == "ingestion.execute"
    assert seen[0].headers["Idempotency-Key"] == "stable-key"
    assert (
        seen[0].content
        == b'{"kind":"x_search","prompt":"agents","max_threads":4,"force_reprocess":false}'
    )


@pytest.mark.parametrize(
    ("method", "operation_type", "path", "payload"),
    [
        ("submit_summarization", "summarization.run", "/api/v1/summarization-runs", {}),
        (
            "submit_theme_analysis",
            "theme_analysis.create",
            "/api/v1/theme-analyses",
            {"query": {}},
        ),
        (
            "submit_digest",
            "digest.create",
            "/api/v1/digests",
            {
                "digest_type": "daily",
                "period_start": "2026-07-15T00:00:00Z",
                "period_end": "2026-07-16T00:00:00Z",
            },
        ),
        (
            "submit_pipeline",
            "pipeline.run",
            "/api/v1/pipeline-runs",
            {
                "period": "daily",
                "period_start": "2026-07-15T00:00:00Z",
                "period_end": "2026-07-16T00:00:00Z",
            },
        ),
        (
            "submit_podcast_script",
            "podcast_script.create",
            "/api/v1/podcast-scripts",
            {"digest_id": 1},
        ),
        (
            "submit_podcast_audio",
            "podcast_audio.create",
            "/api/v1/podcasts",
            {"script_id": 1},
        ),
        (
            "submit_audio_digest",
            "audio_digest.create",
            "/api/v1/audio-digests",
            {"digest_id": 1},
        ),
    ],
)
def test_all_workflow_operation_types(
    method: str, operation_type: str, path: str, payload: dict[str, object]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == path
        return httpx.Response(202, json=_handle(operation_type), request=request)

    client = WorkflowApiClient("https://aca.test", transport=httpx.MockTransport(handler))
    assert getattr(client, method)(payload).operation_type == operation_type


def test_upload_uses_multipart_file(tmp_path: Path) -> None:
    document = tmp_path / "notes.txt"
    document.write_text("hello")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/uploads"
        assert b'filename="notes.txt"' in request.content
        assert b"hello" in request.content
        return httpx.Response(
            201,
            json={
                "id": "upload-1",
                "filename": "notes.txt",
                "media_type": "text/plain",
                "size_bytes": 5,
            },
            request=request,
        )

    client = WorkflowApiClient("https://aca.test", transport=httpx.MockTransport(handler))
    assert client.upload(document).id == "upload-1"


def test_upload_bytes_uses_public_multipart_boundary() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/uploads"
        assert b'filename="notes.txt"' in request.content
        assert b"hello" in request.content
        assert b'name="title"' in request.content
        assert b"Agent notes" in request.content
        return httpx.Response(
            201,
            json={
                "id": "upload-1",
                "filename": "notes.txt",
                "media_type": "text/plain",
                "size_bytes": 5,
            },
            request=request,
        )

    client = WorkflowApiClient("https://aca.test", transport=httpx.MockTransport(handler))
    upload = client.upload_bytes("notes.txt", b"hello", "text/plain", title="Agent notes")
    assert upload.id == "upload-1"


def test_request_json_exposes_authenticated_transport_without_client_internals() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/kb/search"
        assert request.url.params["limit"] == "2"
        assert request.headers["X-Admin-Key"] == "secret"
        assert request.content == b'{"query":"agents"}'
        return httpx.Response(200, json={"data": [{"id": 1}]}, request=request)

    client = WorkflowApiClient(
        "https://aca.test",
        admin_key="secret",
        transport=httpx.MockTransport(handler),
    )
    result = client.request_json(
        "POST", "/api/v1/kb/search", params={"limit": 2}, json={"query": "agents"}
    )
    assert result == {"data": [{"id": 1}]}


@pytest.mark.parametrize(
    ("method_name", "path", "response_json"),
    [
        (
            "list_operations",
            "/api/v1/operations",
            {"data": [], "next_cursor": None},
        ),
        (
            "get_capabilities",
            "/api/v1/capabilities",
            {
                "contract_version": "2.0.0",
                "source_commands": [],
                "operation_types": [],
                "resource_types": [],
                "next_cursor": None,
            },
        ),
        (
            "list_configured_sources",
            "/api/v1/configured-sources",
            {"data": [], "next_cursor": None},
        ),
    ],
)
def test_cursor_page_requests_omit_absent_cursor(
    method_name: str,
    path: str,
    response_json: dict[str, object],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == path
        assert request.url.params["limit"] == "25"
        assert "cursor" not in request.url.params
        return httpx.Response(200, json=response_json, request=request)

    client = WorkflowApiClient("https://aca.test", transport=httpx.MockTransport(handler))
    getattr(client, method_name)(limit=25)


@pytest.mark.parametrize(
    ("method_name", "path", "response_json"),
    [
        (
            "list_operations",
            "/api/v1/operations",
            {"data": [], "next_cursor": None},
        ),
        (
            "get_capabilities",
            "/api/v1/capabilities",
            {
                "contract_version": "2.0.0",
                "source_commands": [],
                "operation_types": [],
                "resource_types": [],
                "next_cursor": None,
            },
        ),
        (
            "list_configured_sources",
            "/api/v1/configured-sources",
            {"data": [], "next_cursor": None},
        ),
    ],
)
def test_cursor_page_requests_preserve_explicit_cursor(
    method_name: str,
    path: str,
    response_json: dict[str, object],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == path
        assert request.url.params["limit"] == "25"
        assert request.url.params["cursor"] == "opaque+/cursor=="
        return httpx.Response(200, json=response_json, request=request)

    client = WorkflowApiClient("https://aca.test", transport=httpx.MockTransport(handler))
    getattr(client, method_name)(limit=25, cursor="opaque+/cursor==")


def test_cursor_iteration_continues_without_duplication() -> None:
    cursors: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor") or None
        cursors.append(cursor)
        data = [_handle(status="completed")]
        if cursor:
            data[0]["operation_id"] = "op-2"
        return httpx.Response(
            200,
            json={"data": data, "next_cursor": "next" if not cursor else None},
            request=request,
        )

    client = WorkflowApiClient("https://aca.test", transport=httpx.MockTransport(handler))
    traversal = client.collect_operations(max_pages=2)
    assert [item.operation_id for item in traversal.data] == ["op-1", "op-2"]
    assert traversal.truncated is False
    assert traversal.next_cursor is None
    assert cursors == [None, "next"]


def test_operation_traversal_stops_at_page_budget_and_signals_continuation() -> None:
    cursors: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor") or None
        cursors.append(cursor)
        operation = _handle(status="completed")
        operation["operation_id"] = f"op-{len(cursors)}"
        return httpx.Response(
            200,
            json={"data": [operation], "next_cursor": f"cursor-{len(cursors)}"},
            request=request,
        )

    client = WorkflowApiClient("https://aca.test", transport=httpx.MockTransport(handler))
    traversal = client.collect_operations(limit=25, max_pages=2, status="queued")

    assert [item.operation_id for item in traversal.data] == ["op-1", "op-2"]
    assert traversal.next_cursor == "cursor-2"
    assert traversal.truncated is True
    assert cursors == [None, "cursor-1"]


def test_operation_list_serializes_status_and_omits_it_when_absent() -> None:
    queries: list[httpx.QueryParams] = []

    def handler(request: httpx.Request) -> httpx.Response:
        queries.append(request.url.params)
        return httpx.Response(200, json={"data": [], "next_cursor": None}, request=request)

    client = WorkflowApiClient("https://aca.test", transport=httpx.MockTransport(handler))
    client.list_operations()
    client.list_operations(status="in_progress")

    assert "status" not in queries[0]
    assert queries[1]["status"] == "in_progress"


def test_ingestion_history_omits_absent_filters_and_serializes_fixed_filters() -> None:
    queries: list[httpx.QueryParams] = []

    def handler(request: httpx.Request) -> httpx.Response:
        queries.append(request.url.params)
        return httpx.Response(
            200,
            json={"data": [_history_item()], "next_cursor": None},
            request=request,
        )

    client = WorkflowApiClient("https://aca.test", transport=httpx.MockTransport(handler))
    client.list_ingestion_history()
    page = client.list_ingestion_history(
        command_key="rss",
        configured_source_key="src_0123456789abcdefabcd",
        outcome="partial",
        status="completed",
        parent_operation_id="91",
        created_after=datetime(2026, 7, 13, 4, tzinfo=UTC),
        created_before=datetime(2026, 7, 14, 4, tzinfo=UTC),
        limit=25,
        cursor="opaque-cursor",
    )

    assert page.data[0].operation_id == "17"
    assert dict(queries[0]) == {"limit": "50"}
    assert dict(queries[1]) == {
        "command_key": "rss",
        "configured_source_key": "src_0123456789abcdefabcd",
        "outcome": "partial",
        "status": "completed",
        "parent_operation_id": "91",
        "created_after": "2026-07-13T04:00:00+00:00",
        "created_before": "2026-07-14T04:00:00+00:00",
        "limit": "25",
        "cursor": "opaque-cursor",
    }


def test_ingestion_history_traversal_forwards_filters_and_stops_at_budget() -> None:
    queries: list[httpx.QueryParams] = []

    def handler(request: httpx.Request) -> httpx.Response:
        queries.append(request.url.params)
        operation_id = str(17 - len(queries))
        return httpx.Response(
            200,
            json={
                "data": [_history_item(operation_id)],
                "next_cursor": f"cursor-{len(queries)}",
            },
            request=request,
        )

    client = WorkflowApiClient("https://aca.test", transport=httpx.MockTransport(handler))
    traversal = client.collect_ingestion_history(
        configured_source_key="src_0123456789abcdefabcd",
        outcome="partial",
        limit=25,
        max_pages=2,
    )

    assert [item.operation_id for item in traversal.data] == ["16", "15"]
    assert traversal.next_cursor == "cursor-2"
    assert traversal.truncated is True
    assert [query.get("cursor") for query in queries] == [None, "cursor-1"]
    assert all(query["configured_source_key"] == "src_0123456789abcdefabcd" for query in queries)
    assert all(query["outcome"] == "partial" for query in queries)


@pytest.mark.parametrize("max_pages", [0, 101])
def test_ingestion_history_traversal_rejects_invalid_page_budget(max_pages: int) -> None:
    client = WorkflowApiClient(
        "https://aca.test",
        transport=httpx.MockTransport(lambda _: httpx.Response(500)),
    )

    with pytest.raises(ValueError, match="max_pages"):
        client.collect_ingestion_history(max_pages=max_pages)


def test_bounded_wait_returns_latest_nonterminal_handle(monkeypatch: pytest.MonkeyPatch) -> None:
    client = WorkflowApiClient(
        "https://aca.test", transport=httpx.MockTransport(lambda _: httpx.Response(500))
    )
    monkeypatch.setattr(
        client, "get_operation", lambda *_args, **_kwargs: type("H", (), {"status": "queued"})()
    )
    assert client.wait_operation("op-1", timeout_seconds=0).status == "queued"


def test_problem_error_preserves_full_rfc7807_document() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "type": "https://aca.test/problems/validation",
                "title": "Invalid command",
                "status": 422,
                "detail": "prompt is required",
                "instance": "/api/v1/ingestions",
                "code": "validation_error",
                "errors": [{"field": "prompt"}],
            },
            request=request,
        )

    client = WorkflowApiClient("https://aca.test", transport=httpx.MockTransport(handler))
    with pytest.raises(ProblemError) as exc_info:
        client.submit_ingestion({"kind": "gmail"})
    assert exc_info.value.problem.code == "validation_error"
    assert exc_info.value.problem.errors == [{"field": "prompt"}]
