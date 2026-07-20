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
    assert [item.operation_id for item in client.iter_operations()] == ["op-1", "op-2"]
    assert cursors == [None, "next"]


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
