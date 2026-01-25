"""Factory for Content model."""

import hashlib
from datetime import UTC, datetime, timedelta

import factory

from src.models.content import Content, ContentSource, ContentStatus


class ContentFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for creating Content instances.

    Traits:
        pending: Creates content in PENDING status
        parsed: Creates content in PARSED status (ready for summarization)
        completed: Creates content in COMPLETED status (default)
        failed: Creates content in FAILED status with error message
        with_audio: Adds audio URL to metadata
        youtube: Creates YouTube content with video metadata
        gmail: Creates Gmail content with email metadata
        rss: Creates RSS content (default)
        file_upload: Creates file upload content

    Examples:
        # Default content (RSS, COMPLETED)
        content = ContentFactory()

        # Pending Gmail content
        content = ContentFactory(gmail=True, pending=True)

        # YouTube with audio
        content = ContentFactory(youtube=True, with_audio=True)
    """

    class Meta:
        model = Content
        sqlalchemy_session = None  # Set by fixture
        sqlalchemy_session_persistence = "commit"

    # Source identification
    source_type = ContentSource.RSS
    source_id = factory.Sequence(lambda n: f"source_{n}")
    source_url = factory.LazyAttribute(lambda o: f"https://example.com/article/{o.source_id}")

    # Identity / Metadata
    title = factory.Sequence(lambda n: f"Test Article {n}: AI in Production")
    author = factory.Faker("name")
    publication = factory.Sequence(lambda n: f"Tech Newsletter {n % 5}")
    published_date = factory.LazyFunction(lambda: datetime.now(UTC) - timedelta(days=1))

    # Canonical content
    markdown_content = factory.LazyAttribute(
        lambda o: f"# {o.title}\n\nThis is the markdown content for testing.\n\n"
        f"## Key Points\n\n- Point 1\n- Point 2\n- Point 3\n"
    )

    # Structured extractions
    tables_json = None
    links_json = factory.LazyFunction(
        lambda: ["https://example.com/link1", "https://example.com/link2"]
    )
    metadata_json = factory.LazyFunction(lambda: {"word_count": 500, "read_time_minutes": 3})

    # Raw preservation
    raw_content = factory.LazyAttribute(
        lambda o: f"<html><body><h1>{o.title}</h1><p>Raw HTML content</p></body></html>"
    )
    raw_format = "html"

    # Parsing metadata
    parser_used = "TrafilaturaParser"
    parser_version = "1.0.0"

    # Deduplication
    content_hash = factory.LazyAttribute(
        lambda o: hashlib.sha256(o.markdown_content.encode()).hexdigest()
    )
    canonical_id = None

    # Processing status
    status = ContentStatus.COMPLETED
    error_message = None

    # Timestamps
    ingested_at = factory.LazyFunction(lambda: datetime.now(UTC) - timedelta(hours=2))
    parsed_at = factory.LazyFunction(lambda: datetime.now(UTC) - timedelta(hours=1))
    processed_at = factory.LazyFunction(lambda: datetime.now(UTC))

    # --- Traits ---

    class Params:
        pending = factory.Trait(
            status=ContentStatus.PENDING,
            parsed_at=None,
            processed_at=None,
        )
        parsed = factory.Trait(
            status=ContentStatus.PARSED,
            processed_at=None,
        )
        completed = factory.Trait(
            status=ContentStatus.COMPLETED,
        )
        failed = factory.Trait(
            status=ContentStatus.FAILED,
            error_message="Processing failed: API rate limit exceeded",
            processed_at=None,
        )
        with_audio = factory.Trait(
            metadata_json=factory.LazyFunction(
                lambda: {
                    "word_count": 500,
                    "read_time_minutes": 3,
                    "audio_url": "https://storage.example.com/audio/content_123.mp3",
                    "audio_duration_seconds": 180,
                }
            )
        )
        youtube = factory.Trait(
            source_type=ContentSource.YOUTUBE,
            source_id=factory.Sequence(lambda n: f"video_id_{n}"),
            source_url=factory.LazyAttribute(
                lambda o: f"https://youtube.com/watch?v={o.source_id}"
            ),
            author=factory.Sequence(lambda n: f"TechChannel{n}"),
            publication=factory.Sequence(lambda n: f"TechChannel{n}"),
            parser_used="YouTubeParser",
            raw_format="transcript_json",
            metadata_json=factory.LazyFunction(
                lambda: {
                    "video_duration_seconds": 1200,
                    "view_count": 50000,
                    "keyframe_count": 15,
                }
            ),
        )
        gmail = factory.Trait(
            source_type=ContentSource.GMAIL,
            source_id=factory.Sequence(lambda n: f"gmail_msg_{n}"),
            source_url=None,
            author=factory.Faker("email"),
            parser_used="GmailParser",
            raw_format="html",
        )
        rss = factory.Trait(
            source_type=ContentSource.RSS,
            parser_used="TrafilaturaParser",
        )
        file_upload = factory.Trait(
            source_type=ContentSource.FILE_UPLOAD,
            source_id=factory.Sequence(lambda n: f"upload_{n}.pdf"),
            source_url=None,
            parser_used="DoclingParser",
            raw_format="pdf",
            metadata_json=factory.LazyFunction(
                lambda: {
                    "page_count": 12,
                    "file_size_bytes": 1024000,
                    "has_tables": True,
                }
            ),
        )
