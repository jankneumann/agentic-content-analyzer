
import pytest
from unittest.mock import MagicMock, patch
import os

# Set dummy env vars before imports
os.environ["ANTHROPIC_API_KEY"] = "dummy"
os.environ["OPENAI_API_KEY"] = "dummy"
os.environ["OTEL_ENABLED"] = "false" # Disable OTel to avoid instrumentation trying to connect

# Mock sqlalchemy create_engine to avoid real DB connection during app import
with patch("sqlalchemy.create_engine") as mock_create_engine:
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    # Also mock src.storage.database._get_engine and _get_provider to be safe
    with patch("src.storage.database._get_engine") as mock_get_engine:
         mock_get_engine.return_value = mock_engine

         from fastapi.testclient import TestClient
         from src.api.app import app
         from src.api import summary_routes

def test_regenerate_with_feedback_error_leakage():
    """
    Test that exceptions in regenerate_with_feedback do not leak internal details.
    """
    # Mock models
    mock_summary = MagicMock()
    mock_summary.id = 123
    mock_summary.content_id = 456

    mock_content = MagicMock()
    mock_content.id = 456

    # Mock DB session
    mock_session = MagicMock()
    mock_query = mock_session.query.return_value
    mock_filter = mock_query.filter.return_value

    mock_filter_return = MagicMock()
    mock_filter_return.first.side_effect = [mock_summary, mock_content]

    mock_query.filter.return_value = mock_filter_return

    # Override get_db
    def override_get_db():
        yield mock_session

    app.dependency_overrides[summary_routes.get_db] = override_get_db

    client = TestClient(app)

    # Mock the summarizer to raise an exception with sensitive info
    sensitive_info = "Sensitive DB Connection String: postgres://user:pass@localhost:5432/db"

    with patch("src.processors.summarizer.NewsletterSummarizer") as MockSummarizer:
        instance = MockSummarizer.return_value
        instance.summarize_content_with_feedback.side_effect = Exception(sensitive_info)

        # Make the request
        response = client.post(
            f"/api/v1/summaries/{mock_summary.id}/regenerate-with-feedback",
            json={"feedback": "Make it shorter"}
        )

        assert response.status_code == 200
        content = ""
        for line in response.iter_lines():
            content += line

        # In a vulnerable implementation, this will pass (finding the sensitive info)
        # assert sensitive_info in content

        # Verify the fix:
        # 1. Sensitive info should NOT be leaked
        assert sensitive_info not in content

        # 2. Generic error message SHOULD be present
        assert "An internal error occurred during summary generation" in content

    # Clean up overrides
    app.dependency_overrides = {}
