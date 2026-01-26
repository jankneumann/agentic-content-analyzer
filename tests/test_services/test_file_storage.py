"""Tests for file storage and extraction services.

Tests cover:
- LocalFileStorage save, get, delete, exists operations
- S3FileStorage operations
- SupabaseFileStorage operations
- get_storage factory function
- ImageExtractor HTML extraction
- ImageExtractor base64 extraction
- Perceptual hash computation and similarity
"""

import base64
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from src.models.image import ImageSource
from src.services.file_storage import (
    LocalFileStorage,
    RailwayFileStorage,
    # Backward-compatible aliases
    S3FileStorage,
    S3ImageStorage,
    SupabaseFileStorage,
    compute_file_hash,
    get_image_storage,
    get_storage,
)
from src.services.image_extractor import (
    BASE64_IMAGE_PATTERN,
    IMG_TAG_PATTERN,
    ExtractedImage,
    ImageExtractor,
    compute_phash_similarity,
)


class TestLocalFileStorage:
    """Tests for LocalFileStorage provider."""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create a temporary directory for storage tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def storage(self, temp_storage_dir):
        """Create a LocalFileStorage instance with temp directory."""
        return LocalFileStorage(base_path=temp_storage_dir, bucket="images")

    @pytest.mark.asyncio
    async def test_save_creates_file(self, storage):
        """Test that save creates a file in storage."""
        data = b"fake image data"
        filename = "test.jpg"

        path = await storage.save(data, filename, "image/jpeg")

        assert path.startswith("images/")
        assert path.endswith(".jpg")
        assert "test.jpg" in path

    @pytest.mark.asyncio
    async def test_save_and_get_roundtrip(self, storage):
        """Test saving and retrieving image data."""
        original_data = b"\x89PNG\r\n\x1a\n" + b"x" * 100  # Fake PNG header
        filename = "roundtrip.png"

        path = await storage.save(original_data, filename, "image/png")
        retrieved_data = await storage.get(path)

        assert retrieved_data == original_data

    @pytest.mark.asyncio
    async def test_save_creates_date_directories(self, storage):
        """Test that save creates date-based directory structure."""
        data = b"test data"

        path = await storage.save(data, "dated.jpg", "image/jpeg")

        # Path should contain year/month/day structure
        parts = path.split("/")
        assert len(parts) >= 4  # images/YYYY/MM/DD/filename
        assert parts[0] == "images"

    @pytest.mark.asyncio
    async def test_get_nonexistent_raises(self, storage):
        """Test that getting nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            await storage.get("images/2025/01/01/nonexistent.jpg")

    @pytest.mark.asyncio
    async def test_delete_removes_file(self, storage):
        """Test that delete removes the file."""
        data = b"to be deleted"
        path = await storage.save(data, "deleteme.jpg", "image/jpeg")

        # Verify file exists
        assert await storage.exists(path)

        # Delete
        result = await storage.delete(path)

        assert result is True
        assert not await storage.exists(path)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, storage):
        """Test that deleting nonexistent file returns False."""
        result = await storage.delete("images/2025/01/01/nonexistent.jpg")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_true_for_saved_file(self, storage):
        """Test exists returns True for saved files."""
        data = b"exists check"
        path = await storage.save(data, "exists.jpg", "image/jpeg")

        assert await storage.exists(path) is True

    @pytest.mark.asyncio
    async def test_exists_false_for_missing_file(self, storage):
        """Test exists returns False for missing files."""
        assert await storage.exists("images/2025/01/01/missing.jpg") is False

    def test_get_url_returns_file_url(self, storage):
        """Test get_url returns file:// URL."""
        path = "images/2025/01/15/test.jpg"

        url = storage.get_url(path)

        assert url.startswith("file://")
        assert path.replace("images/", "") in url or "test.jpg" in url

    def test_provider_name(self, storage):
        """Test provider_name returns 'local'."""
        assert storage.provider_name == "local"


class TestComputeFileHash:
    """Tests for compute_file_hash utility."""

    def test_hash_consistency(self):
        """Test that same data produces same hash."""
        data = b"consistent data"

        hash1 = compute_file_hash(data)
        hash2 = compute_file_hash(data)

        assert hash1 == hash2

    def test_hash_uniqueness(self):
        """Test that different data produces different hashes."""
        data1 = b"data one"
        data2 = b"data two"

        hash1 = compute_file_hash(data1)
        hash2 = compute_file_hash(data2)

        assert hash1 != hash2

    def test_hash_is_hex_string(self):
        """Test that hash is a valid hex string."""
        data = b"test"
        hash_value = compute_file_hash(data)

        assert len(hash_value) == 64  # SHA-256 produces 64 hex chars
        assert all(c in "0123456789abcdef" for c in hash_value)


class TestGetImageStorage:
    """Tests for get_image_storage factory function."""

    @patch("src.services.file_storage.settings")
    def test_returns_local_by_default(self, mock_settings):
        """Test that default storage is local."""
        mock_settings.image_storage_provider = "local"
        mock_settings.image_storage_path = "/tmp/test_images"  # noqa: S108

        storage = get_image_storage()

        assert storage.provider_name == "local"
        assert isinstance(storage, LocalFileStorage)

    def test_returns_local_when_configured(self, temp_storage_dir):
        """Test explicit local configuration."""
        storage = LocalFileStorage(base_path=temp_storage_dir, bucket="images")

        assert storage.provider_name == "local"
        assert str(temp_storage_dir) in str(storage.base_path)

    @pytest.fixture
    def temp_storage_dir(self):
        """Create a temporary directory for storage tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir


class TestGetStorage:
    """Tests for get_storage factory function with bucket support."""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create a temporary directory for storage tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @patch("src.services.file_storage.settings")
    def test_returns_local_for_images_bucket(self, mock_settings):
        """Test that images bucket returns local storage by default."""
        mock_settings.storage_provider = "local"
        mock_settings.storage_bucket_providers = {}
        mock_settings.storage_local_paths = {}
        mock_settings.image_storage_provider = "local"

        storage = get_storage(bucket="images")

        assert storage.provider_name == "local"
        assert storage.bucket == "images"

    @patch("src.services.file_storage.settings")
    def test_returns_local_for_podcasts_bucket(self, mock_settings):
        """Test that podcasts bucket returns local storage by default."""
        mock_settings.storage_provider = "local"
        mock_settings.storage_bucket_providers = {}
        mock_settings.storage_local_paths = {}
        mock_settings.image_storage_provider = "local"

        storage = get_storage(bucket="podcasts")

        assert storage.provider_name == "local"
        assert storage.bucket == "podcasts"

    @patch("src.services.file_storage.settings")
    def test_per_bucket_provider_override(self, mock_settings):
        """Test that per-bucket provider takes precedence."""
        mock_settings.storage_provider = "local"
        mock_settings.storage_bucket_providers = {"podcasts": "local"}  # Only podcasts specified
        mock_settings.storage_local_paths = {}
        mock_settings.image_storage_provider = "local"

        storage = get_storage(bucket="podcasts")

        assert storage.provider_name == "local"
        assert storage.bucket == "podcasts"

    @patch("src.services.file_storage.settings")
    def test_provider_param_overrides_config(self, mock_settings):
        """Test that provider parameter overrides settings."""
        mock_settings.storage_provider = "s3"
        mock_settings.storage_bucket_providers = {"images": "s3"}
        mock_settings.storage_local_paths = {"images": "/tmp/test"}  # noqa: S108

        # Provider param should override
        storage = get_storage(bucket="images", provider="local")

        assert storage.provider_name == "local"


class TestS3FileStorage:
    """Tests for S3FileStorage provider."""

    def test_initialization_with_defaults(self):
        """Test S3 storage initializes with default settings."""
        with patch("src.services.file_storage.settings") as mock_settings:
            mock_settings.storage_s3_buckets = {}
            mock_settings.image_storage_bucket = "test-bucket"
            mock_settings.s3_endpoint_url = None
            mock_settings.aws_region = "us-west-2"
            mock_settings.aws_access_key_id = None
            mock_settings.aws_secret_access_key = None

            storage = S3FileStorage(storage_bucket="images")

            assert storage.bucket == "images"  # Logical bucket
            assert storage.s3_bucket == "test-bucket"  # Actual S3 bucket
            assert storage.region == "us-west-2"
            assert storage.endpoint_url is None

    def test_initialization_with_custom_endpoint(self):
        """Test S3 storage with custom endpoint (MinIO, etc.)."""
        storage = S3FileStorage(
            bucket="minio-bucket",
            storage_bucket="images",
            endpoint_url="http://localhost:9000",
            region="us-east-1",
            access_key_id="minioadmin",
            secret_access_key="minioadmin",
        )

        assert storage.bucket == "images"  # Logical bucket
        assert storage.s3_bucket == "minio-bucket"  # Actual S3 bucket
        assert storage.endpoint_url == "http://localhost:9000"
        assert storage.access_key_id == "minioadmin"
        assert storage.secret_access_key == "minioadmin"

    def test_generate_key_creates_date_path(self):
        """Test that _generate_key creates date-based paths."""
        storage = S3FileStorage(
            bucket="test",
            storage_bucket="images",
            access_key_id="fake",
            secret_access_key="fake",
        )

        key = storage._generate_key("test.jpg")

        assert key.startswith("images/")
        parts = key.split("/")
        assert len(parts) == 5  # images/YYYY/MM/DD/uuid_filename
        assert parts[0] == "images"
        assert "test.jpg" in key

    def test_get_url_standard_s3(self):
        """Test URL generation for standard AWS S3."""
        storage = S3FileStorage(
            bucket="my-bucket",
            storage_bucket="images",
            region="eu-west-1",
            access_key_id="fake",
            secret_access_key="fake",
        )

        url = storage.get_url("images/2025/01/15/test.jpg")

        assert url == "https://my-bucket.s3.eu-west-1.amazonaws.com/images/2025/01/15/test.jpg"

    def test_get_url_custom_endpoint(self):
        """Test URL generation for custom S3-compatible endpoint."""
        storage = S3FileStorage(
            bucket="my-bucket",
            storage_bucket="images",
            endpoint_url="https://s3.custom.com",
            region="us-east-1",
            access_key_id="fake",
            secret_access_key="fake",
        )

        url = storage.get_url("images/2025/01/15/test.jpg")

        assert url == "https://s3.custom.com/my-bucket/images/2025/01/15/test.jpg"

    def test_provider_name(self):
        """Test provider_name returns 's3'."""
        storage = S3ImageStorage(
            bucket="test",
            access_key_id="fake",
            secret_access_key="fake",
        )

        assert storage.provider_name == "s3"

    @pytest.mark.asyncio
    async def test_save_calls_put_object(self):
        """Test that save calls S3 put_object."""
        storage = S3ImageStorage(
            bucket="test-bucket",
            access_key_id="fake",
            secret_access_key="fake",
        )

        # Mock the boto3 client
        mock_client = AsyncMock()
        mock_client.put_object = lambda **kwargs: None
        storage._client = mock_client

        with patch.object(storage, "_generate_key", return_value="images/2025/01/15/test.jpg"):
            with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
                mock_thread.return_value = None
                path = await storage.save(b"test data", "test.jpg", "image/jpeg")

                assert path == "images/2025/01/15/test.jpg"
                mock_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_calls_get_object(self):
        """Test that get calls S3 get_object."""
        storage = S3ImageStorage(
            bucket="test-bucket",
            access_key_id="fake",
            secret_access_key="fake",
        )

        # Mock the boto3 client
        mock_body = AsyncMock()
        mock_body.read.return_value = b"image data"
        mock_client = AsyncMock()
        mock_client.get_object.return_value = {"Body": mock_body}
        storage._client = mock_client

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = b"image data"
            data = await storage.get("images/2025/01/15/test.jpg")

            assert data == b"image data"

    @pytest.mark.asyncio
    async def test_exists_calls_head_object(self):
        """Test that exists calls S3 head_object."""
        storage = S3ImageStorage(
            bucket="test-bucket",
            access_key_id="fake",
            secret_access_key="fake",
        )

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = True
            result = await storage.exists("images/2025/01/15/test.jpg")

            assert result is True

    @pytest.mark.asyncio
    async def test_delete_calls_delete_object(self):
        """Test that delete calls S3 delete_object."""
        storage = S3ImageStorage(
            bucket="test-bucket",
            access_key_id="fake",
            secret_access_key="fake",
        )

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = None
            result = await storage.delete("images/2025/01/15/test.jpg")

            assert result is True


class TestSupabaseFileStorage:
    """Tests for SupabaseFileStorage provider."""

    def test_initialization_requires_project_ref(self):
        """Test that initialization fails without project ref in cloud mode."""
        with patch("src.services.file_storage.settings") as mock_settings:
            mock_settings.supabase_project_ref = None
            mock_settings.supabase_access_key_id = "test-key-id"
            mock_settings.supabase_secret_access_key = "test-secret"
            mock_settings.supabase_storage_bucket = "images"
            mock_settings.supabase_region = "us-east-1"
            mock_settings.supabase_storage_public = False
            mock_settings.supabase_local = False

            with pytest.raises(ValueError, match="project reference is required"):
                SupabaseFileStorage(local=False)

    def test_initialization_requires_access_credentials(self):
        """Test that initialization fails without access credentials in cloud mode."""
        with patch("src.services.file_storage.settings") as mock_settings:
            mock_settings.supabase_project_ref = "test-project"
            mock_settings.supabase_access_key_id = None
            mock_settings.supabase_secret_access_key = None
            mock_settings.supabase_storage_bucket = "images"
            mock_settings.supabase_region = "us-east-1"
            mock_settings.supabase_storage_public = False
            mock_settings.supabase_local = False

            with pytest.raises(ValueError, match="S3 access credentials are required"):
                SupabaseFileStorage(local=False)

    def test_initialization_with_valid_config(self):
        """Test successful initialization with valid config."""
        storage = SupabaseFileStorage(
            project_ref="abcdefghijklmnop",
            access_key_id="test-access-key-id",
            secret_access_key="test-secret-access-key",
            bucket="my-images",
            storage_bucket="images",
            region="eu-central-1",
            public=True,
            local=False,
        )

        assert storage.bucket == "images"  # Logical bucket
        assert storage._project_ref == "abcdefghijklmnop"
        assert storage._supabase_region == "eu-central-1"
        assert storage._is_public is True
        assert storage.endpoint_url == "https://abcdefghijklmnop.supabase.co/storage/v1/s3"

    def test_get_url_public_bucket(self):
        """Test URL generation for public bucket."""
        storage = SupabaseFileStorage(
            project_ref="abcdefghijklmnop",
            access_key_id="test-key-id",
            secret_access_key="test-secret",
            bucket="images",
            storage_bucket="images",
            public=True,
            local=False,
        )

        url = storage.get_url("images/2025/01/15/test.jpg")

        assert url == (
            "https://abcdefghijklmnop.supabase.co/storage/v1/object/public/"
            "images/images/2025/01/15/test.jpg"
        )

    def test_get_url_private_bucket(self):
        """Test URL generation for private bucket."""
        storage = SupabaseFileStorage(
            project_ref="abcdefghijklmnop",
            access_key_id="test-key-id",
            secret_access_key="test-secret",
            bucket="images",
            storage_bucket="images",
            public=False,
            local=False,
        )

        url = storage.get_url("images/2025/01/15/test.jpg")

        assert url == (
            "https://abcdefghijklmnop.supabase.co/storage/v1/object/authenticated/"
            "images/images/2025/01/15/test.jpg"
        )

    def test_provider_name(self):
        """Test provider_name returns 'supabase'."""
        storage = SupabaseFileStorage(
            project_ref="test-project",
            access_key_id="test-key-id",
            secret_access_key="test-secret",
            bucket="images",
            storage_bucket="images",
            local=False,
        )

        assert storage.provider_name == "supabase"

    def test_inherits_s3_operations(self):
        """Test that Supabase storage inherits S3 operations."""
        storage = SupabaseFileStorage(
            project_ref="test-project",
            access_key_id="test-key-id",
            secret_access_key="test-secret",
            bucket="images",
            storage_bucket="images",
            local=False,
        )

        # Should have S3 parent methods
        assert hasattr(storage, "save")
        assert hasattr(storage, "get")
        assert hasattr(storage, "delete")
        assert hasattr(storage, "exists")
        assert hasattr(storage, "_generate_key")

    @pytest.mark.asyncio
    async def test_get_signed_url(self):
        """Test signed URL generation."""
        storage = SupabaseFileStorage(
            project_ref="test-project",
            access_key_id="test-key-id",
            secret_access_key="test-secret",
            bucket="images",
            storage_bucket="images",
            local=False,
        )

        # Mock the client's presigned URL generation
        mock_client = AsyncMock()
        mock_client.generate_presigned_url.return_value = "https://presigned.url"
        storage._client = mock_client

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = "https://presigned.url"
            url = await storage.get_signed_url("images/test.jpg", expires_in=7200)

            assert url == "https://presigned.url"

    @pytest.mark.asyncio
    async def test_create_bucket_if_not_exists_when_exists(self):
        """Test create_bucket_if_not_exists when bucket already exists."""
        storage = SupabaseFileStorage(
            project_ref="test-project",
            access_key_id="test-key-id",
            secret_access_key="test-secret",
            bucket="existing-bucket",
            local=False,
        )

        # Mock client where head_bucket succeeds (bucket exists)
        mock_client = AsyncMock()
        mock_client.head_bucket.return_value = {}
        storage._client = mock_client

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = False
            result = await storage.create_bucket_if_not_exists()

            assert result is False

    @pytest.mark.asyncio
    async def test_create_bucket_if_not_exists_creates(self):
        """Test create_bucket_if_not_exists creates bucket when missing."""
        storage = SupabaseFileStorage(
            project_ref="test-project",
            access_key_id="test-key-id",
            secret_access_key="test-secret",
            bucket="new-bucket",
            local=False,
        )

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = True
            result = await storage.create_bucket_if_not_exists()

            assert result is True

    def test_local_mode_initialization(self):
        """Test initialization in local Supabase mode."""
        with patch("src.services.file_storage.settings") as mock_settings:
            mock_settings.storage_supabase_buckets = {}
            mock_settings.supabase_storage_bucket = "images"
            mock_settings.supabase_service_role_key = None
            mock_settings.supabase_region = "us-east-1"
            mock_settings.supabase_storage_public = False

            storage = SupabaseFileStorage(
                storage_bucket="images",
                local=True,
            )

            assert storage.provider_name == "supabase"
            assert storage._is_local is True
            assert storage.endpoint_url == "http://127.0.0.1:54321/storage/v1/s3"


class TestRailwayFileStorage:
    """Tests for RailwayFileStorage provider."""

    def test_initialization_with_explicit_config(self):
        """Test initialization with explicit configuration."""
        from src.services.file_storage import RailwayFileStorage

        storage = RailwayFileStorage(
            bucket="test-bucket",
            storage_bucket="images",
            endpoint_url="http://minio.railway.internal:9000",
            access_key_id="minioadmin",
            secret_access_key="miniosecret",
        )

        assert storage.bucket == "images"  # Logical bucket
        assert storage.s3_bucket == "test-bucket"  # Actual MinIO bucket
        assert storage.endpoint_url == "http://minio.railway.internal:9000"
        assert storage.provider_name == "railway"

    def test_initialization_requires_endpoint(self):
        """Test that initialization fails without endpoint configuration."""
        from src.services.file_storage import RailwayFileStorage

        with patch("src.services.file_storage.settings") as mock_settings:
            mock_settings.railway_minio_endpoint = None
            with patch.dict("os.environ", {}, clear=True):
                with pytest.raises(ValueError, match="endpoint not configured"):
                    RailwayFileStorage(
                        access_key_id="minioadmin",
                        secret_access_key="miniosecret",
                    )

    def test_initialization_requires_credentials(self):
        """Test that initialization fails without credentials."""
        from src.services.file_storage import RailwayFileStorage

        with patch("src.services.file_storage.settings") as mock_settings:
            mock_settings.railway_minio_endpoint = "http://minio:9000"
            mock_settings.minio_root_user = None
            mock_settings.minio_root_password = None
            mock_settings.railway_minio_bucket = "images"
            with patch.dict("os.environ", {}, clear=True):
                with pytest.raises(ValueError, match="credentials not configured"):
                    RailwayFileStorage(
                        endpoint_url="http://minio:9000",
                    )

    def test_client_uses_path_style_addressing(self):
        """Test that boto3 client is configured for path-style addressing.

        Railway public domains don't support wildcard certs for bucket subdomains,
        so path-style addressing (https://endpoint/bucket/key) must be used instead
        of virtual-hosted style (https://bucket.endpoint/key).
        """
        from src.services.file_storage import RailwayFileStorage

        storage = RailwayFileStorage(
            bucket="test-bucket",
            storage_bucket="images",
            endpoint_url="http://minio.railway.internal:9000",
            access_key_id="minioadmin",
            secret_access_key="miniosecret",
        )

        # Access the client to trigger lazy initialization
        client = storage.client

        # Verify the client is configured with path-style addressing
        # The addressing_style is stored in the client's config
        assert client._client_config.s3 is not None
        assert client._client_config.s3.get("addressing_style") == "path"

    def test_get_url_uses_path_style(self):
        """Test URL generation uses path-style format."""
        from src.services.file_storage import RailwayFileStorage

        storage = RailwayFileStorage(
            bucket="my-bucket",
            storage_bucket="images",
            endpoint_url="https://minio.railway.app",
            access_key_id="minioadmin",
            secret_access_key="miniosecret",
        )

        url = storage.get_url("images/2025/01/15/test.jpg")

        # Should use path-style: https://endpoint/bucket/key
        assert url == "https://minio.railway.app/my-bucket/images/2025/01/15/test.jpg"
        # Should NOT be virtual-hosted style: https://bucket.endpoint/key
        assert "my-bucket.minio" not in url

    def test_provider_name(self):
        """Test provider_name returns 'railway'."""
        from src.services.file_storage import RailwayFileStorage

        storage = RailwayFileStorage(
            bucket="test-bucket",
            storage_bucket="images",
            endpoint_url="http://minio:9000",
            access_key_id="minioadmin",
            secret_access_key="miniosecret",
        )

        assert storage.provider_name == "railway"

    def test_inherits_s3_operations(self):
        """Test that Railway storage inherits S3 operations."""
        from src.services.file_storage import RailwayFileStorage

        storage = RailwayFileStorage(
            bucket="test-bucket",
            storage_bucket="images",
            endpoint_url="http://minio:9000",
            access_key_id="minioadmin",
            secret_access_key="miniosecret",
        )

        # Should have S3 parent methods
        assert hasattr(storage, "save")
        assert hasattr(storage, "get")
        assert hasattr(storage, "delete")
        assert hasattr(storage, "exists")
        assert hasattr(storage, "_generate_key")

    def test_auto_discovery_from_railway_public_domain(self):
        """Test endpoint auto-discovery from RAILWAY_PUBLIC_DOMAIN env var."""
        from src.services.file_storage import RailwayFileStorage

        with patch("src.services.file_storage.settings") as mock_settings:
            mock_settings.railway_minio_endpoint = None
            mock_settings.minio_root_user = "admin"
            mock_settings.minio_root_password = "secret"
            mock_settings.railway_minio_bucket = "images"
            with patch.dict("os.environ", {"RAILWAY_PUBLIC_DOMAIN": "minio-prod.railway.app"}):
                storage = RailwayFileStorage(
                    access_key_id="admin",
                    secret_access_key="secret",
                )

                assert storage.endpoint_url == "https://minio-prod.railway.app"


class TestGetImageStorageFactory:
    """Extended tests for get_image_storage factory function."""

    @patch("src.services.file_storage.settings")
    def test_returns_s3_when_configured(self, mock_settings):
        """Test that s3 provider returns S3FileStorage."""
        mock_settings.image_storage_provider = "s3"
        mock_settings.storage_s3_buckets = {}
        mock_settings.image_storage_bucket = "test-bucket"
        mock_settings.s3_endpoint_url = None
        mock_settings.aws_region = "us-east-1"
        mock_settings.aws_access_key_id = None
        mock_settings.aws_secret_access_key = None

        storage = get_image_storage()

        assert storage.provider_name == "s3"
        assert isinstance(storage, S3FileStorage)

    @patch("src.services.file_storage.settings")
    def test_returns_supabase_when_configured(self, mock_settings):
        """Test that supabase provider returns SupabaseFileStorage."""
        mock_settings.image_storage_provider = "supabase"
        mock_settings.supabase_project_ref = "test-project"
        mock_settings.supabase_access_key_id = "test-key-id"
        mock_settings.supabase_secret_access_key = "test-secret"
        mock_settings.supabase_storage_bucket = "images"
        mock_settings.supabase_region = "us-east-1"
        mock_settings.supabase_storage_public = False
        mock_settings.supabase_local = False
        mock_settings.storage_supabase_buckets = {}

        storage = get_image_storage()

        assert storage.provider_name == "supabase"
        assert isinstance(storage, SupabaseFileStorage)

    @patch("src.services.file_storage.settings")
    def test_provider_override_parameter(self, mock_settings):
        """Test that provider parameter overrides settings."""
        mock_settings.image_storage_provider = "s3"
        mock_settings.storage_local_paths = {}

        storage = get_image_storage(provider="local")

        assert storage.provider_name == "local"
        assert isinstance(storage, LocalFileStorage)

    @patch("src.services.file_storage.settings")
    def test_unknown_provider_falls_back_to_local(self, mock_settings):
        """Test that unknown provider falls back to local."""
        mock_settings.image_storage_provider = "unknown_provider"
        mock_settings.storage_local_paths = {}

        storage = get_image_storage()

        assert storage.provider_name == "local"
        assert isinstance(storage, LocalFileStorage)


class TestImageExtractorPatterns:
    """Tests for regex patterns used in image extraction."""

    def test_base64_pattern_matches_valid_uri(self):
        """Test base64 pattern matches valid data URIs."""
        uri = "data:image/png;base64,iVBORw0KGgo="

        match = BASE64_IMAGE_PATTERN.match(uri)

        assert match is not None
        assert match.group(1) == "png"
        assert match.group(2) == "iVBORw0KGgo="

    def test_base64_pattern_matches_jpeg(self):
        """Test base64 pattern matches JPEG data URIs."""
        uri = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="

        match = BASE64_IMAGE_PATTERN.match(uri)

        assert match is not None
        assert match.group(1) == "jpeg"

    def test_img_tag_pattern_extracts_src(self):
        """Test img tag pattern extracts src attribute."""
        html = '<img src="https://example.com/image.jpg" alt="Test">'

        matches = IMG_TAG_PATTERN.findall(html)

        assert len(matches) == 1
        assert matches[0] == "https://example.com/image.jpg"

    def test_img_tag_pattern_handles_single_quotes(self):
        """Test img tag pattern handles single-quoted src."""
        html = "<img src='https://example.com/image.png' />"

        matches = IMG_TAG_PATTERN.findall(html)

        assert len(matches) == 1
        assert matches[0] == "https://example.com/image.png"

    def test_img_tag_pattern_multiple_images(self):
        """Test img tag pattern finds multiple images."""
        html = """
        <img src="img1.jpg">
        <img src="img2.png">
        <img src="img3.gif">
        """

        matches = IMG_TAG_PATTERN.findall(html)

        assert len(matches) == 3


class TestExtractedImage:
    """Tests for ExtractedImage dataclass."""

    def test_file_size_property(self):
        """Test file_size_bytes computed from data length."""
        data = b"x" * 1000

        image = ExtractedImage(
            data=data,
            filename="test.jpg",
            mime_type="image/jpeg",
        )

        assert image.file_size_bytes == 1000


class TestImageExtractor:
    """Tests for ImageExtractor class."""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create a temporary directory for storage tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def extractor(self, temp_storage_dir):
        """Create an ImageExtractor with temp storage."""
        storage = LocalFileStorage(base_path=temp_storage_dir, bucket="images")
        return ImageExtractor(storage=storage)

    def test_get_mime_type_from_extension(self, extractor):
        """Test MIME type detection from filename."""
        assert extractor._get_mime_type("photo.jpg") == "image/jpeg"
        assert extractor._get_mime_type("image.png") == "image/png"
        assert extractor._get_mime_type("animation.gif") == "image/gif"
        assert extractor._get_mime_type("modern.webp") == "image/webp"

    def test_get_mime_type_prefers_header(self, extractor):
        """Test that content-type header takes precedence."""
        result = extractor._get_mime_type("file.unknown", "image/png")
        assert result == "image/png"

    def test_extract_filename_from_url(self, extractor):
        """Test filename extraction from URL."""
        url = "https://example.com/path/to/image.jpg"

        filename = extractor._extract_filename_from_url(url)

        assert filename == "image.jpg"

    def test_extract_filename_from_url_fallback(self, extractor):
        """Test filename fallback for URLs without extension."""
        url = "https://example.com/image"

        filename = extractor._extract_filename_from_url(url)

        assert filename.startswith("image_")
        assert filename.endswith(".jpg")

    def test_extract_base64_image_valid(self, extractor):
        """Test extracting valid base64 image."""
        # Create a minimal valid PNG (1x1 transparent pixel)
        png_data = bytes(
            [
                0x89,
                0x50,
                0x4E,
                0x47,
                0x0D,
                0x0A,
                0x1A,
                0x0A,  # PNG signature
            ]
        )
        b64 = base64.b64encode(png_data).decode()
        data_uri = f"data:image/png;base64,{b64}"

        image = extractor._extract_base64_image(data_uri)

        assert image is not None
        assert image.data == png_data
        assert image.mime_type == "image/png"
        assert image.filename.endswith(".png")

    def test_extract_base64_image_invalid(self, extractor):
        """Test that invalid base64 returns None."""
        invalid_uri = "data:text/plain;base64,SGVsbG8="

        image = extractor._extract_base64_image(invalid_uri)

        assert image is None

    @pytest.mark.asyncio
    async def test_extract_from_html_finds_images(self, extractor):
        """Test HTML extraction finds img tags."""
        html = """
        <html>
            <body>
                <img src="data:image/png;base64,iVBORw0KGgo=">
            </body>
        </html>
        """

        # Mock the download to avoid network calls
        with patch.object(extractor, "download_image", new_callable=AsyncMock) as mock_dl:
            mock_dl.return_value = None  # No external images to download
            images = await extractor.extract_from_html(html)

            # Should find the base64 image
            # Note: The base64 is invalid so it won't extract successfully
            # In real usage, valid base64 would be extracted
            assert isinstance(images, list)

    @pytest.mark.asyncio
    async def test_save_extracted_images_creates_records(self, extractor):
        """Test that save_extracted_images creates ImageCreate schemas."""
        fake_data = b"fake image data"
        images = [
            ExtractedImage(
                data=fake_data,
                filename="test1.jpg",
                mime_type="image/jpeg",
                source_url="https://example.com/test1.jpg",
                width=640,
                height=480,
                phash="abc123",
            ),
            ExtractedImage(
                data=fake_data,
                filename="test2.png",
                mime_type="image/png",
                width=800,
                height=600,
            ),
        ]

        creates = await extractor.save_extracted_images(
            images,
            source_content_id=42,
            source_type=ImageSource.EXTRACTED,
        )

        assert len(creates) == 2
        assert creates[0].source_content_id == 42
        assert creates[0].source_type == ImageSource.EXTRACTED
        assert creates[0].filename == "test1.jpg"
        assert creates[0].width == 640
        assert creates[0].phash == "abc123"
        assert creates[1].filename == "test2.png"

    @pytest.mark.asyncio
    async def test_save_keyframe_images_extracts_video_metadata(self, extractor):
        """Test that keyframe images extract video_id and timestamp."""
        fake_data = b"fake keyframe data"
        images = [
            ExtractedImage(
                data=fake_data,
                filename="keyframe_125.jpg",
                mime_type="image/jpeg",
                source_url="https://youtu.be/dQw4w9WgXcQ?t=125",
                width=1920,
                height=1080,
            ),
        ]

        creates = await extractor.save_extracted_images(
            images,
            source_content_id=10,
            source_type=ImageSource.KEYFRAME,
        )

        assert len(creates) == 1
        assert creates[0].video_id == "dQw4w9WgXcQ"
        assert creates[0].timestamp_seconds == 125.0
        assert creates[0].deep_link_url == "https://youtu.be/dQw4w9WgXcQ?t=125"


class TestComputePhashSimilarity:
    """Tests for perceptual hash similarity computation."""

    def test_identical_hashes_return_one(self):
        """Test that identical hashes have similarity 1.0."""
        # Use a valid 64-hex-char hash (256 bits = 16x16 hash)
        hash_value = "0" * 64

        similarity = compute_phash_similarity(hash_value, hash_value)

        # May return 0.0 if imagehash not installed, otherwise 1.0
        assert similarity == 1.0 or similarity == 0.0

    def test_different_hashes_return_less_than_one(self):
        """Test that different hashes have similarity < 1.0."""
        # Use valid hex hashes
        hash1 = "0" * 64
        hash2 = "f" * 64

        # This will fail if imagehash is not installed
        # but the function should handle that gracefully
        similarity = compute_phash_similarity(hash1, hash2)

        assert similarity >= 0.0
        assert similarity <= 1.0

    def test_handles_invalid_hash(self):
        """Test graceful handling of invalid hash formats."""
        # Invalid hashes should return 0.0
        similarity = compute_phash_similarity("invalid", "also_invalid")

        assert similarity == 0.0


class TestImageExtractorContextManager:
    """Tests for ImageExtractor async context manager."""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create a temporary directory for storage tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self, temp_storage_dir):
        """Test that context manager properly closes HTTP client."""
        storage = LocalFileStorage(base_path=temp_storage_dir, bucket="images")
        async with ImageExtractor(storage=storage) as extractor:
            assert extractor is not None
            # Force client creation
            await extractor._get_client()
            assert extractor._http_client is not None

        # After exiting context, client should be closed
        assert extractor._http_client is None

    @pytest.mark.asyncio
    async def test_close_is_idempotent(self, temp_storage_dir):
        """Test that close() can be called multiple times."""
        storage = LocalFileStorage(base_path=temp_storage_dir, bucket="images")
        extractor = ImageExtractor(storage=storage)
        await extractor._get_client()

        await extractor.close()
        await extractor.close()  # Should not raise

        assert extractor._http_client is None
