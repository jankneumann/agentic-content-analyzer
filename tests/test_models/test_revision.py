"""Tests for revision context and result models."""

from datetime import UTC, datetime

import pytest

from src.models.digest import Digest, DigestStatus, DigestType
from src.models.newsletter import Newsletter, NewsletterSource
from src.models.revision import RevisionContext, RevisionResult, RevisionTurn
from src.models.summary import NewsletterSummary


@pytest.fixture
def sample_digest():
    """Create sample digest for testing."""
    digest = Digest(
        digest_type=DigestType.DAILY,
        period_start=datetime(2025, 1, 15, 0, 0, 0),
        period_end=datetime(2025, 1, 15, 23, 59, 59),
        title="AI Advances - January 15, 2025",
        executive_overview="Key AI developments this week...",
        strategic_insights=[
            {
                "title": "RAG Architecture Maturity",
                "summary": "Hybrid search becoming standard...",
                "details": ["Detail 1", "Detail 2"],
            }
        ],
        technical_developments=[
            {
                "title": "Vector Database Performance",
                "summary": "10x performance gains...",
                "details": ["Detail 1"],
            }
        ],
        emerging_trends=[
            {
                "title": "Agentic Workflows",
                "summary": "Tool-using agents moving to production...",
                "continuity": "First discussed 3 months ago...",
            }
        ],
        actionable_recommendations={
            "For Leadership": ["Action 1", "Action 2"],
            "For Teams": ["Action 3"],
        },
        sources=[{"title": "AI Weekly", "url": "https://example.com"}],
        newsletter_count=5,
        status=DigestStatus.PENDING_REVIEW,
        agent_framework="claude",
        model_used="claude-sonnet-4-5",
        model_version="20250929",
    )
    digest.id = 1
    return digest


@pytest.fixture
def sample_newsletters():
    """Create sample newsletters for testing."""
    newsletters = []
    for i in range(3):
        newsletter = Newsletter(
            source=NewsletterSource.GMAIL,
            source_id=f"test-{i}",
            title=f"Newsletter {i + 1}",
            sender="test@example.com",
            publication="Tech Weekly",
            published_date=datetime(2025, 1, 15, 10 + i, 0, 0),
            raw_text=f"Content for newsletter {i + 1}",
        )
        newsletter.id = i + 1
        newsletters.append(newsletter)
    return newsletters


@pytest.fixture
def sample_summaries(sample_newsletters):
    """Create sample newsletter summaries for testing."""
    summaries = []
    for newsletter in sample_newsletters:
        summary = NewsletterSummary(
            newsletter_id=newsletter.id,
            executive_summary=f"Summary for {newsletter.title}",
            key_themes=["Theme 1", "Theme 2"],
            strategic_insights=["Insight 1", "Insight 2"],
            technical_details=["Detail 1"],
            actionable_items=["Action 1"],
            notable_quotes=["Quote 1"],
            relevance_scores={},
            agent_framework="claude",
            model_used="claude-haiku-4-5",
            model_version="20251001",
        )
        # Set up relationship
        summary.newsletter = newsletter
        summaries.append(summary)
    return summaries


class TestRevisionContext:
    """Tests for RevisionContext model."""

    def test_initialization(self, sample_digest, sample_summaries):
        """Test RevisionContext initialization."""
        context = RevisionContext(
            digest=sample_digest,
            summaries=sample_summaries,
            theme_analysis=None,
            newsletter_ids=[1, 2, 3],
        )

        assert context.digest == sample_digest
        assert len(context.summaries) == 3
        assert context.theme_analysis is None
        assert context.newsletter_ids == [1, 2, 3]

    def test_post_init_extracts_newsletter_ids(self, sample_digest, sample_summaries):
        """Test that __post_init__ extracts newsletter IDs from summaries."""
        context = RevisionContext(
            digest=sample_digest,
            summaries=sample_summaries,
        )

        # Should auto-populate from summaries
        assert context.newsletter_ids == [1, 2, 3]

    def test_to_llm_context_format(self, sample_digest, sample_summaries):
        """Test formatting context for LLM prompt."""
        context = RevisionContext(
            digest=sample_digest,
            summaries=sample_summaries,
        )

        formatted = context.to_llm_context()

        # Check key sections are present
        assert "## CURRENT DIGEST" in formatted
        assert "Executive Overview" in formatted
        assert "Strategic Insights" in formatted
        assert "Technical Developments" in formatted
        assert "Emerging Trends" in formatted
        assert "Actionable Recommendations" in formatted

        # Check newsletter summaries
        assert "## SOURCE NEWSLETTERS (CONDENSED SUMMARIES)" in formatted
        assert "Newsletter 1" in formatted
        assert "Newsletter 2" in formatted
        assert "Newsletter 3" in formatted

        # Check tool availability note
        assert "## AVAILABLE TOOLS" in formatted
        assert "fetch_newsletter_content" in formatted
        assert "search_newsletters" in formatted

    def test_to_llm_context_includes_metadata(self, sample_digest, sample_summaries):
        """Test that LLM context includes important metadata."""
        context = RevisionContext(
            digest=sample_digest,
            summaries=sample_summaries,
        )

        formatted = context.to_llm_context()

        # Check metadata (enum value in format with markdown bold)
        assert "**Type**:" in formatted
        assert "DigestType.DAILY" in formatted or "daily" in formatted.lower()
        assert "2025-01-15" in formatted
        assert "**Newsletter Count**: 5" in formatted


class TestRevisionResult:
    """Tests for RevisionResult model."""

    def test_initialization(self):
        """Test RevisionResult initialization."""
        result = RevisionResult(
            revised_content="New executive summary text...",
            section_modified="executive_overview",
            explanation="Made summary more concise by focusing on top 3 themes",
            confidence_score=0.95,
            tools_used=["fetch_newsletter_content"],
        )

        assert result.revised_content == "New executive summary text..."
        assert result.section_modified == "executive_overview"
        assert result.explanation.startswith("Made summary more concise")
        assert result.confidence_score == 0.95
        assert result.tools_used == ["fetch_newsletter_content"]

    def test_default_confidence_score(self):
        """Test default confidence score is 1.0."""
        result = RevisionResult(
            revised_content="Test content",
            section_modified="test_section",
            explanation="Test explanation",
        )

        assert result.confidence_score == 1.0

    def test_post_init_initializes_tools_used(self):
        """Test that __post_init__ initializes tools_used to empty list."""
        result = RevisionResult(
            revised_content="Test content",
            section_modified="test_section",
            explanation="Test explanation",
        )

        assert result.tools_used == []

    def test_with_multiple_tools(self):
        """Test RevisionResult with multiple tools used."""
        result = RevisionResult(
            revised_content="Updated content",
            section_modified="strategic_insights",
            explanation="Added more details from newsletters",
            tools_used=["fetch_newsletter_content", "search_newsletters"],
        )

        assert len(result.tools_used) == 2
        assert "fetch_newsletter_content" in result.tools_used
        assert "search_newsletters" in result.tools_used


class TestRevisionTurn:
    """Tests for RevisionTurn model."""

    def test_initialization(self):
        """Test RevisionTurn initialization."""
        timestamp = datetime.now(UTC)
        turn = RevisionTurn(
            turn=1,
            user_input="Make executive summary more concise",
            ai_response="I've condensed the summary to focus on the top 3 themes",
            section_modified="executive_overview",
            change_accepted=True,
            timestamp=timestamp,
            tools_called=["search_newsletters"],
        )

        assert turn.turn == 1
        assert turn.user_input == "Make executive summary more concise"
        assert "condensed" in turn.ai_response
        assert turn.section_modified == "executive_overview"
        assert turn.change_accepted is True
        assert turn.timestamp == timestamp
        assert turn.tools_called == ["search_newsletters"]

    def test_post_init_initializes_tools_called(self):
        """Test that __post_init__ initializes tools_called to empty list."""
        turn = RevisionTurn(
            turn=1,
            user_input="Test input",
            ai_response="Test response",
            section_modified="test_section",
            change_accepted=False,
            timestamp=datetime.now(UTC),
        )

        assert turn.tools_called == []

    def test_to_dict_serialization(self):
        """Test conversion to dictionary for JSON serialization."""
        timestamp = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
        turn = RevisionTurn(
            turn=2,
            user_input="Add technical details",
            ai_response="Added details from newsletters 1 and 3",
            section_modified="technical_developments",
            change_accepted=True,
            timestamp=timestamp,
            tools_called=["fetch_newsletter_content"],
        )

        result = turn.to_dict()

        assert isinstance(result, dict)
        assert result["turn"] == 2
        assert result["user_input"] == "Add technical details"
        assert result["ai_response"] == "Added details from newsletters 1 and 3"
        assert result["section_modified"] == "technical_developments"
        assert result["change_accepted"] is True
        assert result["timestamp"] == "2025-01-15T10:30:00+00:00"
        assert result["tools_called"] == ["fetch_newsletter_content"]

    def test_to_dict_with_no_tools(self):
        """Test to_dict with empty tools_called list."""
        turn = RevisionTurn(
            turn=1,
            user_input="Test",
            ai_response="Response",
            section_modified="test",
            change_accepted=False,
            timestamp=datetime.now(UTC),
        )

        result = turn.to_dict()

        assert result["tools_called"] == []
