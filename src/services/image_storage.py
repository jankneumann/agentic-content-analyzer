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
from datetime import datetime
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
        now = datetime.utcnow()
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
    """

    def __init__(
        self,
        bucket: str | None = None,
        endpoint_url: str | None = None,
        region: str | None = None,
    ) -> None:
        """
        Initialize S3 storage provider.

        Args:
            bucket: S3 bucket name. Defaults to settings.image_storage_bucket
            endpoint_url: Custom endpoint for S3-compatible services
            region: AWS region
        """
        self.bucket = bucket or getattr(settings, "image_storage_bucket", "newsletter-images")
        self.endpoint_url = endpoint_url or getattr(settings, "s3_endpoint_url", None)
        self.region = region or getattr(settings, "aws_region", "us-east-1")
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
                    "boto3 is required for S3 storage. " "Install with: pip install boto3"
                )

            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                region_name=self.region,
            )
        return self._client

    def _generate_key(self, filename: str) -> str:
        """Generate S3 key with date-based organization."""
        now = datetime.utcnow()
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


def get_image_storage() -> ImageStorageProvider:
    """
    Get configured image storage provider.

    Returns provider based on IMAGE_STORAGE_PROVIDER setting:
    - "local" (default): LocalImageStorage
    - "s3": S3ImageStorage

    Returns:
        ImageStorageProvider instance
    """
    provider = getattr(settings, "image_storage_provider", "local")

    if provider == "s3":
        return S3ImageStorage()
    else:
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
