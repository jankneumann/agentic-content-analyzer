"""HTTP client for non-workflow CLI administration and read APIs.

The ApiClient reads api_base_url from Settings (profile-aware) and
authenticates via X-Admin-Key header. Durable workflow commands use
``src.clients.workflow_api_client.WorkflowApiClient`` instead.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Transient HTTP status codes that warrant one retry (per design.md D11).
_RETRYABLE_STATUS = frozenset({429, 502, 503, 504})
# Default retry policy for MCP-style endpoints: 1 retry, 1s backoff.
_DEFAULT_RETRY_ATTEMPTS = 1
_DEFAULT_RETRY_BACKOFF_SECONDS = 1.0
# Default per-request timeout for MCP endpoints (30s per D11).
_MCP_REQUEST_TIMEOUT = 30.0


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
            # FastAPI's redirect_slashes issues a 307 from no-slash to
            # trailing-slash collection routes (e.g. /api/v1/digests ->
            # /api/v1/digests/). httpx does not follow redirects by default,
            # which would surface the 307 as an HTTPStatusError.
            follow_redirects=True,
        )

    def health_check(self) -> bool:
        """Check if the backend API is reachable."""
        try:
            resp = self._client.get("/health")
            return bool(resp.status_code == 200)
        except httpx.ConnectError:
            return False

    # ── Digests (read) ──────────────────────────────────────────────────

    def list_digests(self, **params: Any) -> list[dict[str, Any]]:
        """GET /api/v1/digests/ — list digests (returns a JSON array)."""
        query = {k: v for k, v in params.items() if v is not None}
        resp = self._client.get("/api/v1/digests/", params=query)
        resp.raise_for_status()
        data: list[dict[str, Any]] = resp.json()
        return data

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

    def list_scripts(self, **params: Any) -> list[dict[str, Any]]:
        """GET /api/v1/scripts/ — list podcast scripts (returns a JSON array)."""
        query = {k: v for k, v in params.items() if v is not None}
        resp = self._client.get("/api/v1/scripts/", params=query)
        resp.raise_for_status()
        data: list[dict[str, Any]] = resp.json()
        return data

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

    # ── Sources ───────────────────────────────────────────────────────

    def list_sources(self, **params: Any) -> dict[str, Any]:
        """GET /api/v1/sources — list configured sources with counts."""
        query = {k: v for k, v in params.items() if v is not None}
        resp = self._client.get("/api/v1/sources", params=query)
        resp.raise_for_status()
        return self._resp_json(resp)

    def add_source(self, config: dict[str, Any], description: str | None = None) -> dict[str, Any]:
        """POST /api/v1/sources — add or update a source override."""
        payload: dict[str, Any] = {"config": config}
        if description is not None:
            payload["description"] = description
        resp = self._client.post("/api/v1/sources", json=payload)
        resp.raise_for_status()
        return self._resp_json(resp)

    def remove_source(self, key: str) -> dict[str, Any]:
        """DELETE /api/v1/sources/{key} — delete a source override.

        The natural key (e.g. ``blog:https://www.normaltech.ai/``) is
        URL-encoded so its ``:`` and ``/`` survive transit.
        """
        from urllib.parse import quote

        resp = self._client.delete(f"/api/v1/sources/{quote(key, safe='')}")
        resp.raise_for_status()
        return self._resp_json(resp)

    def set_source_enabled(self, key: str, enabled: bool) -> dict[str, Any]:
        """PATCH /api/v1/sources/{key} — enable/disable a source override."""
        from urllib.parse import quote

        resp = self._client.patch(
            f"/api/v1/sources/{quote(key, safe='')}", json={"enabled": enabled}
        )
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

    # ── MCP-aligned endpoints (with transient retry + 30s timeout) ──────

    def kb_search(self, query: str, limit: int = 20) -> dict[str, Any]:
        """GET /api/v1/kb/search — returns KBSearchResponse shape."""
        return self._request_with_retry(
            "GET", "/api/v1/kb/search", params={"q": query, "limit": limit}
        )

    def kb_list_topics(self, **params: Any) -> list[dict[str, Any]]:
        """GET /api/v1/kb/topics — list topics (returns a JSON array of TopicSummary)."""
        query = {k: v for k, v in params.items() if v is not None}
        resp = self._client.get("/api/v1/kb/topics", params=query)
        resp.raise_for_status()
        data: list[dict[str, Any]] = resp.json()
        return data

    def kb_get_topic(self, slug: str) -> dict[str, Any]:
        """GET /api/v1/kb/topics/{slug} — full TopicResponse (raises 404 if missing)."""
        resp = self._client.get(f"/api/v1/kb/topics/{slug}")
        resp.raise_for_status()
        return self._resp_json(resp)

    def kb_index(self, category: str | None = None) -> dict[str, Any]:
        """GET /api/v1/kb/index — cached KB index markdown."""
        params = {"category": category} if category else None
        resp = self._client.get("/api/v1/kb/index", params=params)
        resp.raise_for_status()
        return self._resp_json(resp)

    def kb_query(self, question: str, file_back: bool = False) -> dict[str, Any]:
        """POST /api/v1/kb/query — KBQueryResponse shape (LLM-backed Q&A)."""
        return self._request_with_retry(
            "POST", "/api/v1/kb/query", json={"question": question, "file_back": file_back}
        )

    def graph_query(self, query: str, limit: int = 20) -> dict[str, Any]:
        """POST /api/v1/graph/query — returns GraphQueryResponse shape."""
        return self._request_with_retry(
            "POST", "/api/v1/graph/query", json={"query": query, "limit": limit}
        )

    def graph_extract_entities(self, content_id: int) -> dict[str, Any]:
        """POST /api/v1/graph/extract-entities — push a content summary into the graph.

        Returns GraphExtractResponse shape {entities_added, relationships_added,
        graph_episode_id}. Raises httpx.HTTPStatusError on 404 (content missing)
        or 409 (no summary yet) — the caller maps those to user-facing messages.
        """
        return self._request_with_retry(
            "POST", "/api/v1/graph/extract-entities", json={"content_id": content_id}
        )

    def references_extract(self, **body: Any) -> dict[str, Any]:
        """POST /api/v1/references/extract — returns ReferencesExtractResponse shape."""
        payload = {k: v for k, v in body.items() if v is not None}
        return self._request_with_retry("POST", "/api/v1/references/extract", json=payload)

    def references_resolve(self, batch_size: int | None = None) -> dict[str, Any]:
        """POST /api/v1/references/resolve — returns ReferencesResolveResponse shape."""
        payload: dict[str, Any] = {}
        if batch_size is not None:
            payload["batch_size"] = batch_size
        return self._request_with_retry("POST", "/api/v1/references/resolve", json=payload)

    def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        attempts: int = _DEFAULT_RETRY_ATTEMPTS,
        backoff: float = _DEFAULT_RETRY_BACKOFF_SECONDS,
        timeout: float = _MCP_REQUEST_TIMEOUT,
    ) -> dict[str, Any]:
        """Issue an HTTP request with one retry on transient errors.

        Per design.md D11: retry once with backoff on {429, 502, 503, 504,
        ConnectError/ReadError}. Non-retryable 4xx propagates immediately.
        Timeout → raises httpx.TimeoutException (does NOT fall back to
        in-process — the caller decides).
        """
        last_exc: Exception | None = None
        for attempt in range(attempts + 1):
            try:
                resp = self._client.request(method, path, params=params, json=json, timeout=timeout)
                if resp.status_code in _RETRYABLE_STATUS and attempt < attempts:
                    logger.warning(
                        "api_client: %s %s returned %d, retrying in %.1fs (attempt %d/%d)",
                        method,
                        path,
                        resp.status_code,
                        backoff,
                        attempt + 1,
                        attempts + 1,
                    )
                    time.sleep(backoff)
                    continue
                resp.raise_for_status()
                return self._resp_json(resp)
            except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError) as exc:
                last_exc = exc
                if attempt < attempts:
                    logger.warning(
                        "api_client: %s %s transport error %s, retrying in %.1fs",
                        method,
                        path,
                        type(exc).__name__,
                        backoff,
                    )
                    time.sleep(backoff)
                    continue
                raise
        # Should be unreachable; satisfy type-checker.
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("retry loop exhausted without response or exception")

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
