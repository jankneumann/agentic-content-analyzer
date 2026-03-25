"""
Document Upload API Routes

File upload endpoints for document ingestion using the unified Content model.
Supports PDF, DOCX, PPTX, XLSX, and other formats.
"""

import logging
import os
import tempfile
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict

from src.api.dependencies import verify_admin_key
from src.config.settings import settings
from src.ingestion.files import FileContentIngestionService, FileIngestionError
from src.models.content import Content, ContentSource
from src.parsers import DoclingParser, MarkItDownParser, ParserRouter, YouTubeParser
from src.storage.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/documents",
    tags=["documents"],
    dependencies=[Depends(verify_admin_key)],
)

# File signature (magic bytes) mapping for upload validation.
# Each entry maps a file extension to a list of valid magic byte prefixes.
# Files with extensions not in this mapping skip signature validation.
FILE_SIGNATURES: dict[str, list[bytes]] = {
    "pdf": [b"%PDF"],
    "docx": [b"PK\x03\x04"],  # DOCX is ZIP-based
    "xlsx": [b"PK\x03\x04"],  # XLSX is ZIP-based
    "pptx": [b"PK\x03\x04"],  # PPTX is ZIP-based
    "zip": [b"PK\x03\x04", b"PK\x05\x06"],  # Regular and empty ZIP
    "png": [b"\x89PNG\r\n\x1a\n"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "gif": [b"GIF87a", b"GIF89a"],
    "html": [b"<!DOCTYPE", b"<!doctype", b"<html", b"<HTML"],
    "htm": [b"<!DOCTYPE", b"<!doctype", b"<html", b"<HTML"],
    "wav": [b"RIFF"],
    "mp3": [b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"],  # ID3v2 or MPEG 1/2/2.5 Layer 3
    "epub": [b"PK\x03\x04"],  # EPUB is ZIP-based
    "msg": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],  # OLE CF
}

# Expected MIME types for file extensions.
# Used to cross-check client-provided Content-Type against declared extension.
# Generic types (application/octet-stream, empty) always bypass this check.
EXTENSION_MIME_MAP: dict[str, set[str]] = {
    "pdf": {"application/pdf"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    },
    "xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
    },
    "pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/zip",
    },
    "zip": {"application/zip", "application/x-zip-compressed"},
    "png": {"image/png"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "gif": {"image/gif"},
    "html": {"text/html", "application/xhtml+xml"},
    "htm": {"text/html", "application/xhtml+xml"},
    "txt": {"text/plain"},
    "md": {"text/plain", "text/markdown"},
    "csv": {"text/csv", "text/plain"},
    "wav": {"audio/wav", "audio/x-wav", "audio/wave"},
    "mp3": {"audio/mpeg", "audio/mp3"},
    "epub": {"application/epub+zip"},
    "msg": {"application/vnd.ms-outlook"},
}

# ============================================================================
# Request/Response Models
# ============================================================================


class DocumentUploadResponse(BaseModel):
    """Response after successful document upload."""

    id: int
    filename: str
    status: str
    format: str
    parser_used: str
    title: str | None
    page_count: int | None
    word_count: int | None
    content_id: int
    is_duplicate: bool = False
    canonical_id: int | None = None
    processing_time_ms: int | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentStatusResponse(BaseModel):
    """Document status and details."""

    id: int
    filename: str
    status: str
    format: str
    parser_used: str | None
    metadata: dict | None
    content_preview: str | None
    tables_count: int
    links_count: int
    content_id: int | None
    processed_at: datetime | None
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)


class SupportedFormatsResponse(BaseModel):
    """List of supported file formats."""

    formats: list[str]
    docling_available: bool
    ocr_enabled: bool
    max_file_size_mb: int


# ============================================================================
# Helper Functions
# ============================================================================


def _validate_file_signature(data: bytes, extension: str) -> str | None:
    """Validate file content matches expected magic bytes for the extension.

    Args:
        data: File content (at least first chunk).
        extension: Lowercase file extension without dot.

    Returns:
        Error message if signature mismatch, None if valid or unknown extension.
    """
    expected_signatures = FILE_SIGNATURES.get(extension)
    if expected_signatures is None:
        # Unknown extension — skip validation (no magic bytes to check)
        return None

    for sig in expected_signatures:
        if data[: len(sig)] == sig:
            return None

    return (
        f"File content does not match expected format for .{extension}. "
        f"The file may be corrupted or have an incorrect extension."
    )


def _validate_mime_type(content_type: str | None, extension: str) -> str | None:
    """Validate client-provided Content-Type against declared file extension.

    Generic MIME types (application/octet-stream, empty/None) bypass this check
    since many clients use them as defaults.

    Args:
        content_type: Client-provided Content-Type header value.
        extension: Lowercase file extension without dot.

    Returns:
        Error message if MIME type contradicts extension, None if valid.
    """
    if not content_type or content_type == "application/octet-stream":
        return None

    expected_mimes = EXTENSION_MIME_MAP.get(extension)
    if expected_mimes is None:
        # Unknown extension — skip MIME validation
        return None

    # Normalize: strip parameters (e.g., "text/html; charset=utf-8" → "text/html")
    mime_base = content_type.split(";")[0].strip().lower()

    if mime_base in expected_mimes:
        return None

    return (
        f"Content-Type '{mime_base}' does not match expected type for .{extension}. "
        f"Expected one of: {sorted(expected_mimes)}"
    )


def get_parser_router() -> ParserRouter:
    """Create a parser router with available parsers."""
    markitdown = MarkItDownParser()
    youtube = YouTubeParser()

    docling = None
    if settings.enable_docling:
        try:
            docling = DoclingParser(
                enable_ocr=settings.docling_enable_ocr,
                max_file_size_mb=settings.docling_max_file_size_mb,
                timeout_seconds=settings.docling_timeout_seconds,
            )
        except ImportError:
            logger.warning("Docling not available, falling back to MarkItDown for PDFs")

    return ParserRouter(
        markitdown_parser=markitdown,
        docling_parser=docling,
        youtube_parser=youtube,
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: Annotated[UploadFile, File(description="Document file to upload")],
    publication: Annotated[str | None, Form(description="Publisher/source name")] = None,
    title: Annotated[str | None, Form(description="Override extracted title")] = None,
    prefer_structured: Annotated[
        bool, Form(description="Prefer Docling for table extraction")
    ] = False,
    ocr_needed: Annotated[bool, Form(description="Force OCR processing")] = False,
) -> DocumentUploadResponse:
    """
    Upload and process a document file.

    Supports PDF, DOCX, PPTX, XLSX, HTML, and other formats.
    The document will be parsed and stored as Content for summarization.

    Returns:
        Document metadata and associated content ID
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    # Get format from filename
    filename = file.filename
    format_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "unknown"

    # Create temporary file to stream upload
    # We use delete=False and manually cleanup in finally block
    # to avoid permission issues on some OSes or if we need to pass path around.
    # Using NamedTemporaryFile as context manager ensures proper resource management.
    temp_path = None

    try:
        # Check file size incrementally to prevent memory exhaustion
        # 1MB chunks
        CHUNK_SIZE = 1024 * 1024
        MAX_BYTES = settings.max_upload_size_mb * 1024 * 1024

        total_bytes = 0
        first_chunk = b""

        with tempfile.NamedTemporaryFile(
            delete=False, mode="wb", suffix=f".{format_ext}" if format_ext != "unknown" else None
        ) as tmp_file:
            temp_path = tmp_file.name
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break

                # Keep first chunk for signature validation
                if not first_chunk:
                    first_chunk = chunk

                total_bytes += len(chunk)
                if total_bytes > MAX_BYTES:
                    size_mb = total_bytes / (1024 * 1024)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File size ({size_mb:.1f}MB) exceeds limit ({settings.max_upload_size_mb}MB)",
                    )

                tmp_file.write(chunk)

        size_mb = total_bytes / (1024 * 1024)

        # Validate file signature (magic bytes) matches declared extension
        if first_chunk:
            signature_error = _validate_file_signature(first_chunk, format_ext)
            if signature_error:
                raise HTTPException(status_code=415, detail=signature_error)

        # Cross-check client-provided MIME type against declared extension
        mime_error = _validate_mime_type(file.content_type, format_ext)
        if mime_error:
            raise HTTPException(status_code=415, detail=mime_error)

        # Create parser router and ingestion service
        parser_router = get_parser_router()

        # Check if format is supported
        supported = set()
        for parser_name in parser_router.available_parsers:
            parser = parser_router.parsers[parser_name]
            supported.update(parser.supported_formats)
            supported.update(parser.fallback_formats)

        # YouTube is not a file format
        supported.discard("youtube")

        if format_ext not in supported:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported format: {format_ext}. Supported: {sorted(supported)}",
            )

        # Process the document using the unified Content model
        with get_db() as db:
            service = FileContentIngestionService(router=parser_router, db=db)

            content = await service.ingest_file(
                file_path=temp_path,
                publication=publication,
                title=title,
                prefer_structured=prefer_structured,
                ocr_needed=ocr_needed,
                format_hint=format_ext,
            )

            # Build response
            is_duplicate = content.canonical_id is not None

            return DocumentUploadResponse(
                id=content.id,
                filename=filename,
                status=content.status.value if content.status else "pending",
                format=format_ext,
                parser_used=content.parser_used
                or (parser_router.route(filename).name if not is_duplicate else "skipped"),
                title=content.title,
                page_count=content.metadata_json.get("page_count")
                if content.metadata_json
                else None,
                word_count=len(content.markdown_content.split())
                if content.markdown_content
                else None,
                content_id=content.id,
                is_duplicate=is_duplicate,
                canonical_id=content.canonical_id,
                processing_time_ms=None,  # Would need to track this
            )

    except FileIngestionError as e:
        raise HTTPException(
            status_code=400, detail="Document upload failed due to an ingestion error"
        )
    except Exception as e:
        # Don't shadow HTTPException
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Document upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Processing failed due to an internal error")
    finally:
        # Cleanup temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                logger.warning(f"Failed to remove temp file: {temp_path}")


@router.get("/formats", response_model=SupportedFormatsResponse)
async def get_supported_formats() -> SupportedFormatsResponse:
    """
    Get list of supported file formats.

    Returns information about available parsers and configuration.
    """
    router = get_parser_router()

    formats = set()
    for parser_name in router.available_parsers:
        parser = router.parsers[parser_name]
        formats.update(parser.supported_formats)
        formats.update(parser.fallback_formats)

    # Remove youtube since it's not a file format
    formats.discard("youtube")

    return SupportedFormatsResponse(
        formats=sorted(formats),
        docling_available=router.has_docling,
        ocr_enabled=settings.docling_enable_ocr,
        max_file_size_mb=settings.max_upload_size_mb,
    )


@router.get("/{document_id}", response_model=DocumentStatusResponse)
async def get_document_status(document_id: int) -> DocumentStatusResponse:
    """
    Get document processing status and details.

    Args:
        document_id: Content ID of the uploaded document

    Returns:
        Document status, metadata, and content summary
    """
    with get_db() as db:
        content = (
            db.query(Content)
            .filter(Content.id == document_id)
            .filter(Content.source_type == ContentSource.FILE_UPLOAD)
            .first()
        )

        if not content:
            raise HTTPException(
                status_code=404,
                detail=f"Document with ID {document_id} not found",
            )

        # Extract format from metadata or raw_format
        format_ext = content.raw_format or "unknown"

        # Content preview (first 500 chars of markdown)
        content_preview = None
        if content.markdown_content:
            content_preview = content.markdown_content[:500]
            if len(content.markdown_content) > 500:
                content_preview += "..."

        # Count links and tables
        links_count = len(content.links_json) if content.links_json else 0
        tables_count = len(content.tables_json) if content.tables_json else 0

        return DocumentStatusResponse(
            id=content.id,
            filename=content.title or "Unknown",
            status=content.status.value if content.status else "unknown",
            format=format_ext,
            parser_used=content.parser_used,
            metadata={
                "title": content.title,
                "author": content.author,
                "publication": content.publication,
                "published_date": content.published_date.isoformat()
                if content.published_date
                else None,
                **(content.metadata_json or {}),
            },
            content_preview=content_preview,
            tables_count=tables_count,
            links_count=links_count,
            content_id=content.id,
            processed_at=content.processed_at,
            error_message=content.error_message,
        )
