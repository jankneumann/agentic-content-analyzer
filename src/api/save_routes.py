"""Save URL API endpoints for mobile content capture.

These endpoints allow saving URLs for background content extraction,
supporting iOS Shortcuts, bookmarklets, Chrome extension, and web forms.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, HttpUrl, StringConstraints

from src.models.content import Content, ContentSource, ContentStatus
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Maximum HTML payload size (5 MB)
MAX_HTML_SIZE = 5 * 1024 * 1024

router = APIRouter(prefix="/api/v1/content", tags=["save"])

# Templates for the web save page (path relative to this file, not CWD)
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))


# Request/Response Models
class SaveURLRequest(BaseModel):
    """Request body for saving a URL."""

    url: HttpUrl = Field(..., description="URL to save and extract content from")
    title: str | None = Field(None, max_length=1000, description="Optional title")
    excerpt: str | None = Field(None, max_length=5000, description="Optional excerpt/selection")
    tags: list[Annotated[str, StringConstraints(max_length=100)]] | None = Field(
        default=None, max_length=20, description="Optional tags"
    )
    notes: str | None = Field(None, max_length=10000, description="Optional user notes")
    source: str | None = Field(None, max_length=50, description="Capture source identifier")


class SavePageRequest(BaseModel):
    """Request body for saving a page with client-captured HTML."""

    url: HttpUrl = Field(..., description="Source URL (for dedup and metadata)")
    html: Annotated[str, StringConstraints(max_length=MAX_HTML_SIZE)] = Field(
        ..., description="Rendered HTML from the browser (max 5 MB)"
    )
    title: str | None = Field(None, max_length=1000, description="Page title")
    excerpt: str | None = Field(None, max_length=5000, description="Optional excerpt/selection")
    tags: list[Annotated[str, StringConstraints(max_length=100)]] | None = Field(
        default=None, max_length=20, description="Optional tags"
    )
    notes: str | None = Field(None, max_length=10000, description="Optional user notes")
    source: str | None = Field(None, max_length=50, description="Capture source identifier")


class SaveURLResponse(BaseModel):
    """Response for save URL operation."""

    content_id: int = Field(..., description="ID of the created/existing content")
    status: str = Field(..., description="Status: 'queued' or 'exists'")
    message: str = Field(..., description="Human-readable message")
    duplicate: bool = Field(False, description="Whether URL was already saved")


# SavePageResponse uses the same shape as SaveURLResponse for consistency
SavePageResponse = SaveURLResponse


class ContentStatusResponse(BaseModel):
    """Response for content status query."""

    content_id: int
    status: str
    title: str | None = None
    word_count: int | None = None
    error: str | None = None


# Helper to enqueue extraction task
async def _enqueue_extraction(content_id: int) -> None:
    """Enqueue URL extraction task.

    Uses PGQueuer if available, otherwise falls back to direct extraction.
    """
    try:
        from src.queue.setup import enqueue_queue_job

        await enqueue_queue_job(
            "extract_url_content",
            {"content_id": content_id},
        )
        logger.info(f"Enqueued extraction task for content_id={content_id}")
    except Exception as e:
        if isinstance(e, ImportError):
            logger.warning("PGQueuer not available, using direct extraction")
        else:
            logger.warning(f"PGQueuer enqueue failed ({e}), using direct extraction")

        from src.services.url_extractor import URLExtractor

        with get_db() as db:
            extractor = URLExtractor(db)
            await extractor.extract_content(content_id)


# Helper to process client-supplied HTML
async def _process_client_html(content_id: int, html: str, source_url: str) -> None:
    """Process client-supplied HTML.

    Parses HTML to markdown, extracts and stores images, and updates the Content record.
    """
    from src.services.html_processor import process_client_html

    with get_db() as db:
        await process_client_html(db, content_id, html, source_url)


@router.post("/save-url", response_model=SaveURLResponse, status_code=201)
async def save_url(
    request: SaveURLRequest,
    background_tasks: BackgroundTasks,
) -> SaveURLResponse:
    """Save a URL for content extraction.

    Creates a Content record and queues background extraction.
    Returns immediately with the content ID for status polling.

    If the URL already exists, returns the existing content ID
    with status "exists".
    """
    url_str = str(request.url)

    with get_db() as db:
        # Check for duplicate
        existing = db.query(Content).filter(Content.source_url == url_str).first()
        if existing:
            return SaveURLResponse(
                content_id=existing.id,
                status="exists",
                message="URL already saved.",
                duplicate=True,
            )

        # Build metadata
        metadata: dict = {}
        if request.excerpt:
            metadata["excerpt"] = request.excerpt
        if request.tags:
            metadata["tags"] = request.tags
        if request.notes:
            metadata["notes"] = request.notes
        if request.source:
            metadata["capture_source"] = request.source

        # Create content record
        content = Content(
            source_type=ContentSource.WEBPAGE,
            source_id=f"webpage:{url_str}",
            source_url=url_str,
            title=request.title or url_str,  # Use URL as title until extracted
            markdown_content="",  # Placeholder until extraction completes
            content_hash=generate_markdown_hash(""),
            status=ContentStatus.PENDING,
            metadata_json=metadata if metadata else None,
            ingested_at=datetime.now(UTC),
        )

        db.add(content)
        db.commit()
        db.refresh(content)

        content_id = content.id
        logger.info(f"Created content record: id={content_id}, url={url_str}")

    # Enqueue extraction task in background
    background_tasks.add_task(_enqueue_extraction, content_id)

    return SaveURLResponse(
        content_id=content_id,
        status="queued",
        message="URL saved. Content extraction in progress.",
        duplicate=False,
    )


@router.post("/save-page", response_model=SavePageResponse, status_code=201)
async def save_page(
    request: SavePageRequest,
    background_tasks: BackgroundTasks,
) -> SavePageResponse:
    """Save a page with client-captured HTML content.

    Creates a Content record and processes the HTML to extract markdown and images.
    Returns immediately with the content ID for status polling.

    This endpoint is used by the Chrome extension when "Capture full page" mode
    is enabled, allowing capture of paywall-gated and JS-rendered content.

    If the URL already exists, returns the existing content ID with status "exists".
    """
    url_str = str(request.url)

    with get_db() as db:
        # Check for duplicate by URL
        existing = db.query(Content).filter(Content.source_url == url_str).first()
        if existing:
            return SavePageResponse(
                content_id=existing.id,
                status="exists",
                message="URL already saved.",
                duplicate=True,
            )

        # Build metadata with capture method flag
        metadata: dict = {"capture_method": "client_html"}
        if request.excerpt:
            metadata["excerpt"] = request.excerpt
        if request.tags:
            metadata["tags"] = request.tags
        if request.notes:
            metadata["notes"] = request.notes
        if request.source:
            metadata["capture_source"] = request.source

        # Create content record
        content = Content(
            source_type=ContentSource.WEBPAGE,
            source_id=f"webpage:{url_str}",
            source_url=url_str,
            title=request.title or url_str,  # Use URL as title until extracted
            markdown_content="",  # Placeholder until processing completes
            content_hash=generate_markdown_hash(""),
            status=ContentStatus.PENDING,
            metadata_json=metadata,
            ingested_at=datetime.now(UTC),
        )

        db.add(content)
        db.commit()
        db.refresh(content)

        content_id = content.id
        logger.info(f"Created content record for client HTML: id={content_id}, url={url_str}")

    # Process HTML in background
    background_tasks.add_task(_process_client_html, content_id, request.html, url_str)

    return SavePageResponse(
        content_id=content_id,
        status="queued",
        message="Page saved. Content processing in progress.",
        duplicate=False,
    )


@router.get("/{content_id}/status", response_model=ContentStatusResponse)
async def get_content_status(content_id: int) -> ContentStatusResponse:
    """Get the extraction status of a content record.

    Use this to poll for extraction completion after saving a URL.
    """
    with get_db() as db:
        content = db.query(Content).filter(Content.id == content_id).first()
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")

        word_count = None
        if content.markdown_content:
            word_count = len(content.markdown_content.split())

        return ContentStatusResponse(
            content_id=content.id,
            status=content.status.value,
            title=content.title,
            word_count=word_count,
            error=content.error_message,
        )


# Web Save Page (for bookmarklet and mobile fallback)
@router.get("/save", response_class=HTMLResponse, include_in_schema=False)
async def save_page_form(
    request: Request,
    url: Annotated[str | None, Query(description="URL to save", max_length=2000)] = None,
    title: Annotated[str | None, Query(description="Page title", max_length=1000)] = None,
    excerpt: Annotated[str | None, Query(description="Selected text", max_length=5000)] = None,
) -> HTMLResponse:
    """Render the web save page.

    This page is used by:
    - Bookmarklets that redirect here with URL params
    - Mobile browsers as a fallback when shortcuts don't work
    - Direct access for manual URL entry

    Query params are pre-filled into the form.
    """
    # Derive API base URL from request for cross-origin bookmarklet support
    api_base_url = str(request.base_url).rstrip("/")

    return templates.TemplateResponse(
        "save.html",
        {
            "request": request,
            "url": url or "",
            "title": title or "",
            "excerpt": excerpt or "",
            "api_base_url": api_base_url,
        },
    )


# Bookmarklet generator/installation page
@router.get("/bookmarklet", response_class=HTMLResponse, include_in_schema=False)
async def bookmarklet_page(request: Request) -> HTMLResponse:
    """Render the bookmarklet installation page.

    Generates a bookmarklet pre-configured with this server's URL.
    Users drag the link to their bookmarks bar for one-click saving.
    """
    api_base_url = str(request.base_url).rstrip("/")

    return templates.TemplateResponse(
        "bookmarklet.html",
        {
            "request": request,
            "api_base_url": api_base_url,
        },
    )
