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


@pytest.mark.asyncio
async def test_extract_themes_openai(
    theme_analyzer, mock_model_config, mock_newsletters_and_summaries
):
    newsletters, summaries = mock_newsletters_and_summaries

    # Configure mock for OpenAI provider
    mock_model_config.get_providers_for_model.return_value = [
        ProviderConfig(provider=Provider.OPENAI, api_key="test-key")
    ]
    mock_model_config.get_provider_model_id.return_value = "gpt-4-test"

    # Mock OpenAI client
    with patch("src.processors.theme_analyzer.OpenAI") as MockOpenAI:
        mock_client = MockOpenAI.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """
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
        """
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_client.chat.completions.create.return_value = mock_response

        # Run extraction
        themes = await theme_analyzer._extract_themes_with_llm(newsletters, summaries, [], 10, 0.5)

        # Verify OpenAI client was used
        MockOpenAI.assert_called_once_with(api_key="test-key")
        mock_client.chat.completions.create.assert_called_once()

        # Verify theme extraction
        assert len(themes) == 1
        assert themes[0].name == "Test Theme"
        assert themes[0].trend == ThemeTrend.EMERGING
        assert theme_analyzer.provider_used == Provider.OPENAI


@pytest.mark.asyncio
async def test_extract_themes_anthropic(
    theme_analyzer, mock_model_config, mock_newsletters_and_summaries
):
    newsletters, summaries = mock_newsletters_and_summaries

    # Configure mock for Anthropic provider
    mock_model_config.get_providers_for_model.return_value = [
        ProviderConfig(provider=Provider.ANTHROPIC, api_key="test-key")
    ]
    mock_model_config.get_provider_model_id.return_value = "claude-test"

    # Mock Anthropic client
    with patch("src.processors.theme_analyzer.Anthropic") as MockAnthropic:
        mock_client = MockAnthropic.return_value
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = """
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
        """
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response

        # Run extraction
        themes = await theme_analyzer._extract_themes_with_llm(newsletters, summaries, [], 10, 0.5)

        # Verify Anthropic client was used
        MockAnthropic.assert_called_once_with(api_key="test-key")
        mock_client.messages.create.assert_called_once()

        # Verify theme extraction
        assert len(themes) == 1
        assert themes[0].name == "Test Theme"
        assert theme_analyzer.provider_used == Provider.ANTHROPIC


@pytest.mark.asyncio
async def test_extract_themes_fallback(
    theme_analyzer, mock_model_config, mock_newsletters_and_summaries
):
    """Test fallback from Anthropic (failed) to OpenAI (success)."""
    newsletters, summaries = mock_newsletters_and_summaries

    # Configure mock to return both providers
    mock_model_config.get_providers_for_model.return_value = [
        ProviderConfig(provider=Provider.ANTHROPIC, api_key="anthropic-key"),
        ProviderConfig(provider=Provider.OPENAI, api_key="openai-key"),
    ]
    mock_model_config.get_provider_model_id.side_effect = lambda m, p: f"{p}-model"

    with (
        patch("src.processors.theme_analyzer.Anthropic") as MockAnthropic,
        patch("src.processors.theme_analyzer.OpenAI") as MockOpenAI,
    ):
        # Anthropic fails
        anthropic_client = MockAnthropic.return_value
        anthropic_client.messages.create.side_effect = Exception("API Error")

        # OpenAI succeeds
        openai_client = MockOpenAI.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "[]"  # Empty themes for simplicity
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        openai_client.chat.completions.create.return_value = mock_response

        # Run extraction
        themes = await theme_analyzer._extract_themes_with_llm(newsletters, summaries, [], 10, 0.5)

        # Verify Anthropic was called and failed
        MockAnthropic.assert_called_once()
        anthropic_client.messages.create.assert_called_once()

        # Verify OpenAI was called and succeeded
        MockOpenAI.assert_called_once()
        openai_client.chat.completions.create.assert_called_once()

        assert theme_analyzer.provider_used == Provider.OPENAI
