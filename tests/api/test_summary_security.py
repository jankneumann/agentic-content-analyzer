"""Security tests for summary API endpoints.

Focuses on information leakage and other security vulnerabilities.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.models.content import Content
from src.models.summary import Summary


def test_regenerate_with_feedback_error_leakage(
    client: TestClient, sample_content_with_summary: tuple[Content, Summary]
):
    """
    Test that exceptions during regeneration do not leak sensitive information.

    This test verifies that if the summarizer raises an exception containing
    sensitive data (like a DB connection string), that data is NOT exposed
    to the client in the response.
    """
    _content, summary = sample_content_with_summary
    sensitive_secret = "CRITICAL_SECRET_VALUE"

    # Mock the summarizer to raise an exception with sensitive info
    # We patch the ContentSummarizer because it is aliased as NewsletterSummarizer
    # and imported inside the endpoint function.
    with patch(
        "src.processors.summarizer.ContentSummarizer.summarize_content_with_feedback"
    ) as mock_summarize:
        mock_summarize.side_effect = Exception(f"Database connection failed: {sensitive_secret}")

        response = client.post(
            f"/api/v1/summaries/{summary.id}/regenerate-with-feedback",
            json={"feedback": "Make it shorter"},
        )

        # The endpoint returns a streaming response.
        # We need to iterate over the lines to check the content.
        assert response.status_code == 200

        content_text = response.text

        # Check that we received an error message
        assert '"status": "error"' in content_text

        # KEY ASSERTION: The sensitive secret should NOT be in the response
        assert (
            sensitive_secret not in content_text
        ), "VULNERABILITY: Sensitive secret leaked in error message!"

        # Assert that we get the safe generic error message
        assert "An internal error occurred during regeneration" in content_text
