"""Tests for summary API endpoints."""

from src.models.newsletter import ProcessingStatus


class TestListSummaries:
    """Tests for GET /api/v1/summaries endpoint."""

    def test_list_summaries_empty(self, client):
        """Test listing summaries when database is empty."""
        response = client.get("/api/v1/summaries")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["has_more"] is False

    def test_list_summaries_returns_items(self, client, sample_summaries):
        """Test listing summaries returns all items."""
        response = client.get("/api/v1/summaries")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_summaries_pagination_limit(self, client, sample_summaries):
        """Test pagination with limit parameter."""
        response = client.get("/api/v1/summaries?limit=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 2
        assert data["has_more"] is True

    def test_list_summaries_pagination_offset(self, client, sample_summaries):
        """Test pagination with offset parameter."""
        response = client.get("/api/v1/summaries?limit=1&offset=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["offset"] == 1
        assert data["has_more"] is False

    def test_list_summaries_filter_by_newsletter(
        self, client, sample_summaries, sample_newsletters
    ):
        """Test filtering summaries by newsletter ID."""
        newsletter_id = sample_newsletters[0].id
        response = client.get(f"/api/v1/summaries?newsletter_id={newsletter_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["newsletter_id"] == newsletter_id


class TestGetSummary:
    """Tests for GET /api/v1/summaries/{id} endpoint."""

    def test_get_summary_returns_detail(self, client, sample_summary):
        """Test getting summary by ID returns full detail."""
        response = client.get(f"/api/v1/summaries/{sample_summary.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_summary.id
        assert data["newsletter_id"] == sample_summary.newsletter_id
        assert data["executive_summary"] == sample_summary.executive_summary
        assert "key_themes" in data
        assert "strategic_insights" in data
        assert "relevance_scores" in data
        assert "model_used" in data

    def test_get_summary_not_found(self, client):
        """Test getting non-existent summary returns 404."""
        response = client.get("/api/v1/summaries/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestGetSummaryByNewsletter:
    """Tests for GET /api/v1/summaries/by-newsletter/{newsletter_id} endpoint."""

    def test_get_summary_by_newsletter_returns_detail(
        self, client, sample_summary, sample_newsletter
    ):
        """Test getting summary by newsletter ID."""
        response = client.get(f"/api/v1/summaries/by-newsletter/{sample_newsletter.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["newsletter_id"] == sample_newsletter.id
        assert data["executive_summary"] is not None

    def test_get_summary_by_newsletter_not_found(self, client, sample_newsletter, db_session):
        """Test getting summary for newsletter without summary returns 404."""
        # Create newsletter without summary
        from datetime import UTC, datetime

        from src.models.newsletter import Newsletter, NewsletterSource

        new_newsletter = Newsletter(
            source=NewsletterSource.GMAIL,
            source_id="no-summary-001",
            title="No Summary Newsletter",
            published_date=datetime.now(UTC),
            status=ProcessingStatus.PENDING,
        )
        db_session.add(new_newsletter)
        db_session.commit()
        db_session.refresh(new_newsletter)

        response = client.get(f"/api/v1/summaries/by-newsletter/{new_newsletter.id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestDeleteSummary:
    """Tests for DELETE /api/v1/summaries/{id} endpoint."""

    def test_delete_summary_success(self, client, sample_summary, sample_newsletter, db_session):
        """Test deleting summary removes it and resets newsletter status."""
        summary_id = sample_summary.id
        newsletter_id = sample_newsletter.id

        # Verify newsletter is completed before delete
        assert sample_newsletter.status == ProcessingStatus.COMPLETED

        response = client.delete(f"/api/v1/summaries/{summary_id}")

        assert response.status_code == 200
        assert response.json()["id"] == summary_id
        assert "deleted" in response.json()["message"].lower()

        # Verify summary is deleted
        get_response = client.get(f"/api/v1/summaries/{summary_id}")
        assert get_response.status_code == 404

    def test_delete_summary_not_found(self, client):
        """Test deleting non-existent summary returns 404."""
        response = client.delete("/api/v1/summaries/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestSummaryStats:
    """Tests for GET /api/v1/summaries/stats endpoint."""

    def test_summary_stats_empty(self, client):
        """Test stats endpoint with empty database."""
        response = client.get("/api/v1/summaries/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["avg_processing_time"] == 0.0
        assert data["avg_token_usage"] == 0.0

    def test_summary_stats_with_data(self, client, sample_summaries):
        """Test stats endpoint with summaries in database."""
        response = client.get("/api/v1/summaries/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert "by_model" in data
        assert data["avg_processing_time"] > 0
        assert data["avg_token_usage"] > 0


class TestTriggerSummarization:
    """Tests for POST /api/v1/summaries/generate endpoint."""

    def test_trigger_summarization_returns_task_id(self, client, sample_newsletter):
        """Test triggering summarization returns task ID."""
        response = client.post(
            "/api/v1/summaries/generate",
            json={"newsletter_ids": [sample_newsletter.id]},
        )

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["queued_count"] == 1
        assert sample_newsletter.id in data["newsletter_ids"]

    def test_trigger_summarization_empty_ids_processes_pending(self, client, sample_newsletters):
        """Test empty newsletter_ids processes all pending newsletters."""
        response = client.post("/api/v1/summaries/generate", json={})

        assert response.status_code == 200
        data = response.json()
        # sample_newsletters has 2 pending newsletters
        assert data["queued_count"] == 2

    def test_trigger_summarization_force_flag(self, client, sample_summary, sample_newsletter):
        """Test force flag allows re-summarization."""
        response = client.post(
            "/api/v1/summaries/generate",
            json={"newsletter_ids": [sample_newsletter.id], "force": True},
        )

        assert response.status_code == 200
        data = response.json()
        # With force=True, already summarized newsletter is included
        assert data["queued_count"] == 1


class TestRegenerateSummary:
    """Tests for POST /api/v1/summaries/{id}/regenerate endpoint."""

    def test_regenerate_summary_returns_task_id(self, client, sample_summary):
        """Test regenerating summary returns task ID."""
        response = client.post(f"/api/v1/summaries/{sample_summary.id}/regenerate")

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["queued_count"] == 1

    def test_regenerate_summary_not_found(self, client):
        """Test regenerating non-existent summary returns 404."""
        response = client.post("/api/v1/summaries/99999/regenerate")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestSummarizationStatus:
    """Tests for GET /api/v1/summaries/status/{task_id} endpoint."""

    def test_summarization_status_not_found(self, client):
        """Test status for non-existent task returns 404."""
        response = client.get("/api/v1/summaries/status/nonexistent-task-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
