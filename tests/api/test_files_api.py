"""Tests for files API endpoints.

Tests cover:
- File retrieval from storage buckets
- Content-Type detection
- Range request support
- Error handling for invalid buckets and missing files
"""

import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for storage tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestFilesAPI:
    """Tests for /api/v1/files endpoints."""

    def test_invalid_bucket_returns_400(self, client):
        """Test that invalid bucket name returns 400."""
        response = client.get("/api/v1/files/invalid-bucket/test.jpg")

        assert response.status_code == 400
        assert "Invalid bucket" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_file_not_found_returns_404(self, client, temp_storage_dir):
        """Test that missing file returns 404."""
        with patch("src.api.files_routes.get_storage") as mock_get_storage:
            mock_storage = AsyncMock()
            mock_storage.exists = AsyncMock(return_value=False)
            mock_storage.provider_name = "local"
            mock_get_storage.return_value = mock_storage

            response = client.get("/api/v1/files/images/nonexistent.jpg")

            assert response.status_code == 404
            assert "File not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_file_local_storage(self, client):
        """Test getting a file from local storage."""
        with patch("src.api.files_routes.get_storage") as mock_get_storage:
            mock_storage = AsyncMock()
            mock_storage.exists = AsyncMock(return_value=True)
            mock_storage.get = AsyncMock(return_value=b"fake image data")
            mock_storage.provider_name = "local"
            mock_get_storage.return_value = mock_storage

            response = client.get("/api/v1/files/images/2025/01/24/test.jpg")

            assert response.status_code == 200
            assert response.content == b"fake image data"
            assert response.headers["Content-Type"] == "image/jpeg"
            assert response.headers["Accept-Ranges"] == "bytes"

    @pytest.mark.asyncio
    async def test_get_file_detects_content_type(self, client):
        """Test that content type is correctly detected from extension."""
        with patch("src.api.files_routes.get_storage") as mock_get_storage:
            mock_storage = AsyncMock()
            mock_storage.exists = AsyncMock(return_value=True)
            mock_storage.get = AsyncMock(return_value=b"fake png data")
            mock_storage.provider_name = "local"
            mock_get_storage.return_value = mock_storage

            response = client.get("/api/v1/files/images/2025/01/24/test.png")

            assert response.headers["Content-Type"] == "image/png"

    @pytest.mark.asyncio
    async def test_get_file_audio_content_type(self, client):
        """Test audio content type detection."""
        with patch("src.api.files_routes.get_storage") as mock_get_storage:
            mock_storage = AsyncMock()
            mock_storage.exists = AsyncMock(return_value=True)
            mock_storage.get = AsyncMock(return_value=b"fake mp3 data")
            mock_storage.provider_name = "local"
            mock_get_storage.return_value = mock_storage

            response = client.get("/api/v1/files/podcasts/2025/01/24/podcast.mp3")

            assert response.headers["Content-Type"] == "audio/mpeg"

    @pytest.mark.asyncio
    async def test_range_request_partial_content(self, client):
        """Test range request returns partial content."""
        with patch("src.api.files_routes.get_storage") as mock_get_storage:
            # Create 1000 bytes of data
            test_data = b"x" * 1000
            mock_storage = AsyncMock()
            mock_storage.exists = AsyncMock(return_value=True)
            mock_storage.get = AsyncMock(return_value=test_data)
            mock_storage.provider_name = "local"
            mock_get_storage.return_value = mock_storage

            response = client.get(
                "/api/v1/files/podcasts/2025/01/24/test.mp3",
                headers={"Range": "bytes=0-99"},
            )

            assert response.status_code == 206
            assert len(response.content) == 100
            assert response.headers["Content-Range"] == "bytes 0-99/1000"
            assert response.headers["Content-Length"] == "100"

    @pytest.mark.asyncio
    async def test_range_request_open_ended(self, client):
        """Test open-ended range request."""
        with patch("src.api.files_routes.get_storage") as mock_get_storage:
            test_data = b"x" * 1000
            mock_storage = AsyncMock()
            mock_storage.exists = AsyncMock(return_value=True)
            mock_storage.get = AsyncMock(return_value=test_data)
            mock_storage.provider_name = "local"
            mock_get_storage.return_value = mock_storage

            response = client.get(
                "/api/v1/files/podcasts/2025/01/24/test.mp3",
                headers={"Range": "bytes=500-"},
            )

            assert response.status_code == 206
            assert len(response.content) == 500
            assert response.headers["Content-Range"] == "bytes 500-999/1000"

    @pytest.mark.asyncio
    async def test_range_request_suffix(self, client):
        """Test suffix range request (last N bytes)."""
        with patch("src.api.files_routes.get_storage") as mock_get_storage:
            test_data = b"x" * 1000
            mock_storage = AsyncMock()
            mock_storage.exists = AsyncMock(return_value=True)
            mock_storage.get = AsyncMock(return_value=test_data)
            mock_storage.provider_name = "local"
            mock_get_storage.return_value = mock_storage

            response = client.get(
                "/api/v1/files/podcasts/2025/01/24/test.mp3",
                headers={"Range": "bytes=-100"},
            )

            assert response.status_code == 206
            assert len(response.content) == 100
            assert response.headers["Content-Range"] == "bytes 900-999/1000"

    @pytest.mark.asyncio
    async def test_cloud_storage_redirects_to_signed_url(self, client):
        """Test that cloud storage redirects to signed URL."""
        with patch("src.api.files_routes.get_storage") as mock_get_storage:
            mock_storage = AsyncMock()
            mock_storage.exists = AsyncMock(return_value=True)
            mock_storage.get_signed_url = AsyncMock(
                return_value="https://signed.example.com/file?token=abc"
            )
            mock_storage.provider_name = "s3"
            mock_get_storage.return_value = mock_storage

            response = client.get(
                "/api/v1/files/images/2025/01/24/test.jpg",
                follow_redirects=False,
            )

            assert response.status_code == 302
            assert response.headers["Location"] == "https://signed.example.com/file?token=abc"

    @pytest.mark.asyncio
    async def test_head_request_returns_metadata(self, client):
        """Test HEAD request returns file metadata."""
        with patch("src.api.files_routes.get_storage") as mock_get_storage:
            test_data = b"x" * 500
            mock_storage = AsyncMock()
            mock_storage.exists = AsyncMock(return_value=True)
            mock_storage.get = AsyncMock(return_value=test_data)
            mock_storage.provider_name = "local"
            mock_get_storage.return_value = mock_storage

            response = client.head("/api/v1/files/images/2025/01/24/test.jpg")

            assert response.status_code == 200
            assert response.headers["Content-Length"] == "500"
            assert response.headers["Content-Type"] == "image/jpeg"
            assert response.headers["Accept-Ranges"] == "bytes"
            assert response.content == b""


class TestValidBuckets:
    """Test valid bucket names."""

    @pytest.mark.parametrize("bucket", ["images", "podcasts", "audio-digests"])
    @pytest.mark.asyncio
    async def test_valid_buckets_accepted(self, client, bucket):
        """Test that all valid bucket names are accepted."""
        with patch("src.api.files_routes.get_storage") as mock_get_storage:
            mock_storage = AsyncMock()
            mock_storage.exists = AsyncMock(return_value=False)
            mock_storage.provider_name = "local"
            mock_get_storage.return_value = mock_storage

            response = client.get(f"/api/v1/files/{bucket}/test.file")

            # Should get 404 (not 400), meaning bucket was valid
            assert response.status_code == 404
