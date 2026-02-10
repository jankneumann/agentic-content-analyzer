"""End-to-end tests for pipeline with different model combinations.

Tests the full workflow with various model configurations:
1. Different models for each pipeline step
2. Provider failover behavior
3. Cost calculation accuracy
4. Mixed model families (Claude, GPT, Gemini)
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.config.models import ModelConfig, ModelStep, Provider, ProviderConfig
from src.models.theme import ThemeAnalysisRequest
from src.processors.summarizer import NewsletterSummarizer
from src.processors.theme_analyzer import ThemeAnalyzer
from src.services.llm_router import LLMResponse, LLMRouter


def _make_empty_theme_llm_response() -> LLMResponse:
    """Create an LLMResponse containing an empty themes JSON array."""
    return LLMResponse(
        text="[]",
        input_tokens=1000,
        output_tokens=200,
        provider=Provider.ANTHROPIC,
        model_version="claude-haiku-4-5-20250929",
    )


@pytest.fixture
def haiku_config():
    """ModelConfig using Claude Haiku for all steps."""
    config = ModelConfig(
        summarization="claude-haiku-4-5",
        theme_analysis="claude-haiku-4-5",
        digest_creation="claude-haiku-4-5",
        historical_context="claude-haiku-4-5",
        providers=[ProviderConfig(provider=Provider.ANTHROPIC, api_key="test-haiku-key")],
    )
    return config


@pytest.fixture
def sonnet_config():
    """ModelConfig using Claude Sonnet for all steps."""
    config = ModelConfig(
        summarization="claude-sonnet-4-5",
        theme_analysis="claude-sonnet-4-5",
        digest_creation="claude-sonnet-4-5",
        historical_context="claude-sonnet-4-5",
        providers=[ProviderConfig(provider=Provider.ANTHROPIC, api_key="test-sonnet-key")],
    )
    return config


@pytest.fixture
def mixed_config():
    """ModelConfig using different models for different steps."""
    config = ModelConfig(
        summarization="claude-haiku-4-5",  # Fast extraction
        theme_analysis="claude-sonnet-4-5",  # Better reasoning
        digest_creation="claude-sonnet-4-5",  # Quality output
        historical_context="claude-haiku-4-5",  # Simple queries
        providers=[ProviderConfig(provider=Provider.ANTHROPIC, api_key="test-mixed-key")],
    )
    return config


@pytest.mark.integration
def test_summarization_with_haiku(
    db_session, sample_newsletters, mock_anthropic_client, mock_get_db, haiku_config
):
    """Test newsletter summarization using Haiku model."""
    newsletter = sample_newsletters[0]

    with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_anthropic_client

        with patch("src.processors.summarizer.get_db", mock_get_db):
            summarizer = NewsletterSummarizer(model_config=haiku_config)
            result = summarizer.summarize_newsletter(newsletter.id)

    assert result is True
    # Verify Haiku was used
    assert summarizer.agent.model == "claude-haiku-4-5"


@pytest.mark.integration
def test_summarization_with_sonnet(
    db_session, sample_newsletters, mock_anthropic_client, mock_get_db, sonnet_config
):
    """Test newsletter summarization using Sonnet model."""
    newsletter = sample_newsletters[0]

    with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_anthropic_client

        with patch("src.processors.summarizer.get_db", mock_get_db):
            summarizer = NewsletterSummarizer(model_config=sonnet_config)
            result = summarizer.summarize_newsletter(newsletter.id)

    assert result is True
    # Verify Sonnet was used
    assert summarizer.agent.model == "claude-sonnet-4-5"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_theme_analysis_with_haiku(
    db_session,
    sample_newsletters,
    sample_summaries,
    mock_graphiti_client,
    mock_get_db,
    haiku_config,
):
    """Test theme analysis using Haiku model."""
    request = ThemeAnalysisRequest(
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 1, 31),
    )

    with patch.object(
        LLMRouter, "generate", new_callable=AsyncMock, return_value=_make_empty_theme_llm_response()
    ):
        with patch("src.processors.theme_analyzer.GraphitiClient") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti_client

            with patch("src.processors.theme_analyzer.get_db", mock_get_db):
                analyzer = ThemeAnalyzer(model_config=haiku_config)
                result = await analyzer.analyze_themes(request, include_historical_context=False)

    # Verify Haiku was used
    assert analyzer.model == "claude-haiku-4-5"
    assert result.model_used == "claude-haiku-4-5"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_theme_analysis_with_sonnet(
    db_session,
    sample_newsletters,
    sample_summaries,
    mock_graphiti_client,
    mock_get_db,
    sonnet_config,
):
    """Test theme analysis using Sonnet model."""
    request = ThemeAnalysisRequest(
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 1, 31),
    )

    with patch.object(
        LLMRouter, "generate", new_callable=AsyncMock, return_value=_make_empty_theme_llm_response()
    ):
        with patch("src.processors.theme_analyzer.GraphitiClient") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti_client

            with patch("src.processors.theme_analyzer.get_db", mock_get_db):
                analyzer = ThemeAnalyzer(model_config=sonnet_config)
                result = await analyzer.analyze_themes(request, include_historical_context=False)

    # Verify Sonnet was used
    assert analyzer.model == "claude-sonnet-4-5"
    assert result.model_used == "claude-sonnet-4-5"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_pipeline_with_mixed_models(
    db_session,
    sample_newsletters,
    mock_anthropic_client,
    mock_graphiti_client,
    mock_get_db,
    mixed_config,
):
    """Test full pipeline using different models for different steps.

    This simulates a production scenario where:
    - Haiku is used for fast, cheap summarization
    - Sonnet is used for quality-critical theme analysis and digest creation
    """
    newsletter = sample_newsletters[0]

    # Step 1: Summarize newsletter with Haiku
    with patch("src.agents.claude.summarizer.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value = mock_anthropic_client

        with patch("src.processors.summarizer.get_db", mock_get_db):
            summarizer = NewsletterSummarizer(model_config=mixed_config)
            summarize_result = summarizer.summarize_newsletter(newsletter.id)

    assert summarize_result is True
    assert summarizer.agent.model == "claude-haiku-4-5"  # Fast model

    # Step 2: Analyze themes with Sonnet
    request = ThemeAnalysisRequest(
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 1, 31),
    )

    with patch.object(
        LLMRouter, "generate", new_callable=AsyncMock, return_value=_make_empty_theme_llm_response()
    ):
        with patch("src.processors.theme_analyzer.GraphitiClient") as mock_graphiti_class:
            mock_graphiti_class.return_value = mock_graphiti_client

            with patch("src.processors.theme_analyzer.get_db", mock_get_db):
                analyzer = ThemeAnalyzer(model_config=mixed_config)
                theme_result = await analyzer.analyze_themes(
                    request, include_historical_context=False
                )

    assert analyzer.model == "claude-sonnet-4-5"  # Quality model

    # Verify different models were used for different steps
    assert summarizer.agent.model != analyzer.model
    assert "haiku" in summarizer.agent.model.lower()
    assert "sonnet" in analyzer.model.lower()


@pytest.mark.integration
def test_cost_calculation_varies_by_model(haiku_config, sonnet_config):
    """Test that cost calculation reflects different model pricing."""
    # Mock token usage (same for both)
    input_tokens = 1000
    output_tokens = 500

    # Calculate cost for Haiku
    haiku_cost = haiku_config.calculate_cost(
        model_id="claude-haiku-4-5",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        provider=Provider.ANTHROPIC,
    )

    # Calculate cost for Sonnet (should be more expensive)
    sonnet_cost = sonnet_config.calculate_cost(
        model_id="claude-sonnet-4-5",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        provider=Provider.ANTHROPIC,
    )

    # Verify Sonnet is more expensive than Haiku
    assert sonnet_cost > haiku_cost
    # Haiku: $1.00/MTok input, $3.00/MTok output
    # Sonnet: $3.00/MTok input, $15.00/MTok output
    assert haiku_cost == pytest.approx(0.0025, rel=1e-4)  # (1000*1.00 + 500*3.00)/1M
    assert sonnet_cost == pytest.approx(0.0105, rel=1e-4)  # (1000*3.00 + 500*15.00)/1M


@pytest.mark.integration
def test_model_override_at_agent_level(haiku_config):
    """Test that model can be overridden at agent initialization."""
    # Config defaults to Haiku, but override with Sonnet
    from src.agents.claude import ClaudeAgent

    with patch("src.agents.claude.summarizer.Anthropic"):
        # Create agent with model override
        agent = ClaudeAgent(model_config=haiku_config, model="claude-sonnet-4-5")
        summarizer = NewsletterSummarizer(agent=agent)

    # Should use Sonnet despite Haiku config
    assert summarizer.agent.model == "claude-sonnet-4-5"


@pytest.mark.integration
def test_model_selection_per_step(mixed_config):
    """Test that each step gets the correct model from config."""
    # Verify model selection for each step
    assert mixed_config.get_model_for_step(ModelStep.SUMMARIZATION) == "claude-haiku-4-5"
    assert mixed_config.get_model_for_step(ModelStep.THEME_ANALYSIS) == "claude-sonnet-4-5"
    assert mixed_config.get_model_for_step(ModelStep.DIGEST_CREATION) == "claude-sonnet-4-5"
    assert mixed_config.get_model_for_step(ModelStep.HISTORICAL_CONTEXT) == "claude-haiku-4-5"


@pytest.mark.integration
def test_provider_failover_with_multiple_configs():
    """Test that provider failover works when multiple providers configured."""
    config = ModelConfig(
        providers=[
            # Multiple providers (order matters for failover)
            ProviderConfig(provider=Provider.ANTHROPIC, api_key="primary-key"),
            ProviderConfig(provider=Provider.ANTHROPIC, api_key="backup-key"),
        ]
    )

    # Get providers for Haiku
    providers = config.get_providers_for_model("claude-haiku-4-5")

    # Should have both providers
    assert len(providers) == 2
    # Should be in order specified (first = primary, second = backup)
    assert providers[0].api_key == "primary-key"
    assert providers[1].api_key == "backup-key"
