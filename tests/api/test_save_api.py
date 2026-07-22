"""Integration tests for the Save URL API endpoints.

Tests the mobile content capture API including:
- POST /api/v1/content/save-url - Save URLs for extraction
- GET /api/v1/content/{id}/status - Check extraction status
- GET /api/v1/content/save - Web save page
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.models.content import Content, ContentSource, ContentStatus
from src.utils.content_hash import generate_markdown_hash


def _use_session(session):
    """A get_db() replacement that yields the test session."""
    from contextlib import contextmanager

    @contextmanager
    def _cm():
        yield session

    return _cm


class TestProcessRoutedSave:
    """Background routing finalization, including failure surfacing."""

    @pytest.mark.asyncio
    async def test_youtube_no_content_marks_failed(self, db_session):
        """A video that yields no transcript leaves the row FAILED, not PENDING."""
        from unittest.mock import MagicMock

        from src.api.save_routes import _process_routed_save
        from src.ingestion.result import IngestionResponse

        row = Content(
            source_type=ContentSource.YOUTUBE,
            source_id="youtube:dQw4w9WgXcQ",
            source_url="https://youtu.be/dQw4w9WgXcQ",
            title="Pending video",
            markdown_content="",
            content_hash=generate_markdown_hash(""),
            status=ContentStatus.PENDING,
            metadata_json={"route": "youtube_video"},
            ingested_at=datetime.now(UTC),
        )
        db_session.add(row)
        db_session.commit()
        content_id = row.id

        svc = MagicMock()
        # No transcript / no Gemini -> ok envelope with nothing ingested.
        svc.ingest_video = AsyncMock(
            return_value=IngestionResponse(
                command="ingest.url", source="url", status="ok", items_skipped=1
            )
        )
        with (
            patch("src.ingestion.youtube.YouTubeContentIngestionService", return_value=svc),
            patch("src.api.save_routes.get_db", _use_session(db_session)),
        ):
            await _process_routed_save(content_id)

        refreshed = db_session.query(Content).filter(Content.id == content_id).first()
        assert refreshed.status == ContentStatus.FAILED
        assert refreshed.error_message

    @pytest.mark.asyncio
    async def test_failed_feed_not_completed(self, db_session):
        """An errored feed ingest marks the receipt FAILED, not COMPLETED."""
        from unittest.mock import MagicMock

        from src.api.save_routes import _process_routed_save
        from src.ingestion.result import IngestionError, IngestionResponse

        row = Content(
            source_type=ContentSource.RSS,
            source_id="feed:https://bad.example.com/feed",
            source_url="https://bad.example.com/feed",
            title="Pending feed",
            markdown_content="",
            content_hash=generate_markdown_hash(""),
            status=ContentStatus.PENDING,
            metadata_json={"route": "rss_feed"},
            ingested_at=datetime.now(UTC),
        )
        db_session.add(row)
        db_session.commit()
        content_id = row.id

        svc = MagicMock()
        svc.ingest_content = MagicMock(
            return_value=IngestionResponse(
                command="ingest.rss",
                source="rss",
                status="error",
                errors=[IngestionError(code="http_error", message="404 Not Found")],
            )
        )
        svc.close = MagicMock()
        with (
            patch("src.ingestion.rss.RSSContentIngestionService", return_value=svc),
            patch("src.api.save_routes.get_db", _use_session(db_session)),
        ):
            await _process_routed_save(content_id)

        refreshed = db_session.query(Content).filter(Content.id == content_id).first()
        assert refreshed.status == ContentStatus.FAILED
        assert "404" in (refreshed.error_message or "")


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
    """Tests for the retained canonical web save page."""

    def test_save_page_renders_canonical_ingestion_client(self, client):
        response = client.get("/api/v1/content/save")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "/api/v1/ingestions" in response.text
        assert "operation_id" in response.text

    def test_save_page_prefills_and_escapes_values(self, client):
        response = client.get(
            "/api/v1/content/save"
            "?url=https://example.com/article"
            "&title=%3Cscript%3Ealert(1)%3C/script%3E"
            "&excerpt=Selected%20text"
        )

        assert response.status_code == 200
        assert "https://example.com/article" in response.text
        assert "Selected text" in response.text
        assert "<script>alert" not in response.text
        assert "&lt;script&gt;" in response.text or "&#" in response.text


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


class TestShortcutPageEndpoint:
    def test_shortcut_uses_canonical_ingestion_contract(self, client):
        response = client.get("/api/v1/content/shortcut")

        assert response.status_code == 200
        assert "/api/v1/ingestions" in response.text
        assert '"kind": "url"' in response.text
        assert "operation_id" in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/content/save",
        "/api/v1/content/bookmarklet",
        "/api/v1/content/shortcut",
    ],
)
def test_retained_capture_pages_do_not_reference_retired_mutations(client, path):
    response = client.get(path)

    assert response.status_code == 200
    assert "/api/v1/content/save-url" not in response.text
    assert "/api/v1/content/save-page" not in response.text


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
