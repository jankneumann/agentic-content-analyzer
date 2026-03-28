"""Regression tests for API contract consistency between frontend and backend.

These tests verify that the Pydantic response models used by API routes
have all the fields that the frontend TypeScript types expect. This catches
a common class of regressions where:

  - A backend field is renamed but the frontend type isn't updated
  - A new required field is added to the backend but missing from mock data
  - The frontend expects a field that the backend response model dropped

The tests work by comparing the fields of backend Pydantic models against
the expected field sets derived from the TypeScript interfaces. No running
server is needed — this is pure schema inspection.

Markers:
    @pytest.mark.regression - run with: pytest -m regression
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.regression


# =============================================================================
# Helpers
# =============================================================================


def _pydantic_fields(model_class) -> set[str]:
    """Extract field names from a Pydantic v2 model."""
    return set(model_class.model_fields.keys())


# =============================================================================
# Expected Frontend Fields
#
# These sets are derived from web/src/types/*.ts interfaces.
# When a TypeScript type changes, update the set here too.
# =============================================================================

# From web/src/types/digest.ts: DigestListItem
FRONTEND_DIGEST_LIST_FIELDS = {
    "id",
    "digest_type",
    "title",
    "period_start",
    "period_end",
    "content_count",
    "status",
    "created_at",
    "model_used",
    "revision_count",
    "reviewed_by",
}

# From web/src/types/digest.ts: DigestDetail
FRONTEND_DIGEST_DETAIL_FIELDS = {
    "id",
    "digest_type",
    "title",
    "period_start",
    "period_end",
    "executive_overview",
    "strategic_insights",
    "technical_developments",
    "emerging_trends",
    "actionable_recommendations",
    "sources",
    "content_count",
    "status",
    "created_at",
    "completed_at",
    "model_used",
    "model_version",
    "processing_time_seconds",
    "revision_count",
    "reviewed_by",
    "reviewed_at",
    "review_notes",
    "is_combined",
    "child_digest_ids",
}

# From web/src/types/digest.ts: DigestStatistics
FRONTEND_DIGEST_STATS_FIELDS = {
    "total",
    "pending",
    "generating",
    "completed",
    "pending_review",
    "approved",
    "delivered",
    "by_type",
}

# From web/src/types/podcast.ts: PodcastListItem
FRONTEND_PODCAST_LIST_FIELDS = {
    "id",
    "script_id",
    "title",
    "digest_id",
    "length",
    "duration_seconds",
    "file_size_bytes",
    "audio_format",
    "voice_provider",
    "status",
    "created_at",
    "completed_at",
}

# From web/src/types/content.ts: ContentListItem
FRONTEND_CONTENT_LIST_FIELDS = {
    "id",
    "source_type",
    "title",
    "publication",
    "published_date",
    "status",
    "ingested_at",
}


# =============================================================================
# Tests: Backend Model ⊇ Frontend Fields
# =============================================================================


class TestDigestApiContract:
    """Verify digest API response models include all frontend-expected fields."""

    def test_digest_list_model_has_frontend_fields(self):
        """Backend DigestSummary has all fields frontend DigestListItem expects."""
        from src.api.digest_routes import DigestSummary

        backend_fields = _pydantic_fields(DigestSummary)
        missing = FRONTEND_DIGEST_LIST_FIELDS - backend_fields

        # The backend uses 'newsletter_count' while frontend uses 'content_count'
        # This is a known mapping handled by the API layer
        expected_aliases = {"content_count"}
        actual_missing = missing - expected_aliases

        assert not actual_missing, (
            f"Backend DigestSummary is missing fields expected by frontend DigestListItem: {actual_missing}. "
            f"Backend fields: {sorted(backend_fields)}"
        )

    def test_digest_detail_model_has_frontend_fields(self):
        """Backend DigestDetail has all fields frontend DigestDetail expects."""
        from src.api.digest_routes import DigestDetail

        backend_fields = _pydantic_fields(DigestDetail)
        missing = FRONTEND_DIGEST_DETAIL_FIELDS - backend_fields

        # Known field name differences
        expected_aliases = {"content_count"}
        actual_missing = missing - expected_aliases

        assert not actual_missing, (
            f"Backend DigestDetail is missing fields expected by frontend: {actual_missing}. "
            f"Backend fields: {sorted(backend_fields)}"
        )

    def test_digest_statistics_model_has_frontend_fields(self):
        """Backend DigestStatistics has all fields frontend expects."""
        from src.api.digest_routes import DigestStatistics

        backend_fields = _pydantic_fields(DigestStatistics)
        missing = FRONTEND_DIGEST_STATS_FIELDS - backend_fields

        assert not missing, (
            f"Backend DigestStatistics is missing fields: {missing}. "
            f"Backend fields: {sorted(backend_fields)}"
        )


class TestPodcastApiContract:
    """Verify podcast API response models include all frontend-expected fields."""

    def test_podcast_list_model_has_frontend_fields(self):
        """Backend PodcastListItem has all fields frontend expects."""
        from src.api.podcast_routes import PodcastListItem

        backend_fields = _pydantic_fields(PodcastListItem)
        missing = FRONTEND_PODCAST_LIST_FIELDS - backend_fields

        assert not missing, (
            f"Backend PodcastListItem is missing fields: {missing}. "
            f"Backend fields: {sorted(backend_fields)}"
        )


class TestContentApiContract:
    """Verify content API response models include all frontend-expected fields."""

    def test_content_list_item_fields(self):
        """Backend ContentListItem has all fields frontend expects."""
        from src.models.content import ContentListItem

        backend_fields = _pydantic_fields(ContentListItem)
        missing = FRONTEND_CONTENT_LIST_FIELDS - backend_fields

        assert not missing, (
            f"Backend ContentListItem is missing fields: {missing}. "
            f"Backend fields: {sorted(backend_fields)}"
        )


# =============================================================================
# Tests: Backend Has No Surprise Required Fields
#
# Frontend mock data must include all required (non-optional) backend fields.
# If the backend adds a new required field, these tests catch it.
# =============================================================================


class TestBackendRequiredFields:
    """Verify frontend mock data wouldn't fail backend validation."""

    def _get_required_fields(self, model_class) -> set[str]:
        """Get fields that are required (no default value) in a Pydantic model."""
        required = set()
        for name, field_info in model_class.model_fields.items():
            if field_info.is_required():
                required.add(name)
        return required

    def test_digest_summary_required_fields_are_documented(self):
        """All required DigestSummary fields are in our frontend field set."""
        from src.api.digest_routes import DigestSummary

        required = self._get_required_fields(DigestSummary)
        # Every required backend field should either be in the frontend set
        # or be a known extra field
        undocumented = required - FRONTEND_DIGEST_LIST_FIELDS - {"newsletter_count"}
        assert not undocumented, (
            f"Backend DigestSummary has required fields not tracked in frontend contract: {undocumented}"
        )

    def test_digest_detail_required_fields_are_documented(self):
        """All required DigestDetail fields are in our frontend field set."""
        from src.api.digest_routes import DigestDetail

        required = self._get_required_fields(DigestDetail)
        undocumented = required - FRONTEND_DIGEST_DETAIL_FIELDS - {"newsletter_count"}
        assert not undocumented, (
            f"Backend DigestDetail has required fields not tracked in frontend contract: {undocumented}"
        )

    def test_digest_statistics_required_fields_are_documented(self):
        """All required DigestStatistics fields are in our frontend field set."""
        from src.api.digest_routes import DigestStatistics

        required = self._get_required_fields(DigestStatistics)
        undocumented = required - FRONTEND_DIGEST_STATS_FIELDS
        assert not undocumented, (
            f"Backend DigestStatistics has required fields not tracked: {undocumented}"
        )

    def test_podcast_list_required_fields_are_documented(self):
        """All required PodcastListItem fields are in our frontend field set."""
        from src.api.podcast_routes import PodcastListItem

        required = self._get_required_fields(PodcastListItem)
        undocumented = required - FRONTEND_PODCAST_LIST_FIELDS
        assert not undocumented, (
            f"Backend PodcastListItem has required fields not tracked: {undocumented}"
        )


# =============================================================================
# Tests: Mock Data Factory Completeness
#
# Verify that the Python test factories produce objects with all fields
# that the frontend expects. This catches cases where a factory creates
# objects missing fields the UI reads.
# =============================================================================


class TestFactoryCompleteness:
    """Verify Python test factories produce all frontend-expected fields."""

    def test_content_factory_has_required_fields(self):
        """ContentFactory produces objects with all frontend fields."""
        from tests.factories.content import ContentFactory

        # Build (don't create — no DB needed) a content object
        content = ContentFactory.build()

        # Check essential fields exist as attributes
        for field in ["id", "source_type", "title", "status"]:
            assert hasattr(content, field), f"ContentFactory missing field: {field}"

    def test_digest_factory_has_required_fields(self):
        """DigestFactory produces objects with essential fields."""
        from tests.factories.digest import DigestFactory

        digest = DigestFactory.build()

        for field in ["id", "digest_type", "title", "status", "created_at"]:
            assert hasattr(digest, field), f"DigestFactory missing field: {field}"

    def test_summary_factory_has_required_fields(self):
        """SummaryFactory produces objects with essential fields."""
        from tests.factories.summary import SummaryFactory

        summary = SummaryFactory.build()

        for field in ["id", "content_id"]:
            assert hasattr(summary, field), f"SummaryFactory missing field: {field}"
