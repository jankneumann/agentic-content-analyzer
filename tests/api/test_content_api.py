"""Tests for Content API endpoints.

Tests the unified Content model API including:
- CRUD operations (create, read, update, delete)
- Filtering, pagination, and sorting
- Duplicate detection and merging
- Statistics endpoints
- Background ingestion and summarization triggers
"""

from datetime import UTC, datetime

from src.models.content import Content, ContentSource, ContentStatus


class TestListContents:
    """Tests for GET /api/v1/contents endpoint."""

    def test_list_contents_empty(self, client):
        """Empty database returns empty list."""
        response = client.get("/api/v1/contents")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_contents_returns_items(self, client, sample_contents):
        """Returns all content items with pagination metadata."""
        response = client.get("/api/v1/contents")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["has_next"] is False

    def test_list_contents_filter_by_source(self, client, sample_contents):
        """Filter by source_type returns only matching items."""
        response = client.get("/api/v1/contents?source_type=gmail")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["source_type"] == "gmail"

    def test_list_contents_filter_by_status(self, client, sample_contents):
        """Filter by status returns only matching items."""
        response = client.get("/api/v1/contents?status=parsed")
        assert response.status_code == 200
        data = response.json()
        # sample_contents has 2 PARSED and 1 COMPLETED
        assert len(data["items"]) == 2
        for item in data["items"]:
            assert item["status"] == "parsed"

    def test_list_contents_filter_by_publication(self, client, sample_contents):
        """Filter by publication returns only matching items."""
        response = client.get("/api/v1/contents?publication=AI Weekly")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["publication"] == "AI Weekly"

    def test_list_contents_search(self, client, sample_contents):
        """Search by title returns matching items."""
        response = client.get("/api/v1/contents?search=Vector")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert "Vector" in data["items"][0]["title"]

    def test_list_contents_pagination(self, client, sample_contents):
        """Pagination works correctly."""
        # Get first page with page_size=2
        response = client.get("/api/v1/contents?page_size=2&page=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["has_next"] is True
        assert data["has_prev"] is False

        # Get second page
        response = client.get("/api/v1/contents?page_size=2&page=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["has_next"] is False
        assert data["has_prev"] is True

    def test_list_contents_sort_by_published_date(self, client, sample_contents):
        """Sorting by published_date works correctly."""
        response = client.get("/api/v1/contents?sort_by=published_date&sort_order=asc")
        assert response.status_code == 200
        data = response.json()
        dates = [item["published_date"] for item in data["items"] if item["published_date"]]
        assert dates == sorted(dates)

    def test_list_contents_sort_by_title(self, client, sample_contents):
        """Sorting by title works correctly."""
        response = client.get("/api/v1/contents?sort_by=title&sort_order=asc")
        assert response.status_code == 200
        data = response.json()
        titles = [item["title"] for item in data["items"]]
        assert titles == sorted(titles)


class TestGetContent:
    """Tests for GET /api/v1/contents/{id} endpoint."""

    def test_get_content_success(self, client, sample_content):
        """Returns content detail for valid ID."""
        response = client.get(f"/api/v1/contents/{sample_content.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_content.id
        assert data["title"] == sample_content.title
        assert data["source_type"] == sample_content.source_type.value
        assert "markdown_content" in data

    def test_get_content_not_found(self, client):
        """Returns 404 for non-existent content."""
        response = client.get("/api/v1/contents/99999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_content_includes_metadata(self, client, sample_contents):
        """Returns content with metadata_json field."""
        # sample_contents[2] has metadata_json
        youtube_content = sample_contents[2]
        response = client.get(f"/api/v1/contents/{youtube_content.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["metadata_json"] is not None
        assert "video_id" in data["metadata_json"]


class TestCreateContent:
    """Tests for POST /api/v1/contents endpoint."""

    def test_create_content_success(self, client):
        """Creates new content with valid data."""
        payload = {
            "source_type": "manual",
            "title": "New Test Content",
            "markdown_content": "# Test Content\n\nThis is test content.",
            "author": "Test Author",
            "publication": "Test Publication",
        }
        response = client.post("/api/v1/contents", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Test Content"
        assert data["source_type"] == "manual"
        # Default status is "pending" when created via API
        assert data["status"] in ["pending", "parsed"]
        assert data["id"] is not None

    def test_create_content_auto_generates_source_id(self, client):
        """Auto-generates source_id if not provided."""
        payload = {
            "source_type": "manual",
            "title": "Auto ID Content",
            "markdown_content": "# Content",
        }
        response = client.post("/api/v1/contents", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["source_id"] is not None
        assert data["source_id"].startswith("manual_")

    def test_create_content_with_source_id(self, client):
        """Uses provided source_id."""
        payload = {
            "source_type": "rss",
            "source_id": "custom-source-123",
            "title": "Custom ID Content",
            "markdown_content": "# Content",
        }
        response = client.post("/api/v1/contents", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["source_id"] == "custom-source-123"

    def test_create_content_validation_error(self, client):
        """Returns 422 for invalid data."""
        payload = {
            "source_type": "invalid_source",
            "title": "Test",
            "markdown_content": "# Content",
        }
        response = client.post("/api/v1/contents", json=payload)
        assert response.status_code == 422

    def test_create_content_duplicate_source_id(self, client, sample_content):
        """Returns error for duplicate source_type + source_id."""
        payload = {
            "source_type": sample_content.source_type.value,
            "source_id": sample_content.source_id,
            "title": "Duplicate Content",
            "markdown_content": "# Content",
        }
        response = client.post("/api/v1/contents", json=payload)
        # Should return 409 Conflict or 400 Bad Request
        assert response.status_code in [400, 409]


class TestDeleteContent:
    """Tests for DELETE /api/v1/contents/{id} endpoint."""

    def test_delete_content_success(self, client, sample_content, db_session):
        """Deletes content successfully."""
        content_id = sample_content.id
        response = client.delete(f"/api/v1/contents/{content_id}")
        assert response.status_code == 204

        # Verify deletion
        deleted = db_session.get(Content, content_id)
        assert deleted is None

    def test_delete_content_not_found(self, client):
        """Returns 404 for non-existent content."""
        response = client.delete("/api/v1/contents/99999")
        assert response.status_code == 404


class TestContentDuplicates:
    """Tests for duplicate detection and merging endpoints."""

    def test_get_duplicates_empty(self, client, sample_content):
        """Returns empty list when no duplicates exist."""
        response = client.get(f"/api/v1/contents/{sample_content.id}/duplicates")
        assert response.status_code == 200
        data = response.json()
        # API returns list directly, not dict with "duplicates" key
        assert data == []

    def test_get_duplicates_with_canonical(self, client, db_session, sample_content):
        """Returns duplicates that have this content as canonical."""
        # Create a content that points to sample_content as canonical
        duplicate = Content(
            source_type=ContentSource.RSS,
            source_id="duplicate-source",
            title="Duplicate Content",
            markdown_content=sample_content.markdown_content,
            content_hash="different-hash-123",
            canonical_id=sample_content.id,  # Points to sample_content
            status=ContentStatus.PARSED,
            ingested_at=datetime.now(UTC),
        )
        db_session.add(duplicate)
        db_session.commit()
        db_session.refresh(duplicate)

        response = client.get(f"/api/v1/contents/{sample_content.id}/duplicates")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == duplicate.id

    def test_merge_duplicates_success(self, client, db_session, sample_content):
        """Merges duplicate by setting canonical_id."""
        # Create a duplicate
        duplicate = Content(
            source_type=ContentSource.RSS,
            source_id="to-merge-source",
            title="To Merge Content",
            markdown_content="# Duplicate content",
            content_hash="different-hash",
            status=ContentStatus.PARSED,
            ingested_at=datetime.now(UTC),
        )
        db_session.add(duplicate)
        db_session.commit()
        db_session.refresh(duplicate)

        response = client.post(f"/api/v1/contents/{sample_content.id}/merge/{duplicate.id}")
        assert response.status_code == 200

        # Verify canonical_id was set
        db_session.refresh(duplicate)
        assert duplicate.canonical_id == sample_content.id

    def test_merge_duplicates_not_found(self, client, sample_content):
        """Returns 404 when duplicate doesn't exist."""
        response = client.post(f"/api/v1/contents/{sample_content.id}/merge/99999")
        assert response.status_code == 404

    def test_merge_duplicates_self(self, client, sample_content):
        """Returns 400 when trying to merge with self."""
        response = client.post(f"/api/v1/contents/{sample_content.id}/merge/{sample_content.id}")
        assert response.status_code == 400


class TestContentStats:
    """Tests for GET /api/v1/contents/stats endpoint."""

    def test_stats_empty_database(self, client):
        """Returns zero counts for empty database."""
        response = client.get("/api/v1/contents/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["by_status"] == {}
        assert data["by_source"] == {}

    def test_stats_with_data(self, client, sample_contents):
        """Returns correct statistics for content."""
        response = client.get("/api/v1/contents/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        # sample_contents has: GMAIL, RSS, YOUTUBE
        assert "gmail" in data["by_source"]
        assert "rss" in data["by_source"]
        assert "youtube" in data["by_source"]
        # sample_contents has: 2 parsed, 1 completed
        assert "parsed" in data["by_status"]
        assert "completed" in data["by_status"]

    def test_stats_needs_summarization(self, client, sample_contents):
        """Returns count of content needing summarization."""
        response = client.get("/api/v1/contents/stats")
        assert response.status_code == 200
        data = response.json()
        # Only PENDING and PARSED items need summarization
        # sample_contents has 2 PARSED and 1 COMPLETED (without summary)
        # The COMPLETED item is excluded as it's considered fully processed
        assert data["needs_summarization_count"] == 2


class TestTriggerIngestion:
    """Tests for POST /api/v1/contents/ingest endpoint."""

    def test_trigger_ingestion_gmail(self, client):
        """Triggers Gmail ingestion and returns task_id."""
        # The endpoint starts a background task and returns immediately
        payload = {
            "source": "gmail",
            "max_results": 10,
            "days_back": 7,
        }
        response = client.post("/api/v1/contents/ingest", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["message"] == "Content ingestion queued"
        assert data["source"] == "gmail"

    def test_trigger_ingestion_rss(self, client):
        """Triggers RSS ingestion and returns task_id."""
        payload = {
            "source": "rss",
            "max_results": 50,
            "days_back": 3,
        }
        response = client.post("/api/v1/contents/ingest", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["source"] == "rss"

    def test_trigger_ingestion_invalid_source(self, client):
        """Returns 422 for invalid source type."""
        payload = {
            "source": "invalid",
            "max_results": 10,
        }
        response = client.post("/api/v1/contents/ingest", json=payload)
        assert response.status_code == 422


class TestTriggerSummarization:
    """Tests for POST /api/v1/contents/summarize endpoint."""

    def test_trigger_summarization_all_pending(self, client, sample_contents):
        """Triggers summarization for all pending content."""
        # The endpoint starts a background task and returns immediately
        payload = {}  # Empty = all pending
        response = client.post("/api/v1/contents/summarize", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert "queued_count" in data

    def test_trigger_summarization_specific_ids(self, client, sample_contents):
        """Triggers summarization for specific content IDs."""
        payload = {
            "content_ids": [sample_contents[0].id, sample_contents[2].id],
        }
        response = client.post("/api/v1/contents/summarize", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data


class TestContentWithSummary:
    """Tests for content-summary relationships."""

    def test_get_content_shows_completed_status(self, client, sample_content_with_summary):
        """Content with summary shows completed status."""
        content, _summary = sample_content_with_summary
        response = client.get(f"/api/v1/contents/{content.id}")
        assert response.status_code == 200
        data = response.json()
        # Status should be completed since it has a summary
        assert data["status"] == "completed"

    def test_get_summary_by_content_id(self, client, sample_content_with_summary):
        """Can retrieve summary using content_id."""
        content, summary = sample_content_with_summary
        response = client.get(f"/api/v1/summaries/by-content/{content.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["content_id"] == content.id
        assert data["executive_summary"] == summary.executive_summary
