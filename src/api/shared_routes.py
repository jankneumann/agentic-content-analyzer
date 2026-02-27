"""Public shared content routes.

Unauthenticated endpoints for viewing shared content via token-based URLs.
Supports content negotiation (HTML vs JSON) and rate limiting.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from markdown_it import MarkdownIt

from src.api.share_rate_limiter import share_rate_limiter
from src.models.content import Content
from src.models.digest import Digest
from src.models.summary import Summary
from src.services.file_storage import get_storage
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/shared", tags=["shared"])

# Template setup
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

# Markdown renderer
# Disable HTML rendering to prevent XSS in shared content
_md = MarkdownIt("commonmark", {"html": False})


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind a proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(request: Request) -> None:
    """Check rate limit and raise 429 if exceeded."""
    ip = _get_client_ip(request)
    if share_rate_limiter.is_limited(ip):
        retry_after = share_rate_limiter.get_retry_after(ip)
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def _wants_html(request: Request) -> bool:
    """Check if the client prefers HTML over JSON."""
    accept = request.headers.get("accept", "")
    return "text/html" in accept


def _md_to_html(text: str | None) -> str:
    """Convert markdown text to HTML."""
    if not text:
        return ""
    return _md.render(text)


def _format_date(dt) -> str:
    """Format a datetime for display."""
    if dt is None:
        return ""
    return dt.strftime("%B %d, %Y")


@router.get("/content/{token}")
async def get_shared_content(token: str, request: Request):
    """View shared content by token."""
    _check_rate_limit(request)

    with get_db() as db:
        record = (
            db.query(Content)
            .filter(Content.share_token == token, Content.is_public.is_(True))
            .first()
        )
        if not record:
            raise HTTPException(status_code=404, detail="Shared content not found")

        if _wants_html(request):
            return templates.TemplateResponse(
                "shared/content.html",
                {
                    "request": request,
                    "title": record.title,
                    "author": record.author,
                    "publication": record.publication,
                    "published_date": _format_date(record.published_date),
                    "content_html": _md_to_html(record.markdown_content),
                    "description": (record.markdown_content or "")[:200],
                    "share_url": str(request.url),
                },
            )

        return JSONResponse(
            {
                "id": record.id,
                "title": record.title,
                "author": record.author,
                "publication": record.publication,
                "published_date": record.published_date.isoformat()
                if record.published_date
                else None,
                "markdown_content": record.markdown_content,
                "source_type": record.source_type.value if record.source_type else None,
            }
        )


@router.get("/summary/{token}")
async def get_shared_summary(token: str, request: Request):
    """View shared summary by token."""
    _check_rate_limit(request)

    with get_db() as db:
        record = (
            db.query(Summary)
            .filter(Summary.share_token == token, Summary.is_public.is_(True))
            .first()
        )
        if not record:
            raise HTTPException(status_code=404, detail="Shared summary not found")

        # Get associated content title
        source_title = None
        if record.content_id:
            content = db.query(Content.title).filter(Content.id == record.content_id).first()
            if content:
                source_title = content.title

        if _wants_html(request):
            return templates.TemplateResponse(
                "shared/summary.html",
                {
                    "request": request,
                    "title": f"Summary: {source_title or 'Content'}",
                    "source_title": source_title,
                    "created_at": _format_date(record.created_at),
                    "executive_summary": record.executive_summary,
                    "key_themes": record.key_themes or [],
                    "strategic_insights": record.strategic_insights or [],
                    "actionable_items": record.actionable_items or [],
                    "markdown_html": _md_to_html(record.markdown_content),
                    "description": (record.executive_summary or "")[:200],
                    "share_url": str(request.url),
                },
            )

        return JSONResponse(
            {
                "id": record.id,
                "content_id": record.content_id,
                "source_title": source_title,
                "executive_summary": record.executive_summary,
                "key_themes": record.key_themes,
                "strategic_insights": record.strategic_insights,
                "actionable_items": record.actionable_items,
                "markdown_content": record.markdown_content,
                "created_at": record.created_at.isoformat() if record.created_at else None,
            }
        )


@router.get("/digest/{token}")
async def get_shared_digest(token: str, request: Request):
    """View shared digest by token."""
    _check_rate_limit(request)

    with get_db() as db:
        record = (
            db.query(Digest).filter(Digest.share_token == token, Digest.is_public.is_(True)).first()
        )
        if not record:
            raise HTTPException(status_code=404, detail="Shared digest not found")

        # Check for audio digest
        audio_url = None
        if record.audio_digests:
            latest_audio = max(
                record.audio_digests, key=lambda a: a.created_at or datetime.min.replace(tzinfo=UTC)
            )
            if latest_audio.audio_url:
                # Build audio URL relative to the API
                audio_url = f"/shared/audio/{token}"

        period = ""
        if record.period_start and record.period_end:
            period = f"{_format_date(record.period_start)} - {_format_date(record.period_end)}"

        if _wants_html(request):
            return templates.TemplateResponse(
                "shared/digest.html",
                {
                    "request": request,
                    "title": record.title,
                    "digest_type": record.digest_type.value if record.digest_type else "",
                    "period": period,
                    "newsletter_count": record.newsletter_count,
                    "executive_overview": record.executive_overview,
                    "markdown_html": _md_to_html(record.markdown_content),
                    "audio_url": audio_url,
                    "description": (record.executive_overview or "")[:200],
                    "share_url": str(request.url),
                    "og_type": "article",
                },
            )

        return JSONResponse(
            {
                "id": record.id,
                "title": record.title,
                "digest_type": record.digest_type.value if record.digest_type else None,
                "period_start": record.period_start.isoformat() if record.period_start else None,
                "period_end": record.period_end.isoformat() if record.period_end else None,
                "executive_overview": record.executive_overview,
                "markdown_content": record.markdown_content,
                "newsletter_count": record.newsletter_count,
                "audio_url": audio_url,
                "created_at": record.created_at.isoformat() if record.created_at else None,
            }
        )


@router.get("/audio/{token}")
async def get_shared_audio(token: str, request: Request):
    """Stream audio for a shared digest.

    Serves the audio file directly instead of redirecting to the
    authenticated files endpoint, so unauthenticated recipients
    can play audio on shared digest pages.
    """
    _check_rate_limit(request)

    with get_db() as db:
        record = (
            db.query(Digest).filter(Digest.share_token == token, Digest.is_public.is_(True)).first()
        )
        if not record:
            raise HTTPException(status_code=404, detail="Shared digest not found")

        if not record.audio_digests:
            raise HTTPException(status_code=404, detail="No audio available for this digest")

        latest_audio = max(
            record.audio_digests, key=lambda a: a.created_at or datetime.min.replace(tzinfo=UTC)
        )
        if not latest_audio.audio_url:
            raise HTTPException(status_code=404, detail="Audio file not available")

        audio_filename = os.path.basename(latest_audio.audio_url)

    # Serve directly via storage provider (no auth redirect needed)
    storage = get_storage(bucket="audio-digests")
    storage_path = f"audio-digests/{audio_filename}"

    # Cloud providers: redirect to time-limited signed URL (no auth needed)
    if hasattr(storage, "get_signed_url") and storage.provider_name in (
        "s3",
        "supabase",
        "railway",
    ):
        signed_url = await storage.get_signed_url(storage_path, expires_in=3600)
        return RedirectResponse(url=signed_url, status_code=302)

    # Local storage: serve file directly
    local_path = storage.get_local_path(storage_path)
    if local_path and local_path.exists():
        return FileResponse(
            path=local_path,
            media_type="audio/mpeg",
            filename=audio_filename,
            headers={
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600",
            },
        )

    raise HTTPException(status_code=404, detail="Audio file not available")
