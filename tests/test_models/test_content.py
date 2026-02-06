"""Tests for the unified Content model.

Tests cover:
- ContentSource enum values and behavior
- ContentStatus enum values and behavior
- Content SQLAlchemy model creation and relationships
- Pydantic schemas for API operations
- Content → Summary and Content → Image relationships
"""

from datetime import UTC, datetime

import pytest

from src.models.content import (
    Content,
    ContentCreate,
    ContentListItem,
    ContentListResponse,
    ContentResponse,
    ContentSource,
    ContentStatus,
    ContentUpdate,
)
from src.models.image import Image
from src.models.summary import Summary


class TestContentSourceEnum:
    """Tests for ContentSource enum."""

    def test_all_source_types_defined(self):
        """Verify all expected source types exist."""
        expected_sources = {
            "gmail",
            "rss",
            "file_upload",
            "youtube",
            "manual",
            "webpage",
            "other",
            "podcast",
            "substack",
        }
        actual_sources = {source.value for source in ContentSource}
        assert actual_sources == expected_sources

    def test_source_string_representation(self):
        """Test that source values are lowercase strings."""
        assert ContentSource.GMAIL.value == "gmail"
        assert ContentSource.RSS.value == "rss"
        assert ContentSource.FILE_UPLOAD.value == "file_upload"
        assert ContentSource.YOUTUBE.value == "youtube"
        assert ContentSource.MANUAL.value == "manual"
        assert ContentSource.WEBPAGE.value == "webpage"
        assert ContentSource.OTHER.value == "other"

    def test_source_is_string_enum(self):
        """Test that ContentSource is a string enum for JSON serialization."""
        assert isinstance(ContentSource.GMAIL, str)
        assert ContentSource.GMAIL == "gmail"


class TestContentStatusEnum:
    """Tests for ContentStatus enum."""

    def test_all_status_values_defined(self):
        """Verify all expected status values exist."""
        expected_statuses = {
            "pending",
            "parsing",
            "parsed",
            "processing",
            "completed",
            "failed",
        }
        actual_statuses = {status.value for status in ContentStatus}
        assert actual_statuses == expected_statuses

    def test_status_string_representation(self):
        """Test that status values are lowercase strings."""
        assert ContentStatus.PENDING.value == "pending"
        assert ContentStatus.PARSING.value == "parsing"
        assert ContentStatus.PARSED.value == "parsed"
        assert ContentStatus.PROCESSING.value == "processing"
        assert ContentStatus.COMPLETED.value == "completed"
        assert ContentStatus.FAILED.value == "failed"

    def test_status_is_string_enum(self):
        """Test that ContentStatus is a string enum for JSON serialization."""
        assert isinstance(ContentStatus.PENDING, str)
        assert ContentStatus.PENDING == "pending"


class TestContentModel:
    """Tests for Content SQLAlchemy model."""

    def test_content_creation_minimal(self):
        """Test creating Content with only required fields."""
        content = Content(
            source_type=ContentSource.GMAIL,
            source_id="msg-12345",
            title="Test Newsletter",
            markdown_content="# Test\n\nContent here.",
            content_hash="abc123def456",
        )

        assert content.source_type == ContentSource.GMAIL
        assert content.source_id == "msg-12345"
        assert content.title == "Test Newsletter"
        assert content.markdown_content == "# Test\n\nContent here."
        assert content.content_hash == "abc123def456"
        # Note: SQLAlchemy default values only apply after database insertion
        # In-memory objects have None for columns with defaults until flushed
        assert content.status is None

    def test_content_creation_full(self):
        """Test creating Content with all fields."""
        published_date = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        ingested_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)

        content = Content(
            source_type=ContentSource.YOUTUBE,
            source_id="video-abc123",
            source_url="https://youtube.com/watch?v=abc123",
            title="AI Tutorial Video",
            author="Tech Channel",
            publication="Tech Tutorials",
            published_date=published_date,
            markdown_content="# Video Transcript\n\nContent...",
            tables_json=[{"headers": ["A", "B"], "rows": [["1", "2"]]}],
            links_json=["https://example.com/link1"],
            metadata_json={"duration_seconds": 600, "word_count": 1500},
            raw_content='{"segments": []}',
            raw_format="transcript_json",
            parser_used="YouTubeParser",
            parser_version="1.0.0",
            content_hash="xyz789",
            status=ContentStatus.COMPLETED,
            ingested_at=ingested_at,
        )

        assert content.source_type == ContentSource.YOUTUBE
        assert content.source_url == "https://youtube.com/watch?v=abc123"
        assert content.author == "Tech Channel"
        assert content.publication == "Tech Tutorials"
        assert content.published_date == published_date
        assert content.tables_json == [{"headers": ["A", "B"], "rows": [["1", "2"]]}]
        assert content.links_json == ["https://example.com/link1"]
        assert content.metadata_json == {"duration_seconds": 600, "word_count": 1500}
        assert content.raw_content == '{"segments": []}'
        assert content.raw_format == "transcript_json"
        assert content.parser_used == "YouTubeParser"
        assert content.parser_version == "1.0.0"
        assert content.status == ContentStatus.COMPLETED
        assert content.ingested_at == ingested_at

    def test_content_repr(self):
        """Test Content string representation."""
        content = Content(
            source_type=ContentSource.RSS,
            source_id="rss-article-123",
            title="A Very Long Newsletter Title That Exceeds Fifty Characters Definitely",
            markdown_content="Content",
            content_hash="hash123",
        )
        content.id = 42

        repr_str = repr(content)

        assert "Content" in repr_str
        assert "id=42" in repr_str
        assert "source=rss" in repr_str
        # Title should be truncated to 50 chars
        assert "A Very Long Newsletter Title That Exceeds Fifty Ch" in repr_str

    def test_content_tablename(self):
        """Test that Content uses correct table name."""
        assert Content.__tablename__ == "contents"


class TestContentCreateSchema:
    """Tests for ContentCreate Pydantic schema."""

    def test_create_minimal(self):
        """Test creating ContentCreate with required fields."""
        schema = ContentCreate(
            source_type=ContentSource.MANUAL,
            source_id="manual-001",
            title="Manual Entry",
            markdown_content="# Manual Content",
            content_hash="hash123",
        )

        assert schema.source_type == ContentSource.MANUAL
        assert schema.source_id == "manual-001"
        assert schema.title == "Manual Entry"
        assert schema.markdown_content == "# Manual Content"
        assert schema.content_hash == "hash123"
        # Optional fields should be None
        assert schema.source_url is None
        assert schema.author is None
        assert schema.publication is None
        assert schema.published_date is None
        assert schema.tables_json is None
        assert schema.links_json is None
        assert schema.metadata_json is None
        assert schema.raw_content is None
        assert schema.raw_format is None
        assert schema.parser_used is None
        assert schema.parser_version is None

    def test_create_full(self):
        """Test creating ContentCreate with all fields."""
        published = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)

        schema = ContentCreate(
            source_type=ContentSource.FILE_UPLOAD,
            source_id="file-hash-abc",
            source_url="https://example.com/doc.pdf",
            title="Uploaded Document",
            author="John Doe",
            publication="Research Papers",
            published_date=published,
            markdown_content="# Document\n\nParsed content...",
            tables_json=[{"caption": "Table 1", "headers": ["Col1"], "rows": [["val"]]}],
            links_json=["https://ref1.com", "https://ref2.com"],
            metadata_json={"page_count": 10, "file_size_bytes": 50000},
            raw_content="<pdf binary data>",
            raw_format="pdf",
            parser_used="DoclingParser",
            parser_version="2.60.0",
            content_hash="full-hash-xyz",
        )

        assert schema.source_type == ContentSource.FILE_UPLOAD
        assert schema.author == "John Doe"
        assert schema.published_date == published
        assert len(schema.tables_json) == 1
        assert len(schema.links_json) == 2
        assert schema.metadata_json["page_count"] == 10
        assert schema.parser_used == "DoclingParser"

    def test_create_validation_missing_required(self):
        """Test that missing required fields raise validation error."""
        with pytest.raises(ValueError):
            ContentCreate(
                source_type=ContentSource.GMAIL,
                # Missing source_id, title, markdown_content, content_hash
            )


class TestContentUpdateSchema:
    """Tests for ContentUpdate Pydantic schema."""

    def test_update_single_field(self):
        """Test updating a single field."""
        schema = ContentUpdate(title="Updated Title")

        assert schema.title == "Updated Title"
        assert schema.author is None
        assert schema.markdown_content is None
        assert schema.status is None

    def test_update_multiple_fields(self):
        """Test updating multiple fields."""
        schema = ContentUpdate(
            title="New Title",
            author="New Author",
            status=ContentStatus.COMPLETED,
            error_message=None,
        )

        assert schema.title == "New Title"
        assert schema.author == "New Author"
        assert schema.status == ContentStatus.COMPLETED
        assert schema.error_message is None

    def test_update_status_to_failed(self):
        """Test updating status to failed with error message."""
        schema = ContentUpdate(
            status=ContentStatus.FAILED,
            error_message="Parser timeout after 300 seconds",
        )

        assert schema.status == ContentStatus.FAILED
        assert "timeout" in schema.error_message


class TestContentResponseSchema:
    """Tests for ContentResponse Pydantic schema."""

    def test_response_from_model_data(self):
        """Test creating response from model-like data."""
        ingested = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)

        response = ContentResponse(
            id=42,
            source_type=ContentSource.RSS,
            source_id="rss-feed-001",
            source_url="https://blog.example.com/article",
            title="Blog Article",
            author="Jane Smith",
            publication="Tech Blog",
            published_date=datetime(2025, 1, 14, 8, 0, 0, tzinfo=UTC),
            markdown_content="# Article\n\nContent...",
            tables_json=None,
            links_json=["https://example.com"],
            metadata_json={"word_count": 500},
            parser_used="MarkItDownParser",
            content_hash="response-hash",
            canonical_id=None,
            status=ContentStatus.COMPLETED,
            error_message=None,
            ingested_at=ingested,
            parsed_at=ingested,
            processed_at=ingested,
        )

        assert response.id == 42
        assert response.source_type == ContentSource.RSS
        assert response.title == "Blog Article"
        assert response.status == ContentStatus.COMPLETED
        assert response.ingested_at == ingested

    def test_response_with_canonical_id(self):
        """Test response for a duplicate content with canonical reference."""
        response = ContentResponse(
            id=100,
            source_type=ContentSource.GMAIL,
            source_id="duplicate-msg",
            title="Duplicate Newsletter",
            markdown_content="Same content as original",
            content_hash="same-hash",
            canonical_id=50,  # References the original
            status=ContentStatus.COMPLETED,
            ingested_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
        )

        assert response.canonical_id == 50
        assert response.id == 100


class TestContentListItemSchema:
    """Tests for ContentListItem Pydantic schema."""

    def test_list_item_minimal(self):
        """Test lightweight list item schema."""
        item = ContentListItem(
            id=1,
            source_type=ContentSource.YOUTUBE,
            title="Video Transcript",
            publication=None,
            published_date=None,
            status=ContentStatus.PENDING,
            ingested_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
        )

        assert item.id == 1
        assert item.source_type == ContentSource.YOUTUBE
        assert item.title == "Video Transcript"
        assert item.publication is None
        assert item.status == ContentStatus.PENDING

    def test_list_item_full(self):
        """Test list item with all optional fields."""
        item = ContentListItem(
            id=5,
            source_type=ContentSource.GMAIL,
            title="Newsletter Issue #42",
            publication="AI Weekly",
            published_date=datetime(2025, 1, 15, 8, 0, 0, tzinfo=UTC),
            status=ContentStatus.COMPLETED,
            ingested_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        )

        assert item.publication == "AI Weekly"
        assert item.published_date is not None


class TestContentListResponseSchema:
    """Tests for ContentListResponse Pydantic schema."""

    def test_paginated_response(self):
        """Test paginated list response."""
        items = [
            ContentListItem(
                id=i,
                source_type=ContentSource.RSS,
                title=f"Article {i}",
                publication="Blog",
                published_date=None,
                status=ContentStatus.COMPLETED,
                ingested_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
            )
            for i in range(1, 4)
        ]

        response = ContentListResponse(
            items=items,
            total=25,
            page=1,
            page_size=3,
            has_next=True,
            has_prev=False,
        )

        assert len(response.items) == 3
        assert response.total == 25
        assert response.page == 1
        assert response.page_size == 3
        assert response.has_next is True
        assert response.has_prev is False

    def test_empty_response(self):
        """Test empty list response."""
        response = ContentListResponse(
            items=[],
            total=0,
            page=1,
            page_size=10,
            has_next=False,
            has_prev=False,
        )

        assert len(response.items) == 0
        assert response.total == 0

    def test_last_page_response(self):
        """Test last page of results."""
        items = [
            ContentListItem(
                id=98,
                source_type=ContentSource.FILE_UPLOAD,
                title="Final Document",
                publication=None,
                published_date=None,
                status=ContentStatus.PARSED,
                ingested_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
            )
        ]

        response = ContentListResponse(
            items=items,
            total=98,
            page=10,
            page_size=10,
            has_next=False,
            has_prev=True,
        )

        assert response.has_next is False
        assert response.has_prev is True
        assert response.page == 10


class TestContentRelationships:
    """Tests for Content model relationships."""

    def test_content_has_summaries_relationship(self):
        """Test Content model has summaries relationship attribute."""
        # Verify the relationship is defined on the Content class
        assert hasattr(Content, "summaries")

        # Create a content instance and verify it has an empty list
        content = Content(
            source_type=ContentSource.GMAIL,
            source_id="relationship-test",
            title="Test Content",
            markdown_content="# Test",
            content_hash="hash123",
        )
        # In-memory object won't have relationship loaded, but attribute should exist

    def test_content_has_images_relationship(self):
        """Test Content model has images relationship attribute."""
        # Verify the relationship is defined on the Content class
        assert hasattr(Content, "images")

    def test_summary_has_content_relationship(self):
        """Test Summary model has content relationship attribute."""
        assert hasattr(Summary, "content")

    def test_image_has_source_content_relationship(self):
        """Test Image model has source_content relationship attribute."""
        assert hasattr(Image, "source_content")

    def test_content_summaries_back_populates(self):
        """Test Content.summaries and Summary.content are linked."""
        # Create content
        content = Content(
            source_type=ContentSource.GMAIL,
            source_id="backpopulate-test",
            title="Test Content",
            markdown_content="# Test",
            content_hash="hash456",
        )
        content.id = 1  # Simulate database assignment

        # Create summary linked to content
        summary = Summary(
            content_id=1,
            executive_summary="Test summary",
            key_themes=["test"],
            strategic_insights=["insight"],
            technical_details=["detail"],
            actionable_items=["action"],
            notable_quotes=["quote"],
            relevance_scores={"cto_leadership": 0.8},
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )

        # Verify relationship attribute names match back_populates
        # This confirms the relationship configuration is correct
        # (actual ORM linking requires a database session)
        assert Summary.content.property.back_populates == "summaries"

    def test_content_images_back_populates(self):
        """Test Content.images and Image.source_content are linked."""
        # Verify relationship configuration
        assert Image.source_content.property.back_populates == "images"
