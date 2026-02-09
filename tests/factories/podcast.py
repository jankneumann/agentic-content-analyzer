"""Factories for Podcast models."""

from datetime import UTC, datetime

import factory

from src.models.podcast import Podcast, PodcastScriptRecord, PodcastStatus
from tests.factories.digest import DigestFactory


class PodcastScriptRecordFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for creating PodcastScriptRecord instances.

    Traits:
        pending: Creates script in PENDING status
        pending_review: Creates script in SCRIPT_PENDING_REVIEW status
        approved: Creates script in SCRIPT_APPROVED status
        failed: Creates script in FAILED status with error message
        extended: Creates an extended-length script

    Examples:
        # Default script (standard length, pending review)
        script = PodcastScriptRecordFactory()

        # Approved script
        script = PodcastScriptRecordFactory(approved=True)

        # Extended script linked to specific digest
        script = PodcastScriptRecordFactory(extended=True, digest=my_digest)
    """

    class Meta:
        model = PodcastScriptRecord
        sqlalchemy_session = None  # Set by fixture
        sqlalchemy_session_persistence = "commit"

    # Digest relationship
    digest = factory.SubFactory(DigestFactory)
    digest_id = factory.LazyAttribute(lambda o: o.digest.id if o.digest else None)

    # Script content
    title = factory.Sequence(lambda n: f"AI Digest Podcast Episode {n}")
    length = "standard"
    word_count = 2500
    estimated_duration_seconds = 900
    script_json = factory.LazyAttribute(
        lambda o: {"title": o.title, "sections": [], "length": o.length}
    )

    # Review workflow
    status = PodcastStatus.SCRIPT_PENDING_REVIEW.value
    reviewed_by = None
    reviewed_at = None
    review_notes = None
    revision_count = 0
    revision_history = None

    # Context tracking
    newsletter_ids_available = None
    newsletter_ids_fetched = None
    theme_ids = None
    web_search_queries = None
    tool_call_count = None

    # Generation metadata
    model_used = "claude-sonnet-4-5"
    model_version = "20250514"
    token_usage = factory.LazyFunction(lambda: {"input_tokens": 5000, "output_tokens": 3000})
    processing_time_seconds = 15
    error_message = None

    # Timestamps
    created_at = factory.LazyFunction(lambda: datetime.now(UTC))
    approved_at = None

    # --- Traits ---

    class Params:
        pending = factory.Trait(
            status=PodcastStatus.PENDING.value,
        )
        pending_review = factory.Trait(
            status=PodcastStatus.SCRIPT_PENDING_REVIEW.value,
        )
        approved = factory.Trait(
            status=PodcastStatus.SCRIPT_APPROVED.value,
            reviewed_by="reviewer@example.com",
            reviewed_at=factory.LazyFunction(lambda: datetime.now(UTC)),
            approved_at=factory.LazyFunction(lambda: datetime.now(UTC)),
        )
        failed = factory.Trait(
            status=PodcastStatus.FAILED.value,
            error_message="Script generation failed: API timeout",
        )
        extended = factory.Trait(
            length="extended",
            word_count=5000,
            estimated_duration_seconds=1800,
        )


class PodcastFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for creating Podcast instances.

    Traits:
        completed: Creates a completed podcast with audio
        generating: Creates a podcast in generating status
        failed: Creates a failed podcast with error message

    Examples:
        # Default podcast (completed)
        podcast = PodcastFactory()

        # Podcast linked to specific script
        podcast = PodcastFactory(script=my_script)

        # Failed podcast
        podcast = PodcastFactory(failed=True)
    """

    class Meta:
        model = Podcast
        sqlalchemy_session = None  # Set by fixture
        sqlalchemy_session_persistence = "commit"

    # Script relationship
    script = factory.SubFactory(PodcastScriptRecordFactory, approved=True)
    script_id = factory.LazyAttribute(lambda o: o.script.id if o.script else None)

    # Audio output
    audio_url = factory.Sequence(lambda n: f"/data/podcasts/episode_{n}.mp3")
    audio_format = "mp3"
    duration_seconds = factory.LazyAttribute(
        lambda o: o.script.estimated_duration_seconds if o.script else 900
    )
    file_size_bytes = factory.LazyAttribute(lambda o: (o.duration_seconds or 900) * 16000)

    # Voice configuration
    voice_provider = "openai_tts"
    alex_voice = "alex_male"
    sam_voice = "sam_female"
    voice_config = None

    # Status
    status = "completed"
    error_message = None

    # Timestamps
    created_at = factory.LazyFunction(lambda: datetime.now(UTC))
    completed_at = factory.LazyFunction(lambda: datetime.now(UTC))

    # --- Traits ---

    class Params:
        completed = factory.Trait(
            status="completed",
        )
        generating = factory.Trait(
            status="generating",
            audio_url=None,
            duration_seconds=None,
            file_size_bytes=None,
            completed_at=None,
        )
        failed = factory.Trait(
            status="failed",
            audio_url=None,
            duration_seconds=None,
            file_size_bytes=None,
            completed_at=None,
            error_message="Audio generation failed: TTS provider error",
        )
