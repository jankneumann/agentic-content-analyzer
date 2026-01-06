"""Tests for newsletter API endpoints."""


class TestListNewsletters:
    """Tests for GET /api/v1/newsletters endpoint."""

    def test_list_newsletters_empty(self, client):
        """Test listing newsletters when database is empty."""
        response = client.get("/api/v1/newsletters")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["has_more"] is False

    def test_list_newsletters_returns_items(self, client, sample_newsletters):
        """Test listing newsletters returns all items."""
        response = client.get("/api/v1/newsletters")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        assert data["has_more"] is False

    def test_list_newsletters_pagination_limit(self, client, sample_newsletters):
        """Test pagination with limit parameter."""
        response = client.get("/api/v1/newsletters?limit=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3
        assert data["limit"] == 2
        assert data["has_more"] is True

    def test_list_newsletters_pagination_offset(self, client, sample_newsletters):
        """Test pagination with offset parameter."""
        response = client.get("/api/v1/newsletters?limit=2&offset=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["offset"] == 2
        assert data["has_more"] is False

    def test_list_newsletters_filter_by_source(self, client, sample_newsletters):
        """Test filtering newsletters by source."""
        response = client.get("/api/v1/newsletters?source=gmail")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["source"] == "gmail"

    def test_list_newsletters_filter_by_status(self, client, sample_newsletters):
        """Test filtering newsletters by processing status."""
        response = client.get("/api/v1/newsletters?status=pending")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["status"] == "pending"

    def test_list_newsletters_filter_by_publication(self, client, sample_newsletters):
        """Test filtering newsletters by publication name."""
        response = client.get("/api/v1/newsletters?publication=AI")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert "AI" in data["items"][0]["publication"]

    def test_list_newsletters_search_by_title(self, client, sample_newsletters):
        """Test searching newsletters by title."""
        response = client.get("/api/v1/newsletters?search=Vector")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert "Vector" in data["items"][0]["title"]


class TestGetNewsletter:
    """Tests for GET /api/v1/newsletters/{id} endpoint."""

    def test_get_newsletter_returns_detail(self, client, sample_newsletter):
        """Test getting newsletter by ID returns full detail."""
        response = client.get(f"/api/v1/newsletters/{sample_newsletter.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_newsletter.id
        assert data["title"] == sample_newsletter.title
        assert data["source"] == sample_newsletter.source.value
        assert data["sender"] == sample_newsletter.sender
        assert data["publication"] == sample_newsletter.publication
        assert data["raw_text"] is not None

    def test_get_newsletter_not_found(self, client):
        """Test getting non-existent newsletter returns 404."""
        response = client.get("/api/v1/newsletters/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestDeleteNewsletter:
    """Tests for DELETE /api/v1/newsletters/{id} endpoint."""

    def test_delete_newsletter_success(self, client, sample_newsletter, db_session):
        """Test deleting newsletter removes it from database."""
        newsletter_id = sample_newsletter.id

        response = client.delete(f"/api/v1/newsletters/{newsletter_id}")

        assert response.status_code == 200
        assert response.json()["id"] == newsletter_id
        assert "deleted" in response.json()["message"].lower()

        # Verify newsletter is deleted
        get_response = client.get(f"/api/v1/newsletters/{newsletter_id}")
        assert get_response.status_code == 404

    def test_delete_newsletter_not_found(self, client):
        """Test deleting non-existent newsletter returns 404."""
        response = client.delete("/api/v1/newsletters/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestNewsletterStats:
    """Tests for GET /api/v1/newsletters/stats endpoint."""

    def test_newsletter_stats_empty(self, client):
        """Test stats endpoint with empty database."""
        response = client.get("/api/v1/newsletters/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["pending_count"] == 0
        assert data["summarized_count"] == 0

    def test_newsletter_stats_with_data(self, client, sample_newsletters):
        """Test stats endpoint with newsletters in database."""
        response = client.get("/api/v1/newsletters/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert "by_status" in data
        assert "by_source" in data
        # 2 pending, 1 completed in sample_newsletters
        assert data["pending_count"] == 2
        assert data["summarized_count"] == 1


class TestTriggerIngestion:
    """Tests for POST /api/v1/newsletters/ingest endpoint."""

    def test_trigger_ingestion_returns_task_id(self, client):
        """Test triggering ingestion returns task ID."""
        response = client.post(
            "/api/v1/newsletters/ingest",
            json={"source": "gmail", "max_results": 10, "days_back": 7},
        )

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["source"] == "gmail"
        assert data["max_results"] == 10

    def test_trigger_ingestion_rss_source(self, client):
        """Test triggering RSS ingestion."""
        response = client.post(
            "/api/v1/newsletters/ingest",
            json={"source": "rss", "max_results": 20, "days_back": 14},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "rss"

    def test_trigger_ingestion_default_values(self, client):
        """Test ingestion uses defaults when not specified."""
        response = client.post("/api/v1/newsletters/ingest", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "gmail"  # Default
        assert data["max_results"] == 50  # Default


class TestIngestionStatus:
    """Tests for GET /api/v1/newsletters/ingest/status/{task_id} endpoint."""

    def test_ingestion_status_not_found(self, client):
        """Test status for non-existent task returns 404."""
        response = client.get("/api/v1/newsletters/ingest/status/nonexistent-task-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
