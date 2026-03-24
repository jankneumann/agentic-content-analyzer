"""Tests for extended IngestRequest model and ingestion job enqueueing.

Validates Pydantic model defaults, field constraints, and that
_enqueue_ingestion_job correctly passes source-specific fields
through the job payload.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from src.api.content_routes import IngestRequest

# ---------------------------------------------------------------------------
# IngestRequest model validation
# ---------------------------------------------------------------------------


class TestIngestRequestDefaults:
    def test_defaults(self):
        req = IngestRequest()
        assert req.source == "gmail"
        assert req.max_results is None
        assert req.days_back == 7
        assert req.force_reprocess is False
        assert req.transcribe is True
        assert req.public_only is False
        assert req.query is None
        assert req.prompt is None
        assert req.url is None
        assert req.tags is None

    def test_max_results_none_means_server_defaults(self):
        """max_results=None signals the worker to use sources.d config defaults."""
        req = IngestRequest(source="rss")
        assert req.max_results is None


class TestIngestRequestSourceFields:
    def test_xsearch_fields(self):
        req = IngestRequest(source="xsearch", prompt="AI trends", max_threads=5)
        assert req.prompt == "AI trends"
        assert req.max_threads == 5

    def test_perplexity_fields(self):
        req = IngestRequest(
            source="perplexity",
            prompt="latest AI",
            recency_filter="week",
            context_size="high",
        )
        assert req.recency_filter == "week"
        assert req.context_size == "high"

    def test_url_fields(self):
        req = IngestRequest(
            source="url",
            url="https://example.com",
            title="Test",
            tags=["ai", "ml"],
            notes="Good article",
        )
        assert req.url == "https://example.com"
        assert req.tags == ["ai", "ml"]
        assert req.notes == "Good article"

    def test_substack_session_cookie(self):
        req = IngestRequest(source="substack", session_cookie="sid=abc123")
        assert req.session_cookie == "sid=abc123"

    def test_youtube_public_only(self):
        req = IngestRequest(source="youtube", public_only=True)
        assert req.public_only is True

    def test_gmail_query(self):
        req = IngestRequest(source="gmail", query="label:newsletters")
        assert req.query == "label:newsletters"

    def test_podcast_transcribe_disabled(self):
        req = IngestRequest(source="podcast", transcribe=False)
        assert req.transcribe is False


class TestIngestRequestValidation:
    def test_max_results_too_low(self):
        with pytest.raises(ValidationError):
            IngestRequest(max_results=0)

    def test_max_results_too_high(self):
        with pytest.raises(ValidationError):
            IngestRequest(max_results=201)

    def test_max_results_valid_boundary_low(self):
        req = IngestRequest(max_results=1)
        assert req.max_results == 1

    def test_max_results_valid_boundary_high(self):
        req = IngestRequest(max_results=200)
        assert req.max_results == 200

    def test_days_back_too_low(self):
        with pytest.raises(ValidationError):
            IngestRequest(days_back=0)

    def test_days_back_too_high(self):
        with pytest.raises(ValidationError):
            IngestRequest(days_back=91)


# ---------------------------------------------------------------------------
# _enqueue_ingestion_job payload construction
# ---------------------------------------------------------------------------


class TestEnqueueIngestionJob:
    @patch("src.queue.setup.enqueue_queue_job", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_basic_payload(self, mock_enqueue):
        from src.api.content_routes import _enqueue_ingestion_job

        mock_enqueue.return_value = (42, True)
        req = IngestRequest(source="gmail", days_back=3)
        job_id = await _enqueue_ingestion_job(req)
        assert job_id == 42
        payload = mock_enqueue.call_args[0][1]
        assert payload["source"] == "gmail"
        assert payload["days_back"] == 3
        # max_results should NOT be in payload when None
        assert "max_results" not in payload

    @patch("src.queue.setup.enqueue_queue_job", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_xsearch_payload(self, mock_enqueue):
        from src.api.content_routes import _enqueue_ingestion_job

        mock_enqueue.return_value = (1, True)
        req = IngestRequest(source="xsearch", prompt="AI news", max_threads=3)
        await _enqueue_ingestion_job(req)
        payload = mock_enqueue.call_args[0][1]
        assert payload["source"] == "xsearch"
        assert payload["prompt"] == "AI news"
        assert payload["max_threads"] == 3

    @patch("src.queue.setup.enqueue_queue_job", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_perplexity_payload(self, mock_enqueue):
        from src.api.content_routes import _enqueue_ingestion_job

        mock_enqueue.return_value = (2, True)
        req = IngestRequest(
            source="perplexity",
            prompt="latest AI",
            recency_filter="week",
            context_size="high",
            max_results=10,
        )
        await _enqueue_ingestion_job(req)
        payload = mock_enqueue.call_args[0][1]
        assert payload["prompt"] == "latest AI"
        assert payload["recency_filter"] == "week"
        assert payload["context_size"] == "high"
        assert payload["max_results"] == 10

    @patch("src.queue.setup.enqueue_queue_job", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_url_payload(self, mock_enqueue):
        from src.api.content_routes import _enqueue_ingestion_job

        mock_enqueue.return_value = (3, True)
        req = IngestRequest(
            source="url",
            url="https://example.com/article",
            title="My Article",
            tags=["ai"],
            notes="Worth reading",
        )
        await _enqueue_ingestion_job(req)
        payload = mock_enqueue.call_args[0][1]
        assert payload["url"] == "https://example.com/article"
        assert payload["title"] == "My Article"
        assert payload["tags"] == ["ai"]
        assert payload["notes"] == "Worth reading"

    @patch("src.queue.setup.enqueue_queue_job", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_transcribe_false_included(self, mock_enqueue):
        from src.api.content_routes import _enqueue_ingestion_job

        mock_enqueue.return_value = (4, True)
        req = IngestRequest(source="podcast", transcribe=False)
        await _enqueue_ingestion_job(req)
        payload = mock_enqueue.call_args[0][1]
        assert payload["transcribe"] is False

    @patch("src.queue.setup.enqueue_queue_job", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_transcribe_true_not_in_payload(self, mock_enqueue):
        from src.api.content_routes import _enqueue_ingestion_job

        mock_enqueue.return_value = (5, True)
        req = IngestRequest(source="podcast", transcribe=True)
        await _enqueue_ingestion_job(req)
        payload = mock_enqueue.call_args[0][1]
        # transcribe=True is the default and should NOT be in payload
        assert "transcribe" not in payload

    @patch("src.queue.setup.enqueue_queue_job", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_public_only_true_included(self, mock_enqueue):
        from src.api.content_routes import _enqueue_ingestion_job

        mock_enqueue.return_value = (6, True)
        req = IngestRequest(source="youtube", public_only=True)
        await _enqueue_ingestion_job(req)
        payload = mock_enqueue.call_args[0][1]
        assert payload["public_only"] is True

    @patch("src.queue.setup.enqueue_queue_job", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_public_only_false_not_in_payload(self, mock_enqueue):
        from src.api.content_routes import _enqueue_ingestion_job

        mock_enqueue.return_value = (7, True)
        req = IngestRequest(source="youtube", public_only=False)
        await _enqueue_ingestion_job(req)
        payload = mock_enqueue.call_args[0][1]
        # public_only=False is default, should NOT be in payload
        assert "public_only" not in payload
