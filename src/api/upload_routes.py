"""
Document Upload API Routes

File upload endpoints for document ingestion using the unified Content model.
Supports PDF, DOCX, PPTX, XLSX, and other formats.
"""

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict

from src.api.dependencies import verify_admin_key
from src.config.settings import settings
from src.ingestion.files import FileContentIngestionService
from src.models.content import Content, ContentSource
from src.parsers import DoclingParser, MarkItDownParser, ParserRouter, YouTubeParser
from src.storage.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/documents",
    tags=["documents"],
    dependencies=[Depends(verify_admin_key)],
)


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

    # Check file size incrementally to prevent memory exhaustion
    # 1MB chunks
    CHUNK_SIZE = 1024 * 1024
    MAX_BYTES = settings.max_upload_size_mb * 1024 * 1024

    content_chunks = []
    total_bytes = 0

    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break

        total_bytes += len(chunk)
        if total_bytes > MAX_BYTES:
            size_mb = total_bytes / (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=f"File size ({size_mb:.1f}MB) exceeds limit ({settings.max_upload_size_mb}MB)",
            )

        content_chunks.append(chunk)

    contents = b"".join(content_chunks)
    size_mb = total_bytes / (1024 * 1024)

    # Get format from filename
    filename = file.filename
    format_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "unknown"

    # Create parser router and ingestion service
    parser_router = get_parser_router()

    # Check if format is supported
    supported = set()
    for parser_name in parser_router.available_parsers:
        parser = parser_router.parsers[parser_name]
        supported.update(parser.supported_formats)
        supported.update(parser.fallback_formats)

    if format_ext not in supported and format_ext != "unknown":
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported format: {format_ext}. Supported: {sorted(supported)}",
        )

    # Process the document using the unified Content model
    try:
        with get_db() as db:
            service = FileContentIngestionService(router=parser_router, db=db)

            content = await service.ingest_bytes(
                data=contents,
                filename=filename,
                publication=publication,
                title=title,
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

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Document upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Processing failed due to an internal error")


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
