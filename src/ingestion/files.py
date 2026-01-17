"""File upload ingestion service.

Provides both legacy Newsletter ingestion and new Content model ingestion.
The Content-based ingestion (FileContentIngestionService) is the preferred
approach for new code as part of the unified content model refactor.
"""

import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.models.content import Content, ContentSource, ContentStatus
from src.models.document import DocumentContent
from src.models.newsletter import Newsletter, NewsletterSource, ProcessingStatus
from src.parsers.router import ParserRouter
from src.utils.content_hash import generate_markdown_hash

logger = logging.getLogger(__name__)


def calculate_file_hash_sync(file_path: Path) -> str:
    """Calculate SHA-256 hash of file contents (blocking).

    Args:
        file_path: Path to the file

    Returns:
        Hex-encoded SHA-256 hash
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


class FileIngestionService:
    """Service for ingesting uploaded files into the newsletter system.

    Handles file parsing, deduplication, and storage as Newsletter records.
    """

    def __init__(
        self,
        router: ParserRouter,
        db: Session,
    ) -> None:
        """Initialize the file ingestion service.

        Args:
            router: Parser router for format-based parsing
            db: Database session for storing records
        """
        self.router = router
        self.db = db
        self.max_file_size_mb = settings.max_upload_size_mb

    async def ingest_file(
        self,
        file_path: Path | str,
        publication: str | None = None,
        title: str | None = None,
        prefer_structured: bool = False,
        ocr_needed: bool = False,
    ) -> Newsletter:
        """Ingest a file and create a Newsletter record.

        Args:
            file_path: Path to the file to ingest
            publication: Optional publisher/source name
            title: Optional title override (uses extracted or filename if not provided)
            prefer_structured: Prefer Docling for table extraction
            ocr_needed: Force OCR processing

        Returns:
            Created or existing Newsletter record

        Raises:
            ValueError: If file exceeds size limit or format not supported
            FileNotFoundError: If file does not exist
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check file size
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > self.max_file_size_mb:
            raise ValueError(
                f"File size ({size_mb:.1f}MB) exceeds limit ({self.max_file_size_mb}MB)"
            )

        # Calculate file hash for deduplication
        file_hash = await self._calculate_file_hash(file_path)

        # Check for existing duplicate
        existing = self._find_duplicate(file_hash)
        if existing:
            logger.info(f"Found existing document with hash {file_hash[:8]}...")
            return self._create_duplicate_link(existing, file_path, publication)

        # Parse the document
        logger.info(f"Parsing {file_path.name} with router...")
        content = await self.router.parse(
            str(file_path),
            prefer_structured=prefer_structured,
            ocr_needed=ocr_needed,
        )

        # Create newsletter record
        newsletter = self._create_newsletter(
            content=content,
            file_path=file_path,
            file_hash=file_hash,
            publication=publication,
            title_override=title,
        )

        self.db.add(newsletter)
        self.db.commit()
        self.db.refresh(newsletter)

        logger.info(
            f"Ingested {file_path.name} as newsletter ID {newsletter.id} "
            f"(parser: {content.parser_used}, {content.processing_time_ms}ms)"
        )

        return newsletter

    async def ingest_bytes(
        self,
        data: bytes | BinaryIO,
        filename: str,
        publication: str | None = None,
        title: str | None = None,
        format_hint: str | None = None,
    ) -> Newsletter:
        """Ingest raw bytes and create a Newsletter record.

        Args:
            data: File content as bytes or file-like object
            filename: Original filename for format detection
            publication: Optional publisher/source name
            title: Optional title override
            format_hint: Optional format hint (e.g., "pdf")

        Returns:
            Created or existing Newsletter record
        """
        # Get bytes if file-like object
        if hasattr(data, "read"):
            file_bytes = data.read()  # type: ignore[union-attr]
        else:
            file_bytes = data  # type: ignore[assignment]

        # Check size
        size_mb = len(file_bytes) / (1024 * 1024)  # type: ignore[arg-type]
        if size_mb > self.max_file_size_mb:
            raise ValueError(
                f"File size ({size_mb:.1f}MB) exceeds limit ({self.max_file_size_mb}MB)"
            )

        # Calculate hash for deduplication
        file_hash = hashlib.sha256(file_bytes).hexdigest()  # type: ignore[arg-type]

        # Check for existing duplicate
        existing = self._find_duplicate(file_hash)
        if existing:
            logger.info(f"Found existing document with hash {file_hash[:8]}...")
            return self._create_duplicate_link(existing, Path(filename), publication)

        # Detect format from filename if not provided
        if not format_hint:
            format_hint = Path(filename).suffix.lower().lstrip(".")

        # Parse the document
        logger.info(f"Parsing {filename} from bytes...")
        content = await self.router.parse(file_bytes, format_hint=format_hint)  # type: ignore[arg-type]

        # Create newsletter record
        newsletter = self._create_newsletter(
            content=content,
            file_path=Path(filename),
            file_hash=file_hash,
            publication=publication,
            title_override=title,
        )

        self.db.add(newsletter)
        self.db.commit()
        self.db.refresh(newsletter)

        logger.info(
            f"Ingested {filename} as newsletter ID {newsletter.id} "
            f"(parser: {content.parser_used})"
        )

        return newsletter

    async def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file contents asynchronously.

        Args:
            file_path: Path to the file

        Returns:
            Hex-encoded SHA-256 hash
        """
        return await asyncio.to_thread(calculate_file_hash_sync, file_path)

    def _find_duplicate(self, file_hash: str) -> Newsletter | None:
        """Find existing newsletter with the same content hash.

        Args:
            file_hash: SHA-256 hash to search for

        Returns:
            Existing Newsletter if found, None otherwise
        """
        return (
            self.db.query(Newsletter)
            .filter(Newsletter.content_hash == file_hash)
            .filter(Newsletter.source == NewsletterSource.FILE_UPLOAD)
            .first()
        )

    def _create_duplicate_link(
        self,
        canonical: Newsletter,
        file_path: Path,
        publication: str | None,
    ) -> Newsletter:
        """Create a new Newsletter record linked to the canonical version.

        Args:
            canonical: The original Newsletter to link to
            file_path: Path of the duplicate file
            publication: Optional publication override

        Returns:
            New Newsletter record linked to canonical
        """
        # Generate a unique source_id for this duplicate
        source_id = f"file_dup_{file_path.name}_{datetime.now(UTC).isoformat()}"

        newsletter = Newsletter(
            source=NewsletterSource.FILE_UPLOAD,
            source_id=source_id,
            title=f"[Duplicate] {canonical.title}",
            sender=None,
            publication=publication or canonical.publication,
            published_date=datetime.now(UTC),
            url=None,
            raw_html=None,  # Don't duplicate content
            raw_text=None,
            extracted_links=[],
            content_hash=canonical.content_hash,
            canonical_newsletter_id=canonical.id,
            status=ProcessingStatus.COMPLETED,
            ingested_at=datetime.now(UTC),
        )

        self.db.add(newsletter)
        self.db.commit()
        self.db.refresh(newsletter)

        logger.info(f"Created duplicate link: newsletter {newsletter.id} -> {canonical.id}")

        return newsletter

    def _create_newsletter(
        self,
        content: DocumentContent,
        file_path: Path,
        file_hash: str,
        publication: str | None,
        title_override: str | None,
    ) -> Newsletter:
        """Create a Newsletter record from parsed content.

        Args:
            content: Parsed document content
            file_path: Original file path
            file_hash: SHA-256 hash of file
            publication: Optional publication name
            title_override: Optional title override

        Returns:
            Newsletter record (not yet committed)
        """
        # Determine title: override > extracted > filename
        title = title_override
        if not title and content.metadata.title:
            title = content.metadata.title
        if not title:
            title = file_path.stem

        # Generate unique source_id from hash and timestamp
        source_id = f"file_{file_hash[:16]}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"

        # Convert content to newsletter fields
        raw_text, raw_html, links = content.to_newsletter_content()

        return Newsletter(
            source=NewsletterSource.FILE_UPLOAD,
            source_id=source_id,
            title=title,
            sender=content.metadata.author,
            publication=publication,
            published_date=content.metadata.created_date or datetime.now(UTC),
            url=None,
            raw_html=raw_html,
            raw_text=raw_text,
            extracted_links=links,
            content_hash=file_hash,
            canonical_newsletter_id=None,
            status=ProcessingStatus.PENDING,
            ingested_at=datetime.now(UTC),
        )

    def get_supported_formats(self) -> list[str]:
        """Get list of supported file formats.

        Returns:
            List of supported file extensions
        """
        formats = set()

        # Collect from available parsers
        for parser_name in self.router.available_parsers:
            parser = self.router.parsers[parser_name]
            formats.update(parser.supported_formats)
            formats.update(parser.fallback_formats)

        # Remove YouTube since it's not a file format
        formats.discard("youtube")

        return sorted(formats)


class FileContentIngestionService:
    """Service for ingesting uploaded files into the unified Content model.

    This is the preferred ingestion service for new code. It creates Content
    records with markdown as the primary format, enabling the unified content
    pipeline for summarization and digest creation.
    """

    def __init__(
        self,
        router: ParserRouter,
        db: Session,
    ) -> None:
        """Initialize the file content ingestion service.

        Args:
            router: Parser router for format-based parsing
            db: Database session for storing records
        """
        self.router = router
        self.db = db
        self.max_file_size_mb = settings.max_upload_size_mb

    async def ingest_file(
        self,
        file_path: Path | str,
        publication: str | None = None,
        title: str | None = None,
        prefer_structured: bool = False,
        ocr_needed: bool = False,
    ) -> Content:
        """Ingest a file and create a Content record.

        Args:
            file_path: Path to the file to ingest
            publication: Optional publisher/source name
            title: Optional title override (uses extracted or filename if not provided)
            prefer_structured: Prefer Docling for table extraction
            ocr_needed: Force OCR processing

        Returns:
            Created or existing Content record

        Raises:
            ValueError: If file exceeds size limit or format not supported
            FileNotFoundError: If file does not exist
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check file size
        size_mb = file_path.stat().st_size / (1024 * 1024)
        if size_mb > self.max_file_size_mb:
            raise ValueError(
                f"File size ({size_mb:.1f}MB) exceeds limit ({self.max_file_size_mb}MB)"
            )

        # Calculate file hash for deduplication
        file_hash = await self._calculate_file_hash(file_path)

        # Check for existing duplicate
        existing = self._find_duplicate(file_hash)
        if existing:
            logger.info(f"Found existing content with hash {file_hash[:8]}...")
            return self._create_duplicate_link(existing, file_path, publication)

        # Parse the document
        logger.info(f"Parsing {file_path.name} with router for Content model...")
        doc_content = await self.router.parse(
            str(file_path),
            prefer_structured=prefer_structured,
            ocr_needed=ocr_needed,
        )

        # Create content record
        content = self._create_content(
            doc_content=doc_content,
            file_path=file_path,
            file_hash=file_hash,
            publication=publication,
            title_override=title,
        )

        self.db.add(content)
        self.db.commit()
        self.db.refresh(content)

        logger.info(
            f"Ingested {file_path.name} as content ID {content.id} "
            f"(parser: {doc_content.parser_used}, {doc_content.processing_time_ms}ms)"
        )

        return content

    async def ingest_bytes(
        self,
        data: bytes | BinaryIO,
        filename: str,
        publication: str | None = None,
        title: str | None = None,
        format_hint: str | None = None,
    ) -> Content:
        """Ingest raw bytes and create a Content record.

        Args:
            data: File content as bytes or file-like object
            filename: Original filename for format detection
            publication: Optional publisher/source name
            title: Optional title override
            format_hint: Optional format hint (e.g., "pdf")

        Returns:
            Created or existing Content record
        """
        # Get bytes if file-like object
        if hasattr(data, "read"):
            file_bytes = data.read()  # type: ignore[union-attr]
        else:
            file_bytes = data  # type: ignore[assignment]

        # Check size
        size_mb = len(file_bytes) / (1024 * 1024)  # type: ignore[arg-type]
        if size_mb > self.max_file_size_mb:
            raise ValueError(
                f"File size ({size_mb:.1f}MB) exceeds limit ({self.max_file_size_mb}MB)"
            )

        # Calculate hash for deduplication
        file_hash = hashlib.sha256(file_bytes).hexdigest()  # type: ignore[arg-type]

        # Check for existing duplicate
        existing = self._find_duplicate(file_hash)
        if existing:
            logger.info(f"Found existing content with hash {file_hash[:8]}...")
            return self._create_duplicate_link(existing, Path(filename), publication)

        # Detect format from filename if not provided
        if not format_hint:
            format_hint = Path(filename).suffix.lower().lstrip(".")

        # Parse the document
        logger.info(f"Parsing {filename} from bytes for Content model...")
        doc_content = await self.router.parse(file_bytes, format_hint=format_hint)  # type: ignore[arg-type]

        # Create content record
        content = self._create_content(
            doc_content=doc_content,
            file_path=Path(filename),
            file_hash=file_hash,
            publication=publication,
            title_override=title,
        )

        self.db.add(content)
        self.db.commit()
        self.db.refresh(content)

        logger.info(
            f"Ingested {filename} as content ID {content.id} "
            f"(parser: {doc_content.parser_used})"
        )

        return content

    async def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file contents asynchronously."""
        return await asyncio.to_thread(calculate_file_hash_sync, file_path)

    def _find_duplicate(self, file_hash: str) -> Content | None:
        """Find existing content with the same file hash."""
        return (
            self.db.query(Content)
            .filter(Content.content_hash == file_hash)
            .filter(Content.source_type == ContentSource.FILE_UPLOAD)
            .first()
        )

    def _create_duplicate_link(
        self,
        canonical: Content,
        file_path: Path,
        publication: str | None,
    ) -> Content:
        """Create a new Content record linked to the canonical version."""
        source_id = f"file_dup_{file_path.name}_{datetime.now(UTC).isoformat()}"

        content = Content(
            source_type=ContentSource.FILE_UPLOAD,
            source_id=source_id,
            source_url=None,
            title=f"[Duplicate] {canonical.title}",
            author=None,
            publication=publication or canonical.publication,
            published_date=datetime.now(UTC),
            markdown_content="",  # Don't duplicate content
            links_json=[],
            metadata_json={"duplicate_of": canonical.id},
            raw_content=None,
            raw_format=None,
            parser_used=None,
            content_hash=canonical.content_hash,
            canonical_id=canonical.id,
            status=ContentStatus.COMPLETED,
            ingested_at=datetime.now(UTC),
        )

        self.db.add(content)
        self.db.commit()
        self.db.refresh(content)

        logger.info(f"Created duplicate link: content {content.id} -> {canonical.id}")

        return content

    def _create_content(
        self,
        doc_content: DocumentContent,
        file_path: Path,
        file_hash: str,
        publication: str | None,
        title_override: str | None,
    ) -> Content:
        """Create a Content record from parsed document content.

        Args:
            doc_content: Parsed document content
            file_path: Original file path
            file_hash: SHA-256 hash of file
            publication: Optional publication name
            title_override: Optional title override

        Returns:
            Content record (not yet committed)
        """
        # Determine title: override > extracted > filename
        title = title_override
        if not title and doc_content.metadata.title:
            title = doc_content.metadata.title
        if not title:
            title = file_path.stem

        # Generate unique source_id from hash and timestamp
        source_id = f"file_{file_hash[:16]}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"

        # Generate content hash from markdown (for future dedup by content)
        markdown_hash = generate_markdown_hash(doc_content.markdown_content)

        # Extract tables if available
        tables_json = None
        if doc_content.tables:
            tables_json = [t.model_dump() for t in doc_content.tables]

        return Content(
            source_type=ContentSource.FILE_UPLOAD,
            source_id=source_id,
            source_url=None,
            title=title,
            author=doc_content.metadata.author,
            publication=publication,
            published_date=doc_content.metadata.created_date or datetime.now(UTC),
            markdown_content=doc_content.markdown_content,
            tables_json=tables_json,
            links_json=doc_content.links,
            metadata_json={
                "filename": file_path.name,
                "source_format": doc_content.source_format.value
                if doc_content.source_format
                else None,
                "page_count": doc_content.metadata.page_count,
                "word_count": doc_content.metadata.word_count,
                "processing_time_ms": doc_content.processing_time_ms,
                "warnings": doc_content.warnings,
            },
            raw_content=None,  # File content not stored; original file preserved elsewhere
            raw_format=doc_content.source_format.value if doc_content.source_format else None,
            parser_used=doc_content.parser_used,
            parser_version=None,
            content_hash=markdown_hash,  # Use markdown hash for content dedup
            canonical_id=None,
            status=ContentStatus.PARSED,
            ingested_at=datetime.now(UTC),
        )

    def get_supported_formats(self) -> list[str]:
        """Get list of supported file formats."""
        formats = set()

        for parser_name in self.router.available_parsers:
            parser = self.router.parsers[parser_name]
            formats.update(parser.supported_formats)
            formats.update(parser.fallback_formats)

        formats.discard("youtube")

        return sorted(formats)
