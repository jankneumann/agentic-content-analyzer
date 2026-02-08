"""Tests for security vulnerability reproduction: Information Leakage in Script API."""

from unittest.mock import patch

from src.services.script_review_service import ScriptReviewService


class TestScriptErrorLeakage:
    """Tests for verifying that internal error details are not leaked to the client."""

    def test_get_script_leaks_exception_message(self, client, sample_script):
        """Test that get_script does NOT leak exception details.

        This test verifies the fix for the vulnerability where a ValueError's message
        was returned directly to the API client.
        """
        sensitive_info = "SENSITIVE_DB_CONNECTION_STRING"

        # Mock the service to raise a ValueError with sensitive info
        with patch.object(
            ScriptReviewService,
            "get_script_for_review",
            side_effect=ValueError(f"Connection failed: {sensitive_info}"),
        ):
            response = client.get(f"/api/v1/scripts/{sample_script.id}")

            # Assert that the sensitive info is NOT leaked
            assert response.status_code == 404
            detail = response.json()["detail"]
            assert sensitive_info not in detail
            assert detail == "Script not found or unavailable"
