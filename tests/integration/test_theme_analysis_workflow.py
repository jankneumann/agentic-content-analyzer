"""Integration tests for theme analysis workflow.

Tests the end-to-end flow:
1. Newsletters and summaries exist in database
2. Theme analyzer processes data
3. Themes are extracted and analyzed
4. Results include historical context (if enabled)
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.theme import ThemeAnalysisRequest
from src.processors.theme_analyzer import ThemeAnalyzer


@pytest.fixture
def mock_theme_llm_response():
    """Mock LLM response for theme extraction."""
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_analyze_themes_success(
    db_session,
    sample_newsletters,
    sample_summaries,
    mock_graphiti_client,
    mock_theme_llm_response,
    mock_get_db,
):
    """Test successful theme analysis workflow."""
    # Create request for the date range covering our sample data
    request = ThemeAnalysisRequest(
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 1, 31),
        min_newsletters=1,
        max_themes=10,
        relevance_threshold=0.5,
    )

    # Mock Anthropic client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=mock_theme_llm_response)]
    mock_client.messages.create.return_value = mock_response

    # Run theme analysis
    with patch("src.processors.theme_analyzer.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_client

        with patch("src.processors.theme_analyzer.GraphitiClient") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti_client

            with patch("src.processors.theme_analyzer.get_db", mock_get_db):
                analyzer = ThemeAnalyzer()
                result = await analyzer.analyze_themes(
                    request, include_historical_context=False
                )

    # Verify results
    assert result is not None
    assert result.newsletter_count == 3
    assert result.total_themes == 2

    # Verify themes
    themes = result.themes
    assert len(themes) == 2

    # Check first theme
    theme1 = themes[0]
    assert theme1.name == "Large Language Models"
    assert theme1.category.value == "ml_ai"
    assert theme1.trend.value == "growing"
    assert theme1.relevance_score == 0.9
    assert "AI Agents" in theme1.related_themes
    assert len(theme1.key_points) == 3

    # Check second theme
    theme2 = themes[1]
    assert theme2.name == "Vector Databases"
    assert theme2.category.value == "data_engineering"
    assert theme2.trend.value == "established"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_analyze_themes_with_historical_context(
    db_session,
    sample_newsletters,
    sample_summaries,
    mock_graphiti_client,
    mock_theme_llm_response,
    mock_get_db,
):
    """Test theme analysis with historical context enrichment."""
    request = ThemeAnalysisRequest(
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 1, 31),
    )

    # Mock Anthropic client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=mock_theme_llm_response)]
    mock_client.messages.create.return_value = mock_response

    # Mock HistoricalContextAnalyzer
    mock_historical = AsyncMock()
    mock_historical.enrich_themes_with_history = AsyncMock(
        side_effect=lambda themes, **kwargs: themes  # Return themes unchanged
    )

    with patch("src.processors.theme_analyzer.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_client

        with patch("src.processors.theme_analyzer.GraphitiClient") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti_client

            with patch(
                "src.processors.theme_analyzer.HistoricalContextAnalyzer"
            ) as mock_historical_class:
                mock_historical_class.return_value = mock_historical

                with patch("src.processors.theme_analyzer.get_db", mock_get_db):

                    analyzer = ThemeAnalyzer()
                    result = await analyzer.analyze_themes(
                        request, include_historical_context=True
                    )

    # Verify historical context analyzer was called
    mock_historical.enrich_themes_with_history.assert_called_once()

    # Verify results
    assert result is not None
    assert result.newsletter_count == 3
    assert result.total_themes == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_analyze_themes_insufficient_newsletters(
    db_session,
    sample_newsletters,
    sample_summaries,
    mock_graphiti_client,
    mock_get_db,
):
    """Test theme analysis with insufficient newsletters."""
    # Request minimum 10 newsletters, but only 3 exist
    request = ThemeAnalysisRequest(
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 1, 31),
        min_newsletters=10,
    )

    with patch("src.processors.theme_analyzer.Anthropic"):
        with patch("src.processors.theme_analyzer.GraphitiClient") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti_client

            with patch("src.processors.theme_analyzer.get_db", mock_get_db):

                analyzer = ThemeAnalyzer()
                result = await analyzer.analyze_themes(request)

    # Should return empty result
    assert result.newsletter_count == 0
    assert result.total_themes == 0
    assert len(result.themes) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_analyze_themes_relevance_filtering(
    db_session,
    sample_newsletters,
    sample_summaries,
    mock_graphiti_client,
    mock_get_db,
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
    mock_client.messages.create.return_value = mock_response

    # Request with 0.5 threshold
    request = ThemeAnalysisRequest(
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 1, 31),
        relevance_threshold=0.5,
    )

    with patch("src.processors.theme_analyzer.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_client

        with patch("src.processors.theme_analyzer.GraphitiClient") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti_client

            with patch("src.processors.theme_analyzer.get_db", mock_get_db):

                analyzer = ThemeAnalyzer()
                result = await analyzer.analyze_themes(request)

    # Only high relevance theme should be included
    assert result.total_themes == 1
    assert result.themes[0].name == "High Relevance Theme"
    assert result.themes[0].relevance_score >= 0.5


@pytest.mark.integration
@pytest.mark.asyncio
async def test_analyze_themes_no_summaries(
    db_session, sample_newsletters, mock_graphiti_client, mock_get_db
):
    """Test theme analysis when newsletters exist but no summaries."""
    request = ThemeAnalysisRequest(
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 1, 31),
    )

    # Note: sample_summaries fixture not included, so no summaries exist

    with patch("src.processors.theme_analyzer.Anthropic"):
        with patch("src.processors.theme_analyzer.GraphitiClient") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti_client

            with patch("src.processors.theme_analyzer.get_db", mock_get_db):

                analyzer = ThemeAnalyzer()
                result = await analyzer.analyze_themes(request)

    # Should find newsletters but generate no themes (no summaries to analyze)
    assert result.newsletter_count == 3  # Newsletters exist
    assert result.total_themes == 0  # But no summaries, so no themes generated
