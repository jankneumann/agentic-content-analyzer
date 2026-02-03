"""Integration tests for the Save URL API endpoints.

Tests the mobile content capture API including:
- POST /api/v1/content/save-url - Save URLs for extraction
- GET /api/v1/content/{id}/status - Check extraction status
- GET /api/v1/content/save - Web save page
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from src.models.content import Content, ContentSource, ContentStatus
from src.utils.content_hash import generate_markdown_hash


class TestSaveURLEndpoint:
    """Tests for POST /api/v1/content/save-url."""

    def test_save_url_creates_content(self, client, db_session):
        """Successfully creates content record for new URL."""
        with patch("src.api.save_routes._enqueue_extraction", new_callable=AsyncMock):
            response = client.post(
                "/api/v1/content/save-url",
                json={
                    "url": "https://example.com/article",
                    "title": "Test Article",
                    "source": "ios_shortcut",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "queued"
        assert data["duplicate"] is False
        assert "content_id" in data
        assert data["message"] == "URL saved. Content extraction in progress."

        # Verify content was created in database
        content = db_session.query(Content).filter(Content.id == data["content_id"]).first()
        assert content is not None
        assert content.source_url == "https://example.com/article"
        assert content.title == "Test Article"
        assert content.status == ContentStatus.PENDING
        assert content.source_type == ContentSource.WEBPAGE
        # Verify NOT NULL fields are populated
        assert content.source_id == "webpage:https://example.com/article"
        assert content.markdown_content == ""
        assert content.content_hash is not None and len(content.content_hash) == 64

    def test_save_url_detects_duplicate(self, client, db_session):
        """Returns existing content for duplicate URL."""
        # Create existing content
        existing = Content(
            source_type=ContentSource.WEBPAGE,
            source_id="webpage:https://example.com/existing",
            source_url="https://example.com/existing",
            title="Existing Article",
            markdown_content="Existing content.",
            content_hash=generate_markdown_hash("Existing content."),
            status=ContentStatus.PARSED,
            ingested_at=datetime.now(UTC),
        )
        db_session.add(existing)
        db_session.commit()
        existing_id = existing.id

        # Try to save the same URL
        with patch("src.api.save_routes._enqueue_extraction", new_callable=AsyncMock):
            response = client.post(
                "/api/v1/content/save-url",
                json={"url": "https://example.com/existing"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "exists"
        assert data["duplicate"] is True
        assert data["content_id"] == existing_id

    def test_save_url_with_all_fields(self, client, db_session):
        """Saves all optional fields to metadata."""
        with patch("src.api.save_routes._enqueue_extraction", new_callable=AsyncMock):
            response = client.post(
                "/api/v1/content/save-url",
                json={
                    "url": "https://example.com/full-article",
                    "title": "Full Article",
                    "excerpt": "This is a selected excerpt from the page.",
                    "tags": ["ai", "technology"],
                    "notes": "Important article about AI trends.",
                    "source": "bookmarklet",
                },
            )

        assert response.status_code == 201
        data = response.json()

        # Verify metadata was stored
        content = db_session.query(Content).filter(Content.id == data["content_id"]).first()
        assert content.metadata_json["excerpt"] == "This is a selected excerpt from the page."
        assert content.metadata_json["tags"] == ["ai", "technology"]
        assert content.metadata_json["notes"] == "Important article about AI trends."
        assert content.metadata_json["capture_source"] == "bookmarklet"

    def test_save_url_uses_url_as_title_when_not_provided(self, client, db_session):
        """Uses URL as title when title not provided."""
        with patch("src.api.save_routes._enqueue_extraction", new_callable=AsyncMock):
            response = client.post(
                "/api/v1/content/save-url",
                json={"url": "https://example.com/no-title"},
            )

        assert response.status_code == 201
        content = (
            db_session.query(Content).filter(Content.id == response.json()["content_id"]).first()
        )
        assert content.title == "https://example.com/no-title"

    def test_save_url_validates_url_format(self, client):
        """Rejects invalid URL formats."""
        response = client.post(
            "/api/v1/content/save-url",
            json={"url": "not-a-valid-url"},
        )

        assert response.status_code == 422  # Validation error

    def test_save_url_requires_url_field(self, client):
        """Requires url field in request body."""
        response = client.post(
            "/api/v1/content/save-url",
            json={"title": "No URL provided"},
        )

        assert response.status_code == 422


class TestContentStatusEndpoint:
    """Tests for GET /api/v1/content/{id}/status."""

    def test_get_status_pending(self, client, db_session):
        """Returns status for pending content."""
        content = Content(
            source_type=ContentSource.WEBPAGE,
            source_id="webpage:https://example.com/pending",
            source_url="https://example.com/pending",
            title="Pending Article",
            markdown_content="",
            content_hash=generate_markdown_hash(""),
            status=ContentStatus.PENDING,
            ingested_at=datetime.now(UTC),
        )
        db_session.add(content)
        db_session.commit()

        response = client.get(f"/api/v1/content/{content.id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["content_id"] == content.id
        assert data["status"] == "pending"
        assert data["title"] == "Pending Article"
        assert data["word_count"] is None
        assert data["error"] is None

    def test_get_status_parsed(self, client, db_session):
        """Returns status with word count for parsed content."""
        content = Content(
            source_type=ContentSource.WEBPAGE,
            source_id="webpage:https://example.com/parsed",
            source_url="https://example.com/parsed",
            title="Parsed Article",
            markdown_content="This is the extracted content with several words.",
            content_hash=generate_markdown_hash(
                "This is the extracted content with several words."
            ),
            status=ContentStatus.PARSED,
            ingested_at=datetime.now(UTC),
        )
        db_session.add(content)
        db_session.commit()

        response = client.get(f"/api/v1/content/{content.id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "parsed"
        assert data["word_count"] == 8  # "This is the extracted content with several words."

    def test_get_status_failed(self, client, db_session):
        """Returns error message for failed content."""
        content = Content(
            source_type=ContentSource.WEBPAGE,
            source_id="webpage:https://example.com/failed",
            source_url="https://example.com/failed",
            title="Failed Article",
            markdown_content="",
            content_hash=generate_markdown_hash(""),
            status=ContentStatus.FAILED,
            error_message="Connection timeout after 30 seconds",
            ingested_at=datetime.now(UTC),
        )
        db_session.add(content)
        db_session.commit()

        response = client.get(f"/api/v1/content/{content.id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "Connection timeout after 30 seconds"

    def test_get_status_not_found(self, client):
        """Returns 404 for non-existent content."""
        response = client.get("/api/v1/content/99999/status")

        assert response.status_code == 404
        assert response.json()["detail"] == "Content not found"


class TestSavePageEndpoint:
    """Tests for GET /api/v1/content/save (web save page)."""

    def test_save_page_renders(self, client):
        """Renders the save page HTML."""
        response = client.get("/api/v1/content/save")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_save_page_prefills_url(self, client):
        """Pre-fills URL from query parameter."""
        response = client.get("/api/v1/content/save?url=https://example.com/prefilled")

        assert response.status_code == 200
        assert "https://example.com/prefilled" in response.text

    def test_save_page_prefills_title_and_excerpt(self, client):
        """Pre-fills title and excerpt from query parameters."""
        response = client.get(
            "/api/v1/content/save"
            "?url=https://example.com/article"
            "&title=Test%20Title"
            "&excerpt=Selected%20text"
        )

        assert response.status_code == 200
        assert "Test Title" in response.text
        assert "Selected text" in response.text

    def test_save_page_escapes_special_characters(self, client):
        """Verifies XSS protection via Jinja2 autoescaping."""
        response = client.get(
            '/api/v1/content/save?url=https://example.com/"onmouseover="alert(1)'
            '&title=<script>alert("xss")</script>'
        )

        assert response.status_code == 200
        # Raw script tag should not appear in output (Jinja2 escapes it)
        assert "<script>alert" not in response.text
        # Escaped version should be present
        assert "&lt;script&gt;" in response.text or "&#" in response.text

    def test_save_page_includes_api_base_url(self, client):
        """Save page includes the API base URL for cross-origin support."""
        response = client.get("/api/v1/content/save")

        assert response.status_code == 200
        assert "API_BASE" in response.text


class TestBookmarkletPageEndpoint:
    """Tests for GET /api/v1/content/bookmarklet (installation page)."""

    def test_bookmarklet_page_renders(self, client):
        """Renders the bookmarklet installation page."""
        response = client.get("/api/v1/content/bookmarklet")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_bookmarklet_page_contains_bookmarklet_code(self, client):
        """Page contains the bookmarklet JavaScript code."""
        response = client.get("/api/v1/content/bookmarklet")

        assert response.status_code == 200
        assert "javascript:" in response.text
        assert "/api/v1/content/save" in response.text

    def test_bookmarklet_page_includes_api_base_url(self, client):
        """Bookmarklet code includes the server's base URL."""
        response = client.get("/api/v1/content/bookmarklet")

        assert response.status_code == 200
        # The template injects api_base_url into the bookmarklet code
        assert "api_base_url" in response.text or "BASE_URL" in response.text


class TestCORSConfiguration:
    """Tests for CORS configuration allowing mobile clients."""

    def test_cors_allows_configured_origins(self, client):
        """CORS headers allow requests from configured origins."""
        # Send a regular request with Origin header to check CORS response
        response = client.get(
            "/api/v1/content/save",
            headers={"Origin": "http://localhost:3000"},
        )

        assert response.status_code == 200
        # CORS middleware should include Access-Control-Allow-Origin for configured origins
        cors_header = response.headers.get("access-control-allow-origin")
        assert cors_header is not None, "CORS Access-Control-Allow-Origin header missing"


class TestInputValidation:
    """Tests for request validation edge cases."""

    def test_save_url_rejects_oversized_tags(self, client):
        """Rejects tags exceeding per-tag length limit."""
        response = client.post(
            "/api/v1/content/save-url",
            json={
                "url": "https://example.com/tag-test",
                "tags": ["a" * 101],  # Exceeds 100 char limit
            },
        )

        assert response.status_code == 422


class TestEnqueueExtraction:
    """Tests for the extraction enqueuing logic."""

    def test_enqueue_uses_pgqueuer_when_available(self, client, db_session):
        """Uses PGQueuer to enqueue extraction when available."""
        mock_queries = AsyncMock()

        with patch("src.queue.setup.get_queue_queries", return_value=mock_queries):
            response = client.post(
                "/api/v1/content/save-url",
                json={"url": "https://example.com/enqueue-test"},
            )

        assert response.status_code == 201
        # Note: Due to background task execution, we can't easily verify the enqueue call
        # in this test. The _enqueue_extraction function is tested separately.


class TestSavePageEndpointAPI:
    """Tests for POST /api/v1/content/save-page (client HTML capture)."""

    def test_save_page_creates_content_with_html(self, client, db_session):
        """Successfully creates content record with HTML payload."""
        html_content = (
            "<html><head><title>Test Article</title></head><body><p>Test content</p></body></html>"
        )

        with patch("src.api.save_routes._process_client_html", new_callable=AsyncMock):
            response = client.post(
                "/api/v1/content/save-page",
                json={
                    "url": "https://example.com/paywall-article",
                    "html": html_content,
                    "title": "Test Paywall Article",
                    "source": "chrome_extension",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "queued"
        assert data["duplicate"] is False
        assert "content_id" in data
        assert data["message"] == "Page saved. Content processing in progress."

        # Verify content was created with correct metadata
        content = db_session.query(Content).filter(Content.id == data["content_id"]).first()
        assert content is not None
        assert content.source_url == "https://example.com/paywall-article"
        assert content.title == "Test Paywall Article"
        assert content.status == ContentStatus.PENDING
        assert content.source_type == ContentSource.WEBPAGE
        assert content.metadata_json["capture_method"] == "client_html"
        assert content.metadata_json["capture_source"] == "chrome_extension"

    def test_save_page_rejects_missing_html(self, client):
        """Rejects request without required html field."""
        response = client.post(
            "/api/v1/content/save-page",
            json={
                "url": "https://example.com/no-html",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_save_page_rejects_missing_url(self, client):
        """Rejects request without required url field."""
        response = client.post(
            "/api/v1/content/save-page",
            json={
                "html": "<html></html>",
            },
        )

        assert response.status_code == 422  # Validation error

    def test_save_page_detects_duplicate_url(self, client, db_session):
        """Returns existing content for duplicate URL."""
        # Create existing content
        existing = Content(
            source_type=ContentSource.WEBPAGE,
            source_id="webpage:https://example.com/existing-page",
            source_url="https://example.com/existing-page",
            title="Existing Page",
            markdown_content="Existing content.",
            content_hash=generate_markdown_hash("Existing content."),
            status=ContentStatus.PARSED,
            ingested_at=datetime.now(UTC),
        )
        db_session.add(existing)
        db_session.commit()
        existing_id = existing.id

        # Try to save the same URL with HTML
        with patch("src.api.save_routes._process_client_html", new_callable=AsyncMock):
            response = client.post(
                "/api/v1/content/save-page",
                json={
                    "url": "https://example.com/existing-page",
                    "html": "<html><body>Different content</body></html>",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "exists"
        assert data["duplicate"] is True
        assert data["content_id"] == existing_id

    def test_save_page_with_all_optional_fields(self, client, db_session):
        """Saves all optional fields to metadata."""
        html_content = "<html><body><p>Full page content</p></body></html>"

        with patch("src.api.save_routes._process_client_html", new_callable=AsyncMock):
            response = client.post(
                "/api/v1/content/save-page",
                json={
                    "url": "https://example.com/full-page",
                    "html": html_content,
                    "title": "Full Page Article",
                    "excerpt": "Selected text from the page.",
                    "tags": ["ai", "technology"],
                    "notes": "Important article about AI.",
                    "source": "chrome_extension",
                },
            )

        assert response.status_code == 201
        data = response.json()

        # Verify all metadata was stored
        content = db_session.query(Content).filter(Content.id == data["content_id"]).first()
        assert content.metadata_json["capture_method"] == "client_html"
        assert content.metadata_json["excerpt"] == "Selected text from the page."
        assert content.metadata_json["tags"] == ["ai", "technology"]
        assert content.metadata_json["notes"] == "Important article about AI."
        assert content.metadata_json["capture_source"] == "chrome_extension"

    def test_save_page_rejects_oversized_html(self, client):
        """Rejects HTML payload exceeding 5 MB limit."""
        # Create HTML larger than 5 MB
        oversized_html = "<html>" + "x" * (5 * 1024 * 1024 + 1) + "</html>"

        response = client.post(
            "/api/v1/content/save-page",
            json={
                "url": "https://example.com/large-page",
                "html": oversized_html,
            },
        )

        assert response.status_code == 422  # Validation error for size constraint

    def test_save_page_uses_url_as_title_when_not_provided(self, client, db_session):
        """Uses URL as title when title not provided."""
        html_content = "<html><body><p>Content</p></body></html>"

        with patch("src.api.save_routes._process_client_html", new_callable=AsyncMock):
            response = client.post(
                "/api/v1/content/save-page",
                json={
                    "url": "https://example.com/no-title-page",
                    "html": html_content,
                },
            )

        assert response.status_code == 201
        content = (
            db_session.query(Content).filter(Content.id == response.json()["content_id"]).first()
        )
        assert content.title == "https://example.com/no-title-page"
