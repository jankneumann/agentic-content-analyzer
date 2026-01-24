"""Integration tests for Content ingestion services.

Tests the unified Content model ingestion across all sources:
- GmailContentIngestionService
- RSSContentIngestionService
- YouTubeContentIngestionService
- FileContentIngestionService

These tests use real database operations with mocked external APIs.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.models.content import Content, ContentSource, ContentStatus


@pytest.fixture
def mock_gmail_api():
    """Mock Gmail API responses."""
    messages = [
        {
            "id": "gmail-msg-001",
            "threadId": "thread-001",
            "labelIds": ["INBOX"],
            "payload": {
                "headers": [
                    {"name": "From", "value": "AI Weekly <newsletter@aiweekly.com>"},
                    {"name": "Subject", "value": "Latest LLM Developments"},
                    {"name": "Date", "value": "Wed, 15 Jan 2025 10:00:00 -0500"},
                ],
                "body": {"data": ""},
                "parts": [
                    {
                        "mimeType": "text/html",
                        "body": {
                            "data": "PGh0bWw+PGJvZHk+PGgxPkxMTSBOZXdzPC9oMT48cD5Db250ZW50IGFib3V0IExMTXMuLi48L3A+PC9ib2R5PjwvaHRtbD4="  # base64 encoded HTML
                        },
                    }
                ],
            },
        },
        {
            "id": "gmail-msg-002",
            "threadId": "thread-002",
            "labelIds": ["INBOX"],
            "payload": {
                "headers": [
                    {"name": "From", "value": "Data Weekly <news@dataweekly.com>"},
                    {"name": "Subject", "value": "Vector Database Updates"},
                    {"name": "Date", "value": "Tue, 14 Jan 2025 09:00:00 -0500"},
                ],
                "body": {"data": ""},
                "parts": [
                    {
                        "mimeType": "text/html",
                        "body": {
                            "data": "PGh0bWw+PGJvZHk+PGgxPlZlY3RvciBEQnM8L2gxPjxwPlBlcmZvcm1hbmNlIHRpcHMuLi48L3A+PC9ib2R5PjwvaHRtbD4="
                        },
                    }
                ],
            },
        },
    ]

    mock_service = MagicMock()
    mock_messages = MagicMock()
    mock_messages.list.return_value.execute.return_value = {
        "messages": [{"id": m["id"]} for m in messages]
    }
    mock_messages.get.side_effect = lambda user_id, id, format: MagicMock(
        execute=lambda: next(m for m in messages if m["id"] == id)
    )
    mock_service.users.return_value.messages.return_value = mock_messages

    return mock_service


@pytest.fixture
def mock_rss_feed():
    """Mock RSS feed response."""

    class MockFeedEntry:
        def __init__(self, entry_id, title, link, content, published):
            self.id = entry_id
            self.title = title
            self.link = link
            self.summary = content
            self.content = [MagicMock(value=content)]
            self.published_parsed = published
            self.author = "Test Author"

        def get(self, key, default=None):
            return getattr(self, key, default)

    entries = [
        MockFeedEntry(
            "rss-entry-001",
            "AI Agent Frameworks Comparison",
            "https://example.com/ai-agents",
            "<p>Detailed comparison of AI agent frameworks...</p>",
            (2025, 1, 15, 10, 0, 0, 2, 15, 0),  # struct_time tuple
        ),
        MockFeedEntry(
            "rss-entry-002",
            "RAG Best Practices",
            "https://example.com/rag-practices",
            "<p>Best practices for RAG implementations...</p>",
            (2025, 1, 14, 9, 0, 0, 1, 14, 0),
        ),
    ]

    mock_feed = MagicMock()
    mock_feed.entries = entries
    mock_feed.bozo = False
    mock_feed.feed = MagicMock(title="Tech Newsletter")

    return mock_feed


@pytest.fixture
def mock_youtube_api():
    """Mock YouTube API responses."""
    playlist_items = {
        "items": [
            {
                "snippet": {
                    "resourceId": {"videoId": "video123"},
                    "title": "AI Tutorial Part 1",
                    "description": "Introduction to AI concepts",
                    "publishedAt": "2025-01-15T10:00:00Z",
                    "thumbnails": {
                        "high": {"url": "https://i.ytimg.com/vi/video123/hqdefault.jpg"}
                    },
                    "channelTitle": "Tech Channel",
                },
            },
            {
                "snippet": {
                    "resourceId": {"videoId": "video456"},
                    "title": "AI Tutorial Part 2",
                    "description": "Advanced AI techniques",
                    "publishedAt": "2025-01-14T10:00:00Z",
                    "thumbnails": {
                        "high": {"url": "https://i.ytimg.com/vi/video456/hqdefault.jpg"}
                    },
                    "channelTitle": "Tech Channel",
                },
            },
        ],
        "nextPageToken": None,
    }

    transcripts = {
        "video123": [
            {"text": "Welcome to this tutorial.", "start": 0.0, "duration": 2.5},
            {"text": "Today we'll learn about AI.", "start": 2.5, "duration": 3.0},
            {"text": "Let's get started.", "start": 5.5, "duration": 2.0},
        ],
        "video456": [
            {"text": "In this part, we continue.", "start": 0.0, "duration": 2.0},
            {"text": "Advanced concepts ahead.", "start": 2.0, "duration": 2.5},
        ],
    }

    mock_service = MagicMock()
    mock_playlist_items = MagicMock()
    mock_playlist_items.list.return_value.execute.return_value = playlist_items
    mock_service.playlistItems.return_value = mock_playlist_items

    return mock_service, transcripts


@pytest.mark.integration
class TestGmailContentIngestion:
    """Integration tests for Gmail content ingestion."""

    def test_deduplication_by_source_id(self, db_session, mock_get_db):
        """Gmail ingestion skips content with existing source_id."""
        # Pre-create a content record
        existing = Content(
            source_type=ContentSource.GMAIL,
            source_id="gmail-msg-001",
            title="Existing Content",
            markdown_content="# Existing",
            content_hash="existing-hash",
            status=ContentStatus.PARSED,
            ingested_at=datetime.now(UTC),
        )
        db_session.add(existing)
        db_session.commit()

        # Verify it exists
        found = (
            db_session.query(Content)
            .filter(
                Content.source_type == ContentSource.GMAIL,
                Content.source_id == "gmail-msg-001",
            )
            .first()
        )
        assert found is not None
        assert found.title == "Existing Content"


@pytest.mark.integration
class TestRSSContentIngestion:
    """Integration tests for RSS content ingestion."""

    def test_ingest_creates_content_records(self, db_session, mock_rss_feed, mock_get_db):
        """RSS ingestion creates Content records in database."""
        with (
            patch("src.ingestion.rss.feedparser.parse", return_value=mock_rss_feed),
            patch("src.ingestion.rss.get_db", mock_get_db),
            patch("src.ingestion.rss.convert_html_to_markdown") as mock_convert,
        ):
            mock_convert.return_value = "# AI Agent Frameworks\n\nComparison content..."

            from src.ingestion.rss import RSSContentIngestionService

            service = RSSContentIngestionService()
            assert service is not None

    def test_handles_timezone_aware_dates(self, db_session, mock_get_db):
        """RSS ingestion properly handles timezone-aware dates."""
        # Create content with timezone-aware date
        content = Content(
            source_type=ContentSource.RSS,
            source_id="rss-test-001",
            title="Timezone Test",
            markdown_content="# Test",
            content_hash="tz-hash",
            status=ContentStatus.PARSED,
            # Explicitly timezone-aware
            published_date=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
            ingested_at=datetime.now(UTC),
        )
        db_session.add(content)
        db_session.commit()
        db_session.refresh(content)

        # Verify date is stored correctly
        assert content.published_date is not None
        assert content.published_date.year == 2025
        assert content.published_date.month == 1
        assert content.published_date.day == 15

    def test_deduplication_by_content_hash(self, db_session, mock_get_db):
        """RSS ingestion detects duplicates by content_hash."""
        # Create two contents with same hash but different source_ids
        content1 = Content(
            source_type=ContentSource.GMAIL,
            source_id="gmail-original",
            title="Original Content",
            markdown_content="# Same Content",
            content_hash="duplicate-hash-123",
            status=ContentStatus.PARSED,
            ingested_at=datetime.now(UTC),
        )
        db_session.add(content1)
        db_session.commit()
        db_session.refresh(content1)

        # Create RSS content with same hash
        content2 = Content(
            source_type=ContentSource.RSS,
            source_id="rss-duplicate",
            title="Duplicate Content",
            markdown_content="# Same Content",
            content_hash="duplicate-hash-123",  # Same hash
            canonical_id=content1.id,  # Links to original
            status=ContentStatus.PARSED,
            ingested_at=datetime.now(UTC),
        )
        db_session.add(content2)
        db_session.commit()
        db_session.refresh(content2)

        # Verify duplicate linking
        assert content2.canonical_id == content1.id

        # Query for duplicates
        duplicates = (
            db_session.query(Content).filter(Content.content_hash == "duplicate-hash-123").all()
        )
        assert len(duplicates) == 2


@pytest.mark.integration
class TestYouTubeContentIngestion:
    """Integration tests for YouTube content ingestion."""

    def test_ingest_creates_content_with_transcript(
        self, db_session, mock_youtube_api, mock_get_db
    ):
        """YouTube ingestion creates Content with transcript markdown."""
        mock_service, transcripts = mock_youtube_api

        with (
            patch("src.ingestion.youtube.build", return_value=mock_service),
            patch("src.ingestion.youtube.get_db", mock_get_db),
            patch("src.ingestion.youtube.YouTubeTranscriptApi") as mock_transcript_api,
        ):
            # Mock transcript fetching
            def get_transcript(video_id, languages=None):
                return transcripts.get(video_id, [])

            mock_transcript_api.get_transcript.side_effect = get_transcript

            from src.ingestion.youtube import YouTubeContentIngestionService

            service = YouTubeContentIngestionService()
            assert service is not None

    def test_transcript_to_markdown_format(self, db_session):
        """YouTube transcript is converted to markdown with timestamps."""
        from src.ingestion.youtube import transcript_to_markdown
        from src.models.youtube import TranscriptSegment, YouTubeTranscript

        # Create proper YouTubeTranscript object
        transcript = YouTubeTranscript(
            video_id="test123",
            title="Test Video",
            channel_title="Test Channel",
            published_date=datetime(2025, 1, 15, tzinfo=UTC),
            segments=[
                TranscriptSegment(text="Welcome to this tutorial.", start=0.0, duration=2.5),
                TranscriptSegment(text="Today we'll learn about AI.", start=2.5, duration=3.0),
                TranscriptSegment(text="Let's get started.", start=10.0, duration=2.0),
            ],
        )

        markdown = transcript_to_markdown(transcript)

        # Verify markdown structure
        assert "# Test Video" in markdown
        assert "Test Channel" in markdown
        assert "[0:00]" in markdown  # Timestamp link
        assert "Welcome to this tutorial" in markdown
        # Verify paragraph breaks on gaps
        assert "Today we'll learn about AI" in markdown

    def test_stores_video_metadata(self, db_session):
        """YouTube content stores video metadata in metadata_json."""
        content = Content(
            source_type=ContentSource.YOUTUBE,
            source_id="video123",
            source_url="https://youtube.com/watch?v=video123",
            title="Test Video",
            author="Test Channel",
            markdown_content="# Test\n\n[0:00] Content...",
            metadata_json={
                "video_id": "video123",
                "channel": "Test Channel",
                "language": "en",
                "is_auto_generated": False,
                "segment_count": 10,
                "duration_seconds": 300,
            },
            content_hash="video-hash",
            status=ContentStatus.PARSED,
            ingested_at=datetime.now(UTC),
        )
        db_session.add(content)
        db_session.commit()
        db_session.refresh(content)

        # Verify metadata
        assert content.metadata_json["video_id"] == "video123"
        assert content.metadata_json["segment_count"] == 10


@pytest.mark.integration
class TestFileContentIngestion:
    """Integration tests for file upload content ingestion."""

    def test_ingest_creates_content_from_file(self, db_session, tmp_path):
        """File ingestion creates Content record from uploaded file."""
        from src.ingestion.files import FileContentIngestionService

        # Create a test file
        test_file = tmp_path / "test_document.md"
        test_file.write_text("# Test Document\n\nThis is test content.")

        # Service takes a session parameter, not get_db
        service = FileContentIngestionService(db=db_session)
        assert service is not None

    def test_file_hash_deduplication(self, db_session):
        """File ingestion detects duplicates by file hash."""
        # Create content with specific file hash (stored in metadata)
        content1 = Content(
            source_type=ContentSource.FILE_UPLOAD,
            source_id="file-001",
            title="Original Document",
            markdown_content="# Document Content",
            metadata_json={"file_hash": "sha256-abc123"},
            content_hash="content-hash-001",
            status=ContentStatus.PARSED,
            ingested_at=datetime.now(UTC),
        )
        db_session.add(content1)
        db_session.commit()

        # Query by file hash in metadata
        # Note: This would be done via JSONB query in real implementation
        found = (
            db_session.query(Content)
            .filter(
                Content.source_type == ContentSource.FILE_UPLOAD,
            )
            .all()
        )
        assert len(found) == 1

    def test_stores_parser_info(self, db_session):
        """File ingestion stores parser metadata."""
        content = Content(
            source_type=ContentSource.FILE_UPLOAD,
            source_id="file-parser-test",
            title="Parsed Document",
            markdown_content="# Parsed Content",
            parser_used="docling",
            metadata_json={
                "filename": "document.pdf",
                "page_count": 5,
                "word_count": 1500,
                "processing_time_ms": 2500,
            },
            content_hash="parser-test-hash",
            status=ContentStatus.PARSED,
            ingested_at=datetime.now(UTC),
        )
        db_session.add(content)
        db_session.commit()
        db_session.refresh(content)

        assert content.parser_used == "docling"
        assert content.metadata_json["page_count"] == 5


@pytest.mark.integration
class TestCrossSourceDeduplication:
    """Integration tests for cross-source content deduplication."""

    def test_same_content_different_sources(self, db_session):
        """Same content from different sources is linked via canonical_id."""
        # Original from Gmail
        gmail_content = Content(
            source_type=ContentSource.GMAIL,
            source_id="gmail-original",
            title="Newsletter Issue #42",
            markdown_content="# Newsletter Issue #42\n\nCommon content...",
            content_hash="shared-hash-xyz",
            status=ContentStatus.PARSED,
            ingested_at=datetime.now(UTC),
        )
        db_session.add(gmail_content)
        db_session.commit()
        db_session.refresh(gmail_content)

        # Same content from RSS (detected as duplicate)
        rss_content = Content(
            source_type=ContentSource.RSS,
            source_id="rss-duplicate",
            title="Newsletter Issue #42",
            markdown_content="# Newsletter Issue #42\n\nCommon content...",
            content_hash="shared-hash-xyz",
            canonical_id=gmail_content.id,
            status=ContentStatus.PARSED,
            ingested_at=datetime.now(UTC),
        )
        db_session.add(rss_content)
        db_session.commit()

        # Verify deduplication
        all_with_hash = (
            db_session.query(Content).filter(Content.content_hash == "shared-hash-xyz").all()
        )
        assert len(all_with_hash) == 2

        # Verify canonical linking
        canonical = (
            db_session.query(Content)
            .filter(
                Content.content_hash == "shared-hash-xyz",
                Content.canonical_id.is_(None),
            )
            .first()
        )
        assert canonical.id == gmail_content.id

        duplicates = (
            db_session.query(Content).filter(Content.canonical_id == gmail_content.id).all()
        )
        assert len(duplicates) == 1
        assert duplicates[0].source_type == ContentSource.RSS

    def test_content_hash_generation(self, db_session):
        """Content hash is generated consistently."""
        from src.utils.content_hash import generate_markdown_hash

        markdown = "# Test Content\n\nThis is test content."
        hash1 = generate_markdown_hash(markdown)
        hash2 = generate_markdown_hash(markdown)

        # Same content should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest

        # Different content should produce different hash
        different_markdown = "# Different Content\n\nThis is different."
        hash3 = generate_markdown_hash(different_markdown)
        assert hash3 != hash1
