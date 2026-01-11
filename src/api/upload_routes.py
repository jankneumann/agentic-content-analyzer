"""
Document Upload API Routes

File upload endpoints for document ingestion.
Supports PDF, DOCX, PPTX, XLSX, and other formats.
"""

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from src.config.settings import settings
from src.ingestion.files import FileIngestionService
from src.models.newsletter import Newsletter, NewsletterSource, ProcessingStatus
from src.parsers import DoclingParser, MarkItDownParser, ParserRouter, YouTubeParser
from src.storage.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


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
    newsletter_id: int
    is_duplicate: bool = False
    canonical_id: int | None = None
    processing_time_ms: int | None = None

    class Config:
        from_attributes = True


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
    newsletter_id: int | None
    processed_at: datetime | None
    error_message: str | None

    class Config:
        from_attributes = True


class SupportedFormatsResponse(BaseModel):
    """List of supported file formats."""

    formats: list[str]
    docling_available: bool
    ocr_enabled: bool
    max_file_size_mb: int


# ============================================================================
# Helper Functions
# ============================================================================


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
    publication: Annotated[
        str | None, Form(description="Publisher/source name")
    ] = None,
    title: Annotated[
        str | None, Form(description="Override extracted title")
    ] = None,
    prefer_structured: Annotated[
        bool, Form(description="Prefer Docling for table extraction")
    ] = False,
    ocr_needed: Annotated[
        bool, Form(description="Force OCR processing")
    ] = False,
) -> DocumentUploadResponse:
    """
    Upload and process a document file.

    Supports PDF, DOCX, PPTX, XLSX, HTML, and other formats.
    The document will be parsed and stored as a newsletter for summarization.

    Returns:
        Document metadata and associated newsletter ID
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    # Check file size
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)

    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            status_code=413,
            detail=f"File size ({size_mb:.1f}MB) exceeds limit ({settings.max_upload_size_mb}MB)",
        )

    # Get format from filename
    filename = file.filename
    format_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "unknown"

    # Create parser router and ingestion service
    router = get_parser_router()

    # Check if format is supported
    supported = set()
    for parser_name in router.available_parsers:
        parser = router.parsers[parser_name]
        supported.update(parser.supported_formats)
        supported.update(parser.fallback_formats)

    if format_ext not in supported and format_ext != "unknown":
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported format: {format_ext}. Supported: {sorted(supported)}",
        )

    # Process the document
    try:
        with get_db() as db:
            service = FileIngestionService(router=router, db=db)

            newsletter = await service.ingest_bytes(
                data=contents,
                filename=filename,
                publication=publication,
                title=title,
                format_hint=format_ext,
            )

            # Build response
            is_duplicate = newsletter.canonical_newsletter_id is not None

            return DocumentUploadResponse(
                id=newsletter.id,
                filename=filename,
                status=newsletter.status.value if newsletter.status else "pending",
                format=format_ext,
                parser_used=router.route(filename).name if not is_duplicate else "skipped",
                title=newsletter.title,
                page_count=None,  # Would need to store this separately
                word_count=len(newsletter.raw_text.split()) if newsletter.raw_text else None,
                newsletter_id=newsletter.id,
                is_duplicate=is_duplicate,
                canonical_id=newsletter.canonical_newsletter_id,
                processing_time_ms=None,  # Would need to track this
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")


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
        document_id: Newsletter ID of the uploaded document

    Returns:
        Document status, metadata, and content summary
    """
    with get_db() as db:
        newsletter = (
            db.query(Newsletter)
            .filter(Newsletter.id == document_id)
            .filter(Newsletter.source == NewsletterSource.FILE_UPLOAD)
            .first()
        )

        if not newsletter:
            raise HTTPException(
                status_code=404,
                detail=f"Document with ID {document_id} not found",
            )

        # Extract format from source_id if available
        format_ext = "unknown"
        if newsletter.source_id and "_" in newsletter.source_id:
            # source_id format: file_{hash}_{timestamp}
            pass  # Format would need to be stored separately

        # Content preview (first 500 chars)
        content_preview = None
        if newsletter.raw_text:
            content_preview = newsletter.raw_text[:500]
            if len(newsletter.raw_text) > 500:
                content_preview += "..."

        # Count links
        links_count = len(newsletter.extracted_links) if newsletter.extracted_links else 0

        return DocumentStatusResponse(
            id=newsletter.id,
            filename=newsletter.title or "Unknown",
            status=newsletter.status.value if newsletter.status else "unknown",
            format=format_ext,
            parser_used=None,  # Would need to store this
            metadata={
                "title": newsletter.title,
                "sender": newsletter.sender,
                "publication": newsletter.publication,
                "published_date": newsletter.published_date.isoformat() if newsletter.published_date else None,
            },
            content_preview=content_preview,
            tables_count=0,  # Would need to store extracted tables
            links_count=links_count,
            newsletter_id=newsletter.id,
            processed_at=newsletter.processed_at,
            error_message=newsletter.error_message,
        )
