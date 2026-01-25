"""Image extraction service for HTML, PDF, and YouTube video content.

This module extracts images from various content sources:
- HTML: Downloads external images, extracts inline base64 images
- PDF: Extracts embedded images (via docling/pdf parsers)
- YouTube: Extracts keyframes using scene detection (via KeyframeExtractor)

All extracted images are deduplicated using perceptual hashing (phash).
"""

import asyncio
import base64
import hashlib
import re
import urllib.parse
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING

import httpx

from src.config import settings
from src.models.image import ImageCreate, ImageSource
from src.services.file_storage import FileStorageProvider, get_image_storage
from src.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Common image MIME types
IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".bmp": "image/bmp",
    ".ico": "image/x-icon",
}

# Base64 data URI pattern
BASE64_IMAGE_PATTERN = re.compile(r"data:image/([a-zA-Z0-9+-]+);base64,([A-Za-z0-9+/=]+)")

# HTML img tag pattern
IMG_TAG_PATTERN = re.compile(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)


@dataclass
class ExtractedImage:
    """Represents an image extracted from content."""

    data: bytes
    filename: str
    mime_type: str
    source_url: str | None = None
    alt_text: str | None = None
    width: int | None = None
    height: int | None = None
    phash: str | None = None

    @property
    def file_size_bytes(self) -> int:
        return len(self.data)


class ImageExtractor:
    """Extract images from various content sources.

    Handles HTML img tags, base64 embedded images, and integrates
    with KeyframeExtractor for YouTube video keyframes.
    """

    def __init__(
        self,
        storage: FileStorageProvider | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Initialize the image extractor.

        Args:
            storage: Storage provider for saving images
            http_client: HTTP client for downloading external images
        """
        self.storage = storage or get_image_storage()
        self._http_client = http_client
        self._owns_client = http_client is None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": "Newsletter-Aggregator/1.0"},
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client if we own it."""
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def __aenter__(self) -> "ImageExtractor":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    def compute_phash(self, image_data: bytes) -> str | None:
        """
        Compute perceptual hash of an image for deduplication.

        Args:
            image_data: Image data as bytes

        Returns:
            Hex string hash or None if failed
        """
        try:
            import imagehash
            from PIL import Image as PILImage
        except ImportError:
            logger.warning(
                "imagehash/Pillow not installed. " "Install with: pip install imagehash Pillow"
            )
            return None

        try:
            img = PILImage.open(BytesIO(image_data))
            hash_value = imagehash.average_hash(img, hash_size=16)
            return str(hash_value)
        except Exception as e:
            logger.warning(f"Error computing phash: {e}")
            return None

    def get_image_dimensions(self, image_data: bytes) -> tuple[int | None, int | None]:
        """
        Get image dimensions.

        Args:
            image_data: Image data as bytes

        Returns:
            Tuple of (width, height) or (None, None) if failed
        """
        try:
            from PIL import Image as PILImage
        except ImportError:
            return None, None

        try:
            img = PILImage.open(BytesIO(image_data))
            return img.width, img.height
        except Exception:
            return None, None

    def _get_mime_type(self, filename: str, content_type: str | None = None) -> str:
        """Determine MIME type from filename or content-type header."""
        if content_type and content_type.startswith("image/"):
            return content_type

        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return IMAGE_MIME_TYPES.get(ext, "image/jpeg")

    def _extract_filename_from_url(self, url: str) -> str:
        """Extract filename from URL."""
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        if path:
            filename = path.rsplit("/", 1)[-1]
            if filename and "." in filename:
                return filename
        # Generate a hash-based filename (md5 for uniqueness, not security)
        return f"image_{hashlib.md5(url.encode()).hexdigest()[:8]}.jpg"  # noqa: S324

    async def download_image(
        self,
        url: str,
        base_url: str | None = None,
    ) -> ExtractedImage | None:
        """
        Download an image from a URL.

        Args:
            url: Image URL (absolute or relative)
            base_url: Base URL for resolving relative URLs

        Returns:
            ExtractedImage or None if download failed
        """
        # Resolve relative URLs
        if base_url and not url.startswith(("http://", "https://", "data:")):
            url = urllib.parse.urljoin(base_url, url)

        # Handle base64 data URIs
        if url.startswith("data:"):
            return self._extract_base64_image(url)

        try:
            client = await self._get_client()
            response = await client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                logger.debug(f"Skipping non-image URL: {url} (type: {content_type})")
                return None

            data = response.content
            filename = self._extract_filename_from_url(url)
            mime_type = self._get_mime_type(filename, content_type)
            width, height = self.get_image_dimensions(data)
            phash = self.compute_phash(data)

            return ExtractedImage(
                data=data,
                filename=filename,
                mime_type=mime_type,
                source_url=url,
                width=width,
                height=height,
                phash=phash,
            )

        except Exception as e:
            logger.warning(f"Failed to download image from {url}: {e}")
            return None

    def _extract_base64_image(self, data_uri: str) -> ExtractedImage | None:
        """Extract image from base64 data URI."""
        match = BASE64_IMAGE_PATTERN.match(data_uri)
        if not match:
            return None

        try:
            image_type = match.group(1)
            base64_data = match.group(2)
            data = base64.b64decode(base64_data)

            filename = f"embedded_{hashlib.md5(data).hexdigest()[:8]}.{image_type}"  # noqa: S324
            mime_type = f"image/{image_type}"
            width, height = self.get_image_dimensions(data)
            phash = self.compute_phash(data)

            return ExtractedImage(
                data=data,
                filename=filename,
                mime_type=mime_type,
                width=width,
                height=height,
                phash=phash,
            )

        except Exception as e:
            logger.warning(f"Failed to decode base64 image: {e}")
            return None

    async def extract_from_html(
        self,
        html: str,
        base_url: str | None = None,
        max_images: int = 50,
    ) -> list[ExtractedImage]:
        """
        Extract images from HTML content.

        Args:
            html: HTML string
            base_url: Base URL for resolving relative image URLs
            max_images: Maximum number of images to extract

        Returns:
            List of ExtractedImage objects
        """
        # Find all img tags
        img_urls = IMG_TAG_PATTERN.findall(html)

        # Also find base64 images
        base64_images = BASE64_IMAGE_PATTERN.findall(html)

        images: list[ExtractedImage] = []

        # Download external images (with concurrency limit)
        semaphore = asyncio.Semaphore(5)

        async def _download_with_limit(url: str) -> ExtractedImage | None:
            async with semaphore:
                return await self.download_image(url, base_url)

        tasks = [_download_with_limit(url) for url in img_urls[:max_images]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, ExtractedImage):
                images.append(result)

        # Extract base64 images
        for img_type, b64_data in base64_images[: max_images - len(images)]:
            data_uri = f"data:image/{img_type};base64,{b64_data}"
            img = self._extract_base64_image(data_uri)
            if img:
                images.append(img)

        logger.info(f"Extracted {len(images)} images from HTML")
        return images

    def extract_youtube_keyframes(
        self,
        video_id: str,
        transcript_segments: list[dict] | None = None,
    ) -> list[ExtractedImage]:
        """
        Extract keyframes from a YouTube video.

        Args:
            video_id: YouTube video ID
            transcript_segments: Optional transcript for timestamp matching

        Returns:
            List of ExtractedImage objects
        """
        if not getattr(settings, "youtube_keyframe_extraction", False):
            logger.debug("YouTube keyframe extraction is disabled")
            return []

        try:
            from src.ingestion.youtube_keyframes import KeyframeExtractor
        except ImportError:
            logger.warning("KeyframeExtractor not available")
            return []

        try:
            extractor = KeyframeExtractor()

            if not extractor.is_available():
                logger.warning("ffmpeg not available for keyframe extraction")
                return []

            result = extractor.extract_keyframes_for_video(video_id, transcript_segments)

            if result.error:
                logger.warning(f"Keyframe extraction error: {result.error}")
                return []

            images: list[ExtractedImage] = []

            for slide in result.slides:
                try:
                    with open(slide.path, "rb") as f:
                        data = f.read()

                    width, height = self.get_image_dimensions(data)
                    phash = slide.hash_value or self.compute_phash(data)

                    # Generate YouTube deep link
                    timestamp = int(slide.timestamp)
                    deep_link = f"https://youtu.be/{video_id}?t={timestamp}"

                    images.append(
                        ExtractedImage(
                            data=data,
                            filename=f"{video_id}_{timestamp:06d}.jpg",
                            mime_type="image/jpeg",
                            source_url=deep_link,
                            width=width,
                            height=height,
                            phash=phash,
                        )
                    )

                except Exception as e:
                    logger.warning(f"Error reading keyframe {slide.path}: {e}")

            # Cleanup frames directory
            extractor.cleanup_frames_dir(video_id)

            logger.info(f"Extracted {len(images)} keyframes from video {video_id}")
            return images

        except Exception as e:
            logger.error(f"Failed to extract keyframes from {video_id}: {e}")
            return []

    async def save_extracted_images(
        self,
        images: list[ExtractedImage],
        source_content_id: int | None = None,
        source_summary_id: int | None = None,
        source_digest_id: int | None = None,
        source_type: ImageSource = ImageSource.EXTRACTED,
    ) -> list[ImageCreate]:
        """
        Save extracted images to storage and return create schemas.

        Args:
            images: List of ExtractedImage objects
            source_content_id: FK to Content
            source_summary_id: FK to Summary
            source_digest_id: FK to Digest
            source_type: Type of image source

        Returns:
            List of ImageCreate schemas ready for database insertion
        """
        creates: list[ImageCreate] = []

        for img in images:
            try:
                # Save to storage
                path = await self.storage.save(
                    data=img.data,
                    filename=img.filename,
                    content_type=img.mime_type,
                )

                # Extract video_id and timestamp from URL for keyframes
                video_id = None
                timestamp_seconds = None
                deep_link_url = None

                if source_type == ImageSource.KEYFRAME and img.source_url:
                    # Parse youtu.be/xxx?t=123 format
                    if "youtu.be/" in img.source_url:
                        parts = img.source_url.split("youtu.be/")[1]
                        video_id = parts.split("?")[0]
                        if "t=" in img.source_url:
                            timestamp_seconds = float(img.source_url.split("t=")[1].split("&")[0])
                        deep_link_url = img.source_url

                creates.append(
                    ImageCreate(
                        source_type=source_type,
                        source_content_id=source_content_id,
                        source_summary_id=source_summary_id,
                        source_digest_id=source_digest_id,
                        source_url=img.source_url,
                        video_id=video_id,
                        timestamp_seconds=timestamp_seconds,
                        deep_link_url=deep_link_url,
                        storage_path=path,
                        storage_provider=self.storage.provider_name,
                        filename=img.filename,
                        mime_type=img.mime_type,
                        width=img.width,
                        height=img.height,
                        file_size_bytes=img.file_size_bytes,
                        alt_text=img.alt_text,
                        phash=img.phash,
                    )
                )

            except Exception as e:
                logger.error(f"Failed to save image {img.filename}: {e}")

        return creates


def compute_phash_similarity(hash1: str, hash2: str) -> float:
    """
    Compute similarity between two perceptual hashes.

    Args:
        hash1: First hash string
        hash2: Second hash string

    Returns:
        Similarity score between 0.0 (different) and 1.0 (identical)
    """
    try:
        import imagehash
    except ImportError:
        return 0.0

    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        distance = h1 - h2
        max_distance = 16 * 16  # For hash_size=16
        return 1.0 - (distance / max_distance)
    except Exception:
        return 0.0
