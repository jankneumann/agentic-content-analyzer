import pytest
from unittest.mock import patch, AsyncMock
from src.models.content import Content, ContentStatus

def test_upload_file_too_large(client):
    """Test that uploading a file larger than the limit returns 413."""
    # Mock settings.max_upload_size_mb to be small (e.g. 1MB)
    with patch("src.config.settings.settings.max_upload_size_mb", 1):
        # Create a file content larger than 1MB (e.g. 1.5MB)
        large_content = b"a" * (1024 * 1024 + 512 * 1024)

        files = {
            "file": ("large_file.txt", large_content, "text/plain")
        }

        response = client.post("/api/v1/documents/upload", files=files)

        assert response.status_code == 413
        assert "exceeds limit" in response.json()["detail"]

def test_upload_file_within_limit(client):
    """Test that uploading a file within the limit is accepted."""
    # Mock settings.max_upload_size_mb to be 2MB
    with patch("src.config.settings.settings.max_upload_size_mb", 2):
        # Create a file content smaller than 2MB (e.g. 1MB)
        content = b"a" * (1024 * 1024)

        files = {
            "file": ("ok_file.txt", content, "text/plain")
        }

        with patch("src.api.upload_routes.FileContentIngestionService") as mock_service:
            mock_instance = mock_service.return_value

            # Make ingest_bytes return a mock content object
            mock_content = Content(
                id=1,
                title="Test",
                status=ContentStatus.PARSED,
                source_id="test",
                source_type="file_upload"
            )
            mock_instance.ingest_bytes = AsyncMock(return_value=mock_content)

            response = client.post("/api/v1/documents/upload", files=files)

            assert response.status_code == 200
