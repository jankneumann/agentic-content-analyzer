"""Integration tests for ClaudeAgent.

These tests simulate real API interactions using mocks to verify
the agent handles API responses, errors, and various scenarios correctly.
"""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.agents.claude.summarizer import ClaudeAgent
from src.config.models import MODEL_REGISTRY, ModelConfig, Provider, ProviderConfig
from src.models.newsletter import Newsletter, NewsletterSource, ProcessingStatus
from src.models.summary import SummaryData


@pytest.fixture
def test_model_config() -> ModelConfig:
    """Create test ModelConfig with Anthropic provider."""
    config = ModelConfig()
    config.add_provider(
        ProviderConfig(
            provider=Provider.ANTHROPIC,
            api_key="test-api-key-123",
        )
    )
    return config


@pytest.fixture
def sample_newsletter() -> Newsletter:
    """Create sample newsletter for testing."""
    newsletter = Newsletter(
        source=NewsletterSource.GMAIL,
        source_id="test-123",
        sender="test@example.com",
        publication="Tech Weekly",
        title="AI Advances in 2025",
        raw_html="<html><body>Newsletter about AI advances</body></html>",
        raw_text="Newsletter content about AI advances and new LLM developments.",
        published_date=datetime(2025, 1, 15, 10, 0, 0),
        url="https://example.com/newsletter",
        status=ProcessingStatus.PENDING,
    )
    newsletter.id = 1
    return newsletter


@pytest.fixture
def mock_anthropic_response():
    """Create a mock Anthropic API response."""
    mock_response = MagicMock()
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 500

    mock_content = MagicMock()
    mock_content.text = json.dumps(
        {
            "executive_summary": "Major AI advancements this week including new LLM releases.",
            "key_themes": ["LLM Performance", "Cost Reduction", "Multimodal AI"],
            "strategic_insights": [
                "LLM costs decreasing by 40% enables broader adoption",
                "Multimodal capabilities becoming table stakes",
            ],
            "technical_details": [
                "Context windows expanded to 1M tokens",
                "New embedding models with better accuracy",
            ],
            "actionable_items": [
                "Evaluate new LLM pricing for cost optimization",
                "Test multimodal features for product applications",
            ],
            "notable_quotes": [
                "Context is king in the new AI landscape",
                "Cost reduction unlocks enterprise use cases",
            ],
            "relevance_scores": {
                "cto_leadership": 0.9,
                "technical_teams": 0.85,
                "individual_developers": 0.7,
            },
        }
    )
    mock_response.content = [mock_content]
    return mock_response


@patch("src.agents.claude.summarizer.Anthropic")
def test_summarize_newsletter_success(
    mock_anthropic, test_model_config, sample_newsletter, mock_anthropic_response
):
    """Test successful newsletter summarization with mocked LLM."""
    # Setup mock
    mock_client = mock_anthropic.return_value
    mock_client.messages.create.return_value = mock_anthropic_response

    agent = ClaudeAgent(model_config=test_model_config)
    response = agent.summarize_newsletter(sample_newsletter)

    assert response.success
    assert isinstance(response.data, SummaryData)
    assert (
        response.data.executive_summary
        == "Major AI advancements this week including new LLM releases."
    )
    assert response.data.token_usage == 600  # 100 + 500
    assert response.metadata["provider"] == Provider.ANTHROPIC.value

    # Verify API was called correctly
    mock_client.messages.create.assert_called_once()
    call_args = mock_client.messages.create.call_args
    assert call_args.kwargs["max_tokens"] == 4096
    assert call_args.kwargs["temperature"] == 0.0


@patch("src.agents.claude.summarizer.Anthropic")
def test_summarize_newsletter_json_parse_error(
    mock_anthropic, test_model_config, sample_newsletter
):
    """Test handling of malformed LLM response (not valid JSON)."""
    # Setup mock to return invalid JSON
    mock_response = MagicMock()
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    mock_content = MagicMock()
    mock_content.text = "This is not valid JSON."
    mock_response.content = [mock_content]

    mock_client = mock_anthropic.return_value
    mock_client.messages.create.return_value = mock_response

    agent = ClaudeAgent(model_config=test_model_config)
    response = agent.summarize_newsletter(sample_newsletter)

    assert not response.success
    assert "Failed to parse response as JSON" in response.error


@patch("src.agents.claude.summarizer.Anthropic")
def test_summarize_newsletter_api_error(mock_anthropic, test_model_config, sample_newsletter):
    """Test handling of API errors."""
    # Setup mock to raise an exception
    mock_client = mock_anthropic.return_value
    mock_client.messages.create.side_effect = Exception("API Connection Error")

    agent = ClaudeAgent(model_config=test_model_config)
    response = agent.summarize_newsletter(sample_newsletter)

    assert not response.success
    assert "All providers failed" in response.error
    assert "API Connection Error" in response.error


@patch("src.agents.claude.summarizer.Anthropic")
def test_summarize_newsletter_with_specific_model(
    mock_anthropic, test_model_config, sample_newsletter, mock_anthropic_response
):
    """Test summarization with a specific model from registry."""
    # Use any valid Claude model from the registry
    claude_models = [m for m in MODEL_REGISTRY.keys() if "claude" in m]
    if not claude_models:
        pytest.skip("No Claude models found in registry")

    test_model = claude_models[0]

    mock_client = mock_anthropic.return_value
    mock_client.messages.create.return_value = mock_anthropic_response

    agent = ClaudeAgent(model_config=test_model_config, model=test_model)
    response = agent.summarize_newsletter(sample_newsletter)

    assert response.success
    assert response.data.model_used == test_model

    # Verify the correct provider model ID was used
    # This depends on what the config resolves to
    provider_model_id = test_model_config.get_provider_model_id(test_model, Provider.ANTHROPIC)

    call_args = mock_client.messages.create.call_args
    assert call_args.kwargs["model"] == provider_model_id


@patch("src.agents.claude.summarizer.Anthropic")
def test_summarize_newsletter_retry_mechanism(
    mock_anthropic, test_model_config, sample_newsletter, mock_anthropic_response
):
    """Test that the agent doesn't retry on the same provider if it fails (unless configured otherwise)."""
    # Currently implementation tries each provider once.
    # We only have one provider configured in test_model_config.

    mock_client = mock_anthropic.return_value
    # First call fails, second call (if there were one) succeeds
    # But with one provider, it should just fail
    mock_client.messages.create.side_effect = Exception("First failure")

    agent = ClaudeAgent(model_config=test_model_config)
    response = agent.summarize_newsletter(sample_newsletter)

    assert not response.success
    assert mock_client.messages.create.call_count == 1


@patch("src.agents.claude.summarizer.Anthropic")
def test_summarize_newsletter_with_feedback(
    mock_anthropic, test_model_config, sample_newsletter, mock_anthropic_response
):
    """Test summarization with feedback."""
    mock_client = mock_anthropic.return_value
    mock_client.messages.create.return_value = mock_anthropic_response

    agent = ClaudeAgent(model_config=test_model_config)
    feedback = "Please focus more on the technical details."

    response = agent.summarize_newsletter_with_feedback(sample_newsletter, feedback)

    assert response.success
    assert isinstance(response.data, SummaryData)

    # Check that feedback is in the prompt
    call_args = mock_client.messages.create.call_args
    prompt_sent = call_args.kwargs["messages"][0]["content"]
    assert feedback in prompt_sent
    assert "User Feedback and Context" in prompt_sent
