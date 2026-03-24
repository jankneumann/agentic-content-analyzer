"""Thin HTTP client for CLI → backend API communication.

The ApiClient reads api_base_url from Settings (profile-aware) and
authenticates via X-Admin-Key header. All CLI commands use this client
in HTTP mode (default), falling back to direct service calls when
--direct is passed or the backend is unreachable.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class SSEEvent:
    """Parsed Server-Sent Events event."""

    def __init__(self, data: str, event: str = "message", id: str | None = None):
        self.data = data
        self.event = event
        self.id = id

    def json(self) -> dict[str, Any]:
        import json

        result: dict[str, Any] = json.loads(self.data)
        return result


class ApiClient:
    """Sync HTTP client for CLI → API communication.

    Uses httpx with profile-aware base URL and admin key authentication.
    """

    def __init__(
        self,
        base_url: str,
        admin_key: str | None = None,
        timeout: float = 300.0,
    ):
        headers: dict[str, str] = {}
        if admin_key:
            headers["X-Admin-Key"] = admin_key
        self._client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers=headers,
        )

    def health_check(self) -> bool:
        """Check if the backend API is reachable."""
        try:
            resp = self._client.get("/health")
            return bool(resp.status_code == 200)
        except httpx.ConnectError:
            return False

    # ── Ingestion ──────────────────────────────────────────────────────

    def ingest(self, **params: Any) -> dict[str, Any]:
        """POST /api/v1/contents/ingest — trigger ingestion job.

        Returns IngestResponse dict with task_id, message, source, max_results.
        """
        # Remove None values so server-side defaults apply
        payload = {k: v for k, v in params.items() if v is not None}
        resp = self._client.post("/api/v1/contents/ingest", json=payload)
        resp.raise_for_status()
        return self._resp_json(resp)

    def stream_ingest_status(self, task_id: str) -> Iterator[SSEEvent]:
        """GET /api/v1/contents/ingest/status/{task_id} — stream SSE events."""
        yield from self._stream_sse(f"/api/v1/contents/ingest/status/{task_id}")

    # ── Summarization ──────────────────────────────────────────────────

    def summarize(self, **params: Any) -> dict[str, Any]:
        """POST /api/v1/contents/summarize — trigger summarization."""
        payload = {k: v for k, v in params.items() if v is not None}
        resp = self._client.post("/api/v1/contents/summarize", json=payload)
        resp.raise_for_status()
        return self._resp_json(resp)

    def stream_summarize_status(self, task_id: str) -> Iterator[SSEEvent]:
        """GET /api/v1/contents/summarize/status/{task_id} — stream SSE."""
        yield from self._stream_sse(f"/api/v1/contents/summarize/status/{task_id}")

    # ── Pipeline ───────────────────────────────────────────────────────

    def run_pipeline(self, **params: Any) -> dict[str, Any]:
        """POST /api/v1/pipeline/run — trigger full pipeline."""
        payload = {k: v for k, v in params.items() if v is not None}
        resp = self._client.post("/api/v1/pipeline/run", json=payload)
        resp.raise_for_status()
        return self._resp_json(resp)

    def stream_pipeline_status(self, job_id: int) -> Iterator[SSEEvent]:
        """GET /api/v1/pipeline/status/{job_id} — stream SSE."""
        yield from self._stream_sse(f"/api/v1/pipeline/status/{job_id}")

    # ── Digests ────────────────────────────────────────────────────────

    def create_digest(self, **params: Any) -> dict[str, Any]:
        """POST /api/v1/digests/generate — create a digest."""
        payload = {k: v for k, v in params.items() if v is not None}
        resp = self._client.post("/api/v1/digests/generate", json=payload)
        resp.raise_for_status()
        return self._resp_json(resp)

    # ── Jobs ───────────────────────────────────────────────────────────

    def list_jobs(self, **params: Any) -> dict[str, Any]:
        """GET /api/v1/jobs — list jobs with filters."""
        query = {k: v for k, v in params.items() if v is not None}
        resp = self._client.get("/api/v1/jobs", params=query)
        resp.raise_for_status()
        return self._resp_json(resp)

    def get_job(self, job_id: int) -> dict[str, Any]:
        """GET /api/v1/jobs/{job_id} — get job details."""
        resp = self._client.get(f"/api/v1/jobs/{job_id}")
        resp.raise_for_status()
        return self._resp_json(resp)

    def retry_job(self, job_id: int) -> dict[str, Any]:
        """POST /api/v1/jobs/{job_id}/retry — retry a failed job."""
        resp = self._client.post(f"/api/v1/jobs/{job_id}/retry")
        resp.raise_for_status()
        return self._resp_json(resp)

    # ── Digests (read) ──────────────────────────────────────────────────

    def list_digests(self, **params: Any) -> dict[str, Any]:
        """GET /api/v1/digests — list digests."""
        query = {k: v for k, v in params.items() if v is not None}
        resp = self._client.get("/api/v1/digests", params=query)
        resp.raise_for_status()
        return self._resp_json(resp)

    def get_digest(self, digest_id: int) -> dict[str, Any]:
        """GET /api/v1/digests/{digest_id} — get digest details."""
        resp = self._client.get(f"/api/v1/digests/{digest_id}")
        resp.raise_for_status()
        return self._resp_json(resp)

    def review_digest(self, digest_id: int, **params: Any) -> dict[str, Any]:
        """POST /api/v1/digests/{digest_id}/review — approve/reject digest."""
        payload = {k: v for k, v in params.items() if v is not None}
        resp = self._client.post(f"/api/v1/digests/{digest_id}/review", json=payload)
        resp.raise_for_status()
        return self._resp_json(resp)

    # ── Themes ────────────────────────────────────────────────────────

    def analyze_themes(self, **params: Any) -> dict[str, Any]:
        """POST /api/v1/themes/analyze — run theme analysis."""
        payload = {k: v for k, v in params.items() if v is not None}
        resp = self._client.post("/api/v1/themes/analyze", json=payload)
        resp.raise_for_status()
        return self._resp_json(resp)

    # ── Podcast Scripts ───────────────────────────────────────────────

    def generate_podcast(self, **params: Any) -> dict[str, Any]:
        """POST /api/v1/podcasts/generate — generate podcast script."""
        payload = {k: v for k, v in params.items() if v is not None}
        resp = self._client.post("/api/v1/podcasts/generate", json=payload)
        resp.raise_for_status()
        return self._resp_json(resp)

    def list_scripts(self, **params: Any) -> dict[str, Any]:
        """GET /api/v1/scripts — list podcast scripts."""
        query = {k: v for k, v in params.items() if v is not None}
        resp = self._client.get("/api/v1/scripts", params=query)
        resp.raise_for_status()
        return self._resp_json(resp)

    # ── Settings ──────────────────────────────────────────────────────

    def list_settings(self, **params: Any) -> dict[str, Any]:
        """GET /api/v1/settings/overrides — list setting overrides."""
        query = {k: v for k, v in params.items() if v is not None}
        resp = self._client.get("/api/v1/settings/overrides", params=query)
        resp.raise_for_status()
        return self._resp_json(resp)

    def get_setting(self, key: str) -> dict[str, Any]:
        """GET /api/v1/settings/overrides/{key} — get a setting."""
        resp = self._client.get(f"/api/v1/settings/overrides/{key}")
        resp.raise_for_status()
        return self._resp_json(resp)

    def set_setting(self, key: str, value: str) -> dict[str, Any]:
        """PUT /api/v1/settings/overrides/{key} — set a setting override."""
        resp = self._client.put(f"/api/v1/settings/overrides/{key}", json={"value": value})
        resp.raise_for_status()
        return self._resp_json(resp)

    def delete_setting(self, key: str) -> dict[str, Any]:
        """DELETE /api/v1/settings/overrides/{key} — remove a setting override."""
        resp = self._client.delete(f"/api/v1/settings/overrides/{key}")
        resp.raise_for_status()
        return self._resp_json(resp)

    # ── Prompts ───────────────────────────────────────────────────────

    def list_prompts(self, **params: Any) -> dict[str, Any]:
        """GET /api/v1/settings/overrides — list prompts (via overrides API)."""
        query = {"prefix": "prompt.", **{k: v for k, v in params.items() if v is not None}}
        resp = self._client.get("/api/v1/settings/overrides", params=query)
        resp.raise_for_status()
        return self._resp_json(resp)

    def get_prompt(self, key: str) -> dict[str, Any]:
        """GET /api/v1/settings/overrides/{key} — get prompt value."""
        resp = self._client.get(f"/api/v1/settings/overrides/{key}")
        resp.raise_for_status()
        return self._resp_json(resp)

    def set_prompt(self, key: str, value: str) -> dict[str, Any]:
        """PUT /api/v1/settings/overrides/{key} — set prompt override."""
        resp = self._client.put(f"/api/v1/settings/overrides/{key}", json={"value": value})
        resp.raise_for_status()
        return self._resp_json(resp)

    def reset_prompt(self, key: str) -> dict[str, Any]:
        """DELETE /api/v1/settings/overrides/{key} — reset prompt to default."""
        resp = self._client.delete(f"/api/v1/settings/overrides/{key}")
        resp.raise_for_status()
        return self._resp_json(resp)

    # ── Internal ───────────────────────────────────────────────────────

    @staticmethod
    def _resp_json(resp: httpx.Response) -> dict[str, Any]:
        """Extract JSON from response with proper typing."""
        data: dict[str, Any] = resp.json()
        return data

    def _stream_sse(self, path: str) -> Iterator[SSEEvent]:
        """Stream Server-Sent Events from the given path.

        Parses the SSE protocol (data:, event:, id: lines) and yields
        SSEEvent objects. Stops on connection close or terminal event.
        """
        with self._client.stream("GET", path) as response:
            response.raise_for_status()
            event_type = "message"
            event_id: str | None = None
            data_lines: list[str] = []

            for line in response.iter_lines():
                if line.startswith("data: "):
                    data_lines.append(line[6:])
                elif line.startswith("event: "):
                    event_type = line[7:]
                elif line.startswith("id: "):
                    event_id = line[4:]
                elif line == "":
                    # Empty line = end of event
                    if data_lines:
                        yield SSEEvent(
                            data="\n".join(data_lines),
                            event=event_type,
                            id=event_id,
                        )
                    data_lines = []
                    event_type = "message"
                    event_id = None

    def close(self) -> None:
        """Close the underlying httpx client."""
        self._client.close()


def get_api_client() -> ApiClient:
    """Create an ApiClient from current Settings.

    Reads api_base_url and admin_api_key from the active profile/env.
    """
    from src.config.settings import get_settings

    settings = get_settings()
    return ApiClient(
        base_url=settings.api_base_url,
        admin_key=getattr(settings, "admin_api_key", None),
        timeout=float(settings.api_timeout),
    )
