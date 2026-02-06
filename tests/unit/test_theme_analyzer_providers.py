"""Tests for theme analyzer multi-provider support."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.config.models import (
    ModelConfig,
    ModelFamily,
    Provider,
    ProviderConfig,
)
from src.models.theme import ThemeTrend
from src.processors.theme_analyzer import ThemeAnalyzer
from src.services.llm_router import LLMResponse


@pytest.fixture
def mock_model_config():
    config = MagicMock(spec=ModelConfig)
    config.get_model_for_step.return_value = "test-model"
    config.get_family.return_value = ModelFamily.CLAUDE
    config.calculate_cost.return_value = 0.01
    return config


@pytest.fixture
def theme_analyzer(mock_model_config):
    # Mock get_model_config to return our mock config
    with patch("src.processors.theme_analyzer.get_model_config", return_value=mock_model_config):
        analyzer = ThemeAnalyzer(model_config=mock_model_config)
        return analyzer


@pytest.fixture
def mock_newsletters_and_summaries():
    newsletters = [
        {
            "id": 1,
            "title": "Test Newsletter",
            "publication": "Test Pub",
            "published_date": datetime.now(),
        }
    ]
    summaries = [
        {
            "newsletter_id": 1,
            "executive_summary": "Summary",
            "key_themes": ["Theme 1"],
            "strategic_insights": ["Insight 1"],
            "technical_details": ["Detail 1"],
        }
    ]
    return newsletters, summaries


@pytest.fixture
def mock_llm_response():
    """Create a mock LLMResponse with theme extraction results."""
    return LLMResponse(
        text="""
        [
            {
                "name": "Test Theme",
                "description": "Test Description",
                "category": "ml_ai",
                "trend": "emerging",
                "relevance_score": 0.9,
                "strategic_relevance": 0.8,
                "tactical_relevance": 0.7,
                "novelty_score": 0.6,
                "cross_functional_impact": 0.5
            }
        ]
        """,
        provider=Provider.OPENAI,
        model_version="test-model",
        input_tokens=100,
        output_tokens=50,
    )


@pytest.mark.asyncio
async def test_extract_themes_openai(
    theme_analyzer, mock_model_config, mock_newsletters_and_summaries, mock_llm_response
):
    newsletters, summaries = mock_newsletters_and_summaries

    # Configure mock for OpenAI provider
    mock_model_config.get_providers_for_model.return_value = [
        ProviderConfig(provider=Provider.OPENAI, api_key="test-key")
    ]
    mock_model_config.get_provider_model_id.return_value = "gpt-4-test"

    # Mock LLMRouter.generate
    mock_llm_response.provider = Provider.OPENAI
    with patch.object(theme_analyzer.llm_router, "generate", return_value=mock_llm_response):
        themes = await theme_analyzer._extract_themes_with_llm(newsletters, summaries, [], 10, 0.5)

    # Verify theme extraction
    assert len(themes) == 1
    assert themes[0].name == "Test Theme"
    assert themes[0].trend == ThemeTrend.EMERGING
    assert theme_analyzer.provider_used == Provider.OPENAI


@pytest.mark.asyncio
async def test_extract_themes_anthropic(
    theme_analyzer, mock_model_config, mock_newsletters_and_summaries, mock_llm_response
):
    newsletters, summaries = mock_newsletters_and_summaries

    # Configure mock for Anthropic provider
    mock_model_config.get_providers_for_model.return_value = [
        ProviderConfig(provider=Provider.ANTHROPIC, api_key="test-key")
    ]
    mock_model_config.get_provider_model_id.return_value = "claude-test"

    # Mock LLMRouter.generate
    mock_llm_response.provider = Provider.ANTHROPIC
    with patch.object(theme_analyzer.llm_router, "generate", return_value=mock_llm_response):
        themes = await theme_analyzer._extract_themes_with_llm(newsletters, summaries, [], 10, 0.5)

    # Verify theme extraction
    assert len(themes) == 1
    assert themes[0].name == "Test Theme"
    assert theme_analyzer.provider_used == Provider.ANTHROPIC


@pytest.mark.asyncio
async def test_extract_themes_fallback(
    theme_analyzer, mock_model_config, mock_newsletters_and_summaries, mock_llm_response
):
    """Test fallback from Anthropic (failed) to OpenAI (success)."""
    newsletters, summaries = mock_newsletters_and_summaries

    # Configure mock to return both providers
    mock_model_config.get_providers_for_model.return_value = [
        ProviderConfig(provider=Provider.ANTHROPIC, api_key="anthropic-key"),
        ProviderConfig(provider=Provider.OPENAI, api_key="openai-key"),
    ]
    mock_model_config.get_provider_model_id.side_effect = lambda m, p: f"{p}-model"

    # Mock LLMRouter.generate to fail on first call (Anthropic) and succeed on second (OpenAI)
    call_count = 0

    async def mock_generate(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call (Anthropic) fails
            raise Exception("API Error")
        # Second call (OpenAI) succeeds
        mock_llm_response.provider = Provider.OPENAI
        mock_llm_response.text = "[]"  # Empty themes for simplicity
        return mock_llm_response

    with patch.object(theme_analyzer.llm_router, "generate", side_effect=mock_generate):
        themes = await theme_analyzer._extract_themes_with_llm(newsletters, summaries, [], 10, 0.5)

    # Verify fallback occurred
    assert call_count == 2
    assert theme_analyzer.provider_used == Provider.OPENAI
