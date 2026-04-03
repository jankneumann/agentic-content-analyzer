from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app


# Minimal client fixture that mocks DB dependencies
@pytest.fixture
def client():
    with patch("src.api.upload_routes.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db
        with TestClient(app) as test_client:
            yield test_client


def test_upload_value_error_leak(client):
    """Test that ValueError exceptions during upload are leaked in the response detail."""

    # Define a secret that shouldn't be exposed
    secret_message = "Internal path /var/lib/secrets/key.pem not found"

    # Mock FileContentIngestionService to raise a ValueError
    with patch("src.api.upload_routes.FileContentIngestionService") as mock_service_cls:
        mock_instance = mock_service_cls.return_value
        # Mock ingest_bytes to raise ValueError when awaited
        mock_instance.ingest_bytes = AsyncMock(side_effect=ValueError(secret_message))

        # Create a dummy file
        files = {"file": ("test.txt", b"dummy content", "text/plain")}

        # Perform the request
        # We need to bypass the admin key check or mock it,
        # but upload route requires verify_admin_key dependency.
        # We can override the dependency.

        from src.api.dependencies import verify_admin_key

        app.dependency_overrides[verify_admin_key] = lambda: "test-admin-key"

        try:
            response = client.post(
                "/api/v1/documents/upload", files=files, headers={"X-Admin-Key": "test-admin-key"}
            )

            # Assertions
            # After fix, unexpected ValueError should be 500
            assert response.status_code == 500
            detail = response.json()["detail"]

            # This asserts that the vulnerability is FIXED (leakage DOES NOT happen)
            assert secret_message not in detail
            assert "Processing failed due to an internal error" in detail
        finally:
            app.dependency_overrides = {}
