"""Tests for the Image model and schemas.

Tests cover:
- ImageSource enum values and behavior
- Image SQLAlchemy model creation and relationships
- Pydantic schemas for API operations
"""

import uuid
from datetime import UTC, datetime

from src.models.image import (
    Image,
    ImageCreate,
    ImageListItem,
    ImageListResponse,
    ImageMetadata,
    ImageResponse,
    ImageSource,
    ImageUpdate,
)


class TestImageSourceEnum:
    """Tests for ImageSource enum."""

    def test_all_source_types_defined(self):
        """Verify all expected source types exist."""
        expected_sources = {
            "extracted",
            "keyframe",
            "ai_generated",
        }
        actual_sources = {source.value for source in ImageSource}
        assert actual_sources == expected_sources

    def test_source_string_representation(self):
        """Test that source values are lowercase strings."""
        assert ImageSource.EXTRACTED.value == "extracted"
        assert ImageSource.KEYFRAME.value == "keyframe"
        assert ImageSource.AI_GENERATED.value == "ai_generated"

    def test_source_is_string_enum(self):
        """Test that ImageSource is a string enum for JSON serialization."""
        assert isinstance(ImageSource.EXTRACTED, str)
        assert ImageSource.EXTRACTED == "extracted"


class TestImageModel:
    """Tests for Image SQLAlchemy model."""

    def test_image_creation_minimal(self):
        """Test creating Image with only required fields."""
        image = Image(
            source_type=ImageSource.EXTRACTED,
            storage_path="images/2025/01/15/abc123_test.jpg",
            storage_provider="local",
            filename="test.jpg",
            mime_type="image/jpeg",
        )

        assert image.source_type == ImageSource.EXTRACTED
        assert image.storage_path == "images/2025/01/15/abc123_test.jpg"
        assert image.storage_provider == "local"
        assert image.filename == "test.jpg"
        assert image.mime_type == "image/jpeg"

    def test_image_creation_keyframe(self):
        """Test creating Image for YouTube keyframe."""
        image = Image(
            source_type=ImageSource.KEYFRAME,
            source_content_id=42,
            video_id="dQw4w9WgXcQ",
            timestamp_seconds=125.5,
            deep_link_url="https://youtu.be/dQw4w9WgXcQ?t=125",
            storage_path="images/2025/01/15/keyframe_125.jpg",
            storage_provider="local",
            filename="keyframe_125.jpg",
            mime_type="image/jpeg",
            width=1920,
            height=1080,
            phash="a0b1c2d3e4f5a6b7",
        )

        assert image.source_type == ImageSource.KEYFRAME
        assert image.video_id == "dQw4w9WgXcQ"
        assert image.timestamp_seconds == 125.5
        assert image.deep_link_url == "https://youtu.be/dQw4w9WgXcQ?t=125"
        assert image.width == 1920
        assert image.height == 1080
        assert image.phash == "a0b1c2d3e4f5a6b7"

    def test_image_creation_ai_generated(self):
        """Test creating Image for AI-generated image."""
        image = Image(
            source_type=ImageSource.AI_GENERATED,
            source_digest_id=10,
            storage_path="images/2025/01/15/generated_hero.png",
            storage_provider="s3",
            filename="generated_hero.png",
            mime_type="image/png",
            width=1024,
            height=1024,
            generation_prompt="A futuristic AI newsletter header",
            generation_model="dall-e-3",
            generation_params={"size": "1024x1024", "quality": "hd"},
        )

        assert image.source_type == ImageSource.AI_GENERATED
        assert image.source_digest_id == 10
        assert image.generation_prompt == "A futuristic AI newsletter header"
        assert image.generation_model == "dall-e-3"
        assert image.generation_params == {"size": "1024x1024", "quality": "hd"}

    def test_image_dimensions_property(self):
        """Test the dimensions computed property."""
        image = Image(
            source_type=ImageSource.EXTRACTED,
            storage_path="path/image.jpg",
            storage_provider="local",
            filename="image.jpg",
            mime_type="image/jpeg",
            width=800,
            height=600,
        )

        assert image.dimensions == "800x600"

    def test_image_dimensions_none_when_missing(self):
        """Test dimensions returns None when width/height not set."""
        image = Image(
            source_type=ImageSource.EXTRACTED,
            storage_path="path/image.jpg",
            storage_provider="local",
            filename="image.jpg",
            mime_type="image/jpeg",
        )

        assert image.dimensions is None

    def test_image_get_youtube_deep_link(self):
        """Test YouTube deep link generation."""
        image = Image(
            source_type=ImageSource.KEYFRAME,
            storage_path="path/keyframe.jpg",
            storage_provider="local",
            filename="keyframe.jpg",
            mime_type="image/jpeg",
            video_id="abc123xyz",
            timestamp_seconds=300.5,
        )

        link = image.get_youtube_deep_link()
        assert link == "https://youtu.be/abc123xyz?t=300"

    def test_image_get_youtube_deep_link_none(self):
        """Test deep link returns None when not a keyframe."""
        image = Image(
            source_type=ImageSource.EXTRACTED,
            storage_path="path/image.jpg",
            storage_provider="local",
            filename="image.jpg",
            mime_type="image/jpeg",
        )

        assert image.get_youtube_deep_link() is None

    def test_image_repr(self):
        """Test Image string representation."""
        image = Image(
            source_type=ImageSource.EXTRACTED,
            storage_path="path/photo.jpg",
            storage_provider="local",
            filename="photo.jpg",
            mime_type="image/jpeg",
        )
        image.id = uuid.uuid4()

        repr_str = repr(image)

        assert "Image" in repr_str
        assert "extracted" in repr_str
        assert "photo.jpg" in repr_str

    def test_image_tablename(self):
        """Test that Image uses correct table name."""
        assert Image.__tablename__ == "images"


class TestImageCreateSchema:
    """Tests for ImageCreate Pydantic schema."""

    def test_create_minimal(self):
        """Test creating ImageCreate with required fields."""
        schema = ImageCreate(
            source_type=ImageSource.EXTRACTED,
            storage_path="images/test.jpg",
            filename="test.jpg",
            mime_type="image/jpeg",
        )

        assert schema.source_type == ImageSource.EXTRACTED
        assert schema.storage_path == "images/test.jpg"
        assert schema.filename == "test.jpg"
        assert schema.mime_type == "image/jpeg"
        assert schema.storage_provider == "local"  # default
        # Optional fields should be None
        assert schema.source_content_id is None
        assert schema.source_summary_id is None
        assert schema.source_digest_id is None
        assert schema.source_url is None
        assert schema.video_id is None
        assert schema.width is None
        assert schema.height is None
        assert schema.phash is None

    def test_create_keyframe(self):
        """Test creating ImageCreate for keyframe."""
        schema = ImageCreate(
            source_type=ImageSource.KEYFRAME,
            source_content_id=42,
            video_id="xyz789",
            timestamp_seconds=60.0,
            deep_link_url="https://youtu.be/xyz789?t=60",
            storage_path="images/keyframe.jpg",
            storage_provider="local",
            filename="keyframe.jpg",
            mime_type="image/jpeg",
            width=1280,
            height=720,
            phash="abc123def456",
        )

        assert schema.source_type == ImageSource.KEYFRAME
        assert schema.source_content_id == 42
        assert schema.video_id == "xyz789"
        assert schema.timestamp_seconds == 60.0
        assert schema.deep_link_url == "https://youtu.be/xyz789?t=60"
        assert schema.width == 1280
        assert schema.height == 720
        assert schema.phash == "abc123def456"

    def test_create_with_descriptive_metadata(self):
        """Test creating ImageCreate with alt text and caption."""
        schema = ImageCreate(
            source_type=ImageSource.EXTRACTED,
            storage_path="images/diagram.png",
            filename="diagram.png",
            mime_type="image/png",
            alt_text="Architecture diagram showing data flow",
            caption="Figure 1: System Architecture Overview",
        )

        assert schema.alt_text == "Architecture diagram showing data flow"
        assert schema.caption == "Figure 1: System Architecture Overview"

    def test_create_ai_generated(self):
        """Test creating ImageCreate for AI-generated image."""
        schema = ImageCreate(
            source_type=ImageSource.AI_GENERATED,
            source_digest_id=5,
            storage_path="images/header.png",
            storage_provider="s3",
            filename="header.png",
            mime_type="image/png",
            generation_prompt="Create a newsletter header",
            generation_model="dall-e-3",
            generation_params={"quality": "hd"},
        )

        assert schema.source_type == ImageSource.AI_GENERATED
        assert schema.generation_prompt == "Create a newsletter header"
        assert schema.generation_model == "dall-e-3"
        assert schema.generation_params == {"quality": "hd"}


class TestImageUpdateSchema:
    """Tests for ImageUpdate Pydantic schema."""

    def test_update_single_field(self):
        """Test updating a single field."""
        schema = ImageUpdate(alt_text="New alt text")

        assert schema.alt_text == "New alt text"
        assert schema.caption is None
        assert schema.ai_description is None

    def test_update_multiple_fields(self):
        """Test updating multiple fields."""
        schema = ImageUpdate(
            alt_text="Updated alt",
            caption="Updated caption",
            ai_description="AI describes this as...",
        )

        assert schema.alt_text == "Updated alt"
        assert schema.caption == "Updated caption"
        assert schema.ai_description == "AI describes this as..."

    def test_update_storage_fields(self):
        """Test updating storage-related fields."""
        schema = ImageUpdate(
            storage_path="new/path/image.jpg",
            storage_provider="s3",
        )

        assert schema.storage_path == "new/path/image.jpg"
        assert schema.storage_provider == "s3"


class TestImageResponseSchema:
    """Tests for ImageResponse Pydantic schema."""

    def test_response_from_model_data(self):
        """Test creating response from model-like data."""
        image_id = uuid.uuid4()
        created = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)

        response = ImageResponse(
            id=image_id,
            source_type=ImageSource.EXTRACTED,
            source_content_id=42,
            source_url="https://example.com/image.jpg",
            storage_path="images/2025/01/15/abc_image.jpg",
            storage_provider="local",
            filename="image.jpg",
            mime_type="image/jpeg",
            width=800,
            height=600,
            dimensions="800x600",
            alt_text="Example image",
            phash="hash123",
            created_at=created,
        )

        assert response.id == image_id
        assert response.source_type == ImageSource.EXTRACTED
        assert response.source_content_id == 42
        assert response.dimensions == "800x600"
        assert response.created_at == created

    def test_response_keyframe(self):
        """Test response for YouTube keyframe."""
        image_id = uuid.uuid4()

        response = ImageResponse(
            id=image_id,
            source_type=ImageSource.KEYFRAME,
            source_content_id=10,
            video_id="dQw4w9WgXcQ",
            timestamp_seconds=125.0,
            deep_link_url="https://youtu.be/dQw4w9WgXcQ?t=125",
            storage_path="images/keyframe.jpg",
            storage_provider="local",
            filename="keyframe_125.jpg",
            mime_type="image/jpeg",
            width=1920,
            height=1080,
            dimensions="1920x1080",
            created_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
        )

        assert response.video_id == "dQw4w9WgXcQ"
        assert response.timestamp_seconds == 125.0
        assert response.deep_link_url == "https://youtu.be/dQw4w9WgXcQ?t=125"


class TestImageListItemSchema:
    """Tests for ImageListItem Pydantic schema."""

    def test_list_item(self):
        """Test lightweight list item schema."""
        image_id = uuid.uuid4()

        item = ImageListItem(
            id=image_id,
            source_type=ImageSource.EXTRACTED,
            filename="photo.jpg",
            mime_type="image/jpeg",
            dimensions="640x480",
            created_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
        )

        assert item.id == image_id
        assert item.source_type == ImageSource.EXTRACTED
        assert item.filename == "photo.jpg"
        assert item.dimensions == "640x480"

    def test_list_item_without_dimensions(self):
        """Test list item without dimensions."""
        item = ImageListItem(
            id=uuid.uuid4(),
            source_type=ImageSource.AI_GENERATED,
            filename="generated.png",
            mime_type="image/png",
            dimensions=None,
            created_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
        )

        assert item.dimensions is None


class TestImageListResponseSchema:
    """Tests for ImageListResponse Pydantic schema."""

    def test_paginated_response(self):
        """Test paginated list response."""
        items = [
            ImageListItem(
                id=uuid.uuid4(),
                source_type=ImageSource.EXTRACTED,
                filename=f"image_{i}.jpg",
                mime_type="image/jpeg",
                dimensions="800x600",
                created_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
            )
            for i in range(3)
        ]

        response = ImageListResponse(
            items=items,
            total=25,
            page=1,
            page_size=3,
            has_next=True,
            has_prev=False,
        )

        assert len(response.items) == 3
        assert response.total == 25
        assert response.has_next is True
        assert response.has_prev is False

    def test_empty_response(self):
        """Test empty list response."""
        response = ImageListResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
        )

        assert len(response.items) == 0
        assert response.total == 0
        assert response.has_next is False
        assert response.has_prev is False


class TestImageMetadataSchema:
    """Tests for ImageMetadata Pydantic schema."""

    def test_metadata_creation(self):
        """Test creating image metadata."""
        metadata = ImageMetadata(
            width=1920,
            height=1080,
            mime_type="image/jpeg",
            file_size_bytes=250000,
            phash="a1b2c3d4e5f6",
        )

        assert metadata.width == 1920
        assert metadata.height == 1080
        assert metadata.mime_type == "image/jpeg"
        assert metadata.file_size_bytes == 250000
        assert metadata.phash == "a1b2c3d4e5f6"

    def test_metadata_minimal(self):
        """Test creating metadata with only required fields."""
        metadata = ImageMetadata(
            mime_type="image/png",
            file_size_bytes=50000,
        )

        assert metadata.mime_type == "image/png"
        assert metadata.file_size_bytes == 50000
        assert metadata.width is None
        assert metadata.height is None
        assert metadata.phash is None
