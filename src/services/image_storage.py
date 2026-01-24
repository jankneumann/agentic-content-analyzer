"""Image storage abstraction for local and cloud storage providers.

This module provides a unified interface for storing and retrieving images,
supporting both local filesystem and S3-compatible cloud storage.

Usage:
    storage = get_image_storage()
    path = await storage.save(image_data, filename, content_type)
    data = await storage.get(path)
    await storage.delete(path)
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


class ImageStorageProvider(ABC):
    """Abstract base class for image storage providers."""

    @abstractmethod
    async def save(
        self,
        data: bytes | BinaryIO,
        filename: str,
        content_type: str,
        **metadata: str,
    ) -> str:
        """
        Save image data to storage.

        Args:
            data: Image data as bytes or file-like object
            filename: Original filename (used for extension)
            content_type: MIME type of the image
            **metadata: Additional metadata to store

        Returns:
            Storage path (relative to storage root)
        """
        ...

    @abstractmethod
    async def get(self, path: str) -> bytes:
        """
        Retrieve image data from storage.

        Args:
            path: Storage path returned by save()

        Returns:
            Image data as bytes

        Raises:
            FileNotFoundError: If image doesn't exist
        """
        ...

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """
        Delete image from storage.

        Args:
            path: Storage path returned by save()

        Returns:
            True if deleted, False if not found
        """
        ...

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """
        Check if image exists in storage.

        Args:
            path: Storage path to check

        Returns:
            True if exists, False otherwise
        """
        ...

    @abstractmethod
    def get_url(self, path: str) -> str:
        """
        Get URL for accessing the image.

        Args:
            path: Storage path

        Returns:
            URL string (file:// for local, https:// for cloud)
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'local', 's3')."""
        ...


class LocalImageStorage(ImageStorageProvider):
    """Local filesystem image storage provider.

    Organizes images in date-based directories:
    {base_path}/images/{year}/{month}/{day}/{uuid}_{filename}
    """

    def __init__(self, base_path: str | None = None) -> None:
        """
        Initialize local storage provider.

        Args:
            base_path: Base directory for image storage.
                       Defaults to settings.image_storage_path
        """
        self.base_path = Path(base_path or getattr(settings, "image_storage_path", "data/images"))
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"LocalImageStorage initialized at {self.base_path}")

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

        relative_path = f"images/{date_dir}/{unique_filename}"
        full_path = self.base_path / date_dir / unique_filename

        return full_path, relative_path

    async def save(
        self,
        data: bytes | BinaryIO,
        filename: str,
        content_type: str,
        **metadata: str,
    ) -> str:
        """Save image to local filesystem."""
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

        logger.debug(f"Saved image to {relative_path}")
        return relative_path

    def _resolve_path(self, path: str) -> Path:
        """Resolve a relative storage path to a full filesystem path.

        The relative path format is 'images/{year}/{month}/{day}/{filename}'.
        We strip the 'images/' prefix since files are stored under base_path.
        """
        if path.startswith("images/"):
            # Strip 'images/' prefix - files stored in base_path/{date}/{file}
            path = path[7:]  # Remove 'images/'
        return self.base_path / path

    async def get(self, path: str) -> bytes:
        """Retrieve image from local filesystem."""
        full_path = self._resolve_path(path)

        if not full_path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        def _read() -> bytes:
            with open(full_path, "rb") as f:
                return f.read()

        return await asyncio.to_thread(_read)

    async def delete(self, path: str) -> bool:
        """Delete image from local filesystem."""
        full_path = self._resolve_path(path)

        if not full_path.exists():
            return False

        def _delete() -> None:
            os.remove(full_path)

        await asyncio.to_thread(_delete)
        logger.debug(f"Deleted image: {path}")
        return True

    async def exists(self, path: str) -> bool:
        """Check if image exists in local filesystem."""
        full_path = self._resolve_path(path)
        return full_path.exists()

    def get_url(self, path: str) -> str:
        """Get file:// URL for local image."""
        full_path = self._resolve_path(path)
        return f"file://{full_path.absolute()}"

    @property
    def provider_name(self) -> str:
        return "local"


class S3ImageStorage(ImageStorageProvider):
    """S3-compatible cloud image storage provider.

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
        endpoint_url: str | None = None,
        region: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        """
        Initialize S3 storage provider.

        Args:
            bucket: S3 bucket name. Defaults to settings.image_storage_bucket
            endpoint_url: Custom endpoint for S3-compatible services
            region: AWS region
            access_key_id: AWS access key ID (optional, uses boto3 defaults)
            secret_access_key: AWS secret access key (optional, uses boto3 defaults)
        """
        self.bucket = bucket or getattr(settings, "image_storage_bucket", "newsletter-images")
        self.endpoint_url = endpoint_url or getattr(settings, "s3_endpoint_url", None)
        self.region = region or getattr(settings, "aws_region", "us-east-1")
        self.access_key_id = access_key_id or getattr(settings, "aws_access_key_id", None)
        self.secret_access_key = secret_access_key or getattr(
            settings, "aws_secret_access_key", None
        )
        self._client = None
        logger.debug(f"S3ImageStorage initialized for bucket {self.bucket}")

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
        return f"images/{date_prefix}/{unique_filename}"

    async def save(
        self,
        data: bytes | BinaryIO,
        filename: str,
        content_type: str,
        **metadata: str,
    ) -> str:
        """Save image to S3."""
        key = self._generate_key(filename)

        # Get bytes if file-like object
        if hasattr(data, "read"):
            data = data.read()  # type: ignore[union-attr]

        def _upload() -> None:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                Metadata=metadata,
            )

        await asyncio.to_thread(_upload)
        logger.debug(f"Saved image to s3://{self.bucket}/{key}")
        return key

    async def get(self, path: str) -> bytes:
        """Retrieve image from S3."""

        def _download() -> bytes:
            response = self.client.get_object(Bucket=self.bucket, Key=path)
            return response["Body"].read()

        try:
            return await asyncio.to_thread(_download)
        except Exception as e:
            raise FileNotFoundError(f"Image not found: {path}") from e

    async def delete(self, path: str) -> bool:
        """Delete image from S3."""

        def _delete() -> None:
            self.client.delete_object(Bucket=self.bucket, Key=path)

        try:
            await asyncio.to_thread(_delete)
            logger.debug(f"Deleted image from s3://{self.bucket}/{path}")
            return True
        except Exception:
            return False

    async def exists(self, path: str) -> bool:
        """Check if image exists in S3."""

        def _head() -> bool:
            try:
                self.client.head_object(Bucket=self.bucket, Key=path)
                return True
            except Exception:
                return False

        return await asyncio.to_thread(_head)

    def get_url(self, path: str) -> str:
        """Get URL for S3 image."""
        if self.endpoint_url:
            return f"{self.endpoint_url}/{self.bucket}/{path}"
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{path}"

    @property
    def provider_name(self) -> str:
        return "s3"


class SupabaseImageStorage(S3ImageStorage):
    """Supabase Storage provider using S3-compatible API.

    Supabase Storage exposes an S3-compatible endpoint for each project.
    This provider configures the S3 client with Supabase-specific settings.

    Configuration:
    - Endpoint: https://{project_ref}.supabase.co/storage/v1/s3
    - Access Key ID: From SUPABASE_ACCESS_KEY_ID
    - Secret Access Key: From SUPABASE_SECRET_ACCESS_KEY

    Credentials can be obtained from:
    Supabase Dashboard > Project Settings > API > S3 Access Keys
    """

    def __init__(
        self,
        bucket: str | None = None,
        project_ref: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        region: str | None = None,
        public: bool | None = None,
    ) -> None:
        """
        Initialize Supabase storage provider.

        Args:
            bucket: Storage bucket name. Defaults to settings.supabase_storage_bucket
            project_ref: Supabase project reference. Defaults to settings.supabase_project_ref
            access_key_id: S3 access key ID. Defaults to settings.supabase_access_key_id
            secret_access_key: S3 secret access key. Defaults to settings.supabase_secret_access_key
            region: Supabase region. Defaults to settings.supabase_region
            public: Whether bucket is public. Defaults to settings.supabase_storage_public
        """
        self._project_ref = project_ref or getattr(settings, "supabase_project_ref", None)
        self._access_key_id = access_key_id or getattr(settings, "supabase_access_key_id", None)
        self._secret_access_key = secret_access_key or getattr(
            settings, "supabase_secret_access_key", None
        )
        self._supabase_region = region or getattr(settings, "supabase_region", "us-east-1")
        self._is_public = (
            public if public is not None else getattr(settings, "supabase_storage_public", False)
        )

        if not self._project_ref:
            raise ValueError(
                "Supabase project reference is required. "
                "Set SUPABASE_PROJECT_REF in environment."
            )

        if not self._access_key_id or not self._secret_access_key:
            raise ValueError(
                "Supabase S3 access credentials are required for storage. "
                "Set SUPABASE_ACCESS_KEY_ID and SUPABASE_SECRET_ACCESS_KEY in environment. "
                "Get these from Supabase Dashboard > Project Settings > API > S3 Access Keys."
            )

        # Construct Supabase S3 endpoint
        endpoint_url = f"https://{self._project_ref}.supabase.co/storage/v1/s3"
        bucket_name = bucket or getattr(settings, "supabase_storage_bucket", "images")

        # Initialize parent S3 client with Supabase credentials
        super().__init__(
            bucket=bucket_name,
            endpoint_url=endpoint_url,
            region=self._supabase_region,
            access_key_id=self._access_key_id,
            secret_access_key=self._secret_access_key,
        )

        logger.debug(
            f"SupabaseImageStorage initialized for project {self._project_ref}, "
            f"bucket {bucket_name}"
        )

    def get_url(self, path: str) -> str:
        """Get public or authenticated URL for Supabase image.

        For public buckets, returns the direct public URL.
        For private buckets, returns a URL that requires authentication.

        Args:
            path: Storage path (key) of the image

        Returns:
            URL string for accessing the image
        """
        if self._is_public:
            # Public bucket URL format
            return (
                f"https://{self._project_ref}.supabase.co/storage/v1/object/public/"
                f"{self.bucket}/{path}"
            )
        else:
            # Authenticated bucket URL format (requires auth header)
            return (
                f"https://{self._project_ref}.supabase.co/storage/v1/object/authenticated/"
                f"{self.bucket}/{path}"
            )

    async def get_signed_url(self, path: str, expires_in: int = 3600) -> str:
        """Generate a signed URL for temporary access to private objects.

        Args:
            path: Storage path (key) of the image
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            Pre-signed URL with temporary access
        """

        def _generate_presigned() -> str:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": path},
                ExpiresIn=expires_in,
            )

        return await asyncio.to_thread(_generate_presigned)

    async def create_bucket_if_not_exists(self) -> bool:
        """Create the storage bucket if it doesn't exist.

        Returns:
            True if bucket was created, False if it already existed
        """

        def _create_bucket() -> bool:
            try:
                self.client.head_bucket(Bucket=self.bucket)
                return False  # Bucket exists
            except Exception:
                # Bucket doesn't exist, create it
                self.client.create_bucket(Bucket=self.bucket)
                logger.info(f"Created Supabase storage bucket: {self.bucket}")
                return True

        return await asyncio.to_thread(_create_bucket)

    @property
    def provider_name(self) -> str:
        return "supabase"


def get_image_storage(provider: str | None = None) -> ImageStorageProvider:
    """
    Get configured image storage provider.

    Returns provider based on IMAGE_STORAGE_PROVIDER setting:
    - "local" (default): LocalImageStorage
    - "s3": S3ImageStorage
    - "supabase": SupabaseImageStorage

    Args:
        provider: Override the configured provider (optional)

    Returns:
        ImageStorageProvider instance

    Raises:
        ValueError: If Supabase provider is requested but not configured
    """
    provider = provider or getattr(settings, "image_storage_provider", "local")

    match provider:
        case "s3":
            return S3ImageStorage()
        case "supabase":
            return SupabaseImageStorage()
        case _:  # "local" or any other value
            return LocalImageStorage()


def compute_file_hash(data: bytes) -> str:
    """
    Compute SHA-256 hash of file data.

    Args:
        data: File content as bytes

    Returns:
        Hex-encoded SHA-256 hash
    """
    return hashlib.sha256(data).hexdigest()
