"""Tests for Content Query API endpoints.

Tests the query preview, summarize with query, and digest with query endpoints:
- POST /api/v1/contents/query/preview
- POST /api/v1/contents/summarize (with query and dry_run)
- POST /api/v1/digests/generate (with content_query and dry_run)
"""


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
