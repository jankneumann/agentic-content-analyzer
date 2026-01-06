"""Helpers for mocking external API calls with cached responses."""

import json
from pathlib import Path
from unittest.mock import MagicMock

# Path to cached API responses
TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"
ANTHROPIC_RESPONSES_DIR = TEST_DATA_DIR / "api_responses" / "anthropic"
OPENAI_RESPONSES_DIR = TEST_DATA_DIR / "api_responses" / "openai"


def load_cached_response(provider: str, filename: str) -> dict:
    """
    Load cached API response from JSON file.

    Args:
        provider: 'anthropic' or 'openai'
        filename: Name of JSON file in the provider's directory

    Returns:
        Dictionary with API response data
    """
    if provider == "anthropic":
        file_path = ANTHROPIC_RESPONSES_DIR / filename
    elif provider == "openai":
        file_path = OPENAI_RESPONSES_DIR / filename
    else:
        raise ValueError(f"Unknown provider: {provider}")

    if not file_path.exists():
        raise FileNotFoundError(f"Cached response not found: {file_path}")

    with open(file_path) as f:
        return json.load(f)


def create_anthropic_mock_response(response_file: str) -> MagicMock:
    """
    Create mock Anthropic API response from cached file.

    Args:
        response_file: Filename in api_responses/anthropic/

    Returns:
        MagicMock configured to return cached response
    """
    response_data = load_cached_response("anthropic", response_file)

    # Create mock response object matching Anthropic API structure
    mock_response = MagicMock()
    mock_response.id = response_data["id"]
    mock_response.type = response_data["type"]
    mock_response.role = response_data["role"]
    mock_response.model = response_data["model"]
    mock_response.stop_reason = response_data["stop_reason"]
    mock_response.stop_sequence = response_data.get("stop_sequence")

    # Mock content blocks
    mock_content = []
    for content_block in response_data["content"]:
        mock_block = MagicMock()
        mock_block.type = content_block["type"]
        mock_block.text = content_block["text"]
        mock_content.append(mock_block)

    mock_response.content = mock_content

    # Mock usage
    mock_usage = MagicMock()
    mock_usage.input_tokens = response_data["usage"]["input_tokens"]
    mock_usage.output_tokens = response_data["usage"]["output_tokens"]
    mock_response.usage = mock_usage

    return mock_response


def create_openai_mock_response(response_file: str) -> MagicMock:
    """
    Create mock OpenAI API response from cached file.

    Args:
        response_file: Filename in api_responses/openai/

    Returns:
        MagicMock configured to return cached response
    """
    response_data = load_cached_response("openai", response_file)

    # Create mock response object matching OpenAI API structure
    mock_response = MagicMock()
    mock_response.object = response_data["object"]
    mock_response.model = response_data["model"]

    # Mock data (embeddings)
    mock_data = []
    for item in response_data["data"]:
        mock_item = MagicMock()
        mock_item.object = item["object"]
        mock_item.embedding = item["embedding"]
        mock_item.index = item["index"]
        mock_data.append(mock_item)

    mock_response.data = mock_data

    # Mock usage
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = response_data["usage"]["prompt_tokens"]
    mock_usage.total_tokens = response_data["usage"]["total_tokens"]
    mock_response.usage = mock_usage

    return mock_response


def create_anthropic_summarization_responses() -> list[MagicMock]:
    """
    Create list of mock responses for all test newsletters.

    Returns:
        List of mock responses in order:
        [llm_advances, vector_databases, agent_frameworks]
    """
    return [
        create_anthropic_mock_response("summarize_llm_advances.json"),
        create_anthropic_mock_response("summarize_vector_databases.json"),
        create_anthropic_mock_response("summarize_agent_frameworks.json"),
    ]


def get_summary_response_mapping() -> dict[str, str]:
    """
    Get mapping of newsletter filenames to their summary response files.

    Returns:
        Dict mapping newsletter filename -> response filename
    """
    return {
        "newsletter_1_llm_advances.json": "summarize_llm_advances.json",
        "newsletter_2_vector_databases.json": "summarize_vector_databases.json",
        "newsletter_3_agent_frameworks.json": "summarize_agent_frameworks.json",
    }
