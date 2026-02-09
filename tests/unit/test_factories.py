"""Unit tests for Factory Boy factories.

Tests factory creation without database (build mode) to verify
factory configuration is correct.
"""

import pytest

from src.models.content import ContentSource, ContentStatus
from src.models.digest import DigestStatus, DigestType
from src.models.podcast import PodcastStatus
from tests.factories import (
    ContentFactory,
    DigestFactory,
    PodcastFactory,
    PodcastScriptRecordFactory,
    SummaryFactory,
)


class TestContentFactory:
    """Tests for ContentFactory."""

    def test_build_creates_content_dict(self):
        """Factory build() creates Content without database."""
        content = ContentFactory.build()

        assert content.title is not None
        assert content.source_type == ContentSource.RSS
        assert content.status == ContentStatus.COMPLETED
        assert content.markdown_content is not None
        assert content.content_hash is not None

    def test_build_with_pending_trait(self):
        """Pending trait sets correct status and clears timestamps."""
        content = ContentFactory.build(pending=True)

        assert content.status == ContentStatus.PENDING
        assert content.parsed_at is None
        assert content.processed_at is None

    def test_build_with_youtube_trait(self):
        """YouTube trait sets correct source type and metadata."""
        content = ContentFactory.build(youtube=True)

        assert content.source_type == ContentSource.YOUTUBE
        assert content.parser_used == "YouTubeParser"
        assert "youtube.com" in content.source_url
        assert content.metadata_json is not None
        assert "video_duration_seconds" in content.metadata_json

    def test_build_with_gmail_trait(self):
        """Gmail trait sets correct source type."""
        content = ContentFactory.build(gmail=True)

        assert content.source_type == ContentSource.GMAIL
        assert content.parser_used == "GmailParser"
        assert content.source_url is None

    def test_build_with_file_upload_trait(self):
        """File upload trait sets correct source type and metadata."""
        content = ContentFactory.build(file_upload=True)

        assert content.source_type == ContentSource.FILE_UPLOAD
        assert content.parser_used == "DoclingParser"
        assert content.metadata_json is not None
        assert "page_count" in content.metadata_json

    def test_build_with_audio_trait(self):
        """With audio trait includes audio URL in metadata."""
        content = ContentFactory.build(with_audio=True)

        assert content.metadata_json is not None
        assert "audio_url" in content.metadata_json
        assert "audio_duration_seconds" in content.metadata_json

    def test_build_with_failed_trait(self):
        """Failed trait sets status and error message."""
        content = ContentFactory.build(failed=True)

        assert content.status == ContentStatus.FAILED
        assert content.error_message is not None
        assert "failed" in content.error_message.lower()

    def test_sequence_generates_unique_ids(self):
        """Factory sequence generates unique source_ids."""
        content1 = ContentFactory.build()
        content2 = ContentFactory.build()

        assert content1.source_id != content2.source_id
        assert content1.title != content2.title

    def test_content_hash_computed_from_markdown(self):
        """Content hash is SHA-256 of markdown content."""
        import hashlib

        content = ContentFactory.build()
        expected_hash = hashlib.sha256(content.markdown_content.encode()).hexdigest()

        assert content.content_hash == expected_hash


class TestSummaryFactory:
    """Tests for SummaryFactory."""

    def test_build_creates_summary(self):
        """Factory build() creates Summary without database."""
        summary = SummaryFactory.build()

        assert summary.executive_summary is not None
        assert isinstance(summary.key_themes, list)
        assert isinstance(summary.strategic_insights, list)
        assert isinstance(summary.relevance_scores, dict)
        assert summary.agent_framework == "anthropic"
        assert summary.model_used == "claude-sonnet-4-5"

    def test_build_with_minimal_trait(self):
        """Minimal trait creates summary with minimal fields."""
        summary = SummaryFactory.build(minimal=True)

        assert summary.key_themes == ["AI"]
        assert summary.strategic_insights == ["Key insight"]
        assert summary.technical_details == []
        assert summary.notable_quotes == []

    def test_build_with_openai_trait(self):
        """OpenAI trait sets correct agent framework."""
        summary = SummaryFactory.build(openai=True)

        assert summary.agent_framework == "openai"
        assert summary.model_used == "gpt-4o"

    def test_build_with_high_relevance_trait(self):
        """High relevance trait sets high scores."""
        summary = SummaryFactory.build(high_relevance=True)

        assert summary.relevance_scores["overall"] >= 0.9

    def test_build_with_low_relevance_trait(self):
        """Low relevance trait sets low scores."""
        summary = SummaryFactory.build(low_relevance=True)

        assert summary.relevance_scores["overall"] <= 0.3


class TestDigestFactory:
    """Tests for DigestFactory."""

    def test_build_creates_digest(self):
        """Factory build() creates Digest without database."""
        digest = DigestFactory.build()

        assert digest.title is not None
        assert digest.digest_type == DigestType.DAILY
        assert digest.status == DigestStatus.COMPLETED
        assert digest.period_start is not None
        assert digest.period_end is not None
        assert isinstance(digest.strategic_insights, list)

    def test_build_with_weekly_trait(self):
        """Weekly trait creates weekly digest with longer period."""
        digest = DigestFactory.build(weekly=True)

        assert digest.digest_type == DigestType.WEEKLY
        assert "Weekly" in digest.title
        # Weekly has more newsletters
        assert digest.newsletter_count >= 15

    def test_build_with_pending_trait(self):
        """Pending trait sets status and clears completed_at."""
        digest = DigestFactory.build(pending=True)

        assert digest.status == DigestStatus.PENDING
        assert digest.completed_at is None

    def test_build_with_pending_review_trait(self):
        """Pending review trait sets correct status."""
        digest = DigestFactory.build(pending_review=True)

        assert digest.status == DigestStatus.PENDING_REVIEW

    def test_build_with_approved_trait(self):
        """Approved trait sets reviewer info."""
        digest = DigestFactory.build(approved=True)

        assert digest.status == DigestStatus.APPROVED
        assert digest.reviewed_by is not None
        assert digest.review_notes is not None
        assert digest.reviewed_at is not None

    def test_build_with_delivered_trait(self):
        """Delivered trait sets delivery timestamp."""
        digest = DigestFactory.build(delivered=True)

        assert digest.status == DigestStatus.DELIVERED
        assert digest.delivered_at is not None

    def test_build_with_sources_trait(self):
        """With sources trait includes content IDs."""
        digest = DigestFactory.build(with_sources=True)

        assert digest.source_content_ids is not None
        assert len(digest.source_content_ids) == 5
        assert digest.newsletter_count == 5

    def test_build_with_combined_trait(self):
        """Combined trait marks as combined digest."""
        digest = DigestFactory.build(combined=True)

        assert digest.is_combined is True
        assert digest.child_digest_ids is not None
        assert digest.source_digest_count == 3


class TestPodcastScriptRecordFactory:
    """Tests for PodcastScriptRecordFactory."""

    def test_build_creates_script(self):
        """Factory build() creates PodcastScriptRecord without database."""
        script = PodcastScriptRecordFactory.build()

        assert script.title is not None
        assert script.length == "standard"
        assert script.word_count == 2500
        assert script.estimated_duration_seconds == 900
        assert script.status == PodcastStatus.SCRIPT_PENDING_REVIEW.value
        assert script.model_used == "claude-sonnet-4-5"
        assert script.script_json is not None

    def test_build_with_approved_trait(self):
        """Approved trait sets reviewer info and timestamps."""
        script = PodcastScriptRecordFactory.build(approved=True)

        assert script.status == PodcastStatus.SCRIPT_APPROVED.value
        assert script.reviewed_by is not None
        assert script.reviewed_at is not None
        assert script.approved_at is not None

    def test_build_with_failed_trait(self):
        """Failed trait sets error message."""
        script = PodcastScriptRecordFactory.build(failed=True)

        assert script.status == PodcastStatus.FAILED.value
        assert script.error_message is not None
        assert "failed" in script.error_message.lower()

    def test_build_with_extended_trait(self):
        """Extended trait sets longer duration and word count."""
        script = PodcastScriptRecordFactory.build(extended=True)

        assert script.length == "extended"
        assert script.word_count == 5000
        assert script.estimated_duration_seconds == 1800

    def test_build_with_pending_trait(self):
        """Pending trait sets correct status."""
        script = PodcastScriptRecordFactory.build(pending=True)

        assert script.status == PodcastStatus.PENDING.value


class TestPodcastFactory:
    """Tests for PodcastFactory."""

    def test_build_creates_podcast(self):
        """Factory build() creates Podcast without database."""
        podcast = PodcastFactory.build()

        assert podcast.audio_format == "mp3"
        assert podcast.voice_provider == "openai_tts"
        assert podcast.status == "completed"
        assert podcast.audio_url is not None

    def test_build_with_generating_trait(self):
        """Generating trait clears audio fields."""
        podcast = PodcastFactory.build(generating=True)

        assert podcast.status == "generating"
        assert podcast.audio_url is None
        assert podcast.duration_seconds is None
        assert podcast.completed_at is None

    def test_build_with_failed_trait(self):
        """Failed trait sets error message and clears audio fields."""
        podcast = PodcastFactory.build(failed=True)

        assert podcast.status == "failed"
        assert podcast.error_message is not None
        assert podcast.audio_url is None
        assert podcast.completed_at is None


class TestFactoryIntegration:
    """Tests for factory combinations and edge cases."""

    def test_multiple_traits_can_combine(self):
        """Multiple traits can be combined."""
        content = ContentFactory.build(youtube=True, pending=True)

        assert content.source_type == ContentSource.YOUTUBE
        assert content.status == ContentStatus.PENDING

    def test_digest_weekly_approved(self):
        """Weekly and approved traits combine correctly."""
        digest = DigestFactory.build(weekly=True, approved=True)

        assert digest.digest_type == DigestType.WEEKLY
        assert digest.status == DigestStatus.APPROVED
        assert digest.reviewed_by is not None


@pytest.mark.integration
class TestFactoryWithDatabase:
    """Integration tests for factories with database.

    These tests require the test database to be running.
    Run with: pytest -m integration
    """

    def test_content_factory_create(self, db_session, content_factory):
        """Factory create() persists to database."""
        content = content_factory.create()

        assert content.id is not None
        # Verify in database
        from src.models.content import Content

        db_content = db_session.query(Content).get(content.id)
        assert db_content is not None
        assert db_content.title == content.title

    def test_summary_factory_creates_content(self, db_session, summary_factory):
        """SummaryFactory auto-creates Content via SubFactory."""
        summary = summary_factory.create()

        assert summary.id is not None
        assert summary.content_id is not None
        assert summary.content is not None
        assert summary.content.id == summary.content_id

    def test_batch_create(self, db_session, content_factory):
        """create_batch creates multiple instances."""
        contents = content_factory.create_batch(5)

        assert len(contents) == 5
        for content in contents:
            assert content.id is not None

    def test_factory_with_trait_in_database(self, db_session, digest_factory):
        """Traits work correctly with database creation."""
        digest = digest_factory.create(weekly=True, pending_review=True)

        assert digest.id is not None
        assert digest.digest_type == DigestType.WEEKLY
        assert digest.status == DigestStatus.PENDING_REVIEW
