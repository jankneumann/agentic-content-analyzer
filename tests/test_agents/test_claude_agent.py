"""Tests for LLMSummarizationAgent (and ClaudeAgent backward-compat alias).

Unit tests for pure functions (prompt creation, JSON extraction, validation).
Integration tests for LLM routing via LLMRouter.generate_sync() mocking.
"""

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from src.agents.claude.summarizer import ClaudeAgent, LLMSummarizationAgent
from src.config.models import MODEL_REGISTRY, ModelConfig, ModelStep, Provider, ProviderConfig
from src.models.content import Content, ContentSource, ContentStatus
from src.models.summary import SummaryData
from src.services.llm_router import LLMResponse


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
def sample_content() -> Content:
    """Create sample content for testing."""
    content = Content(
        source_type=ContentSource.GMAIL,
        source_id="test-123",
        source_url="https://example.com/content",
        title="AI Advances in 2025",
        author="test@example.com",
        publication="Tech Weekly",
        published_date=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        markdown_content="# AI Advances\n\nContent about AI advances and new LLM developments.",
        raw_content="<html><body>Newsletter about AI advances</body></html>",
        raw_format="html",
        content_hash="testhash123",
        status=ContentStatus.PARSED,
        ingested_at=datetime.now(UTC),
    )
    content.id = 1
    return content


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


# ========================================================================
# Backward compatibility
# ========================================================================


def test_claude_agent_alias_is_llm_summarization_agent():
    """ClaudeAgent should be an alias for LLMSummarizationAgent."""
    assert ClaudeAgent is LLMSummarizationAgent


# ========================================================================
# Initialization
# ========================================================================


def test_initialization_with_model_config(test_model_config):
    """Test initialization with ModelConfig."""
    agent = LLMSummarizationAgent(model_config=test_model_config)

    assert agent.model in MODEL_REGISTRY, f"Model {agent.model} not in registry"
    assert agent.model_config is not None
    assert agent.router is not None
    assert agent.step == ModelStep.SUMMARIZATION


def test_initialization_with_custom_model(test_model_config):
    """Test initialization with custom model override."""
    claude_models = [m for m in MODEL_REGISTRY.keys() if "claude" in m]
    test_model = claude_models[0]

    agent = LLMSummarizationAgent(model_config=test_model_config, model=test_model)

    assert agent.model == test_model
    assert agent.model in MODEL_REGISTRY


def test_initialization_backward_compatibility_api_key():
    """Test initialization with api_key (backward compatibility)."""
    agent = ClaudeAgent(api_key="test-key")

    assert agent.model in MODEL_REGISTRY
    assert agent.api_key == "test-key"
    assert agent.router is not None


# ========================================================================
# Summarization via LLMRouter
# ========================================================================


def test_summarize_content_calls_router(test_model_config, sample_content, sample_summary_dict):
    """summarize_content should delegate to LLMRouter.generate_sync()."""
    mock_response = LLMResponse(
        text=json.dumps(sample_summary_dict),
        input_tokens=500,
        output_tokens=300,
        provider=Provider.ANTHROPIC,
        model_version="claude-haiku-4-5-20250414",
    )

    agent = LLMSummarizationAgent(model_config=test_model_config, model="claude-haiku-4-5")

    with patch.object(agent.router, "generate_sync", return_value=mock_response) as mock_gen:
        result = agent.summarize_content(sample_content)

        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args.kwargs
        assert call_kwargs["max_tokens"] == 4096
        assert call_kwargs["temperature"] == 0.0
        assert result.success is True
        assert result.data.executive_summary == sample_summary_dict["executive_summary"]
        assert result.metadata["provider"] == "anthropic"
        assert result.metadata["input_tokens"] == 500


def test_summarize_content_with_gemini_model(sample_content, sample_summary_dict):
    """Should work with non-Anthropic models (the whole point of the refactor)."""
    config = ModelConfig()
    # No Anthropic provider needed — router handles provider resolution

    mock_response = LLMResponse(
        text=json.dumps(sample_summary_dict),
        input_tokens=300,
        output_tokens=200,
        provider=Provider.GOOGLE_AI,
        model_version="gemini-2.5-flash-lite",
    )

    agent = LLMSummarizationAgent(model_config=config, model="gemini-2.5-flash-lite")

    with patch.object(agent.router, "generate_sync", return_value=mock_response):
        result = agent.summarize_content(sample_content)

        assert result.success is True
        assert result.metadata["provider"] == "google_ai"


def test_summarize_content_handles_llm_error(test_model_config, sample_content):
    """Should return error AgentResponse when router raises."""
    agent = LLMSummarizationAgent(model_config=test_model_config)

    with patch.object(agent.router, "generate_sync", side_effect=RuntimeError("API key missing")):
        result = agent.summarize_content(sample_content)

        assert result.success is False
        assert "API key missing" in result.error


def test_summarize_content_with_feedback(test_model_config, sample_content, sample_summary_dict):
    """summarize_content_with_feedback should also use router."""
    mock_response = LLMResponse(
        text=json.dumps(sample_summary_dict),
        input_tokens=600,
        output_tokens=350,
        provider=Provider.ANTHROPIC,
    )

    agent = LLMSummarizationAgent(model_config=test_model_config, model="claude-haiku-4-5")

    with patch.object(agent.router, "generate_sync", return_value=mock_response):
        result = agent.summarize_content_with_feedback(
            sample_content, "Please add more detail about RAG"
        )

        assert result.success is True
        assert result.data.executive_summary == sample_summary_dict["executive_summary"]


def test_summarize_content_handles_json_parse_error(test_model_config, sample_content):
    """Should return error when LLM response is not valid JSON."""
    mock_response = LLMResponse(
        text="This is not JSON at all",
        input_tokens=100,
        output_tokens=50,
        provider=Provider.ANTHROPIC,
    )

    agent = LLMSummarizationAgent(model_config=test_model_config)

    with patch.object(agent.router, "generate_sync", return_value=mock_response):
        result = agent.summarize_content(sample_content)

        assert result.success is False
        assert "Failed to parse response as JSON" in result.error


# ========================================================================
# Prompt creation (unchanged from original — tests exercise base class)
# ========================================================================


def test_create_content_prompt(sample_content, test_model_config):
    """Test prompt creation with content."""
    agent = LLMSummarizationAgent(model_config=test_model_config)
    prompt = agent._create_content_prompt(sample_content)

    assert "AI Advances in 2025" in prompt
    assert "Tech Weekly" in prompt
    assert "2025-01-15" in prompt
    assert "Content about AI advances" in prompt
    assert "JSON format" in prompt
    assert "executive_summary" in prompt
    assert "key_themes" in prompt
    assert "strategic_insights" in prompt


def test_create_content_prompt_raw_fallback(test_model_config):
    """Test prompt falls back to raw content when no markdown."""
    content = Content(
        source_type=ContentSource.GMAIL,
        source_id="test-123",
        source_url="https://example.com/content",
        title="Test Content",
        author="test@example.com",
        publication="Tech Weekly",
        published_date=datetime(2025, 1, 15, tzinfo=UTC),
        markdown_content="",
        raw_content="<html><body>HTML content only</body></html>",
        raw_format="html",
        content_hash="testhash",
        status=ContentStatus.PARSED,
        ingested_at=datetime.now(UTC),
    )
    content.id = 1

    agent = LLMSummarizationAgent(model_config=test_model_config)
    prompt = agent._create_content_prompt(content)

    assert "Test Content" in prompt


def test_create_content_prompt_truncates_long_content(test_model_config):
    """Test prompt truncates very long content."""
    long_text = "A" * 25000

    content = Content(
        source_type=ContentSource.GMAIL,
        source_id="test-123",
        source_url="https://example.com/content",
        title="Long Content",
        author="test@example.com",
        publication="Tech Weekly",
        published_date=datetime(2025, 1, 15, tzinfo=UTC),
        markdown_content=long_text,
        content_hash="testhash",
        status=ContentStatus.PARSED,
        ingested_at=datetime.now(UTC),
    )
    content.id = 1

    agent = LLMSummarizationAgent(model_config=test_model_config)
    prompt = agent._create_content_prompt(content)

    content_start = prompt.find("**Content:**") + len("**Content:**")
    content_end = prompt.find("**Required Output")
    content_section = prompt[content_start:content_end].strip()

    assert len(content_section) <= 20200
    assert "[Content truncated...]" in content_section


# ========================================================================
# Summary validation (unchanged — tests exercise base class)
# ========================================================================


def test_validate_summary_data_complete(sample_summary_dict, test_model_config):
    """Test validation of complete summary data."""
    agent = LLMSummarizationAgent(model_config=test_model_config)
    summary_data = agent._validate_summary_data(sample_summary_dict, content_id=1)

    assert isinstance(summary_data, SummaryData)
    assert summary_data.content_id == 1
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
    assert summary_data.model_used in MODEL_REGISTRY


def test_validate_summary_data_minimal(test_model_config):
    """Test validation with minimal data (defaults)."""
    minimal_data = {
        "executive_summary": "Short summary",
    }

    agent = LLMSummarizationAgent(model_config=test_model_config)
    summary_data = agent._validate_summary_data(minimal_data, content_id=2)

    assert summary_data.content_id == 2
    assert summary_data.executive_summary == "Short summary"
    assert summary_data.key_themes == []
    assert summary_data.strategic_insights == []
    assert summary_data.technical_details == []
    assert summary_data.actionable_items == []
    assert summary_data.notable_quotes == []
    assert summary_data.relevance_scores == {}


def test_validate_summary_data_custom_model(test_model_config):
    """Test validation includes custom model name."""
    claude_models = [m for m in MODEL_REGISTRY.keys() if "claude" in m]
    test_model = claude_models[0]

    agent = LLMSummarizationAgent(model_config=test_model_config, model=test_model)
    summary_data = agent._validate_summary_data({"executive_summary": "Test"}, content_id=1)

    assert summary_data.model_used == test_model
    assert summary_data.model_used in MODEL_REGISTRY


# ========================================================================
# JSON extraction (unchanged)
# ========================================================================


def test_extract_json_from_response_plain(test_model_config):
    """Test extracting JSON from plain response."""
    response = '{"key": "value", "number": 42}'

    agent = LLMSummarizationAgent(model_config=test_model_config)
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

    agent = LLMSummarizationAgent(model_config=test_model_config)
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

    agent = LLMSummarizationAgent(model_config=test_model_config)
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

    agent = LLMSummarizationAgent(model_config=test_model_config)
    result = agent._extract_json_from_response(response)

    assert result["executive_summary"] == "Test"


def test_extract_json_from_response_invalid(test_model_config):
    """Test extraction fails gracefully with invalid JSON."""
    response = "This is not valid JSON at all"

    agent = LLMSummarizationAgent(model_config=test_model_config)

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

    agent = LLMSummarizationAgent(model_config=test_model_config)

    with pytest.raises(json.JSONDecodeError):
        agent._extract_json_from_response(response)
