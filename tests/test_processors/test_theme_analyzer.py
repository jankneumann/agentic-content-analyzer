"""Tests for ThemeAnalyzer."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.models import MODEL_REGISTRY, Provider, ProviderConfig
from src.models.theme import (
    ThemeAnalysisRequest,
    ThemeCategory,
    ThemeTrend,
)
from src.processors.theme_analyzer import ThemeAnalyzer
from src.services.llm_router import LLMResponse


@pytest.fixture
def sample_contents() -> list[dict]:
    """Create sample content items for testing."""
    return [
        {
            "id": 1,
            "title": "AI Advances",
            "publication": "Tech Weekly",
            "published_date": datetime(2025, 1, 15),
            "source_type": "rss",
        },
        {
            "id": 2,
            "title": "Vector Databases",
            "publication": "Data News",
            "published_date": datetime(2025, 1, 10),
            "source_type": "gmail",
        },
        {
            "id": 3,
            "title": "LLM Updates",
            "publication": "AI Digest",
            "published_date": datetime(2025, 1, 5),
            "source_type": "rss",
        },
    ]


@pytest.fixture
def sample_newsletters(sample_contents) -> list[dict]:
    """Alias for sample_contents (legacy tests)."""
    return sample_contents


@pytest.fixture
def sample_summaries() -> list[dict]:
    """Create sample summaries for testing."""
    return [
        {
            "content_id": 1,
            "executive_summary": "Major AI breakthroughs this week.",
            "key_themes": ["LLMs", "AI Agents"],
            "theme_tags": [],
            "strategic_insights": ["Cost reduction in LLMs", "Agent adoption growing"],
            "technical_details": ["New context windows", "Better embeddings"],
        },
        {
            "content_id": 2,
            "executive_summary": "Vector database performance improvements.",
            "key_themes": ["Vector Search", "Embeddings"],
            "theme_tags": [],
            "strategic_insights": ["Database selection critical"],
            "technical_details": ["Hybrid search techniques"],
        },
        {
            "content_id": 3,
            "executive_summary": "Latest LLM releases.",
            "key_themes": ["GPT", "Claude"],
            "theme_tags": [],
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
def mock_llm_response_text() -> str:
    """Create mock LLM response text for theme extraction."""
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
    with patch("src.processors.theme_analyzer.LLMRouter") as mock_router:
        analyzer = ThemeAnalyzer()

        # Model should be from registry and configured for theme_analysis step
        assert analyzer.model in MODEL_REGISTRY, f"Model {analyzer.model} not in registry"
        assert analyzer.model_config is not None
        assert analyzer.framework in ["claude", "gemini", "gpt"]
        assert not analyzer.use_large_context
        mock_router.assert_called_once()


def test_theme_analyzer_initialization_with_model_override():
    """Test ThemeAnalyzer with custom model."""
    with patch("src.processors.theme_analyzer.LLMRouter"):
        # Use any valid model from the registry
        available_models = list(MODEL_REGISTRY.keys())
        test_model = available_models[0]  # Use first model from registry

        analyzer = ThemeAnalyzer(model_override=test_model)

        assert analyzer.model == test_model
        assert analyzer.model in MODEL_REGISTRY


def test_theme_analyzer_large_context_warning():
    """Test warning when large context mode requested."""
    with patch("src.processors.theme_analyzer.LLMRouter"):
        with patch("src.processors.theme_analyzer.logger") as mock_logger:
            analyzer = ThemeAnalyzer(use_large_context=True)

            # Should log warning about Gemini not implemented
            mock_logger.warning.assert_called_once()
            assert "Large context analysis requested" in mock_logger.warning.call_args[0][0]


@pytest.mark.asyncio
async def test_analyze_themes_insufficient_newsletters():
    """Test analysis with insufficient newsletters."""
    request = ThemeAnalysisRequest(
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 1, 31),
        min_newsletters=5,
    )

    with patch("src.processors.theme_analyzer.LLMRouter"):
        with patch("src.processors.theme_analyzer.GraphitiClient") as mock_graphiti:
            mock_graphiti.return_value.close = MagicMock()

            with patch("src.processors.theme_analyzer.get_db") as mock_get_db:
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
    assert result.model_used == analyzer.model


def test_build_summary_context(sample_newsletters, sample_summaries):
    """Test building summary context string."""
    with patch("src.processors.theme_analyzer.LLMRouter"):
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
    with patch("src.processors.theme_analyzer.LLMRouter"):
        analyzer = ThemeAnalyzer()
        context = analyzer._build_graphiti_context(sample_graphiti_themes)

        assert "Knowledge Graph Insights" in context
        assert "RAG" in context
        assert "Retrieval Augmented Generation" in context
        assert "Vector DB" in context


def test_build_theme_extraction_prompt():
    """Test building theme extraction prompt."""
    with patch("src.processors.theme_analyzer.LLMRouter"):
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


def test_parse_theme_response(sample_newsletters, mock_llm_response_text):
    """Test parsing LLM response into ThemeData objects."""
    with patch("src.processors.theme_analyzer.LLMRouter"):
        analyzer = ThemeAnalyzer()
        themes = analyzer._parse_theme_response(mock_llm_response_text, sample_newsletters)

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


@pytest.mark.asyncio
async def test_extract_themes_with_relevance_filtering(
    sample_contents, sample_summaries, sample_graphiti_themes
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

    with patch("src.processors.theme_analyzer.LLMRouter") as MockRouter:
        mock_router_instance = MockRouter.return_value
        # Use AsyncMock for generate
        mock_router_instance.generate = AsyncMock(return_value=LLMResponse(
            text=mock_response_low_relevance,
            input_tokens=100,
            output_tokens=50,
            provider=Provider.ANTHROPIC,
            model_version="test-version"
        ))

        analyzer = ThemeAnalyzer()

        # Mock providers
        analyzer.model_config.get_providers_for_model = MagicMock(
            return_value=[ProviderConfig(provider=Provider.ANTHROPIC, api_key="test-key")]
        )
        analyzer.model_config.calculate_cost = MagicMock(return_value=0.0015)

        themes = await analyzer._extract_themes_with_llm(
            contents=sample_contents,
            summaries=sample_summaries,
            graphiti_themes=sample_graphiti_themes,
            max_themes=10,
            relevance_threshold=0.5,
        )

        # Only the high relevance theme should remain
        assert len(themes) == 1
        assert themes[0].name == "High Relevance Theme"
        assert themes[0].relevance_score >= 0.5


@pytest.mark.asyncio
async def test_extract_themes_providers_failover(
    sample_contents, sample_summaries, sample_graphiti_themes
):
    """Test that multiple providers are attempted in failover loop."""

    with patch("src.processors.theme_analyzer.LLMRouter") as MockRouter:
        mock_router_instance = MockRouter.return_value

        # First call fails, second succeeds. Use side_effect with AsyncMock.
        mock_router_instance.generate = AsyncMock(side_effect=[
            Exception("Bedrock Error"),
            LLMResponse(
                text="[]", # Empty JSON for simplicity
                input_tokens=100,
                output_tokens=50,
                provider=Provider.GOOGLE_VERTEX,
                model_version="test-version"
            )
        ])

        analyzer = ThemeAnalyzer()

        # Configure multiple providers including new ones
        providers = [
            ProviderConfig(provider=Provider.AWS_BEDROCK, api_key=""),
            ProviderConfig(provider=Provider.GOOGLE_VERTEX, api_key="")
        ]
        analyzer.model_config.get_providers_for_model = MagicMock(return_value=providers)
        analyzer.model_config.calculate_cost = MagicMock(return_value=0.0015)

        await analyzer._extract_themes_with_llm(
            contents=sample_contents,
            summaries=sample_summaries,
            graphiti_themes=sample_graphiti_themes,
            max_themes=10,
            relevance_threshold=0.5,
        )

        # Verify generate called twice with correct providers
        assert mock_router_instance.generate.call_count == 2

        # Check providers used
        calls = mock_router_instance.generate.call_args_list
        assert calls[0].kwargs['provider'] == Provider.AWS_BEDROCK
        assert calls[1].kwargs['provider'] == Provider.GOOGLE_VERTEX
