"""Transport-neutral synchronous client for canonical workflow HTTP APIs."""

from __future__ import annotations

import mimetypes
import time
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, TypeAdapter, ValidationError

from src.contracts.workflow_models import (
    AudioDigestRequest,
    CapabilityDocument,
    ConfiguredSourcePage,
    DigestCreateRequest,
    IngestCommand,
    OperationHandle,
    OperationPage,
    PipelineRequest,
    PodcastAudioRequest,
    PodcastScriptRequest,
    Problem,
    SummarizationRequest,
    ThemeAnalysisRequest,
    UploadReference,
)

_ModelT = TypeVar("_ModelT", bound=BaseModel)
_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
_INGEST_ADAPTER: TypeAdapter[IngestCommand] = TypeAdapter(IngestCommand)


class ProblemError(RuntimeError):
    """An HTTP request failed with a canonical RFC 7807 problem."""

    def __init__(self, problem: Problem):
        super().__init__(problem.detail)
        self.problem = problem


class WorkflowApiClient:
    """Canonical HTTP client shared by CLI and MCP transports."""

    def __init__(
        self,
        base_url: str,
        *,
        admin_key: str | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        headers = {"X-Admin-Key": admin_key} if admin_key else None
        self._client = httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
            follow_redirects=True,
            transport=transport,
        )

    def __enter__(self) -> WorkflowApiClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def upload(
        self,
        path: str | Path,
        *,
        title: str | None = None,
        publication: str | None = None,
    ) -> UploadReference:
        file_path = Path(path)
        media_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        data = {
            key: value
            for key, value in {"title": title, "publication": publication}.items()
            if value
        }
        with file_path.open("rb") as stream:
            response = self._client.post(
                "/api/v1/uploads",
                files={"file": (file_path.name, stream, media_type)},
                data=data,
            )
        return self._decode(response, UploadReference)

    def submit_ingestion(
        self,
        command: IngestCommand | Mapping[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> OperationHandle:
        validated = _INGEST_ADAPTER.validate_python(command)
        return self._submit("/api/v1/ingestions", validated, idempotency_key=idempotency_key)

    def submit_summarization(
        self,
        request: SummarizationRequest | Mapping[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> OperationHandle:
        return self._submit_typed(
            "/api/v1/summarization-runs", SummarizationRequest, request, idempotency_key
        )

    def submit_theme_analysis(
        self,
        request: ThemeAnalysisRequest | Mapping[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> OperationHandle:
        return self._submit_typed(
            "/api/v1/theme-analyses", ThemeAnalysisRequest, request, idempotency_key
        )

    def submit_digest(
        self,
        request: DigestCreateRequest | Mapping[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> OperationHandle:
        return self._submit_typed("/api/v1/digests", DigestCreateRequest, request, idempotency_key)

    def submit_pipeline(
        self, request: PipelineRequest | Mapping[str, Any], *, idempotency_key: str | None = None
    ) -> OperationHandle:
        return self._submit_typed(
            "/api/v1/pipeline-runs", PipelineRequest, request, idempotency_key
        )

    def submit_podcast_script(
        self,
        request: PodcastScriptRequest | Mapping[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> OperationHandle:
        return self._submit_typed(
            "/api/v1/podcast-scripts", PodcastScriptRequest, request, idempotency_key
        )

    def submit_podcast_audio(
        self,
        request: PodcastAudioRequest | Mapping[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> OperationHandle:
        return self._submit_typed("/api/v1/podcasts", PodcastAudioRequest, request, idempotency_key)

    def submit_audio_digest(
        self, request: AudioDigestRequest | Mapping[str, Any], *, idempotency_key: str | None = None
    ) -> OperationHandle:
        return self._submit_typed(
            "/api/v1/audio-digests", AudioDigestRequest, request, idempotency_key
        )

    def list_operations(self, *, limit: int = 50, cursor: str | None = None) -> OperationPage:
        response = self._client.get("/api/v1/operations", params={"limit": limit, "cursor": cursor})
        return self._decode(response, OperationPage)

    def iter_operations(
        self, *, limit: int = 50, cursor: str | None = None
    ) -> Iterator[OperationHandle]:
        next_cursor = cursor
        while True:
            page = self.list_operations(limit=limit, cursor=next_cursor)
            yield from page.data
            if page.next_cursor is None:
                return
            next_cursor = page.next_cursor

    def get_operation(self, operation_id: str, *, wait_seconds: int = 0) -> OperationHandle:
        response = self._client.get(
            f"/api/v1/operations/{operation_id}", params={"wait_seconds": wait_seconds}
        )
        return self._decode(response, OperationHandle)

    def wait_operation(
        self,
        operation_id: str,
        *,
        timeout_seconds: float = 300.0,
        poll_interval: float = 0.5,
    ) -> OperationHandle:
        deadline = time.monotonic() + max(timeout_seconds, 0)
        latest = self.get_operation(operation_id)
        while latest.status not in _TERMINAL_STATUSES:
            remaining = deadline - time.monotonic()
            if remaining < 1:
                return latest
            wait_seconds = min(30, int(remaining))
            latest = self.get_operation(operation_id, wait_seconds=wait_seconds)
            if latest.status not in _TERMINAL_STATUSES and poll_interval:
                time.sleep(min(poll_interval, max(deadline - time.monotonic(), 0)))
        return latest

    def retry_operation(self, operation_id: str) -> OperationHandle:
        return self._decode(
            self._client.post(f"/api/v1/operations/{operation_id}/retry"), OperationHandle
        )

    def cancel_operation(self, operation_id: str) -> OperationHandle:
        return self._decode(
            self._client.post(f"/api/v1/operations/{operation_id}/cancel"), OperationHandle
        )

    def get_capabilities(self, *, limit: int = 50, cursor: str | None = None) -> CapabilityDocument:
        response = self._client.get(
            "/api/v1/capabilities", params={"limit": limit, "cursor": cursor}
        )
        return self._decode(response, CapabilityDocument)

    def list_configured_sources(
        self, *, limit: int = 50, cursor: str | None = None
    ) -> ConfiguredSourcePage:
        response = self._client.get(
            "/api/v1/configured-sources", params={"limit": limit, "cursor": cursor}
        )
        return self._decode(response, ConfiguredSourcePage)

    def _submit_typed(
        self,
        path: str,
        model: type[_ModelT],
        request: _ModelT | Mapping[str, Any],
        idempotency_key: str | None,
    ) -> OperationHandle:
        validated = request if isinstance(request, model) else model.model_validate(request)
        return self._submit(path, validated, idempotency_key=idempotency_key)

    def _submit(
        self, path: str, request: BaseModel, *, idempotency_key: str | None
    ) -> OperationHandle:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        response = self._client.post(
            path,
            json=request.model_dump(mode="json", exclude_none=True),
            headers=headers,
        )
        return self._decode(response, OperationHandle)

    @staticmethod
    def _decode(response: httpx.Response, model: type[_ModelT]) -> _ModelT:
        if response.is_error:
            try:
                problem = Problem.model_validate(response.json())
            except (ValueError, ValidationError):
                problem = Problem(
                    type="about:blank",
                    title="HTTP request failed",
                    status=response.status_code,
                    detail=response.text or response.reason_phrase,
                    instance=str(response.request.url),
                )
            raise ProblemError(problem)
        return model.model_validate(response.json())
