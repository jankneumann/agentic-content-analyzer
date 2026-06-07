"""Save URL API endpoints for mobile content capture.

These endpoints allow saving URLs for background content extraction,
supporting iOS Shortcuts, bookmarklets, Chrome extension, and web forms.
"""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, HttpUrl, StringConstraints

from src.api.save_rate_limiter import save_rate_limiter
from src.ingestion.url_router import RouteKind, classify_url, route_to_source
from src.models.content import Content, ContentSource, ContentStatus
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.logging import get_logger
from src.utils.youtube_links import extract_playlist_id, extract_video_id

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


# ---------------------------------------------------------------------------
# Auto-routing helpers for shared URLs
# ---------------------------------------------------------------------------


def _source_id_for_route(url: str, kind: RouteKind) -> str:
    """Compute the ``source_id`` for a shared URL given its route.

    YouTube routes use the canonical ``youtube:<video_id>`` /
    ``youtube_playlist:<id>`` keys so the row lines up with the rows the
    YouTube ingestion service creates (and so the in-place fill on
    ``youtube_video`` finds it). Everything else keeps the legacy
    ``webpage:<url>`` / ``feed:<url>`` shapes.
    """
    if kind == RouteKind.YOUTUBE_VIDEO:
        vid = extract_video_id(url)
        return f"youtube:{vid}" if vid else f"webpage:{url}"
    if kind == RouteKind.YOUTUBE_PLAYLIST:
        pid = extract_playlist_id(url)
        return f"youtube_playlist:{pid}" if pid else f"webpage:{url}"
    if kind == RouteKind.RSS_FEED:
        return f"feed:{url}"
    return f"webpage:{url}"


def _find_existing_for_route(db, url: str, kind: RouteKind) -> Content | None:
    """Find an already-saved row for *url*, honouring route-specific dedup.

    A YouTube video may already exist under a different URL form (it was
    ingested from a playlist or shared as youtu.be vs. watch?v=). Deduping by
    the ``youtube:<id>`` source_id avoids both a duplicate save and an
    IntegrityError against the unique (source_type, source_id) index.
    """
    existing = db.query(Content).filter(Content.source_url == url).first()
    if existing:
        return existing

    if kind == RouteKind.YOUTUBE_VIDEO:
        vid = extract_video_id(url)
        if vid:
            return (
                db.query(Content)
                .filter(
                    Content.source_type == ContentSource.YOUTUBE,
                    Content.source_id == f"youtube:{vid}",
                )
                .first()
            )
    return None


def _finalize_receipt(content_id: int, items_ingested: int, label: str) -> None:
    """Mark a multi-item route's tracking row as a completed receipt.

    Feeds and playlists expand into many individual Content rows, so the row
    created for the shared URL itself becomes a small receipt: it is set to
    COMPLETED (a terminal status the summarizer ignores) with a one-line note
    and the ingested count in metadata.
    """
    with get_db() as db:
        content = db.query(Content).filter(Content.id == content_id).first()
        if content is None:
            return
        content.status = ContentStatus.COMPLETED
        content.markdown_content = (
            f"Ingested {items_ingested} item(s) from this {label}: {content.source_url}"
        )
        meta = dict(content.metadata_json or {})
        meta["items_ingested"] = items_ingested
        meta["is_receipt"] = True
        content.metadata_json = meta


async def _process_routed_save(content_id: int) -> None:
    """Background processing for a shared URL that was auto-routed.

    Reads the route stored on the row's metadata and dispatches:

    - ``youtube_video``    -> fill this row in place with the transcript/analysis
    - ``rss_feed``         -> ingest the feed's entries, mark this row a receipt
    - ``youtube_playlist`` -> ingest the playlist's videos, mark this row a receipt

    Falls back to plain URL extraction if the route is missing/unknown.
    """
    with get_db() as db:
        content = db.query(Content).filter(Content.id == content_id).first()
        if content is None:
            logger.error(f"_process_routed_save: content {content_id} not found")
            return
        meta = content.metadata_json or {}
        route = meta.get("route")
        url = content.source_url
        tags = meta.get("tags")
        notes = meta.get("notes")

    try:
        if route == RouteKind.YOUTUBE_VIDEO.value:
            from src.ingestion.youtube import YouTubeContentIngestionService

            service = YouTubeContentIngestionService()
            # force_reprocess=True so _process_video updates the pre-created
            # youtube:<id> row in place rather than skipping it.
            await service.ingest_video(url, force_reprocess=True, tags=tags, notes=notes)
            return

        if route == RouteKind.RSS_FEED.value:
            from src.config.sources import RSSSource
            from src.ingestion.rss import RSSContentIngestionService

            svc = RSSContentIngestionService()
            try:
                resp = await asyncio.to_thread(
                    lambda: svc.ingest_content(sources=[RSSSource(url=url, tags=tags or [])])
                )
            finally:
                svc.close()
            _finalize_receipt(content_id, resp.items_ingested, "feed")
            return

        if route == RouteKind.YOUTUBE_PLAYLIST.value:
            from src.ingestion.youtube import YouTubeContentIngestionService

            pid = extract_playlist_id(url)
            if not pid:
                raise ValueError(f"Could not extract a playlist id from: {url}")
            service = YouTubeContentIngestionService()
            result = await service.ingest_playlist(pid)
            _finalize_receipt(content_id, result.items_fetched, "playlist")
            return

        # Unknown/missing route — fall back to generic extraction.
        logger.warning(f"_process_routed_save: unknown route '{route}', extracting as web page")
        from src.services.url_extractor import URLExtractor

        with get_db() as db:
            await URLExtractor(db).extract_content(content_id)

    except Exception as e:
        logger.error(f"Routed save failed for content_id={content_id}: {e}")
        with get_db() as db:
            content = db.query(Content).filter(Content.id == content_id).first()
            if content is not None:
                content.status = ContentStatus.FAILED
                content.error_message = str(e)
        raise


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
    http_request: Request,
) -> SaveURLResponse:
    """Save a URL for content extraction.

    Creates a Content record and queues background extraction.
    Returns immediately with the content ID for status polling.

    If the URL already exists, returns the existing content ID
    with status "exists".
    """
    client_ip = http_request.client.host if http_request.client else "unknown"
    if save_rate_limiter.is_limited(client_ip):
        retry_after = save_rate_limiter.get_retry_after(client_ip)
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    url_str = str(request.url)

    # Auto-route the shared URL to the right handler (YouTube video/playlist,
    # RSS feed, or generic web page). The web-page path is unchanged.
    kind = classify_url(url_str)

    with get_db() as db:
        # Check for duplicate (route-aware: a YouTube video may already exist
        # under a different URL form / source_id).
        existing = _find_existing_for_route(db, url_str, kind)
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
        # Record the routing decision so the background task knows how to
        # process this row (web pages don't need it — they keep prior behaviour).
        if kind != RouteKind.WEBPAGE:
            metadata["route"] = kind.value

        # Create content record
        content = Content(
            source_type=route_to_source(kind),
            source_id=_source_id_for_route(url_str, kind),
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
        logger.info(f"Created content record: id={content_id}, url={url_str}, route={kind.value}")

    # Enqueue processing in the background. Web pages keep the original
    # extraction path (and the original message, for client compatibility);
    # routed types go through the router.
    if kind == RouteKind.WEBPAGE:
        background_tasks.add_task(_enqueue_extraction, content_id)
        message = "URL saved. Content extraction in progress."
    else:
        background_tasks.add_task(_process_routed_save, content_id)
        message = f"URL saved. Routed to {kind.value} ingestion."

    return SaveURLResponse(
        content_id=content_id,
        status="queued",
        message=message,
        duplicate=False,
    )


@router.post("/save-page", response_model=SavePageResponse, status_code=201)
async def save_page(
    request: SavePageRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
) -> SavePageResponse:
    """Save a page with client-captured HTML content.

    Creates a Content record and processes the HTML to extract markdown and images.
    Returns immediately with the content ID for status polling.

    This endpoint is used by the Chrome extension when "Capture full page" mode
    is enabled, allowing capture of paywall-gated and JS-rendered content.

    If the URL already exists, returns the existing content ID with status "exists".
    """
    client_ip = http_request.client.host if http_request.client else "unknown"
    if save_rate_limiter.is_limited(client_ip):
        retry_after = save_rate_limiter.get_retry_after(client_ip)
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

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
        request,
        "save.html",
        {
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
        request,
        "bookmarklet.html",
        {
            "api_base_url": api_base_url,
        },
    )


# iOS Shortcut installation page
@router.get("/shortcut", response_class=HTMLResponse, include_in_schema=False)
async def shortcut_page(request: Request) -> HTMLResponse:
    """Render the iOS Shortcut installation page.

    Provides instructions for installing the iOS Shortcut that enables
    saving URLs directly from the iOS Share Sheet.
    """
    api_base_url = str(request.base_url).rstrip("/")

    return templates.TemplateResponse(
        request,
        "shortcut.html",
        {
            "api_base_url": api_base_url,
        },
    )
