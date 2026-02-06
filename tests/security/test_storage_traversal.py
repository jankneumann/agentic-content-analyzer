"""Security tests for path traversal vulnerabilities in file storage.

These tests verify that malicious paths with traversal sequences (../) are
properly rejected to prevent unauthorized file access.
"""

import asyncio

import pytest

from src.services.file_storage import LocalFileStorage


class TestStorageTraversal:
    """Test path traversal prevention in LocalFileStorage."""

    @pytest.fixture
    def storage_setup(self, tmp_path):
        """Set up a test storage directory with a secret file outside of it."""
        # Create base storage directory
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()

        # Create a secret file outside storage
        secret_file = tmp_path / "secret.txt"
        secret_file.write_text("SUPER_SECRET_DATA")

        storage = LocalFileStorage(base_path=str(storage_dir), bucket="test")

        return storage, storage_dir, secret_file

    def test_path_traversal_read(self, storage_setup):
        """Test that path traversal in read operations is rejected."""
        storage, _storage_dir, _secret_file = storage_setup
        traversal_path = "test/../secret.txt"

        with pytest.raises(ValueError, match="Path traversal detected"):
            asyncio.run(storage.get(traversal_path))

    def test_path_traversal_exists(self, storage_setup):
        """Test that path traversal in exists operations is rejected."""
        storage, _storage_dir, _secret_file = storage_setup
        traversal_path = "test/../secret.txt"

        with pytest.raises(ValueError, match="Path traversal detected"):
            asyncio.run(storage.exists(traversal_path))

    def test_path_traversal_delete(self, storage_setup):
        """Test that path traversal in delete operations is rejected."""
        storage, _storage_dir, _secret_file = storage_setup
        traversal_path = "test/../secret.txt"

        with pytest.raises(ValueError, match="Path traversal detected"):
            asyncio.run(storage.delete(traversal_path))
