"""Tests for table sorting functionality across all API endpoints.

Tests the sort_by and sort_order query parameters for:
- GET /api/v1/contents
- GET /api/v1/summaries
- GET /api/v1/digests/
- GET /api/v1/scripts/
- GET /api/v1/podcasts/
"""

from datetime import UTC, datetime

import pytest

from src.models.content import ContentStatus
from src.models.podcast import PodcastStatus
from tests.factories.content import ContentFactory
from tests.factories.digest import DigestFactory
from tests.factories.podcast import PodcastFactory, PodcastScriptRecordFactory
from tests.factories.summary import SummaryFactory

# ==============================================================================
# Content Sorting Tests
# ==============================================================================


class TestContentSorting:
    """Tests for GET /api/v1/contents sorting functionality."""

    @pytest.fixture
    def sortable_contents(self, db_session):
        """Create contents with different values for sorting tests."""
        return [
            ContentFactory(
                gmail=True,
                parsed=True,
                source_id="sort-test-001",
                title="Alpha Newsletter",
                publication="Alpha Pub",
                published_date=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
                content_hash="hash-alpha",
                ingested_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
            ),
            ContentFactory(
                rss=True,
                source_id="sort-test-002",
                title="Beta Newsletter",
                publication="Beta Pub",
                published_date=datetime(2025, 1, 14, 10, 0, 0, tzinfo=UTC),
                content_hash="hash-beta",
                status=ContentStatus.COMPLETED,
                ingested_at=datetime(2025, 1, 14, 12, 0, 0, tzinfo=UTC),
            ),
            ContentFactory(
                youtube=True,
                pending=True,
                source_id="sort-test-003",
                title="Charlie Newsletter",
                publication="Charlie Pub",
                published_date=datetime(2025, 1, 13, 10, 0, 0, tzinfo=UTC),
                content_hash="hash-charlie",
                ingested_at=datetime(2025, 1, 13, 12, 0, 0, tzinfo=UTC),
            ),
        ]

    def test_sort_by_title_ascending(self, client, sortable_contents):
        """Test sorting contents by title in ascending order."""
        response = client.get("/api/v1/contents?sort_by=title&sort_order=asc")

        assert response.status_code == 200
        data = response.json()
        titles = [item["title"] for item in data["items"]]
        assert titles == ["Alpha Newsletter", "Beta Newsletter", "Charlie Newsletter"]

    def test_sort_by_title_descending(self, client, sortable_contents):
        """Test sorting contents by title in descending order."""
        response = client.get("/api/v1/contents?sort_by=title&sort_order=desc")

        assert response.status_code == 200
        data = response.json()
        titles = [item["title"] for item in data["items"]]
        assert titles == ["Charlie Newsletter", "Beta Newsletter", "Alpha Newsletter"]

    def test_sort_by_ingested_at_ascending(self, client, sortable_contents):
        """Test sorting contents by ingested_at in ascending order."""
        response = client.get("/api/v1/contents?sort_by=ingested_at&sort_order=asc")

        assert response.status_code == 200
        data = response.json()
        # Oldest first (Charlie → Beta → Alpha)
        titles = [item["title"] for item in data["items"]]
        assert titles == ["Charlie Newsletter", "Beta Newsletter", "Alpha Newsletter"]

    def test_sort_by_ingested_at_descending(self, client, sortable_contents):
        """Test sorting contents by ingested_at in descending order (default)."""
        response = client.get("/api/v1/contents?sort_by=ingested_at&sort_order=desc")

        assert response.status_code == 200
        data = response.json()
        # Newest first (Alpha → Beta → Charlie)
        titles = [item["title"] for item in data["items"]]
        assert titles == ["Alpha Newsletter", "Beta Newsletter", "Charlie Newsletter"]

    def test_sort_by_source_type(self, client, sortable_contents):
        """Test sorting contents by source_type."""
        response = client.get("/api/v1/contents?sort_by=source_type&sort_order=asc")

        assert response.status_code == 200
        data = response.json()
        # Source types sorted alphabetically: gmail, rss, youtube
        source_types = [item["source_type"] for item in data["items"]]
        assert source_types == ["gmail", "rss", "youtube"]

    def test_invalid_sort_by_falls_back_to_default(self, client, sortable_contents):
        """Test that invalid sort_by field falls back to default field (ingested_at).

        Note: Only sort_by falls back to default; sort_order is still respected.
        """
        response = client.get("/api/v1/contents?sort_by=invalid_field&sort_order=asc")

        assert response.status_code == 200
        data = response.json()
        # Falls back to ingested_at, but respects sort_order=asc (oldest first)
        titles = [item["title"] for item in data["items"]]
        assert titles == ["Charlie Newsletter", "Beta Newsletter", "Alpha Newsletter"]

    def test_default_sort_without_parameters(self, client, sortable_contents):
        """Test that default sort is ingested_at descending when no params given."""
        response = client.get("/api/v1/contents")

        assert response.status_code == 200
        data = response.json()
        # Default: ingested_at desc (newest first)
        titles = [item["title"] for item in data["items"]]
        assert titles == ["Alpha Newsletter", "Beta Newsletter", "Charlie Newsletter"]

    def test_sort_with_pagination(self, client, sortable_contents):
        """Test that sorting works correctly with pagination."""
        # Get first page sorted by title ascending
        response = client.get("/api/v1/contents?sort_by=title&sort_order=asc&page=1&page_size=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        titles = [item["title"] for item in data["items"]]
        assert titles == ["Alpha Newsletter", "Beta Newsletter"]

        # Get second page
        response = client.get("/api/v1/contents?sort_by=title&sort_order=asc&page=2&page_size=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Charlie Newsletter"


# ==============================================================================
# Summary Sorting Tests
# ==============================================================================


class TestSummarySorting:
    """Tests for GET /api/v1/summaries sorting functionality."""

    @pytest.fixture
    def sortable_contents(self, db_session):
        """Create contents for summary sorting tests."""
        return [
            ContentFactory(
                gmail=True,
                source_id="summary-sort-001",
                title="Alpha for Summary",
                publication="Alpha Pub",
                content_hash="hash-s-alpha",
                status=ContentStatus.COMPLETED,
                ingested_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
            ),
            ContentFactory(
                rss=True,
                source_id="summary-sort-002",
                title="Beta for Summary",
                publication="Beta Pub",
                content_hash="hash-s-beta",
                status=ContentStatus.COMPLETED,
                ingested_at=datetime(2025, 1, 14, 12, 0, 0, tzinfo=UTC),
            ),
        ]

    @pytest.fixture
    def sortable_summaries(self, db_session, sortable_contents):
        """Create summaries with different values for sorting tests."""
        return [
            SummaryFactory(
                content=sortable_contents[0],
                executive_summary="Alpha summary",
                key_themes=["Theme A"],
                relevance_scores={"cto_leadership": 0.9},
                agent_framework="claude",
                model_used="claude-haiku-4-5",
                token_usage=1000,
                processing_time_seconds=2.0,
            ),
            SummaryFactory(
                content=sortable_contents[1],
                executive_summary="Beta summary",
                key_themes=["Theme B"],
                relevance_scores={"cto_leadership": 0.8},
                agent_framework="claude",
                model_used="claude-sonnet-4-5",
                token_usage=2000,
                processing_time_seconds=3.0,
            ),
        ]

    def test_sort_by_model_used_ascending(self, client, sortable_summaries):
        """Test sorting summaries by model_used in ascending order."""
        response = client.get("/api/v1/summaries?sort_by=model_used&sort_order=asc")

        assert response.status_code == 200
        data = response.json()
        models = [item["model_used"] for item in data["items"]]
        # haiku comes before sonnet alphabetically
        assert models == ["claude-haiku-4-5", "claude-sonnet-4-5"]

    def test_sort_by_model_used_descending(self, client, sortable_summaries):
        """Test sorting summaries by model_used in descending order."""
        response = client.get("/api/v1/summaries?sort_by=model_used&sort_order=desc")

        assert response.status_code == 200
        data = response.json()
        models = [item["model_used"] for item in data["items"]]
        assert models == ["claude-sonnet-4-5", "claude-haiku-4-5"]

    def test_sort_by_created_at_ascending(self, client, sortable_summaries):
        """Test sorting summaries by created_at in ascending order."""
        response = client.get("/api/v1/summaries?sort_by=created_at&sort_order=asc")

        assert response.status_code == 200
        data = response.json()
        # Should be sorted by creation time
        assert len(data["items"]) == 2

    def test_invalid_sort_by_falls_back_to_default(self, client, sortable_summaries):
        """Test that invalid sort_by field falls back to default."""
        response = client.get("/api/v1/summaries?sort_by=invalid_field")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2


# ==============================================================================
# Digest Sorting Tests
# ==============================================================================


class TestDigestSorting:
    """Tests for GET /api/v1/digests/ sorting functionality."""

    @pytest.fixture
    def sortable_digests(self, db_session):
        """Create digests with different values for sorting tests."""
        return [
            DigestFactory(
                daily=True,
                approved=True,
                period_start=datetime(2025, 1, 15, 0, 0, 0, tzinfo=UTC),
                period_end=datetime(2025, 1, 15, 23, 59, 59, tzinfo=UTC),
                title="Alpha Digest",
                executive_overview="Alpha overview",
                strategic_insights=[],
                technical_developments=[],
                emerging_trends=[],
                actionable_recommendations={},
                sources=[],
                newsletter_count=3,
                agent_framework="claude",
                model_used="claude-sonnet-4-5",
            ),
            DigestFactory(
                weekly=True,
                pending_review=True,
                period_start=datetime(2025, 1, 8, 0, 0, 0, tzinfo=UTC),
                period_end=datetime(2025, 1, 15, 23, 59, 59, tzinfo=UTC),
                title="Beta Digest",
                executive_overview="Beta overview",
                strategic_insights=[],
                technical_developments=[],
                emerging_trends=[],
                actionable_recommendations={},
                sources=[],
                newsletter_count=10,
                agent_framework="claude",
                model_used="claude-sonnet-4-5",
            ),
        ]

    def test_sort_by_digest_type_ascending(self, client, sortable_digests):
        """Test sorting digests by digest_type in ascending order."""
        response = client.get("/api/v1/digests/?sort_by=digest_type&sort_order=asc")

        assert response.status_code == 200
        data = response.json()
        types = [item["digest_type"] for item in data]
        # daily comes before weekly alphabetically
        assert types == ["daily", "weekly"]

    def test_sort_by_digest_type_descending(self, client, sortable_digests):
        """Test sorting digests by digest_type in descending order."""
        response = client.get("/api/v1/digests/?sort_by=digest_type&sort_order=desc")

        assert response.status_code == 200
        data = response.json()
        types = [item["digest_type"] for item in data]
        assert types == ["weekly", "daily"]

    def test_sort_by_status(self, client, sortable_digests):
        """Test sorting digests by status.

        Note: PostgreSQL sorts enums by ordinal position, not alphabetically.
        DigestStatus ordinals: PENDING_REVIEW=4, APPROVED=5
        """
        response = client.get("/api/v1/digests/?sort_by=status&sort_order=asc")

        assert response.status_code == 200
        data = response.json()
        statuses = [item["status"] for item in data]
        # Sorted by enum ordinal: PENDING_REVIEW (4) before APPROVED (5)
        assert statuses == ["PENDING_REVIEW", "APPROVED"]

    def test_sort_by_period_start(self, client, sortable_digests):
        """Test sorting digests by period_start."""
        response = client.get("/api/v1/digests/?sort_by=period_start&sort_order=asc")

        assert response.status_code == 200
        data = response.json()
        # Weekly (Jan 8) comes before Daily (Jan 15)
        titles = [item["title"] for item in data]
        assert titles == ["Beta Digest", "Alpha Digest"]

    def test_invalid_sort_by_falls_back_to_default(self, client, sortable_digests):
        """Test that invalid sort_by field falls back to default."""
        response = client.get("/api/v1/digests/?sort_by=invalid_field")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


# ==============================================================================
# Script Sorting Tests
# ==============================================================================


class TestScriptSorting:
    """Tests for GET /api/v1/scripts/ sorting functionality."""

    @pytest.fixture
    def sortable_digests(self, db_session):
        """Create digests for script sorting tests."""
        return [
            DigestFactory(
                daily=True,
                approved=True,
                period_start=datetime(2025, 1, 15, 0, 0, 0, tzinfo=UTC),
                period_end=datetime(2025, 1, 15, 23, 59, 59, tzinfo=UTC),
                title="Digest for Script 1",
                executive_overview="Overview",
                strategic_insights=[],
                technical_developments=[],
                emerging_trends=[],
                actionable_recommendations={},
                sources=[],
                newsletter_count=3,
                agent_framework="claude",
                model_used="claude-sonnet-4-5",
            ),
            DigestFactory(
                weekly=True,
                approved=True,
                period_start=datetime(2025, 1, 8, 0, 0, 0, tzinfo=UTC),
                period_end=datetime(2025, 1, 15, 23, 59, 59, tzinfo=UTC),
                title="Digest for Script 2",
                executive_overview="Overview",
                strategic_insights=[],
                technical_developments=[],
                emerging_trends=[],
                actionable_recommendations={},
                sources=[],
                newsletter_count=10,
                agent_framework="claude",
                model_used="claude-sonnet-4-5",
            ),
        ]

    @pytest.fixture
    def sortable_scripts(self, db_session, sortable_digests):
        """Create scripts with different values for sorting tests."""
        return [
            PodcastScriptRecordFactory(
                digest=sortable_digests[0],
                title="Alpha Script",
                length="standard",
                word_count=1000,
                estimated_duration_seconds=400,
                status=PodcastStatus.SCRIPT_PENDING_REVIEW.value,
                model_used="claude-sonnet-4-5",
            ),
            PodcastScriptRecordFactory(
                digest=sortable_digests[1],
                title="Beta Script",
                extended=True,
                word_count=2000,
                estimated_duration_seconds=800,
                status=PodcastStatus.SCRIPT_APPROVED.value,
                model_used="claude-sonnet-4-5",
            ),
        ]

    def test_sort_by_status_ascending(self, client, sortable_scripts):
        """Test sorting scripts by status in ascending order."""
        response = client.get("/api/v1/scripts/?sort_by=status&sort_order=asc")

        assert response.status_code == 200
        data = response.json()
        statuses = [item["status"] for item in data]
        # script_approved comes before script_pending_review alphabetically
        assert statuses == ["script_approved", "script_pending_review"]

    def test_sort_by_status_descending(self, client, sortable_scripts):
        """Test sorting scripts by status in descending order."""
        response = client.get("/api/v1/scripts/?sort_by=status&sort_order=desc")

        assert response.status_code == 200
        data = response.json()
        statuses = [item["status"] for item in data]
        assert statuses == ["script_pending_review", "script_approved"]

    def test_sort_by_digest_id(self, client, sortable_scripts):
        """Test sorting scripts by digest_id."""
        response = client.get("/api/v1/scripts/?sort_by=digest_id&sort_order=asc")

        assert response.status_code == 200
        data = response.json()
        # Scripts should be sorted by their digest_id
        assert len(data) == 2

    def test_invalid_sort_by_falls_back_to_default(self, client, sortable_scripts):
        """Test that invalid sort_by field falls back to default."""
        response = client.get("/api/v1/scripts/?sort_by=invalid_field")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


# ==============================================================================
# Podcast Sorting Tests
# ==============================================================================


class TestPodcastSorting:
    """Tests for GET /api/v1/podcasts/ sorting functionality."""

    @pytest.fixture
    def sortable_scripts(self, db_session):
        """Create scripts for podcast sorting tests."""
        return [
            PodcastScriptRecordFactory(
                approved=True,
                digest=DigestFactory(
                    daily=True,
                    approved=True,
                    period_start=datetime(2025, 1, 15, 0, 0, 0, tzinfo=UTC),
                    period_end=datetime(2025, 1, 15, 23, 59, 59, tzinfo=UTC),
                    title="Digest 1",
                    executive_overview="Overview",
                    strategic_insights=[],
                    technical_developments=[],
                    emerging_trends=[],
                    actionable_recommendations={},
                    sources=[],
                    newsletter_count=3,
                    agent_framework="claude",
                    model_used="claude-sonnet-4-5",
                ),
                title="Script 1",
                length="standard",
                word_count=1000,
                estimated_duration_seconds=400,
                model_used="claude-sonnet-4-5",
            ),
            PodcastScriptRecordFactory(
                approved=True,
                extended=True,
                digest=DigestFactory(
                    weekly=True,
                    approved=True,
                    period_start=datetime(2025, 1, 8, 0, 0, 0, tzinfo=UTC),
                    period_end=datetime(2025, 1, 15, 23, 59, 59, tzinfo=UTC),
                    title="Digest 2",
                    executive_overview="Overview",
                    strategic_insights=[],
                    technical_developments=[],
                    emerging_trends=[],
                    actionable_recommendations={},
                    sources=[],
                    newsletter_count=10,
                    agent_framework="claude",
                    model_used="claude-sonnet-4-5",
                ),
                title="Script 2",
                word_count=2000,
                estimated_duration_seconds=800,
                model_used="claude-sonnet-4-5",
            ),
        ]

    @pytest.fixture
    def sortable_podcasts(self, db_session, sortable_scripts):
        """Create podcasts with different values for sorting tests."""
        return [
            PodcastFactory(
                script=sortable_scripts[0],
                voice_provider="openai_tts",
                duration_seconds=400,
                file_size_bytes=500000,
            ),
            PodcastFactory(
                script=sortable_scripts[1],
                voice_provider="elevenlabs",
                duration_seconds=800,
                file_size_bytes=1000000,
            ),
        ]

    def test_sort_by_duration_ascending(self, client, sortable_podcasts):
        """Test sorting podcasts by duration_seconds in ascending order."""
        response = client.get("/api/v1/podcasts/?sort_by=duration_seconds&sort_order=asc")

        assert response.status_code == 200
        data = response.json()
        durations = [item["duration_seconds"] for item in data]
        assert durations == [400, 800]

    def test_sort_by_duration_descending(self, client, sortable_podcasts):
        """Test sorting podcasts by duration_seconds in descending order."""
        response = client.get("/api/v1/podcasts/?sort_by=duration_seconds&sort_order=desc")

        assert response.status_code == 200
        data = response.json()
        durations = [item["duration_seconds"] for item in data]
        assert durations == [800, 400]

    def test_sort_by_file_size_ascending(self, client, sortable_podcasts):
        """Test sorting podcasts by file_size_bytes in ascending order."""
        response = client.get("/api/v1/podcasts/?sort_by=file_size_bytes&sort_order=asc")

        assert response.status_code == 200
        data = response.json()
        sizes = [item["file_size_bytes"] for item in data]
        assert sizes == [500000, 1000000]

    def test_sort_by_file_size_descending(self, client, sortable_podcasts):
        """Test sorting podcasts by file_size_bytes in descending order."""
        response = client.get("/api/v1/podcasts/?sort_by=file_size_bytes&sort_order=desc")

        assert response.status_code == 200
        data = response.json()
        sizes = [item["file_size_bytes"] for item in data]
        assert sizes == [1000000, 500000]

    def test_invalid_sort_by_falls_back_to_default(self, client, sortable_podcasts):
        """Test that invalid sort_by field falls back to default."""
        response = client.get("/api/v1/podcasts/?sort_by=invalid_field")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
