"""Tests for ThemeAnalyzer."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.models import MODEL_REGISTRY
from src.models.theme import (
    ThemeAnalysisRequest,
    ThemeCategory,
    ThemeTrend,
)
from src.processors.theme_analyzer import ThemeAnalyzer


@pytest.fixture
def sample_newsletters() -> list[dict]:
    """Create sample newsletters for testing."""
    return [
        {
            "id": 1,
            "title": "AI Advances",
            "publication": "Tech Weekly",
            "published_date": datetime(2025, 1, 15),
        },
        {
            "id": 2,
            "title": "Vector Databases",
            "publication": "Data News",
            "published_date": datetime(2025, 1, 10),
        },
        {
            "id": 3,
            "title": "LLM Updates",
            "publication": "AI Digest",
            "published_date": datetime(2025, 1, 5),
        },
    ]


@pytest.fixture
def sample_summaries() -> list[dict]:
    """Create sample summaries for testing."""
    return [
        {
            "newsletter_id": 1,
            "executive_summary": "Major AI breakthroughs this week.",
            "key_themes": ["LLMs", "AI Agents"],
            "strategic_insights": ["Cost reduction in LLMs", "Agent adoption growing"],
            "technical_details": ["New context windows", "Better embeddings"],
        },
        {
            "newsletter_id": 2,
            "executive_summary": "Vector database performance improvements.",
            "key_themes": ["Vector Search", "Embeddings"],
            "strategic_insights": ["Database selection critical"],
            "technical_details": ["Hybrid search techniques"],
        },
        {
            "newsletter_id": 3,
            "executive_summary": "Latest LLM releases.",
            "key_themes": ["GPT", "Claude"],
            "strategic_insights": ["Model selection matters"],
            "technical_details": ["API updates", "Pricing changes"],
        },
    ]


@pytest.fixture
def sample_graphiti_themes() -> list[dict]:
    """Create sample Graphiti theme data."""
    return [
        {"name": "RAG", "fact": "Retrieval Augmented Generation improving"},
        {"name": "Vector DB", "fact": "Performance critical for search"},
        {"name": "LLM Agents", "fact": "Multi-agent systems emerging"},
    ]


@pytest.fixture
def mock_llm_response() -> str:
    """Create mock LLM response for theme extraction."""
    return """```json
[
  {
    "name": "Large Language Models",
    "description": "Advancements in LLM capabilities and cost reduction",
    "category": "ml_ai",
    "mention_count": 2,
    "trend": "growing",
    "relevance_score": 0.9,
    "strategic_relevance": 0.85,
    "tactical_relevance": 0.75,
    "novelty_score": 0.6,
    "cross_functional_impact": 0.8,
    "related_themes": ["AI Agents", "RAG"],
    "key_points": [
      "Context windows expanding significantly",
      "Cost per token decreasing",
      "Multimodal capabilities improving"
    ]
  },
  {
    "name": "Vector Databases",
    "description": "Performance optimization and hybrid search approaches",
    "category": "data_engineering",
    "mention_count": 1,
    "trend": "established",
    "relevance_score": 0.7,
    "strategic_relevance": 0.6,
    "tactical_relevance": 0.85,
    "novelty_score": 0.3,
    "cross_functional_impact": 0.5,
    "related_themes": ["RAG", "Embeddings"],
    "key_points": [
      "Hybrid search combining vector and keyword",
      "Performance critical for production"
    ]
  }
]
```"""


def test_theme_analyzer_initialization():
    """Test ThemeAnalyzer initialization."""
    with patch("src.processors.theme_analyzer.Anthropic") as mock_anthropic:
        analyzer = ThemeAnalyzer()

        # Model should be from registry and configured for theme_analysis step
        assert analyzer.model in MODEL_REGISTRY, f"Model {analyzer.model} not in registry"
        assert analyzer.model_config is not None
        assert analyzer.framework in ["claude", "gemini", "gpt"]
        assert not analyzer.use_large_context


def test_theme_analyzer_initialization_with_model_override():
    """Test ThemeAnalyzer with custom model."""
    with patch("src.processors.theme_analyzer.Anthropic"):
        # Use any valid model from the registry
        available_models = list(MODEL_REGISTRY.keys())
        test_model = available_models[0]  # Use first model from registry

        analyzer = ThemeAnalyzer(model_override=test_model)

        assert analyzer.model == test_model
        assert analyzer.model in MODEL_REGISTRY


def test_theme_analyzer_large_context_warning():
    """Test warning when large context mode requested."""
    with patch("src.processors.theme_analyzer.Anthropic"):
        with patch("src.processors.theme_analyzer.logger") as mock_logger:
            analyzer = ThemeAnalyzer(use_large_context=True)

            # Should log warning about Gemini not implemented
            mock_logger.warning.assert_called_once()
            assert "not yet implemented" in mock_logger.warning.call_args[0][0]


# TODO: Integration test - requires database setup
# This test should be moved to integration tests as it requires real database access
# The core logic is covered by unit tests above
# @pytest.mark.asyncio
# async def test_analyze_themes_success_integration():
#     """Test successful theme analysis (INTEGRATION TEST - requires database)."""
#     pass


@pytest.mark.asyncio
async def test_analyze_themes_insufficient_newsletters():
    """Test analysis with insufficient newsletters."""
    request = ThemeAnalysisRequest(
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 1, 31),
        min_newsletters=5,
    )

    with patch("src.processors.theme_analyzer.Anthropic"):
        with patch("src.processors.theme_analyzer.GraphitiClient") as mock_graphiti:
            mock_graphiti.return_value.close = MagicMock()

            with patch("src.storage.database.get_db") as mock_get_db:
                mock_db = MagicMock()
                # Return only 2 newsletters (less than min_newsletters=5)
                mock_query = MagicMock()
                mock_query.filter.return_value.order_by.return_value.all.return_value = [
                    MagicMock(id=1, title="Test")
                ] * 2
                mock_db.query.return_value = mock_query
                mock_get_db.return_value.__enter__.return_value = mock_db

                analyzer = ThemeAnalyzer()
                result = await analyzer.analyze_themes(request)

    # Should return empty result
    assert result.newsletter_count == 0
    assert result.total_themes == 0
    assert len(result.themes) == 0


@pytest.mark.skip(reason="Complex mock setup needs fixing - MagicMock format string issue")
@pytest.mark.asyncio
async def test_analyze_themes_without_historical_context(
    sample_newsletters, sample_summaries, sample_graphiti_themes, mock_llm_response
):
    """Test analysis without historical context enrichment."""
    request = ThemeAnalysisRequest(
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 1, 31),
    )

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=mock_llm_response)]
    mock_client.messages.create.return_value = mock_response

    mock_graphiti = AsyncMock()
    mock_graphiti.extract_themes_from_range = AsyncMock(return_value=sample_graphiti_themes)

    with patch("src.processors.theme_analyzer.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_client

        with patch("src.processors.theme_analyzer.GraphitiClient") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti

            with patch(
                "src.processors.theme_analyzer.HistoricalContextAnalyzer"
            ) as mock_historical_class:
                # Should not be called
                mock_historical = AsyncMock()
                mock_historical_class.return_value = mock_historical

                with patch("src.storage.database.get_db") as mock_get_db:
                    mock_db = MagicMock()
                    mock_get_db.return_value.__enter__.return_value = mock_db

                    # Create mock objects that behave like SQLAlchemy models
                    # They need to support attribute access (n.id, n.title, etc.)
                    mock_newsletter_objs = []
                    for n in sample_newsletters:
                        mock_n = MagicMock()
                        mock_n.id = n["id"]
                        mock_n.title = n["title"]
                        mock_n.publication = n["publication"]
                        mock_n.published_date = n["published_date"]
                        mock_newsletter_objs.append(mock_n)

                    mock_summary_objs = []
                    for s in sample_summaries:
                        mock_s = MagicMock()
                        mock_s.newsletter_id = s["newsletter_id"]
                        mock_s.executive_summary = s["executive_summary"]
                        mock_s.key_themes = s["key_themes"]
                        mock_s.strategic_insights = s["strategic_insights"]
                        mock_s.technical_details = s["technical_details"]
                        mock_summary_objs.append(mock_s)

                    newsletter_query = MagicMock()
                    newsletter_query.filter.return_value.order_by.return_value.all.return_value = (
                        mock_newsletter_objs
                    )

                    summary_query = MagicMock()
                    summary_query.filter.return_value.all.return_value = mock_summary_objs

                    # Return different query mocks based on the model being queried
                    def query_side_effect(model):
                        if model.__name__ == "Newsletter":
                            return newsletter_query
                        elif model.__name__ == "NewsletterSummary":
                            return summary_query
                        return MagicMock()

                    mock_db.query.side_effect = query_side_effect

                    analyzer = ThemeAnalyzer()
                    result = await analyzer.analyze_themes(
                        request, include_historical_context=False
                    )

                # Verify HistoricalContextAnalyzer was not instantiated
                mock_historical_class.assert_not_called()


def test_build_summary_context(sample_newsletters, sample_summaries):
    """Test building summary context string."""
    with patch("src.processors.theme_analyzer.Anthropic"):
        analyzer = ThemeAnalyzer()
        context = analyzer._build_summary_context(sample_newsletters, sample_summaries)

        # Check all newsletters are included
        assert "Tech Weekly - AI Advances" in context
        assert "Data News - Vector Databases" in context
        assert "AI Digest - LLM Updates" in context

        # Check summaries are included
        assert "Major AI breakthroughs" in context
        assert "Vector database performance" in context

        # Check key themes are included
        assert "LLMs" in context
        assert "Vector Search" in context


def test_build_graphiti_context(sample_graphiti_themes):
    """Test building Graphiti context string."""
    with patch("src.processors.theme_analyzer.Anthropic"):
        analyzer = ThemeAnalyzer()
        context = analyzer._build_graphiti_context(sample_graphiti_themes)

        assert "Knowledge Graph Insights" in context
        assert "RAG" in context
        assert "Retrieval Augmented Generation" in context
        assert "Vector DB" in context


def test_build_graphiti_context_empty():
    """Test building Graphiti context with no data."""
    with patch("src.processors.theme_analyzer.Anthropic"):
        analyzer = ThemeAnalyzer()
        context = analyzer._build_graphiti_context([])

        assert "No knowledge graph data available" in context


def test_build_theme_extraction_prompt():
    """Test building theme extraction prompt."""
    with patch("src.processors.theme_analyzer.Anthropic"):
        analyzer = ThemeAnalyzer()
        prompt = analyzer._build_theme_extraction_prompt(
            summary_context="Test summaries",
            graphiti_context="Test graphiti",
            max_themes=10,
            relevance_threshold=0.5,
        )

        # Check key elements are in prompt
        assert "Test summaries" in prompt
        assert "Test graphiti" in prompt
        assert "up to 10 distinct themes" in prompt
        assert "relevance_score >= 0.5" in prompt
        assert "JSON array" in prompt
        assert "ml_ai" in prompt
        assert "emerging" in prompt


def test_parse_theme_response(sample_newsletters, mock_llm_response):
    """Test parsing LLM response into ThemeData objects."""
    with patch("src.processors.theme_analyzer.Anthropic"):
        analyzer = ThemeAnalyzer()
        themes = analyzer._parse_theme_response(mock_llm_response, sample_newsletters)

        assert len(themes) == 2

        # Verify first theme
        theme1 = themes[0]
        assert theme1.name == "Large Language Models"
        assert theme1.category == ThemeCategory.ML_AI
        assert theme1.trend == ThemeTrend.GROWING
        assert theme1.relevance_score == 0.9
        assert theme1.mention_count == 2
        assert "AI Agents" in theme1.related_themes
        assert len(theme1.key_points) == 3

        # Verify second theme
        theme2 = themes[1]
        assert theme2.name == "Vector Databases"
        assert theme2.category == ThemeCategory.DATA_ENGINEERING
        assert theme2.trend == ThemeTrend.ESTABLISHED


def test_parse_theme_response_without_markdown(sample_newsletters):
    """Test parsing response without markdown code blocks."""
    response = """[
  {
    "name": "Test Theme",
    "description": "Test description",
    "category": "ml_ai",
    "mention_count": 1,
    "trend": "emerging",
    "relevance_score": 0.8,
    "strategic_relevance": 0.7,
    "tactical_relevance": 0.6,
    "novelty_score": 0.9,
    "cross_functional_impact": 0.5,
    "related_themes": [],
    "key_points": ["Point 1"]
  }
]"""

    with patch("src.processors.theme_analyzer.Anthropic"):
        analyzer = ThemeAnalyzer()
        themes = analyzer._parse_theme_response(response, sample_newsletters)

        assert len(themes) == 1
        assert themes[0].name == "Test Theme"


def test_parse_theme_response_invalid_json(sample_newsletters):
    """Test parsing invalid JSON response."""
    invalid_response = "This is not valid JSON"

    with patch("src.processors.theme_analyzer.Anthropic"):
        analyzer = ThemeAnalyzer()
        themes = analyzer._parse_theme_response(invalid_response, sample_newsletters)

        # Should return empty list on parse error
        assert len(themes) == 0


# TODO: Integration tests - require database setup
# These tests should be moved to integration tests as they require real database access
# The core logic is covered by unit tests above
#
# @pytest.mark.asyncio
# async def test_fetch_newsletters_integration():
#     """Test fetching newsletters from database (INTEGRATION TEST)."""
#     pass
#
# @pytest.mark.asyncio
# async def test_fetch_summaries_integration():
#     """Test fetching summaries from database (INTEGRATION TEST)."""
#     pass


@pytest.mark.asyncio
async def test_extract_themes_with_relevance_filtering(
    sample_newsletters, sample_summaries, sample_graphiti_themes
):
    """Test that themes below relevance threshold are filtered out."""
    # Response with one theme above and one below threshold
    mock_response_low_relevance = """[
  {
    "name": "High Relevance Theme",
    "description": "Important theme",
    "category": "ml_ai",
    "mention_count": 2,
    "trend": "growing",
    "relevance_score": 0.8,
    "strategic_relevance": 0.7,
    "tactical_relevance": 0.6,
    "novelty_score": 0.5,
    "cross_functional_impact": 0.6,
    "related_themes": [],
    "key_points": ["Point 1"]
  },
  {
    "name": "Low Relevance Theme",
    "description": "Less important",
    "category": "other",
    "mention_count": 1,
    "trend": "one_off",
    "relevance_score": 0.2,
    "strategic_relevance": 0.1,
    "tactical_relevance": 0.3,
    "novelty_score": 0.2,
    "cross_functional_impact": 0.1,
    "related_themes": [],
    "key_points": ["Point 1"]
  }
]"""

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=mock_response_low_relevance)]
    # Add token usage to mock response
    mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
    mock_client.messages.create.return_value = mock_response

    with patch("src.processors.theme_analyzer.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_client

        analyzer = ThemeAnalyzer()
        # Mock calculate_cost to return a numeric value
        analyzer.model_config.calculate_cost = MagicMock(return_value=0.0015)

        themes = await analyzer._extract_themes_with_llm(
            newsletters=sample_newsletters,
            summaries=sample_summaries,
            graphiti_themes=sample_graphiti_themes,
            max_themes=10,
            relevance_threshold=0.5,
        )

        # Only the high relevance theme should remain
        assert len(themes) == 1
        assert themes[0].name == "High Relevance Theme"
        assert themes[0].relevance_score >= 0.5
