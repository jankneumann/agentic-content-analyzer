
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.api.app import app
from src.models.summary import Summary
from src.models.content import Content

@pytest.fixture
def client():
    return TestClient(app)

@patch("src.api.summary_routes.get_db")
@patch("src.processors.summarizer.NewsletterSummarizer")
def test_regenerate_leak(mock_summarizer_cls, mock_get_db, client):
    # Mock DB
    mock_db = MagicMock()
    mock_get_db.return_value.__enter__.return_value = mock_db

    # Mock Summary and Content
    mock_summary = MagicMock(spec=Summary)
    mock_summary.id = 1
    mock_summary.content_id = 10

    mock_content = MagicMock(spec=Content)
    mock_content.id = 10

    mock_db.query.return_value.filter.return_value.first.side_effect = [mock_summary, mock_content]

    # Mock Summarizer to raise an exception
    mock_summarizer_instance = mock_summarizer_cls.return_value
    mock_summarizer_instance.summarize_content_with_feedback.side_effect = Exception("DB Connection String: postgres://user:pass@localhost:5432/db")

    response = client.post(
        "/api/v1/summaries/1/regenerate-with-feedback",
        json={"feedback": "Make it shorter"}
    )

    assert response.status_code == 200
    content = response.content.decode()

    print(f"\nResponse Content:\n{content}")

    # Check that the leak is plugged
    assert "DB Connection String" not in content, "Vulnerability STILL present: Exception details leaking!"
    assert "An internal error occurred" in content, "Generic error message missing!"
