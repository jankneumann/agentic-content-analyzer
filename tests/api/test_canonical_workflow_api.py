from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.workflow_dependencies import (
    get_operation_service,
    get_sources_config,
    get_upload_service,
)
from src.config.sources import GmailSource, SourcesConfig
from src.contracts.workflow_models import OperationHandle, OperationPage, UploadReference
from src.models.jobs import OperationEvent, OperationType
from src.services.operation_service import OperationConflictError, OperationNotFoundError


def _handle(operation_type="ingestion.execute", status="queued") -> OperationHandle:
    return OperationHandle.model_validate(
        {
            "operation_id": "41",
            "operation_type": operation_type,
            "status": status,
            "progress": 100 if status == "completed" else 0,
            "message": status.title(),
            "cancellable": status == "queued",
            "retry_count": 0,
            "status_url": "/api/v1/operations/41",
            "events_url": "/api/v1/operations/41/events",
            "created_at": datetime(2026, 7, 16, tzinfo=UTC),
        }
    )


@pytest.fixture
def operation_service() -> AsyncMock:
    service = AsyncMock()
    service.get.return_value = _handle()
    service.wait.return_value = _handle(status="completed")
    service.list.return_value = OperationPage(data=[_handle()], next_cursor="next")
    service.retry.return_value = _handle()
    service.cancel.return_value = _handle(status="completed")
    service.submit.return_value = _handle()
    service.event = MagicMock(
        side_effect=lambda handle, sequence=0: OperationEvent(
            event_id=f"{handle.operation_id}:{sequence}",
            operation_id=handle.operation_id,
            operation_type=handle.operation_type,
            status=handle.status,
            progress=handle.progress,
            message=handle.message,
            occurred_at=datetime(2026, 7, 16, tzinfo=UTC),
        )
    )
    return service


@pytest.fixture
def canonical_client(monkeypatch, operation_service: AsyncMock):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("APP_SECRET_KEY", "")
    monkeypatch.setenv("ADMIN_API_KEY", "")
    monkeypatch.setenv("WORKER_ENABLED", "false")
    from src.config.settings import get_settings

    get_settings.cache_clear()
    app.dependency_overrides[get_operation_service] = lambda: operation_service
    app.dependency_overrides[get_sources_config] = lambda: SourcesConfig(sources=[])
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_operation_status_wait_list_controls_and_sse(
    canonical_client: TestClient, operation_service: AsyncMock
) -> None:
    assert canonical_client.get("/api/v1/operations/41").status_code == 200
    assert (
        canonical_client.get("/api/v1/operations/41?wait_seconds=5").json()["status"] == "completed"
    )
    assert (
        canonical_client.get("/api/v1/operations?limit=10&cursor=opaque").json()["next_cursor"]
        == "next"
    )
    assert canonical_client.post("/api/v1/operations/41/retry").status_code == 202
    assert canonical_client.post("/api/v1/operations/41/cancel").status_code == 202
    operation_service.wait.assert_awaited_once_with("41", timeout_seconds=5)
    operation_service.list.assert_awaited_once_with(limit=10, cursor="opaque")

    operation_service.get.return_value = _handle(status="completed")
    events = canonical_client.get("/api/v1/operations/41/events", headers={"Last-Event-ID": "41:3"})
    assert events.headers["content-type"].startswith("text/event-stream")
    assert "id: 41:4" in events.text
    assert '"schema_version":2' in events.text


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (OperationNotFoundError("missing"), 404, "operation-not-found"),
        (OperationConflictError("terminal"), 409, "operation-conflict"),
    ],
)
def test_operation_failures_are_rfc7807(
    canonical_client, operation_service, error, status, code
) -> None:
    operation_service.get.side_effect = error
    response = canonical_client.get("/api/v1/operations/404")
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"].endswith(code)
    assert response.json()["instance"] == "/api/v1/operations/404"


def test_ingestion_is_strict_queued_and_rejects_internal_snapshots(
    canonical_client, operation_service
) -> None:
    response = canonical_client.post(
        "/api/v1/ingestions",
        json={"kind": "arxiv_paper", "identifier": "2401.12345"},
        headers={"Idempotency-Key": "paper-2401.12345"},
    )
    extra = canonical_client.post(
        "/api/v1/ingestions",
        json={"kind": "arxiv_paper", "identifier": "2401.12345", "unknown": True},
    )
    internal = canonical_client.post(
        "/api/v1/ingestions",
        json={"kind": "gmail", "configured_sources": [{"query": "secret"}]},
    )
    assert response.status_code == 202
    assert extra.status_code == internal.status_code == 422
    assert extra.headers["content-type"].startswith("application/problem+json")
    operation_service.submit.assert_awaited_once()
    assert operation_service.submit.await_args.args[0] is OperationType.INGESTION_EXECUTE
    assert operation_service.submit.await_args.kwargs["idempotency_key"] == "paper-2401.12345"


def test_config_backed_ingestion_snapshots_enabled_server_configuration(
    canonical_client, operation_service
) -> None:
    app.dependency_overrides[get_sources_config] = lambda: SourcesConfig(
        sources=[GmailSource(query="label:news", name="News")]
    )
    operation_service.submit.reset_mock()

    response = canonical_client.post("/api/v1/ingestions", json={"kind": "gmail"})

    assert response.status_code == 202
    payload = operation_service.submit.await_args.args[1]
    assert payload["configured_sources"] == [
        GmailSource(query="label:news", name="News").model_dump(mode="json")
    ]
    assert "label:news" not in response.text


def test_config_backed_ingestion_without_enabled_sources_fails_synchronously(
    canonical_client, operation_service
) -> None:
    response = canonical_client.post("/api/v1/ingestions", json={"kind": "gmail"})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "No enabled configured sources" in response.json()["detail"]
    operation_service.submit.assert_not_awaited()


@pytest.mark.parametrize(
    ("path", "payload", "operation_type"),
    [
        ("/api/v1/summarization-runs", {"content_ids": [1]}, OperationType.SUMMARIZATION_RUN),
        ("/api/v1/theme-analyses", {"query": {}}, OperationType.THEME_ANALYSIS_CREATE),
        (
            "/api/v1/digests",
            {
                "digest_type": "daily",
                "period_start": "2026-07-15T00:00:00Z",
                "period_end": "2026-07-16T00:00:00Z",
            },
            OperationType.DIGEST_CREATE,
        ),
        (
            "/api/v1/pipeline-runs",
            {
                "period": "daily",
                "period_start": "2026-07-15T00:00:00Z",
                "period_end": "2026-07-16T00:00:00Z",
            },
            OperationType.PIPELINE_RUN,
        ),
        ("/api/v1/podcast-scripts", {"digest_id": 2}, OperationType.PODCAST_SCRIPT_CREATE),
        ("/api/v1/podcasts", {"script_id": 3}, OperationType.PODCAST_AUDIO_CREATE),
        ("/api/v1/audio-digests", {"digest_id": 2}, OperationType.AUDIO_DIGEST_CREATE),
    ],
)
def test_workflow_submissions_compile_to_canonical_operations(
    canonical_client, operation_service, path, payload, operation_type
) -> None:
    operation_service.submit.reset_mock()
    response = canonical_client.post(path, json=payload)
    assert response.status_code == 202, response.text
    assert operation_service.submit.await_args.args[0] is operation_type
    assert operation_service.submit.await_args.args[1]


def test_upload_stores_reference_and_enforces_limits(canonical_client) -> None:
    upload = AsyncMock()
    upload.max_size_bytes = 10
    upload.store.return_value = UploadReference(
        id="upl_ref", filename="notes.txt", media_type="text/plain", size_bytes=5
    )
    app.dependency_overrides[get_upload_service] = lambda: upload
    ok = canonical_client.post(
        "/api/v1/uploads",
        data={"title": "Notes", "publication": "Journal"},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    large = canonical_client.post(
        "/api/v1/uploads", files={"file": ("notes.txt", b"way too large", "text/plain")}
    )
    unsupported = canonical_client.post(
        "/api/v1/uploads", files={"file": ("notes.bin", b"x", "model/gltf-binary")}
    )
    generic = canonical_client.post(
        "/api/v1/uploads",
        files={"file": ("notes.bin", b"x", "application/octet-stream")},
    )
    spoofed = canonical_client.post(
        "/api/v1/uploads", files={"file": ("notes.pdf", b"not a pdf", "application/pdf")}
    )
    extension_mismatch = canonical_client.post(
        "/api/v1/uploads", files={"file": ("notes.txt", b"hello", "application/pdf")}
    )
    assert ok.status_code == 201
    assert large.status_code == 413
    assert (
        unsupported.status_code
        == generic.status_code
        == spoofed.status_code
        == extension_mismatch.status_code
        == 422
    )
    upload.store.assert_awaited_once_with(
        b"hello",
        "notes.txt",
        "text/plain",
        title="Notes",
        publication="Journal",
    )


def test_upload_accepts_valid_pdf_and_rejects_executable_signature(canonical_client) -> None:
    upload = AsyncMock()
    upload.max_size_bytes = 1024
    upload.store.return_value = UploadReference(
        id="upl_pdf", filename="document.pdf", media_type="application/pdf", size_bytes=18
    )
    app.dependency_overrides[get_upload_service] = lambda: upload

    valid = canonical_client.post(
        "/api/v1/uploads",
        files={"file": ("document.pdf", b"%PDF-1.4\nvalid pdf", "application/pdf")},
    )
    executable = canonical_client.post(
        "/api/v1/uploads",
        files={"file": ("malware.pdf", b"\x7fELF\x02\x01\x01", "application/pdf")},
    )

    assert valid.status_code == 201
    assert executable.status_code == 422
    assert "content does not match" in executable.json()["detail"].lower()
    upload.store.assert_awaited_once()


def test_upload_exception_does_not_leak_internal_detail(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("APP_SECRET_KEY", "")
    monkeypatch.setenv("ADMIN_API_KEY", "")
    monkeypatch.setenv("WORKER_ENABLED", "false")
    from src.config.settings import get_settings

    get_settings.cache_clear()
    upload = AsyncMock()
    upload.max_size_bytes = 1024
    secret = "database password=supersecret"
    upload.store.side_effect = RuntimeError(secret)
    app.dependency_overrides[get_upload_service] = lambda: upload
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/uploads",
                files={"file": ("notes.txt", b"hello", "text/plain")},
            )
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    assert secret not in response.text
    assert response.json()["detail"] == "An internal error occurred"


def test_canonical_upload_requires_auth_and_uses_rfc7807(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("APP_SECRET_KEY", "")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")
    monkeypatch.setenv("WORKER_ENABLED", "false")
    from src.config.settings import get_settings

    get_settings.cache_clear()
    upload = AsyncMock()
    upload.max_size_bytes = 10
    upload.store.return_value = UploadReference(
        id="upl_ref", filename="notes.txt", media_type="text/plain", size_bytes=5
    )
    app.dependency_overrides[get_upload_service] = lambda: upload
    try:
        with TestClient(app) as client:
            missing = client.post(
                "/api/v1/uploads", files={"file": ("notes.txt", b"hello", "text/plain")}
            )
            invalid = client.post(
                "/api/v1/uploads",
                files={"file": ("notes.txt", b"hello", "text/plain")},
                headers={"X-Admin-Key": "invalid"},
            )
            accepted = client.post(
                "/api/v1/uploads",
                files={"file": ("notes.txt", b"hello", "text/plain")},
                headers={"X-Admin-Key": "test-admin-key"},
            )
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert missing.status_code == 401
    assert invalid.status_code == 403
    assert accepted.status_code == 201
    assert missing.headers["content-type"].startswith("application/problem+json")
    assert {"type", "title", "status", "detail"} <= missing.json().keys()


def test_legacy_workflow_mutations_are_not_composed(canonical_client) -> None:
    retired = (
        ("post", "/api/v1/contents/ingest"),
        ("get", "/api/v1/contents/ingest/status/task"),
        ("post", "/api/v1/contents/summarize"),
        ("get", "/api/v1/contents/summarize/status/task"),
        ("post", "/api/v1/themes/analyze"),
        ("post", "/api/v1/digests/generate"),
        ("post", "/api/v1/digests/1/regenerate"),
        ("post", "/api/v1/scripts/generate"),
        ("post", "/api/v1/scripts/1/regenerate"),
        ("post", "/api/v1/podcasts/generate"),
        ("post", "/api/v1/pipeline/run"),
        ("get", "/api/v1/pipeline/status/1"),
        ("post", "/api/v1/digests/1/audio"),
        ("post", "/api/v1/jobs/1/retry"),
        ("post", "/api/v1/content/save-url"),
        ("post", "/api/v1/content/save-page"),
        ("post", "/api/v1/summaries/1/regenerate"),
        ("post", "/api/v1/summaries/1/regenerate-with-feedback"),
        ("post", "/api/v1/summaries/1/commit-preview"),
    )
    assert all(
        canonical_client.request(method.upper(), path, json={}).status_code in {404, 405}
        for method, path in retired
    )
