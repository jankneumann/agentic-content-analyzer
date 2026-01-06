"""Simple mock helpers for functional integration tests.

These create minimal valid responses for testing business logic flow.
We don't care about the actual content quality - just that the structure is valid.
"""

from unittest.mock import MagicMock


def create_simple_summary_response(newsletter_id: int = 1) -> MagicMock:
    """
    Create minimal valid Anthropic summary response.

    For functional tests - just needs valid JSON structure, content doesn't matter.
    """
    mock_response = MagicMock()
    mock_response.id = f"msg_test_{newsletter_id}"
    mock_response.type = "message"
    mock_response.role = "assistant"
    mock_response.model = "claude-haiku-4-5"
    mock_response.stop_reason = "end_turn"
    mock_response.stop_sequence = None

    # Minimal valid summary JSON (content doesn't matter for functional tests)
    summary_json = {
        "executive_summary": "Test executive summary",
        "key_themes": ["Theme 1", "Theme 2"],
        "strategic_insights": ["Insight 1"],
        "technical_details": ["Detail 1"],
        "actionable_items": ["Action 1"],
        "notable_quotes": ["Quote 1"],
        "relevance_scores": {
            "cto_leadership": 0.8,
            "technical_teams": 0.9,
            "individual_developers": 0.7,
        },
    }

    import json

    mock_content = MagicMock()
    mock_content.type = "text"
    mock_content.text = json.dumps(summary_json)
    mock_response.content = [mock_content]

    # Mock usage
    mock_usage = MagicMock()
    mock_usage.input_tokens = 100
    mock_usage.output_tokens = 150
    mock_response.usage = mock_usage

    return mock_response


def create_simple_digest_response() -> MagicMock:
    """
    Create minimal valid Anthropic digest response.

    For functional tests - just needs valid JSON structure.
    """
    mock_response = MagicMock()
    mock_response.id = "msg_test_digest"
    mock_response.type = "message"
    mock_response.role = "assistant"
    mock_response.model = "claude-sonnet-4-5"
    mock_response.stop_reason = "end_turn"
    mock_response.stop_sequence = None

    # Minimal valid digest JSON
    digest_json = {
        "title": "Test Digest",
        "executive_overview": "Test overview",
        "strategic_insights": [],
        "technical_developments": [],
        "emerging_trends": [],
        "actionable_recommendations": {
            "cto_leadership": ["Action 1"],
            "technical_teams": ["Action 2"],
            "individual_developers": ["Action 3"],
        },
    }

    import json

    mock_content = MagicMock()
    mock_content.type = "text"
    mock_content.text = json.dumps(digest_json)
    mock_response.content = [mock_content]

    # Mock usage
    mock_usage = MagicMock()
    mock_usage.input_tokens = 500
    mock_usage.output_tokens = 200
    mock_response.usage = mock_usage

    return mock_response


def create_simple_theme_analysis_response(theme_count: int = 3) -> MagicMock:
    """
    Create minimal valid theme analysis response.

    For functional tests - just needs valid structure with N themes.
    """
    mock_response = MagicMock()
    mock_response.id = "msg_test_themes"
    mock_response.type = "message"
    mock_response.role = "assistant"
    mock_response.model = "claude-haiku-4-5"
    mock_response.stop_reason = "end_turn"

    # Minimal valid themes JSON with all required fields
    themes = []
    for i in range(theme_count):
        themes.append(
            {
                "name": f"Test Theme {i + 1}",
                "description": f"Description for theme {i + 1}",
                "category": "ml_ai",  # Required ThemeCategory
                "mention_count": 3,  # Required
                "newsletter_ids": [1, 2, 3],
                "first_seen": "2025-01-13T00:00:00Z",  # Required
                "last_seen": "2025-01-15T00:00:00Z",  # Required
                "trend": "established",  # Required ThemeTrend
                "relevance_score": 0.8,
                "strategic_relevance": 0.8,  # Required
                "tactical_relevance": 0.8,  # Required
            }
        )

    themes_json = {"themes": themes}

    import json

    mock_content = MagicMock()
    mock_content.type = "text"
    mock_content.text = json.dumps(themes_json)
    mock_response.content = [mock_content]

    # Mock usage
    mock_usage = MagicMock()
    mock_usage.input_tokens = 300
    mock_usage.output_tokens = 250
    mock_response.usage = mock_usage

    return mock_response


def create_simple_embedding_response() -> MagicMock:
    """
    Create minimal valid OpenAI embedding response.

    For functional tests - just needs valid structure.
    """
    mock_response = MagicMock()
    mock_response.status_code = 200

    embedding_data = {
        "object": "list",
        "data": [
            {
                "object": "embedding",
                "embedding": [0.001] * 1536,  # Mock 1536-dim embedding
                "index": 0,
            }
        ],
        "model": "text-embedding-3-small",
        "usage": {"prompt_tokens": 8, "total_tokens": 8},
    }

    mock_response.json.return_value = embedding_data
    return mock_response
