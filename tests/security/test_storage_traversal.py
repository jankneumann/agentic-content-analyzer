import asyncio
import sys
from unittest.mock import MagicMock

import pytest

# === Dependency Mocking ===
mock_settings = MagicMock()
mock_settings.storage_local_paths = {}
mock_settings.image_storage_provider = "local"
mock_settings.storage_provider = "local"
mock_settings.storage_bucket_providers = {}
mock_settings.storage_s3_buckets = {}
mock_settings.storage_supabase_buckets = {}

mock_config = MagicMock()
mock_config.settings = mock_settings

sys.modules["src.config"] = mock_config
sys.modules["src.config.settings"] = mock_config
sys.modules["src.config.models"] = MagicMock()
sys.modules["src.utils.logging"] = MagicMock()

# Mock all other services to prevent cascading imports
sys.modules["src.services.chat_service"] = MagicMock()
sys.modules["src.services.content_service"] = MagicMock()
sys.modules["src.services.image_extractor"] = MagicMock()
sys.modules["src.services.prompt_service"] = MagicMock()
sys.modules["src.services.review_service"] = MagicMock()
sys.modules["src.services.script_review_service"] = MagicMock()

# Also mock external libs that might be missing
sys.modules["anthropic"] = MagicMock()
sys.modules["openai"] = MagicMock()
sys.modules["google.oauth2"] = MagicMock()

# Now import
from src.services.file_storage import LocalFileStorage  # noqa: E402


class TestStorageTraversal:
    @pytest.fixture
    def storage_setup(self, tmp_path):
        # Create base storage directory
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()

        # Create a secret file outside storage
        secret_file = tmp_path / "secret.txt"
        secret_file.write_text("SUPER_SECRET_DATA")

        storage = LocalFileStorage(base_path=str(storage_dir), bucket="test")

        return storage, storage_dir, secret_file

    def test_path_traversal_read(self, storage_setup):
        storage, _storage_dir, _secret_file = storage_setup
        traversal_path = "test/../secret.txt"

        with pytest.raises(ValueError, match="Path traversal detected"):
            asyncio.run(storage.get(traversal_path))

    def test_path_traversal_exists(self, storage_setup):
        storage, _storage_dir, _secret_file = storage_setup
        traversal_path = "test/../secret.txt"

        with pytest.raises(ValueError, match="Path traversal detected"):
            asyncio.run(storage.exists(traversal_path))

    def test_path_traversal_delete(self, storage_setup):
        storage, _storage_dir, _secret_file = storage_setup
        traversal_path = "test/../secret.txt"

        with pytest.raises(ValueError, match="Path traversal detected"):
            asyncio.run(storage.delete(traversal_path))
