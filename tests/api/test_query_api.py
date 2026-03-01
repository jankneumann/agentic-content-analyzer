"""Tests for Content Query API endpoints.

Tests the query preview, summarize with query, and digest with query endpoints:
- POST /api/v1/contents/query/preview
- POST /api/v1/contents/summarize (with query and dry_run)
- POST /api/v1/digests/generate (with content_query and dry_run)
"""

from unittest.mock import AsyncMock, patch


class TestQueryPreview:
    """Tests for POST /api/v1/contents/query/preview endpoint."""

    def test_preview_no_filters_matches_all(self, client, sample_contents):
        """Preview with empty query returns all content."""
        response = client.post("/api/v1/contents/query/preview", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 3
        assert len(data["sample_titles"]) == 3
        assert "by_source" in data
        assert "by_status" in data
        assert "date_range" in data

    def test_preview_filter_by_source_type(self, client, sample_contents):
        """Preview with source_types filter returns matching count."""
        response = client.post(
            "/api/v1/contents/query/preview",
            json={"source_types": ["gmail"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert data["by_source"] == {"gmail": 1}

    def test_preview_filter_by_status(self, client, sample_contents):
        """Preview with statuses filter returns correct breakdown."""
        response = client.post(
            "/api/v1/contents/query/preview",
            json={"statuses": ["parsed"]},
        )
        assert response.status_code == 200
        data = response.json()
        # sample_contents has 2 PARSED items
        assert data["total_count"] == 2
        assert data["by_status"] == {"parsed": 2}

    def test_preview_filter_by_search(self, client, sample_contents):
        """Preview with search filter matches titles."""
        response = client.post(
            "/api/v1/contents/query/preview",
            json={"search": "Vector"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert "Vector" in data["sample_titles"][0]

    def test_preview_combined_filters(self, client, sample_contents):
        """Preview with multiple filters intersects them."""
        response = client.post(
            "/api/v1/contents/query/preview",
            json={
                "source_types": ["rss"],
                "statuses": ["completed"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        # sample_contents[1] is RSS + COMPLETED
        assert data["total_count"] == 1

    def test_preview_zero_matches(self, client, sample_contents):
        """Preview with no matches returns 200 with total_count=0."""
        response = client.post(
            "/api/v1/contents/query/preview",
            json={"search": "nonexistent-content-xyz-999"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0
        assert data["by_source"] == {}
        assert data["by_status"] == {}
        assert data["sample_titles"] == []

    def test_preview_empty_database(self, client):
        """Preview with empty database returns 200 with zero count."""
        response = client.post("/api/v1/contents/query/preview", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 0

    def test_preview_invalid_source_type_returns_422(self, client):
        """Preview with invalid source_type returns 422 validation error."""
        response = client.post(
            "/api/v1/contents/query/preview",
            json={"source_types": ["invalid_source"]},
        )
        assert response.status_code == 422

    def test_preview_invalid_sort_by_returns_422(self, client):
        """Preview with invalid sort_by returns 422 validation error."""
        response = client.post(
            "/api/v1/contents/query/preview",
            json={"sort_by": "nonexistent_field"},
        )
        assert response.status_code == 422

    def test_preview_date_range_filter(self, client, sample_contents):
        """Preview with date range filter limits results."""
        # sample_contents[0] is Jan 15, [1] is Jan 14, [2] is Jan 13
        response = client.post(
            "/api/v1/contents/query/preview",
            json={"start_date": "2025-01-14T00:00:00Z"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 2  # Jan 14 and Jan 15

    def test_preview_returns_date_range(self, client, sample_contents):
        """Preview includes date range of matching content."""
        response = client.post("/api/v1/contents/query/preview", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["date_range"]["earliest"] is not None
        assert data["date_range"]["latest"] is not None

    def test_preview_echoes_query(self, client, sample_contents):
        """Preview response includes the query for confirmation."""
        query = {"source_types": ["gmail"], "search": "LLM"}
        response = client.post("/api/v1/contents/query/preview", json=query)
        assert response.status_code == 200
        data = response.json()
        assert data["query"]["source_types"] == ["gmail"]
        assert data["query"]["search"] == "LLM"


class TestSummarizeWithQuery:
    """Tests for POST /api/v1/contents/summarize with query and dry_run."""

    def test_summarize_dry_run_returns_preview(self, client, sample_contents):
        """Summarize with dry_run returns ContentQueryPreview."""
        response = client.post(
            "/api/v1/contents/summarize",
            json={
                "query": {"source_types": ["gmail"]},
                "dry_run": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        # dry_run returns a preview, not a summarize response
        assert "total_count" in data
        assert "by_source" in data
        assert "sample_titles" in data

    def test_summarize_dry_run_defaults_to_pending_parsed(self, client, sample_contents):
        """Summarize dry_run defaults statuses to PENDING + PARSED."""
        response = client.post(
            "/api/v1/contents/summarize",
            json={
                "query": {},
                "dry_run": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Only PENDING and PARSED items (2 of 3)
        assert data["total_count"] == 2
        # Status breakdown should only contain pending/parsed
        for status in data.get("by_status", {}):
            assert status in ("pending", "parsed")

    @patch("src.api.content_routes._enqueue_summarization_batch_job", new_callable=AsyncMock)
    def test_summarize_with_query_enqueues_matching_ids(
        self, mock_enqueue, client, sample_contents
    ):
        """Summarize with query filter enqueues jobs for matching IDs only."""
        mock_enqueue.return_value = (1, 1)

        response = client.post(
            "/api/v1/contents/summarize",
            json={
                "query": {"source_types": ["gmail"]},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["queued_count"] == 1
        # Verify the batch was enqueued
        mock_enqueue.assert_called_once()

    @patch("src.api.content_routes._enqueue_summarization_batch_job", new_callable=AsyncMock)
    def test_summarize_query_takes_precedence_over_content_ids(
        self, mock_enqueue, client, sample_contents
    ):
        """When both query and content_ids provided, query wins."""
        mock_enqueue.return_value = (1, 2)

        response = client.post(
            "/api/v1/contents/summarize",
            json={
                "content_ids": [999],  # Would not match anything
                "query": {"statuses": ["parsed"]},
            },
        )
        assert response.status_code == 200
        data = response.json()
        # query wins — parsed items exist
        assert data["queued_count"] == 2

    @patch("src.api.content_routes._enqueue_summarization_batch_job", new_callable=AsyncMock)
    def test_summarize_no_query_no_ids_defaults(self, mock_enqueue, client, sample_contents):
        """Summarize without query or content_ids uses default behavior."""
        mock_enqueue.return_value = (1, 2)

        response = client.post(
            "/api/v1/contents/summarize",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        # Default behavior: all pending/parsed without summaries
        assert data["queued_count"] == 2

    def test_summarize_query_no_matches(self, client, sample_contents):
        """Summarize with query that matches nothing returns zero count."""
        response = client.post(
            "/api/v1/contents/summarize",
            json={
                "query": {"search": "nonexistent-xyz-999"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["queued_count"] == 0
        assert data["content_ids"] == []

    def test_summarize_dry_run_without_query_returns_preview(self, client, sample_contents):
        """Summarize dry_run without query returns preview (not real execution)."""
        response = client.post(
            "/api/v1/contents/summarize",
            json={"dry_run": True},
        )
        assert response.status_code == 200
        data = response.json()
        # Should return preview, not a SummarizeContentResponse
        assert "total_count" in data
        assert "by_source" in data
        assert "sample_titles" in data
        # Should NOT have task_id (which would indicate real execution)
        assert "task_id" not in data

    def test_summarize_dry_run_with_retry_failed_includes_failed(self, client, sample_contents):
        """Summarize dry_run with retry_failed includes FAILED items in preview."""
        response = client.post(
            "/api/v1/contents/summarize",
            json={
                "dry_run": True,
                "query": {},
                "retry_failed": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        # query echo should include failed status in the defaults
        echoed_statuses = data.get("query", {}).get("statuses", [])
        assert "failed" in echoed_statuses


class TestDigestGenerateWithQuery:
    """Tests for POST /api/v1/digests/generate with content_query and dry_run."""

    def test_digest_dry_run_returns_preview(self, client, sample_contents):
        """Digest generate with dry_run returns ContentQueryPreview dict."""
        response = client.post(
            "/api/v1/digests/generate",
            json={
                "digest_type": "daily",
                "dry_run": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_count" in data
        assert "by_source" in data
        assert "sample_titles" in data

    def test_digest_dry_run_defaults_to_completed(self, client, sample_contents):
        """Digest dry_run defaults statuses to COMPLETED."""
        response = client.post(
            "/api/v1/digests/generate",
            json={
                "digest_type": "daily",
                "dry_run": True,
                "period_start": "2025-01-01T00:00:00Z",
                "period_end": "2025-12-31T23:59:59Z",
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Only COMPLETED items in the status breakdown
        for status in data.get("by_status", {}):
            assert status == "completed"

    def test_digest_dry_run_with_content_query(self, client, sample_contents):
        """Digest dry_run respects content_query filters."""
        response = client.post(
            "/api/v1/digests/generate",
            json={
                "digest_type": "daily",
                "dry_run": True,
                "content_query": {"source_types": ["rss"]},
                "period_start": "2025-01-01T00:00:00Z",
                "period_end": "2025-12-31T23:59:59Z",
            },
        )
        assert response.status_code == 200
        data = response.json()
        # Should only match RSS content
        if data["total_count"] > 0:
            assert "rss" in data["by_source"]

    @patch("src.api.digest_routes.generate_digest_task")
    def test_digest_generate_with_content_query(self, mock_task, client, sample_contents):
        """Digest generate passes content_query to DigestRequest."""
        response = client.post(
            "/api/v1/digests/generate",
            json={
                "digest_type": "daily",
                "content_query": {"source_types": ["gmail"]},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"

    def test_digest_generate_invalid_type_returns_400(self, client):
        """Digest generate with invalid type returns 400."""
        response = client.post(
            "/api/v1/digests/generate",
            json={"digest_type": "invalid_type"},
        )
        assert response.status_code == 400
