"""File storage abstraction for local and cloud storage providers.

This module provides a unified interface for storing and retrieving files,
supporting both local filesystem and S3-compatible cloud storage.

Supports multiple storage buckets for different content types:
- images: Newsletter images, YouTube keyframes
- podcasts: Generated podcast audio files
- audio-digests: Audio versions of digests

Usage:
    # Get storage for a specific bucket
    storage = get_storage(bucket="images")
    path = await storage.save(file_data, filename, content_type)
    data = await storage.get(path)
    await storage.delete(path)

    # Backward-compatible image storage
    storage = get_image_storage()
"""

import asyncio
import hashlib
import os
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Default bucket configurations
DEFAULT_BUCKET_PATHS = {
    "images": "data/images",
    "podcasts": "data/podcasts",
    "audio-digests": "data/audio-digests",
}


class FileStorageProvider(ABC):
    """Abstract base class for file storage providers."""

    @abstractmethod
    async def save(
        self,
        data: bytes | BinaryIO,
        filename: str,
        content_type: str,
        **metadata: str,
    ) -> str:
        """
        Save file data to storage.

        Args:
            data: File data as bytes or file-like object
            filename: Original filename (used for extension)
            content_type: MIME type of the file
            **metadata: Additional metadata to store

        Returns:
            Storage path (relative to storage root)
        """
        ...

    @abstractmethod
    async def get(self, path: str) -> bytes:
        """
        Retrieve file data from storage.

        Args:
            path: Storage path returned by save()

        Returns:
            File data as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        ...

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """
        Delete file from storage.

        Args:
            path: Storage path returned by save()

        Returns:
            True if deleted, False if not found
        """
        ...

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """
        Check if file exists in storage.

        Args:
            path: Storage path to check

        Returns:
            True if exists, False otherwise
        """
        ...

    @abstractmethod
    def get_url(self, path: str) -> str:
        """
        Get URL for accessing the file.

        Args:
            path: Storage path

        Returns:
            URL string (file:// for local, https:// for cloud)
        """
        ...

    def get_local_path(self, path: str) -> Path | None:
        """
        Get the local filesystem path if available.

        Args:
            path: Storage path

        Returns:
            Path object if file is local, None otherwise
        """
        return None

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'local', 's3')."""
        ...

    @property
    @abstractmethod
    def bucket(self) -> str:
        """Return the bucket name this provider is configured for."""
        ...


class LocalFileStorage(FileStorageProvider):
    """Local filesystem file storage provider.

    Organizes files in date-based directories:
    {base_path}/{year}/{month}/{day}/{uuid}_{filename}
    """

    def __init__(
        self,
        base_path: str | None = None,
        bucket: str = "images",
    ) -> None:
        """
        Initialize local storage provider.

        Args:
            base_path: Base directory for file storage.
                       Defaults to settings-based path for the bucket.
            bucket: Bucket name (e.g., 'images', 'podcasts')
        """
        self._bucket = bucket

        if base_path:
            self.base_path = Path(base_path)
        else:
            # Get bucket-specific path from settings or use default
            bucket_paths = getattr(settings, "storage_local_paths", None) or {}
            default_path = DEFAULT_BUCKET_PATHS.get(bucket, f"data/{bucket}")
            self.base_path = Path(bucket_paths.get(bucket, default_path))

        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"LocalFileStorage initialized for bucket '{bucket}' at {self.base_path}")

    @property
    def bucket(self) -> str:
        return self._bucket

    def _generate_path(self, filename: str) -> tuple[Path, str]:
        """
        Generate storage path with date-based organization.

        Returns:
            Tuple of (full_path, relative_path)
        """
        now = datetime.now(UTC)
        date_dir = f"{now.year}/{now.month:02d}/{now.day:02d}"

        # Generate unique filename with UUID prefix (preserves original extension)
        unique_filename = f"{uuid.uuid4().hex[:12]}_{filename}"

        relative_path = f"{self._bucket}/{date_dir}/{unique_filename}"
        full_path = self.base_path / date_dir / unique_filename

        return full_path, relative_path

    async def save(
        self,
        data: bytes | BinaryIO,
        filename: str,
        content_type: str,
        **metadata: str,
    ) -> str:
        """Save file to local filesystem."""
        full_path, relative_path = self._generate_path(filename)

        # Ensure directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Get bytes if file-like object
        if hasattr(data, "read"):
            data = data.read()  # type: ignore[union-attr]

        # Write file in thread pool to avoid blocking
        def _write() -> None:
            with open(full_path, "wb") as f:
                f.write(data)  # type: ignore[arg-type]

        await asyncio.to_thread(_write)

        logger.debug(f"Saved file to {relative_path}")
        return relative_path

    def _resolve_path(self, path: str) -> Path:
        """Resolve a relative storage path to a full filesystem path.

        The relative path format is '{bucket}/{year}/{month}/{day}/{filename}'.
        We strip the bucket prefix since files are stored under base_path.
        """
        # Handle both old 'images/' prefix and new bucket prefixes
        bucket_prefix = f"{self._bucket}/"
        if path.startswith(bucket_prefix):
            path = path[len(bucket_prefix) :]
        elif path.startswith("images/"):
            # Backward compatibility for old image paths
            path = path[7:]  # Remove 'images/'

        # Security check: Prevent path traversal
        try:
            full_path = (self.base_path / path).resolve()
            base_resolved = self.base_path.resolve()
            if not full_path.is_relative_to(base_resolved):
                logger.warning(f"Path traversal attempt blocked: {path}")
                raise ValueError(f"Path traversal detected: {path}")
        except Exception as e:
            # Handle edge cases (e.g. invalid paths)
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Invalid path: {path}") from e

        return full_path

    async def get(self, path: str) -> bytes:
        """Retrieve file from local filesystem."""
        full_path = self._resolve_path(path)

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        def _read() -> bytes:
            with open(full_path, "rb") as f:
                return f.read()

        return await asyncio.to_thread(_read)

    async def delete(self, path: str) -> bool:
        """Delete file from local filesystem."""
        full_path = self._resolve_path(path)

        if not full_path.exists():
            return False

        def _delete() -> None:
            os.remove(full_path)

        await asyncio.to_thread(_delete)
        logger.debug(f"Deleted file: {path}")
        return True

    async def exists(self, path: str) -> bool:
        """Check if file exists in local filesystem."""
        full_path = self._resolve_path(path)
        return full_path.exists()

    def get_url(self, path: str) -> str:
        """Get file:// URL for local file."""
        full_path = self._resolve_path(path)
        return f"file://{full_path.absolute()}"

    def get_local_path(self, path: str) -> Path | None:
        """Get the resolved local path."""
        try:
            return self._resolve_path(path)
        except ValueError:
            # If path traversal detected or invalid path, return None
            # The caller will likely try other methods or fail later
            return None

    @property
    def provider_name(self) -> str:
        return "local"


class S3FileStorage(FileStorageProvider):
    """S3-compatible cloud file storage provider.

    Supports AWS S3, MinIO, and other S3-compatible services.
    Requires boto3 to be installed.

    Authentication methods (in order of precedence):
    1. Explicit credentials passed to constructor
    2. Settings (aws_access_key_id, aws_secret_access_key)
    3. boto3 default credential chain (env vars, ~/.aws/credentials, IAM role)
    """

    def __init__(
        self,
        bucket: str | None = None,
        storage_bucket: str = "images",
        endpoint_url: str | None = None,
        region: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        """
        Initialize S3 storage provider.

        Args:
            bucket: S3 bucket name. Defaults to settings-based bucket for storage_bucket
            storage_bucket: Logical bucket name (e.g., 'images', 'podcasts')
            endpoint_url: Custom endpoint for S3-compatible services
            region: AWS region
            access_key_id: AWS access key ID (optional, uses boto3 defaults)
            secret_access_key: AWS secret access key (optional, uses boto3 defaults)
        """
        self._storage_bucket = storage_bucket

        # Get S3 bucket name from settings or use provided
        if bucket:
            self._bucket = bucket
        else:
            s3_buckets = getattr(settings, "storage_s3_buckets", {})
            default_bucket = getattr(settings, "image_storage_bucket", "newsletter-images")
            self._bucket = s3_buckets.get(storage_bucket, default_bucket)

        self.endpoint_url = endpoint_url or getattr(settings, "s3_endpoint_url", None)
        self.region = region or getattr(settings, "aws_region", "us-east-1")
        self.access_key_id = access_key_id or getattr(settings, "aws_access_key_id", None)
        self.secret_access_key = secret_access_key or getattr(
            settings, "aws_secret_access_key", None
        )
        self._client = None
        logger.debug(
            f"S3FileStorage initialized for bucket '{storage_bucket}' (S3 bucket: {self._bucket})"
        )

    @property
    def bucket(self) -> str:
        return self._storage_bucket

    @property
    def s3_bucket(self) -> str:
        """Return the actual S3 bucket name."""
        return self._bucket

    @property
    def client(self):  # type: ignore[no-untyped-def]
        """Lazy-load boto3 client."""
        if self._client is None:
            try:
                import boto3
            except ImportError:
                raise ImportError(
                    "boto3 is required for S3 storage. Install with: pip install boto3"
                )

            # Build client kwargs
            client_kwargs: dict[str, str | None] = {
                "region_name": self.region,
            }
            if self.endpoint_url:
                client_kwargs["endpoint_url"] = self.endpoint_url

            # Only pass credentials if explicitly provided
            if self.access_key_id and self.secret_access_key:
                client_kwargs["aws_access_key_id"] = self.access_key_id
                client_kwargs["aws_secret_access_key"] = self.secret_access_key

            self._client = boto3.client("s3", **client_kwargs)
        return self._client

    def _generate_key(self, filename: str) -> str:
        """Generate S3 key with date-based organization."""
        now = datetime.now(UTC)
        date_prefix = f"{now.year}/{now.month:02d}/{now.day:02d}"
        unique_filename = f"{uuid.uuid4().hex[:12]}_{filename}"
        return f"{self._storage_bucket}/{date_prefix}/{unique_filename}"

    async def save(
        self,
        data: bytes | BinaryIO,
        filename: str,
        content_type: str,
        **metadata: str,
    ) -> str:
        """Save file to S3."""
        key = self._generate_key(filename)

        # Get bytes if file-like object
        if hasattr(data, "read"):
            data = data.read()  # type: ignore[union-attr]

        def _upload() -> None:
            self.client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                Metadata=metadata,
            )

        await asyncio.to_thread(_upload)
        logger.debug(f"Saved file to s3://{self._bucket}/{key}")
        return key

    async def get(self, path: str) -> bytes:
        """Retrieve file from S3."""

        def _download() -> bytes:
            response = self.client.get_object(Bucket=self._bucket, Key=path)
            return response["Body"].read()

        try:
            return await asyncio.to_thread(_download)
        except Exception as e:
            raise FileNotFoundError(f"File not found: {path}") from e

    async def delete(self, path: str) -> bool:
        """Delete file from S3."""

        def _delete() -> None:
            self.client.delete_object(Bucket=self._bucket, Key=path)

        try:
            await asyncio.to_thread(_delete)
            logger.debug(f"Deleted file from s3://{self._bucket}/{path}")
            return True
        except Exception:
            return False

    async def exists(self, path: str) -> bool:
        """Check if file exists in S3."""

        def _head() -> bool:
            try:
                self.client.head_object(Bucket=self._bucket, Key=path)
                return True
            except Exception:
                return False

        return await asyncio.to_thread(_head)

    def get_url(self, path: str) -> str:
        """Get URL for S3 file."""
        if self.endpoint_url:
            return f"{self.endpoint_url}/{self._bucket}/{path}"
        return f"https://{self._bucket}.s3.{self.region}.amazonaws.com/{path}"

    async def get_signed_url(self, path: str, expires_in: int = 3600) -> str:
        """Generate a signed URL for temporary access to private objects.

        Args:
            path: Storage path (key) of the file
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            Pre-signed URL with temporary access
        """

        def _generate_presigned() -> str:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": path},
                ExpiresIn=expires_in,
            )

        return await asyncio.to_thread(_generate_presigned)

    @property
    def provider_name(self) -> str:
        return "s3"


class SupabaseFileStorage(S3FileStorage):
    """Supabase Storage provider using S3-compatible API.

    Supabase Storage exposes an S3-compatible endpoint for each project.
    This provider configures the S3 client with Supabase-specific settings.

    Cloud Configuration:
    - Endpoint: https://{project_ref}.supabase.co/storage/v1/s3
    - Access Key ID: From SUPABASE_ACCESS_KEY_ID
    - Secret Access Key: From SUPABASE_SECRET_ACCESS_KEY

    Local Configuration (SUPABASE_LOCAL=true):
    - Endpoint: http://127.0.0.1:54321/storage/v1/s3
    - Uses local development keys automatically

    Credentials can be obtained from:
    Supabase Dashboard > Project Settings > API > S3 Access Keys
    """

    # Default local Supabase service role key (from supabase init)
    _LOCAL_SERVICE_ROLE_KEY = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0."
        "EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"
    )

    def __init__(
        self,
        bucket: str | None = None,
        storage_bucket: str = "images",
        project_ref: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        region: str | None = None,
        public: bool | None = None,
        local: bool | None = None,
    ) -> None:
        """
        Initialize Supabase storage provider.

        Args:
            bucket: Supabase bucket name. Defaults to settings-based bucket
            storage_bucket: Logical bucket name (e.g., 'images', 'podcasts')
            project_ref: Supabase project reference. Defaults to settings.supabase_project_ref
            access_key_id: S3 access key ID. Defaults to settings.supabase_access_key_id
            secret_access_key: S3 secret access key. Defaults to settings.supabase_secret_access_key
            region: Supabase region. Defaults to settings.supabase_region
            public: Whether bucket is public. Defaults to settings.supabase_storage_public
            local: Whether to use local Supabase. Defaults to settings.supabase_local
        """
        # Check for local mode first
        self._is_local = local if local is not None else getattr(settings, "supabase_local", False)

        self._supabase_region = region or getattr(settings, "supabase_region", "us-east-1")
        self._is_public = (
            public if public is not None else getattr(settings, "supabase_storage_public", False)
        )

        if self._is_local:
            # Local Supabase configuration
            self._project_ref = project_ref or "local"
            # Use service role key for full access to storage
            self._access_key_id = access_key_id or "supabase"
            self._secret_access_key = secret_access_key or getattr(
                settings, "supabase_service_role_key", self._LOCAL_SERVICE_ROLE_KEY
            )
            endpoint_url = "http://127.0.0.1:54321/storage/v1/s3"

            logger.info(
                f"SupabaseFileStorage initialized in LOCAL mode for bucket '{storage_bucket}'"
            )
        else:
            # Cloud Supabase configuration
            self._project_ref = project_ref or getattr(settings, "supabase_project_ref", None)
            self._access_key_id = access_key_id or getattr(settings, "supabase_access_key_id", None)
            self._secret_access_key = secret_access_key or getattr(
                settings, "supabase_secret_access_key", None
            )

            if not self._project_ref:
                raise ValueError(
                    "Supabase project reference is required. "
                    "Set SUPABASE_PROJECT_REF in environment "
                    "(or set SUPABASE_LOCAL=true for local development)."
                )

            if not self._access_key_id or not self._secret_access_key:
                raise ValueError(
                    "Supabase S3 access credentials are required for storage. "
                    "Set SUPABASE_ACCESS_KEY_ID and SUPABASE_SECRET_ACCESS_KEY in environment. "
                    "Get these from Supabase Dashboard > Project Settings > API > S3 Access Keys. "
                    "(Or set SUPABASE_LOCAL=true for local development)."
                )

            # Construct Supabase S3 endpoint
            endpoint_url = f"https://{self._project_ref}.supabase.co/storage/v1/s3"

        # Get Supabase bucket name from settings
        if bucket:
            bucket_name = bucket
        else:
            supabase_buckets = getattr(settings, "storage_supabase_buckets", {})
            default_bucket = getattr(settings, "supabase_storage_bucket", "images")
            bucket_name = supabase_buckets.get(storage_bucket, default_bucket)

        # Initialize parent S3 client with Supabase credentials
        super().__init__(
            bucket=bucket_name,
            storage_bucket=storage_bucket,
            endpoint_url=endpoint_url,
            region=self._supabase_region,
            access_key_id=self._access_key_id,
            secret_access_key=self._secret_access_key,
        )

        logger.debug(
            f"SupabaseFileStorage initialized for "
            f"{'local' if self._is_local else self._project_ref}, "
            f"bucket '{storage_bucket}' (Supabase bucket: {bucket_name})"
        )

    def get_url(self, path: str) -> str:
        """Get public or authenticated URL for Supabase file.

        For public buckets, returns the direct public URL.
        For private buckets, returns a URL that requires authentication.
        For local Supabase, returns the local endpoint URL.

        Args:
            path: Storage path (key) of the file

        Returns:
            URL string for accessing the file
        """
        if self._is_local:
            # Local Supabase URL format
            if self._is_public:
                return f"http://127.0.0.1:54321/storage/v1/object/public/{self._bucket}/{path}"
            else:
                return (
                    f"http://127.0.0.1:54321/storage/v1/object/authenticated/{self._bucket}/{path}"
                )

        if self._is_public:
            # Public bucket URL format
            return (
                f"https://{self._project_ref}.supabase.co/storage/v1/object/public/"
                f"{self._bucket}/{path}"
            )
        else:
            # Authenticated bucket URL format (requires auth header)
            return (
                f"https://{self._project_ref}.supabase.co/storage/v1/object/authenticated/"
                f"{self._bucket}/{path}"
            )

    async def create_bucket_if_not_exists(self) -> bool:
        """Create the storage bucket if it doesn't exist.

        Returns:
            True if bucket was created, False if it already existed
        """

        def _create_bucket() -> bool:
            try:
                self.client.head_bucket(Bucket=self._bucket)
                return False  # Bucket exists
            except Exception:
                # Bucket doesn't exist, create it
                self.client.create_bucket(Bucket=self._bucket)
                logger.info(f"Created Supabase storage bucket: {self._bucket}")
                return True

        return await asyncio.to_thread(_create_bucket)

    @property
    def provider_name(self) -> str:
        return "supabase"


class RailwayFileStorage(S3FileStorage):
    """Railway MinIO storage provider.

    Railway provides MinIO as an S3-compatible storage service.
    This provider configures the S3 client with Railway-specific settings.

    Environment variables (auto-injected by Railway):
    - MINIO_ROOT_USER: MinIO access key
    - MINIO_ROOT_PASSWORD: MinIO secret key
    - RAILWAY_PUBLIC_DOMAIN: Public endpoint for the MinIO service

    Configuration:
    - RAILWAY_MINIO_ENDPOINT: Override endpoint URL
    - RAILWAY_MINIO_BUCKET: Override bucket name
    """

    def __init__(
        self,
        bucket: str | None = None,
        storage_bucket: str = "images",
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        """
        Initialize Railway MinIO storage provider.

        Args:
            bucket: MinIO bucket name. Defaults to settings or MINIO_BUCKET env var
            storage_bucket: Logical bucket name (e.g., 'images', 'podcasts')
            endpoint_url: MinIO endpoint URL. Auto-discovered from RAILWAY_PUBLIC_DOMAIN
            access_key_id: MinIO access key. Defaults to MINIO_ROOT_USER
            secret_access_key: MinIO secret key. Defaults to MINIO_ROOT_PASSWORD
        """
        import os

        # Get endpoint URL (priority: explicit > settings > Railway env var)
        if endpoint_url:
            self._endpoint = endpoint_url
        elif getattr(settings, "railway_minio_endpoint", None):
            self._endpoint = settings.railway_minio_endpoint
        else:
            # Auto-discover from Railway's public domain
            railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
            if railway_domain:
                self._endpoint = f"https://{railway_domain}"
            else:
                raise ValueError(
                    "Railway MinIO endpoint not configured. Set RAILWAY_MINIO_ENDPOINT "
                    "or ensure RAILWAY_PUBLIC_DOMAIN is available."
                )

        # Get credentials (priority: explicit > settings > Railway env var)
        self._access_key = (
            access_key_id
            or getattr(settings, "minio_root_user", None)
            or os.environ.get("MINIO_ROOT_USER")
        )
        self._secret_key = (
            secret_access_key
            or getattr(settings, "minio_root_password", None)
            or os.environ.get("MINIO_ROOT_PASSWORD")
        )

        if not self._access_key or not self._secret_key:
            raise ValueError(
                "Railway MinIO credentials not configured. Set MINIO_ROOT_USER and "
                "MINIO_ROOT_PASSWORD in your environment."
            )

        # Get bucket name (priority: explicit > settings > env var)
        if bucket:
            bucket_name = bucket
        elif getattr(settings, "railway_minio_bucket", None):
            bucket_name = settings.railway_minio_bucket
        else:
            bucket_name = os.environ.get("MINIO_BUCKET", "images")

        # Initialize parent S3 client with Railway MinIO configuration
        super().__init__(
            bucket=bucket_name,
            storage_bucket=storage_bucket,
            endpoint_url=self._endpoint,
            region="us-east-1",  # MinIO doesn't require a real region
            access_key_id=self._access_key,
            secret_access_key=self._secret_key,
        )

        logger.debug(
            f"RailwayFileStorage initialized for bucket '{storage_bucket}' "
            f"(MinIO bucket: {bucket_name}, endpoint: {self._endpoint})"
        )

    @property
    def client(self):  # type: ignore[no-untyped-def]
        """Lazy-load boto3 client with path-style addressing for Railway MinIO.

        Railway public domains don't support wildcard certs or DNS for bucket
        subdomains, so we must use path-style addressing (https://endpoint/bucket/key)
        instead of virtual-hosted style (https://bucket.endpoint/key).
        """
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError:
                raise ImportError(
                    "boto3 is required for Railway storage. Install with: pip install boto3"
                )

            # Force path-style addressing for MinIO compatibility
            # This avoids TLS/DNS errors with Railway public domains
            s3_config = Config(s3={"addressing_style": "path"})

            self._client = boto3.client(
                "s3",
                region_name=self.region,
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                config=s3_config,
            )
        return self._client

    def get_url(self, path: str) -> str:
        """Get URL for Railway MinIO file.

        Args:
            path: Storage path (key) of the file

        Returns:
            URL string for accessing the file
        """
        return f"{self._endpoint}/{self._bucket}/{path}"

    @property
    def provider_name(self) -> str:
        return "railway"


def get_storage(
    bucket: str = "images",
    provider: str | None = None,
) -> FileStorageProvider:
    """
    Get configured file storage provider for a specific bucket.

    Returns provider based on configuration:
    - Per-bucket provider from STORAGE_BUCKET_PROVIDERS
    - Default STORAGE_PROVIDER setting
    - Falls back to "local"

    Provider types:
    - "local" (default): LocalFileStorage
    - "s3": S3FileStorage
    - "supabase": SupabaseFileStorage
    - "railway": RailwayFileStorage (MinIO)

    Args:
        bucket: Logical bucket name (e.g., 'images', 'podcasts', 'audio-digests')
        provider: Override the configured provider (optional)

    Returns:
        FileStorageProvider instance

    Raises:
        ValueError: If Supabase provider is requested but not configured
    """
    if provider is None:
        # Check per-bucket provider configuration
        bucket_providers = getattr(settings, "storage_bucket_providers", None) or {}
        if bucket in bucket_providers:
            provider = bucket_providers[bucket]
        else:
            # Fall back to default storage provider or image_storage_provider for backward compat
            provider = getattr(
                settings,
                "storage_provider",
                getattr(settings, "image_storage_provider", "local"),
            )

    match provider:
        case "s3":
            return S3FileStorage(storage_bucket=bucket)
        case "supabase":
            return SupabaseFileStorage(storage_bucket=bucket)
        case "railway":
            return RailwayFileStorage(storage_bucket=bucket)
        case _:  # "local" or any other value
            return LocalFileStorage(bucket=bucket)


def get_image_storage(provider: str | None = None) -> FileStorageProvider:
    """
    Get configured image storage provider.

    This is a backward-compatible alias for get_storage(bucket="images").

    Returns provider based on IMAGE_STORAGE_PROVIDER setting:
    - "local" (default): LocalFileStorage
    - "s3": S3FileStorage
    - "supabase": SupabaseFileStorage

    Args:
        provider: Override the configured provider (optional)

    Returns:
        FileStorageProvider instance
    """
    # For backward compatibility, use image_storage_provider setting
    if provider is None:
        provider = getattr(settings, "image_storage_provider", "local")
    return get_storage(bucket="images", provider=provider)


def compute_file_hash(data: bytes) -> str:
    """
    Compute SHA-256 hash of file data.

    Args:
        data: File content as bytes

    Returns:
        Hex-encoded SHA-256 hash
    """
    return hashlib.sha256(data).hexdigest()


# Backward-compatible aliases
ImageStorageProvider = FileStorageProvider
LocalImageStorage = LocalFileStorage
S3ImageStorage = S3FileStorage
SupabaseImageStorage = SupabaseFileStorage
RailwayImageStorage = RailwayFileStorage
