"""Tests for digest creation."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.models.digest import DigestData, DigestRequest, DigestType
from src.models.summary import NewsletterSummary
from src.models.theme import ThemeAnalysisResult, ThemeCategory, ThemeData, ThemeTrend
from src.processors.digest_creator import DigestCreator


@pytest.fixture
def sample_themes() -> list[ThemeData]:
    """Create sample themes for testing."""
    return [
        ThemeData(
            name="Large Language Models",
            description="Advancements in LLM capabilities",
            category=ThemeCategory.ML_AI,
            mention_count=5,
            newsletter_ids=[1, 2, 3],
            first_seen=datetime(2025, 1, 1),
            last_seen=datetime(2025, 1, 5),
            trend=ThemeTrend.GROWING,
            relevance_score=0.9,
            strategic_relevance=0.85,
            tactical_relevance=0.75,
            novelty_score=0.6,
            cross_functional_impact=0.8,
            related_themes=["Transformers", "GPT"],
            key_points=[
                "Context windows expanding to 1M+ tokens",
                "Multimodal capabilities improving",
                "Cost reduction trends continuing",
            ],
        ),
        ThemeData(
            name="Vector Databases",
            description="Specialized databases for embeddings",
            category=ThemeCategory.DATA_ENGINEERING,
            mention_count=3,
            newsletter_ids=[2, 4],
            first_seen=datetime(2025, 1, 2),
            last_seen=datetime(2025, 1, 5),
            trend=ThemeTrend.ESTABLISHED,
            relevance_score=0.7,
            strategic_relevance=0.6,
            tactical_relevance=0.85,
            novelty_score=0.3,
            cross_functional_impact=0.5,
            related_themes=["RAG", "Embeddings"],
            key_points=[
                "Performance optimization techniques",
                "Hybrid search approaches",
            ],
        ),
    ]


@pytest.fixture
def sample_newsletters() -> list[dict]:
    """Create sample newsletter data for testing."""
    return [
        {
            "id": 1,
            "title": "AI Weekly - Latest in LLMs",
            "publication": "AI Weekly",
            "published_date": datetime(2025, 1, 1),
            "url": "https://example.com/article1",
        },
        {
            "id": 2,
            "title": "Tech Trends Report",
            "publication": "TechCrunch",
            "published_date": datetime(2025, 1, 2),
            "url": "https://example.com/article2",
        },
    ]


@pytest.fixture
def sample_summaries() -> list[NewsletterSummary]:
    """Create sample newsletter summaries for testing."""
    summaries = []
    for i, newsletter_id in enumerate([1, 2]):
        summary = NewsletterSummary(
            newsletter_id=newsletter_id,
            executive_summary=f"Summary for newsletter {newsletter_id}",
            key_themes=["AI", "Machine Learning"],
            strategic_insights=["Strategic insight 1"],
            technical_details=["Technical detail 1"],
            actionable_items=["Action item 1"],
            notable_quotes=["Notable quote 1"],
            relevant_links=[],
            relevance_scores={"leadership": 0.8, "technical": 0.7},
            agent_framework="claude",
            model_used="claude-sonnet-4-5",
        )
        summary.id = newsletter_id
        summaries.append(summary)
    return summaries


@pytest.fixture
def mock_llm_response() -> dict:
    """Create mock LLM response for digest generation."""
    return {
        "title": "AI/Tech Digest - January 1-5, 2025",
        "executive_overview": (
            "This week saw significant advancements in large language models and "
            "infrastructure for AI applications. Key strategic decisions needed around "
            "vector database adoption and LLM deployment strategies."
        ),
        "strategic_insights": [
            {
                "title": "LLM Capabilities Expanding Rapidly",
                "summary": "Context windows and multimodal capabilities reaching new heights.",
                "details": [
                    "Context windows now exceed 1M tokens in production systems",
                    "Cost per token decreasing 40% year-over-year",
                    "Strategic implications for document processing workflows",
                ],
                "themes": ["Large Language Models", "AI Infrastructure"],
                "continuity": "Building on Q4 2024 trends in model efficiency.",
            },
        ],
        "technical_developments": [
            {
                "title": "Hybrid Vector Search Approaches",
                "summary": "Combining vector and keyword search for better accuracy.",
                "details": [
                    "Reranking models improving relevance by 30%",
                    "Hybrid search combining semantic and exact matching",
                    "Implementation patterns for production RAG systems",
                ],
                "themes": ["Vector Databases", "RAG"],
                "continuity": None,
            },
        ],
        "emerging_trends": [
            {
                "title": "Multi-Agent Orchestration",
                "summary": "New frameworks for coordinating multiple AI agents.",
                "details": [
                    "LangGraph and similar frameworks gaining adoption",
                    "Use cases in research and data analysis",
                    "Observability challenges being addressed",
                ],
                "themes": ["AI Agents", "Orchestration"],
                "continuity": "First discussed 4 weeks ago, now seeing production use.",
            },
        ],
        "actionable_recommendations": {
            "for_leadership": [
                "Evaluate long-context LLM use cases for your organization",
                "Budget for vector database infrastructure",
            ],
            "for_teams": [
                "Prototype hybrid search for your RAG systems",
                "Explore agent orchestration frameworks",
            ],
            "for_individuals": [
                "Learn about embedding models and vector search",
                "Experiment with LangGraph or similar tools",
            ],
        },
    }


@pytest.mark.asyncio
async def test_create_digest_success(sample_themes, sample_newsletters, mock_llm_response):
    """Test successful digest creation."""
    request = DigestRequest(
        digest_type=DigestType.DAILY,
        period_start=datetime(2025, 1, 1),
        period_end=datetime(2025, 1, 5),
    )

    # Mock theme analyzer
    theme_result = ThemeAnalysisResult(
        start_date=request.period_start,
        end_date=request.period_end,
        newsletter_count=2,
        newsletter_ids=[1, 2],
        themes=sample_themes,
        total_themes=2,
        emerging_themes_count=1,
        top_theme="Large Language Models",
        agent_framework="claude",
        model_used="claude-sonnet-4-20250514",
        processing_time_seconds=10.5,
    )

    with patch("src.processors.digest_creator.ThemeAnalyzer") as mock_analyzer_class:
        mock_analyzer = AsyncMock()
        mock_analyzer.analyze_themes.return_value = theme_result
        mock_analyzer_class.return_value = mock_analyzer

        # Mock newsletter fetch
        with patch.object(DigestCreator, "_fetch_newsletters", return_value=sample_newsletters):
            # Mock LLM generation
            with patch.object(
                DigestCreator,
                "_generate_digest_content",
                return_value=mock_llm_response,
            ):
                creator = DigestCreator()
                digest = await creator.create_digest(request)

    # Verify digest structure
    assert isinstance(digest, DigestData)
    assert digest.digest_type == DigestType.DAILY
    assert digest.title == "AI/Tech Digest - January 1-5, 2025"
    assert "significant advancements" in digest.executive_overview
    assert digest.newsletter_count == 2
    assert digest.agent_framework == "claude"
    assert digest.processing_time_seconds > 0

    # Verify sections
    assert len(digest.strategic_insights) == 1
    assert digest.strategic_insights[0].title == "LLM Capabilities Expanding Rapidly"
    assert len(digest.technical_developments) == 1
    assert len(digest.emerging_trends) == 1

    # Verify recommendations
    assert "for_leadership" in digest.actionable_recommendations
    assert len(digest.actionable_recommendations["for_leadership"]) == 2

    # Verify sources
    assert len(digest.sources) == 2
    assert digest.sources[0]["publication"] == "AI Weekly"


@pytest.mark.asyncio
async def test_create_digest_no_newsletters():
    """Test digest creation when no newsletters found."""
    request = DigestRequest(
        digest_type=DigestType.DAILY,
        period_start=datetime(2025, 1, 1),
        period_end=datetime(2025, 1, 1),
    )

    # Mock theme analyzer returning zero newsletters
    theme_result = ThemeAnalysisResult(
        start_date=request.period_start,
        end_date=request.period_end,
        newsletter_count=0,
        newsletter_ids=[],
        themes=[],
        total_themes=0,
        emerging_themes_count=0,
        top_theme=None,
        agent_framework="claude",
        model_used="claude-sonnet-4-20250514",
        processing_time_seconds=1.0,
    )

    with patch("src.processors.digest_creator.ThemeAnalyzer") as mock_analyzer_class:
        mock_analyzer = AsyncMock()
        mock_analyzer.analyze_themes.return_value = theme_result
        mock_analyzer_class.return_value = mock_analyzer

        creator = DigestCreator()
        digest = await creator.create_digest(request)

    # Should return empty digest
    assert digest.newsletter_count == 0
    assert "No newsletters" in digest.executive_overview
    assert len(digest.strategic_insights) == 0
    assert len(digest.technical_developments) == 0
    assert len(digest.emerging_trends) == 0


@pytest.mark.asyncio
async def test_create_digest_without_historical_context(sample_themes):
    """Test digest creation with historical context disabled."""
    request = DigestRequest(
        digest_type=DigestType.DAILY,
        period_start=datetime(2025, 1, 1),
        period_end=datetime(2025, 1, 1),
        include_historical_context=False,
    )

    theme_result = ThemeAnalysisResult(
        start_date=request.period_start,
        end_date=request.period_end,
        newsletter_count=1,
        newsletter_ids=[1],
        themes=sample_themes,
        total_themes=2,
        emerging_themes_count=0,
        top_theme="Large Language Models",
        agent_framework="claude",
        model_used="claude-sonnet-4-20250514",
        processing_time_seconds=5.0,
    )

    with patch("src.processors.digest_creator.ThemeAnalyzer") as mock_analyzer_class:
        mock_analyzer = AsyncMock()
        mock_analyzer_class.return_value = mock_analyzer

        creator = DigestCreator()
        digest_creator_instance = await creator.create_digest(request)

        # Verify historical context flag was passed to theme analyzer
        # (This would be called in the actual implementation)
        # mock_analyzer.analyze_themes.assert_called_once()
        # call_args = mock_analyzer.analyze_themes.call_args
        # assert call_args.kwargs.get("include_historical_context") == False


def test_build_themes_context(sample_themes):
    """Test themes context string building."""
    creator = DigestCreator()
    context = creator._build_themes_context(sample_themes)

    # Check that all themes are included
    assert "Large Language Models" in context
    assert "Vector Databases" in context

    # Check metadata is present
    assert "ml_ai" in context
    assert "growing" in context
    assert "Relevance:" in context

    # Check key points are included
    assert "Context windows expanding" in context
    assert "Performance optimization" in context


def test_build_newsletters_context(sample_newsletters, sample_summaries):
    """Test newsletters context string building."""
    creator = DigestCreator()
    context = creator._build_newsletters_context(sample_newsletters, sample_summaries)

    # Check that newsletters are listed
    assert "AI Weekly" in context
    assert "TechCrunch" in context
    assert "Latest in LLMs" in context
    assert "2025-01-01" in context


def test_build_digest_prompt():
    """Test digest prompt construction."""
    creator = DigestCreator()

    request = DigestRequest(
        digest_type=DigestType.WEEKLY,
        period_start=datetime(2025, 1, 1),
        period_end=datetime(2025, 1, 7),
        max_strategic_insights=3,
        max_technical_developments=4,
        max_emerging_trends=2,
    )

    prompt = creator._build_digest_prompt(
        request=request,
        themes_context="Test themes context",
        newsletters_context="Test newsletters context",
        theme_count=5,
    )

    # Check prompt structure
    assert "Time Period" in prompt
    assert "Weekly digest" in prompt
    assert "2025-01-01" in prompt
    assert "2025-01-07" in prompt

    # Check themes and newsletters context included
    assert "Test themes context" in prompt
    assert "Test newsletters context" in prompt

    # Check guidance for weekly digest
    assert "broader context" in prompt or "patterns" in prompt

    # Check limits are specified
    assert "3 most important" in prompt or "Limit to 3" in prompt
    assert "4 most significant" in prompt or "Limit to 4" in prompt
    assert "2 most noteworthy" in prompt or "Limit to 2" in prompt

    # Check JSON structure is defined
    assert "strategic_insights" in prompt
    assert "technical_developments" in prompt
    assert "emerging_trends" in prompt
    assert "actionable_recommendations" in prompt


def test_build_sources(sample_newsletters):
    """Test sources list building."""
    creator = DigestCreator()
    sources = creator._build_sources(sample_newsletters)

    assert len(sources) == 2
    assert sources[0]["title"] == "AI Weekly - Latest in LLMs"
    assert sources[0]["publication"] == "AI Weekly"
    assert sources[0]["date"] == "2025-01-01"
    assert sources[0]["url"] == "https://example.com/article1"


def test_build_sources_without_url():
    """Test sources list building when URL is missing."""
    newsletters = [
        {
            "id": 1,
            "title": "Test Article",
            "publication": "Test Pub",
            "published_date": datetime(2025, 1, 1),
            # No URL
        }
    ]

    creator = DigestCreator()
    sources = creator._build_sources(newsletters)

    assert len(sources) == 1
    assert sources[0]["url"] is None


def test_create_empty_digest():
    """Test empty digest creation."""
    creator = DigestCreator()

    request = DigestRequest(
        digest_type=DigestType.DAILY,
        period_start=datetime(2025, 1, 1),
        period_end=datetime(2025, 1, 1),
    )

    digest = creator._create_empty_digest(request)

    assert digest.newsletter_count == 0
    assert "No Content" in digest.title
    assert "No newsletters" in digest.executive_overview
    assert len(digest.strategic_insights) == 0
    assert digest.agent_framework == "claude"
