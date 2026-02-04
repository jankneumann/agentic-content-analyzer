"""Tests for summary API endpoints.

Updated to use unified Content model (not legacy Newsletter).
"""

from datetime import UTC, datetime

from src.config.models import MODEL_REGISTRY
from src.models.content import Content, ContentSource, ContentStatus
from src.models.summary import Summary


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

    def test_list_summaries_returns_items(self, client, db_session):
        """Test listing summaries returns all items."""
        # Create content with summaries
        contents = self._create_contents_with_summaries(db_session, count=2)

        response = client.get("/api/v1/summaries")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_summaries_pagination_limit(self, client, db_session):
        """Test pagination with limit parameter."""
        self._create_contents_with_summaries(db_session, count=2)

        response = client.get("/api/v1/summaries?limit=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 2
        assert data["has_more"] is True

    def test_list_summaries_pagination_offset(self, client, db_session):
        """Test pagination with offset parameter."""
        self._create_contents_with_summaries(db_session, count=2)

        response = client.get("/api/v1/summaries?limit=1&offset=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["offset"] == 1
        assert data["has_more"] is False

    def test_list_summaries_filter_by_content(self, client, db_session):
        """Test filtering summaries by content ID."""
        contents = self._create_contents_with_summaries(db_session, count=2)
        content_id = contents[0].id

        response = client.get(f"/api/v1/summaries?content_id={content_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["content_id"] == content_id

    def _create_contents_with_summaries(self, db_session, count: int = 2) -> list[Content]:
        """Helper to create content with associated summaries."""
        test_model = list(MODEL_REGISTRY.keys())[0]
        contents = []

        for i in range(count):
            content = Content(
                source_type=ContentSource.GMAIL,
                source_id=f"test-content-{i}",
                source_url=f"https://example.com/content{i}",
                title=f"Test Content {i}",
                author=f"Author {i}",
                publication=f"Publication {i}",
                published_date=datetime(2025, 1, 15 - i, 10, 0, 0, tzinfo=UTC),
                markdown_content=f"# Test Content {i}\n\nContent about topic {i}.",
                content_hash=f"hash{i:03d}",
                status=ContentStatus.COMPLETED,
                ingested_at=datetime.now(UTC),
                processed_at=datetime.now(UTC),
            )
            db_session.add(content)
            db_session.commit()
            db_session.refresh(content)

            summary = Summary(
                content_id=content.id,
                executive_summary=f"Executive summary {i}.",
                key_themes=[f"Theme {i}A", f"Theme {i}B"],
                strategic_insights=[f"Insight {i}"],
                technical_details=[f"Technical detail {i}"],
                actionable_items=[f"Action {i}"],
                notable_quotes=[f"Quote {i}"],
                relevance_scores={"cto_leadership": 0.8, "technical_teams": 0.9},
                agent_framework="claude",
                model_used=test_model,
                token_usage=2000 + i * 100,
                processing_time_seconds=3.0 + i * 0.5,
            )
            db_session.add(summary)
            db_session.commit()
            contents.append(content)

        return contents


class TestGetSummary:
    """Tests for GET /api/v1/summaries/{id} endpoint."""

    def test_get_summary_returns_detail(self, client, sample_content_with_summary):
        """Test getting summary by ID returns full detail."""
        content, summary = sample_content_with_summary

        response = client.get(f"/api/v1/summaries/{summary.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == summary.id
        assert data["content_id"] == content.id
        assert data["executive_summary"] == summary.executive_summary
        assert "key_themes" in data
        assert "strategic_insights" in data
        assert "relevance_scores" in data
        assert "model_used" in data

    def test_get_summary_not_found(self, client):
        """Test getting non-existent summary returns 404."""
        response = client.get("/api/v1/summaries/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestGetSummaryByContent:
    """Tests for GET /api/v1/summaries/by-content/{content_id} endpoint."""

    def test_get_summary_by_content_returns_detail(self, client, sample_content_with_summary):
        """Test getting summary by content ID."""
        content, _summary = sample_content_with_summary

        response = client.get(f"/api/v1/summaries/by-content/{content.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["content_id"] == content.id
        assert data["executive_summary"] is not None

    def test_get_summary_by_content_not_found(self, client, sample_content):
        """Test getting summary for content without summary returns 404."""
        response = client.get(f"/api/v1/summaries/by-content/{sample_content.id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestDeleteSummary:
    """Tests for DELETE /api/v1/summaries/{id} endpoint."""

    def test_delete_summary_success(self, client, sample_content_with_summary, db_session):
        """Test deleting summary removes it and resets content status."""
        content, summary = sample_content_with_summary
        summary_id = summary.id

        # Verify content is completed before delete
        assert content.status == ContentStatus.COMPLETED

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

    def test_summary_stats_with_data(self, client, sample_content_with_summary):
        """Test stats endpoint with summaries in database."""
        response = client.get("/api/v1/summaries/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert "by_model" in data
        assert data["avg_processing_time"] > 0
        assert data["avg_token_usage"] > 0


class TestRegenerateSummary:
    """Tests for POST /api/v1/summaries/{id}/regenerate endpoint."""

    def test_regenerate_summary_returns_content_id(self, client, sample_content_with_summary):
        """Test regenerating summary returns content ID for re-summarization."""
        content, summary = sample_content_with_summary

        response = client.post(f"/api/v1/summaries/{summary.id}/regenerate")

        assert response.status_code == 200
        data = response.json()
        assert "content_id" in data
        assert data["content_id"] == content.id

    def test_regenerate_summary_not_found(self, client):
        """Test regenerating non-existent summary returns 404."""
        response = client.post("/api/v1/summaries/99999/regenerate")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestSummaryNavigation:
    """Tests for GET /api/v1/summaries/{id}/navigation endpoint."""

    def test_navigation_returns_position_info(self, client, db_session):
        """Test navigation returns position and total."""
        contents = TestListSummaries()._create_contents_with_summaries(db_session, count=2)

        # Get the summary for the first content
        summary = db_session.query(Summary).filter(Summary.content_id == contents[0].id).first()

        response = client.get(f"/api/v1/summaries/{summary.id}/navigation")

        assert response.status_code == 200
        data = response.json()
        assert "position" in data
        assert "total" in data
        assert data["total"] == 2
        assert data["position"] in (1, 2)

    def test_navigation_returns_prev_next_ids(self, client, db_session):
        """Test navigation returns prev/next IDs."""
        contents = TestListSummaries()._create_contents_with_summaries(db_session, count=2)

        # Get the second summary (which should have prev based on sort order)
        summaries = db_session.query(Summary).order_by(Summary.created_at.desc()).all()
        summary_id = summaries[1].id  # Second in desc order

        response = client.get(f"/api/v1/summaries/{summary_id}/navigation")

        assert response.status_code == 200
        data = response.json()
        assert "prev_id" in data
        assert "next_id" in data
        assert "prev_content_id" in data
        assert "next_content_id" in data

    def test_navigation_first_item_no_prev(self, client, sample_content_with_summary):
        """Test first item has no previous."""
        _content, summary = sample_content_with_summary

        response = client.get(f"/api/v1/summaries/{summary.id}/navigation")

        assert response.status_code == 200
        data = response.json()
        assert data["position"] == 1
        assert data["prev_id"] is None
        assert data["prev_content_id"] is None

    def test_navigation_not_found(self, client):
        """Test navigation for non-existent summary returns 404."""
        response = client.get("/api/v1/summaries/99999/navigation")

        assert response.status_code == 404
