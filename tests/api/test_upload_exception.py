from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def test_upload_exception_leak(client: TestClient):
    """Test that exceptions during upload are leaked in the response detail."""

    # Define a secret that shouldn't be exposed
    secret_message = "Database connection failed: user=admin password=supersecret"

    # Mock FileContentIngestionService to raise an Exception
    with patch("src.api.upload_routes.FileContentIngestionService") as mock_service_cls:
        mock_instance = mock_service_cls.return_value
        # Mock ingest_bytes to raise exception when awaited
        mock_instance.ingest_bytes = AsyncMock(side_effect=Exception(secret_message))

        # Create a dummy file
        files = {"file": ("test.txt", b"dummy content", "text/plain")}

        # Perform the request
        response = client.post(
            "/api/v1/documents/upload", files=files, headers={"X-Admin-Key": "test-admin-key"}
        )

        # Assertions
        assert response.status_code == 500
        detail = response.json()["detail"]

        # Verify the VULNERABILITY is FIXED
        assert secret_message not in detail
        assert "internal error" in detail.lower()
