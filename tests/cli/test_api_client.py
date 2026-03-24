"""Tests for ApiClient HTTP client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.cli.api_client import ApiClient, SSEEvent, get_api_client

# ── Helpers ─────────────────────────────────────────────────────────────


def _make_client(
    handler,
    base_url: str = "http://test",
    admin_key: str | None = "test-key",
) -> ApiClient:
    """Create an ApiClient with a mock transport handler."""
    client = ApiClient(base_url=base_url, admin_key=admin_key)
    client._client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url=base_url,
        headers=dict(client._client.headers),
    )
    return client


def _sse_response(events: list[str]) -> httpx.Response:
    """Build a streaming SSE response from raw SSE text blocks.

    Each string in *events* should be a complete SSE event including
    the trailing blank line, e.g. ``"data: {}\n\n"``.
    """
    body = "".join(events)
    return httpx.Response(
        200,
        content=body.encode(),
        headers={"content-type": "text/event-stream"},
    )


# ── SSEEvent ────────────────────────────────────────────────────────────


class TestSSEEvent:
    def test_basic_attributes(self):
        evt = SSEEvent(data='{"ok": true}', event="status", id="1")
        assert evt.data == '{"ok": true}'
        assert evt.event == "status"
        assert evt.id == "1"

    def test_defaults(self):
        evt = SSEEvent(data="hello")
        assert evt.event == "message"
        assert evt.id is None

    def test_json(self):
        evt = SSEEvent(data='{"count": 3}')
        assert evt.json() == {"count": 3}


# ── __init__ ────────────────────────────────────────────────────────────


class TestApiClientInit:
    def test_sets_base_url(self):
        client = ApiClient(base_url="http://localhost:8000")
        assert str(client._client.base_url) == "http://localhost:8000"
        client.close()

    def test_sets_timeout(self):
        client = ApiClient(base_url="http://test", timeout=60.0)
        assert client._client.timeout.read == 60.0
        assert client._client.timeout.connect == 10.0
        client.close()

    def test_default_timeout(self):
        client = ApiClient(base_url="http://test")
        assert client._client.timeout.read == 300.0
        client.close()

    def test_sets_admin_key_header(self):
        client = ApiClient(base_url="http://test", admin_key="my-secret")
        assert client._client.headers["X-Admin-Key"] == "my-secret"
        client.close()

    def test_no_admin_key_header_when_none(self):
        client = ApiClient(base_url="http://test", admin_key=None)
        assert "X-Admin-Key" not in client._client.headers
        client.close()


# ── health_check ────────────────────────────────────────────────────────


class TestHealthCheck:
    def test_returns_true_on_200(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/health"
            return httpx.Response(200, json={"status": "ok"})

        api = _make_client(handler)
        assert api.health_check() is True

    def test_returns_false_on_non_200(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"status": "degraded"})

        api = _make_client(handler)
        assert api.health_check() is False

    def test_returns_false_on_connect_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        api = _make_client(handler)
        assert api.health_check() is False


# ── ingest ──────────────────────────────────────────────────────────────


class TestIngest:
    def test_post_with_payload(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/contents/ingest"
            assert request.method == "POST"
            import json

            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"task_id": "abc", "message": "ok"})

        api = _make_client(handler)
        result = api.ingest(source="gmail", max_results=10)
        assert result == {"task_id": "abc", "message": "ok"}
        assert captured["body"] == {"source": "gmail", "max_results": 10}

    def test_strips_none_values(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            import json

            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"task_id": "x"})

        api = _make_client(handler)
        api.ingest(source="rss", max_results=None, query=None)
        assert captured["body"] == {"source": "rss"}

    def test_raises_on_error_status(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(422, json={"detail": "bad"})

        api = _make_client(handler)
        with pytest.raises(httpx.HTTPStatusError):
            api.ingest(source="gmail")


# ── stream_ingest_status ────────────────────────────────────────────────


class TestStreamIngestStatus:
    def test_yields_sse_events(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert "/api/v1/contents/ingest/status/task-1" in str(request.url)
            return _sse_response(
                [
                    'data: {"status": "running", "processed": 2}\n\n',
                    'data: {"status": "completed", "processed": 5}\n\n',
                ]
            )

        api = _make_client(handler)
        events = list(api.stream_ingest_status("task-1"))
        assert len(events) == 2
        assert events[0].json() == {"status": "running", "processed": 2}
        assert events[1].json() == {"status": "completed", "processed": 5}

    def test_parses_event_type_and_id(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return _sse_response(
                [
                    "event: progress\nid: 42\ndata: {}\n\n",
                ]
            )

        api = _make_client(handler)
        events = list(api.stream_ingest_status("t"))
        assert len(events) == 1
        assert events[0].event == "progress"
        assert events[0].id == "42"

    def test_multiline_data(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return _sse_response(
                [
                    "data: line1\ndata: line2\n\n",
                ]
            )

        api = _make_client(handler)
        events = list(api.stream_ingest_status("t"))
        assert events[0].data == "line1\nline2"


# ── summarize ───────────────────────────────────────────────────────────


class TestSummarize:
    def test_post_summarize(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/contents/summarize"
            assert request.method == "POST"
            return httpx.Response(200, json={"task_id": "s1", "count": 3})

        api = _make_client(handler)
        result = api.summarize(source="gmail", status="pending")
        assert result == {"task_id": "s1", "count": 3}


# ── run_pipeline ────────────────────────────────────────────────────────


class TestRunPipeline:
    def test_post_pipeline(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/pipeline/run"
            import json

            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"job_id": 99})

        api = _make_client(handler)
        result = api.run_pipeline(digest_type="daily", sources=["gmail", "rss"])
        assert result == {"job_id": 99}
        assert captured["body"] == {"digest_type": "daily", "sources": ["gmail", "rss"]}


# ── create_digest ───────────────────────────────────────────────────────


class TestCreateDigest:
    def test_post_digest(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/digests/generate"
            return httpx.Response(200, json={"digest_id": 7})

        api = _make_client(handler)
        result = api.create_digest(digest_type="weekly")
        assert result == {"digest_id": 7}


# ── list_jobs ───────────────────────────────────────────────────────────


class TestListJobs:
    def test_get_with_query_params(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/jobs"
            assert request.url.params["status"] == "failed"
            return httpx.Response(200, json={"jobs": [], "total": 0})

        api = _make_client(handler)
        result = api.list_jobs(status="failed")
        assert result == {"jobs": [], "total": 0}

    def test_strips_none_params(self):
        def handler(request: httpx.Request) -> httpx.Response:
            # None values should not appear in query string
            assert "status" not in str(request.url)
            return httpx.Response(200, json={"jobs": []})

        api = _make_client(handler)
        api.list_jobs(status=None)


# ── get_job ─────────────────────────────────────────────────────────────


class TestGetJob:
    def test_get_job_by_id(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/jobs/42"
            return httpx.Response(200, json={"id": 42, "status": "completed"})

        api = _make_client(handler)
        result = api.get_job(42)
        assert result["id"] == 42


# ── retry_job ───────────────────────────────────────────────────────────


class TestRetryJob:
    def test_post_retry(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/jobs/5/retry"
            assert request.method == "POST"
            return httpx.Response(200, json={"id": 5, "status": "pending"})

        api = _make_client(handler)
        result = api.retry_job(5)
        assert result["status"] == "pending"


# ── list_settings ───────────────────────────────────────────────────────


class TestListSettings:
    def test_get_settings(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/settings/overrides"
            return httpx.Response(200, json={"overrides": []})

        api = _make_client(handler)
        result = api.list_settings()
        assert result == {"overrides": []}


# ── set_setting ─────────────────────────────────────────────────────────


class TestSetSetting:
    def test_put_setting(self):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/settings/overrides/model_summarization"
            assert request.method == "PUT"
            import json

            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"key": "model_summarization", "value": "gpt-4"})

        api = _make_client(handler)
        result = api.set_setting("model_summarization", "gpt-4")
        assert captured["body"] == {"value": "gpt-4"}
        assert result["key"] == "model_summarization"


# ── delete_setting ──────────────────────────────────────────────────────


class TestDeleteSetting:
    def test_delete_setting(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/settings/overrides/model_summarization"
            assert request.method == "DELETE"
            return httpx.Response(200, json={"deleted": True})

        api = _make_client(handler)
        result = api.delete_setting("model_summarization")
        assert result["deleted"] is True


# ── list_prompts ────────────────────────────────────────────────────────


class TestListPrompts:
    def test_includes_prefix_param(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.params["prefix"] == "prompt."
            return httpx.Response(200, json={"overrides": []})

        api = _make_client(handler)
        api.list_prompts()

    def test_merges_extra_params(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.params["prefix"] == "prompt."
            assert request.url.params["category"] == "pipeline"
            return httpx.Response(200, json={"overrides": []})

        api = _make_client(handler)
        api.list_prompts(category="pipeline")


# ── analyze_themes ──────────────────────────────────────────────────────


class TestAnalyzeThemes:
    def test_post_themes(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/themes/analyze"
            return httpx.Response(200, json={"themes": ["AI agents"]})

        api = _make_client(handler)
        result = api.analyze_themes(days=7)
        assert result == {"themes": ["AI agents"]}


# ── generate_podcast ────────────────────────────────────────────────────


class TestGeneratePodcast:
    def test_post_podcast(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/podcasts/generate"
            return httpx.Response(200, json={"script_id": 1})

        api = _make_client(handler)
        result = api.generate_podcast(digest_id=10)
        assert result == {"script_id": 1}


# ── list_digests / get_digest / review_digest ───────────────────────────


class TestDigestRead:
    def test_list_digests(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/digests"
            return httpx.Response(200, json={"digests": []})

        api = _make_client(handler)
        assert api.list_digests() == {"digests": []}

    def test_get_digest(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/digests/3"
            return httpx.Response(200, json={"id": 3})

        api = _make_client(handler)
        assert api.get_digest(3) == {"id": 3}

    def test_review_digest(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/digests/3/review"
            assert request.method == "POST"
            return httpx.Response(200, json={"status": "approved"})

        api = _make_client(handler)
        assert api.review_digest(3, action="approve")["status"] == "approved"


# ── stream helpers (pipeline / summarize) ───────────────────────────────


class TestStreamPipelineStatus:
    def test_yields_events(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert "/api/v1/pipeline/status/77" in str(request.url)
            return _sse_response(['data: {"stage": "ingest"}\n\n'])

        api = _make_client(handler)
        events = list(api.stream_pipeline_status(77))
        assert len(events) == 1
        assert events[0].json()["stage"] == "ingest"


class TestStreamSummarizeStatus:
    def test_yields_events(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert "/api/v1/contents/summarize/status/s1" in str(request.url)
            return _sse_response(['data: {"done": true}\n\n'])

        api = _make_client(handler)
        events = list(api.stream_summarize_status("s1"))
        assert events[0].json()["done"] is True


# ── close ───────────────────────────────────────────────────────────────


class TestClose:
    def test_close(self):
        client = ApiClient(base_url="http://test")
        client.close()
        # After close, the client should be unusable
        with pytest.raises(RuntimeError, match="client has been closed"):
            client._client.get("/health")


# ── get_api_client factory ──────────────────────────────────────────────


class TestGetApiClient:
    @patch("src.config.settings.get_settings")
    def test_creates_client_from_settings(self, mock_get_settings):
        mock_settings = MagicMock()
        mock_settings.api_base_url = "http://prod:8000"
        mock_settings.admin_api_key = "prod-key"
        mock_settings.api_timeout = 120
        mock_get_settings.return_value = mock_settings

        api = get_api_client()
        try:
            assert str(api._client.base_url) == "http://prod:8000"
            assert api._client.headers["X-Admin-Key"] == "prod-key"
            assert api._client.timeout.read == 120.0
        finally:
            api.close()

    @patch("src.config.settings.get_settings")
    def test_no_admin_key_when_missing(self, mock_get_settings):
        mock_settings = MagicMock(spec=[])
        mock_settings.api_base_url = "http://local:8000"
        mock_settings.api_timeout = 30
        # admin_api_key not present as attribute
        mock_get_settings.return_value = mock_settings

        api = get_api_client()
        try:
            assert "X-Admin-Key" not in api._client.headers
        finally:
            api.close()


# ── Admin key propagation ───────────────────────────────────────────────


class TestAdminKeyPropagation:
    """Verify X-Admin-Key header is sent with requests."""

    def test_header_sent_on_requests(self):
        captured_headers: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, json={})

        api = _make_client(handler, admin_key="secret-123")
        api.list_jobs()
        assert captured_headers.get("x-admin-key") == "secret-123"
