"""Tests for markdown fields in API responses.

Tests that markdown_content, theme_tags, and source_content_ids are
properly returned by Summary and Digest API endpoints.

These tests validate task 12.5 from the refactor-unified-content-model proposal.
"""

from datetime import UTC, datetime

from src.models.content import Content, ContentSource, ContentStatus
from src.models.digest import Digest, DigestStatus, DigestType


class TestSummaryMarkdownAPI:
    """Tests for Summary API markdown field responses."""

    def test_summary_api_returns_markdown(self, client, sample_content_with_summary):
        """Summary API returns markdown_content field."""
        _content, summary = sample_content_with_summary

        response = client.get(f"/api/v1/summaries/{summary.id}")
        assert response.status_code == 200

        data = response.json()
        assert "markdown_content" in data
        assert data["markdown_content"] is not None
        # Summary markdown starts with ## sections (no H1 header)
        assert "## Executive Summary" in data["markdown_content"]

    def test_summary_api_returns_theme_tags(self, client, sample_content_with_summary):
        """Summary API returns theme_tags field."""
        _content, summary = sample_content_with_summary

        response = client.get(f"/api/v1/summaries/{summary.id}")
        assert response.status_code == 200

        data = response.json()
        assert "theme_tags" in data
        assert data["theme_tags"] is not None
        assert isinstance(data["theme_tags"], list)

    def test_summary_by_content_returns_markdown(self, client, sample_content_with_summary):
        """Summary by content_id endpoint returns markdown fields."""
        content, _summary = sample_content_with_summary

        response = client.get(f"/api/v1/summaries/by-content/{content.id}")
        assert response.status_code == 200

        data = response.json()
        assert "markdown_content" in data
        assert "theme_tags" in data


class TestDigestMarkdownAPI:
    """Tests for Digest API markdown field responses."""

    def test_digest_api_returns_markdown(self, client, db_session):
        """Digest API returns markdown_content field."""
        # Create digest with markdown
        digest = Digest(
            digest_type=DigestType.DAILY,
            period_start=datetime(2025, 1, 14, 0, 0, 0, tzinfo=UTC),
            period_end=datetime(2025, 1, 15, 23, 59, 59, tzinfo=UTC),
            title="Test Digest",
            executive_overview="Test overview",
            strategic_insights=[],
            technical_developments=[],
            emerging_trends=[],
            actionable_recommendations={},
            sources=[],
            newsletter_count=0,
            markdown_content="# Test Digest\n\n## Executive Overview\nTest overview.",
            theme_tags=["test", "digest"],
            source_content_ids=[],
            status=DigestStatus.PENDING_REVIEW,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )
        db_session.add(digest)
        db_session.commit()
        db_session.refresh(digest)

        response = client.get(f"/api/v1/digests/{digest.id}")
        assert response.status_code == 200

        data = response.json()
        assert "markdown_content" in data
        assert data["markdown_content"] is not None
        assert "# Test Digest" in data["markdown_content"]

    def test_digest_api_returns_theme_tags(self, client, db_session):
        """Digest API returns theme_tags field."""
        digest = Digest(
            digest_type=DigestType.DAILY,
            period_start=datetime(2025, 1, 14, 0, 0, 0, tzinfo=UTC),
            period_end=datetime(2025, 1, 15, 23, 59, 59, tzinfo=UTC),
            title="Tag Test Digest",
            executive_overview="Overview",
            strategic_insights=[],
            technical_developments=[],
            emerging_trends=[],
            actionable_recommendations={},
            sources=[],
            newsletter_count=0,
            theme_tags=["ai", "llm", "cost-optimization"],
            status=DigestStatus.PENDING_REVIEW,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )
        db_session.add(digest)
        db_session.commit()
        db_session.refresh(digest)

        response = client.get(f"/api/v1/digests/{digest.id}")
        assert response.status_code == 200

        data = response.json()
        assert "theme_tags" in data
        assert "ai" in data["theme_tags"]
        assert "llm" in data["theme_tags"]

    def test_digest_api_returns_source_content_ids(self, client, db_session):
        """Digest API returns source_content_ids field."""
        # Create some content first
        content = Content(
            source_type=ContentSource.GMAIL,
            source_id="source-tracking-test",
            title="Source Test",
            markdown_content="# Test",
            content_hash="source-track-hash",
            status=ContentStatus.COMPLETED,
            ingested_at=datetime.now(UTC),
        )
        db_session.add(content)
        db_session.commit()
        db_session.refresh(content)

        digest = Digest(
            digest_type=DigestType.DAILY,
            period_start=datetime(2025, 1, 14, 0, 0, 0, tzinfo=UTC),
            period_end=datetime(2025, 1, 15, 23, 59, 59, tzinfo=UTC),
            title="Source Track Digest",
            executive_overview="Overview",
            strategic_insights=[],
            technical_developments=[],
            emerging_trends=[],
            actionable_recommendations={},
            sources=[{"content_id": content.id, "title": content.title}],
            newsletter_count=1,
            source_content_ids=[content.id],
            status=DigestStatus.PENDING_REVIEW,
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )
        db_session.add(digest)
        db_session.commit()
        db_session.refresh(digest)

        response = client.get(f"/api/v1/digests/{digest.id}")
        assert response.status_code == 200

        data = response.json()
        assert "source_content_ids" in data
        assert content.id in data["source_content_ids"]
