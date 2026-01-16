"""Tests for ClaudeAgent - Functional tests for pure functions.

Integration tests (LLM API calls) are documented but not implemented.
These should be added to a separate integration test suite.
"""

import json
from datetime import datetime

import pytest

from src.agents.claude.summarizer import ClaudeAgent
from src.config.models import MODEL_REGISTRY, ModelConfig, ModelStep, Provider, ProviderConfig
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
def sample_summary_dict() -> dict:
    """Create sample summary dictionary."""
    return {
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


def test_claude_agent_initialization_with_model_config(test_model_config):
    """Test ClaudeAgent initialization with ModelConfig."""
    agent = ClaudeAgent(model_config=test_model_config)

    # Model should be from registry and configured for SUMMARIZATION step
    assert agent.model in MODEL_REGISTRY, f"Model {agent.model} not in registry"
    assert agent.model_config is not None
    assert agent.framework_name == "claude"
    assert agent.step == ModelStep.SUMMARIZATION


def test_claude_agent_initialization_with_custom_model(test_model_config):
    """Test ClaudeAgent initialization with custom model override."""
    # Use any valid Claude model from the registry
    claude_models = [m for m in MODEL_REGISTRY.keys() if "claude" in m]
    test_model = claude_models[0]  # Use first Claude model

    agent = ClaudeAgent(model_config=test_model_config, model=test_model)

    assert agent.model == test_model
    assert agent.model in MODEL_REGISTRY


def test_claude_agent_initialization_backward_compatibility_api_key():
    """Test ClaudeAgent initialization with api_key (backward compatibility)."""
    agent = ClaudeAgent(api_key="test-key")

    assert agent.model in MODEL_REGISTRY
    assert agent.api_key == "test-key"
    assert agent.framework_name == "claude"


def test_create_summary_prompt_with_text(sample_newsletter, test_model_config):
    """Test prompt creation with text content."""
    agent = ClaudeAgent(model_config=test_model_config)
    prompt = agent._create_summary_prompt(sample_newsletter)

    # Verify key components
    assert "AI Advances in 2025" in prompt
    assert "Tech Weekly" in prompt
    assert "2025-01-15" in prompt
    assert "Newsletter content about AI advances" in prompt
    assert "JSON format" in prompt
    assert "executive_summary" in prompt
    assert "key_themes" in prompt
    assert "strategic_insights" in prompt


def test_create_summary_prompt_html_fallback(test_model_config):
    """Test prompt falls back to HTML when no text content."""
    newsletter = Newsletter(
        source=NewsletterSource.GMAIL,
        source_id="test-123",
        sender="test@example.com",
        publication="Tech Weekly",
        title="Test Newsletter",
        raw_html="<html><body>HTML content only</body></html>",
        raw_text=None,  # No text content
        published_date=datetime(2025, 1, 15),
        status=ProcessingStatus.PENDING,
    )
    newsletter.id = 1

    agent = ClaudeAgent(model_config=test_model_config)
    prompt = agent._create_summary_prompt(newsletter)

    assert "<html><body>HTML content only</body></html>" in prompt


def test_create_summary_prompt_truncates_long_content(test_model_config):
    """Test prompt truncates very long content."""
    long_text = "A" * 20000  # 20K characters

    newsletter = Newsletter(
        source=NewsletterSource.GMAIL,
        source_id="test-123",
        sender="test@example.com",
        publication="Tech Weekly",
        title="Long Newsletter",
        raw_text=long_text,
        published_date=datetime(2025, 1, 15),
        status=ProcessingStatus.PENDING,
    )
    newsletter.id = 1

    agent = ClaudeAgent(model_config=test_model_config)
    prompt = agent._create_summary_prompt(newsletter)

    # Should truncate to ~15K characters (allow small margin for whitespace)
    # The content section should not significantly exceed 15K
    content_start = prompt.find("**Content:**") + len("**Content:**")
    content_end = prompt.find("**Required Output")
    content_section = prompt[content_start:content_end].strip()

    # Allow 100 char margin for whitespace/newlines
    assert len(content_section) <= 15100


def test_validate_summary_data_complete(sample_summary_dict, test_model_config):
    """Test validation of complete summary data."""
    agent = ClaudeAgent(model_config=test_model_config)
    summary_data = agent._validate_summary_data(sample_summary_dict, newsletter_id=1)

    assert isinstance(summary_data, SummaryData)
    assert summary_data.newsletter_id == 1
    assert (
        summary_data.executive_summary
        == "Major AI advancements this week including new LLM releases."
    )
    assert len(summary_data.key_themes) == 3
    assert "LLM Performance" in summary_data.key_themes
    assert len(summary_data.strategic_insights) == 2
    assert len(summary_data.technical_details) == 2
    assert len(summary_data.actionable_items) == 2
    assert len(summary_data.notable_quotes) == 2
    assert summary_data.relevance_scores["cto_leadership"] == 0.9
    assert summary_data.agent_framework == "claude"
    assert summary_data.model_used in MODEL_REGISTRY


def test_validate_summary_data_minimal(test_model_config):
    """Test validation with minimal data (defaults)."""
    minimal_data = {
        "executive_summary": "Short summary",
    }

    agent = ClaudeAgent(model_config=test_model_config)
    summary_data = agent._validate_summary_data(minimal_data, newsletter_id=2)

    assert summary_data.newsletter_id == 2
    assert summary_data.executive_summary == "Short summary"
    assert summary_data.key_themes == []
    assert summary_data.strategic_insights == []
    assert summary_data.technical_details == []
    assert summary_data.actionable_items == []
    assert summary_data.notable_quotes == []
    assert summary_data.relevance_scores == {}


def test_validate_summary_data_custom_model(test_model_config):
    """Test validation includes custom model name."""
    # Use any valid Claude model from the registry
    claude_models = [m for m in MODEL_REGISTRY.keys() if "claude" in m]
    test_model = claude_models[0]

    agent = ClaudeAgent(model_config=test_model_config, model=test_model)
    summary_data = agent._validate_summary_data({"executive_summary": "Test"}, newsletter_id=1)

    assert summary_data.model_used == test_model
    assert summary_data.model_used in MODEL_REGISTRY


def test_extract_json_from_response_plain(test_model_config):
    """Test extracting JSON from plain response."""
    response = '{"key": "value", "number": 42}'

    agent = ClaudeAgent(model_config=test_model_config)
    result = agent._extract_json_from_response(response)

    assert result == {"key": "value", "number": 42}


def test_extract_json_from_response_with_json_markdown(test_model_config):
    """Test extracting JSON from markdown code block with 'json' tag."""
    response = """```json
{
  "executive_summary": "Test summary",
  "key_themes": ["Theme 1", "Theme 2"]
}
```"""

    agent = ClaudeAgent(model_config=test_model_config)
    result = agent._extract_json_from_response(response)

    assert result["executive_summary"] == "Test summary"
    assert result["key_themes"] == ["Theme 1", "Theme 2"]


def test_extract_json_from_response_with_generic_markdown(test_model_config):
    """Test extracting JSON from generic markdown code block."""
    response = """```
{
  "executive_summary": "Test summary",
  "key_themes": ["Theme 1"]
}
```"""

    agent = ClaudeAgent(model_config=test_model_config)
    result = agent._extract_json_from_response(response)

    assert result["executive_summary"] == "Test summary"
    assert result["key_themes"] == ["Theme 1"]


def test_extract_json_from_response_with_surrounding_text(test_model_config):
    """Test extracting JSON when surrounded by explanatory text."""
    response = """Here is the summary in JSON format:

```json
{
  "executive_summary": "Test",
  "key_themes": []
}
```

This should work correctly."""

    agent = ClaudeAgent(model_config=test_model_config)
    result = agent._extract_json_from_response(response)

    assert result["executive_summary"] == "Test"


def test_extract_json_from_response_invalid(test_model_config):
    """Test extraction fails gracefully with invalid JSON."""
    response = "This is not valid JSON at all"

    agent = ClaudeAgent(model_config=test_model_config)

    with pytest.raises(json.JSONDecodeError):
        agent._extract_json_from_response(response)


def test_extract_json_from_response_malformed_markdown(test_model_config):
    """Test extraction fails with malformed markdown blocks."""
    response = """```json
{
  "executive_summary": "Test",
  "key_themes": [  # Missing closing bracket
}
```"""

    agent = ClaudeAgent(model_config=test_model_config)

    with pytest.raises(json.JSONDecodeError):
        agent._extract_json_from_response(response)
