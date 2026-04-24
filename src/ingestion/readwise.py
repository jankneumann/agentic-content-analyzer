"""Readwise Highlights API v2 ingestion.

Imports books + highlights from every Readwise-connected upstream (Kindle,
Instapaper, Pocket, Apple Books, Airr, Reader, podcast, supplemental) via a
single export endpoint.

Each Readwise *book* becomes one Content row (``source_type=readwise``,
``source_id="readwise:{user_book_id}"``). Each *highlight* becomes one
Highlight row (``source='readwise'``, ``target_kind='content'``,
``target_id=content.id``, ``readwise_id=<hl.id>``).

Incremental sync uses the ``updatedAfter`` query param; the latest
``updated_at`` seen in a run is returned to the caller for persistence.

API: https://readwise.io/api_deets  (rate limit 240 req/min)
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from src.config import settings
from src.models.content import Content, ContentSource, ContentStatus
from src.models.highlight import Highlight
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.logging import get_logger

logger = get_logger(__name__)

READWISE_EXPORT_URL = "https://readwise.io/api/v2/export/"
READWISE_AUTH_URL = "https://readwise.io/api/v2/auth/"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ReadwiseIngestResult:
    """Aggregated result of a Readwise ingestion run."""

    books_ingested: int = 0
    books_updated: int = 0
    books_skipped: int = 0
    highlights_created: int = 0
    highlights_updated: int = 0
    highlights_soft_deleted: int = 0
    pages_fetched: int = 0
    latest_updated_at: datetime | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def items_ingested(self) -> int:
        """Count for orchestrator compatibility (treats books as the unit)."""
        return self.books_ingested + self.books_updated


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ReadwiseClient:
    """HTTP client for the Readwise Highlights API v2.

    Uses ``Authorization: Token <key>``. Respects the 240 req/min limit via
    simple per-call sleep when the server responds with 429.
    """

    def __init__(self, api_key: str | None = None, timeout: float = 30.0) -> None:
        self.api_key = api_key or settings.readwise_api_key
        if not self.api_key:
            raise ValueError(
                "READWISE_API_KEY is required. Get one at https://readwise.io/access_token "
                "and set it in .env, .secrets.yaml, or environment."
            )
        self._client = httpx.Client(
            timeout=timeout,
            headers={"Authorization": f"Token {self.api_key}"},
        )

    def verify_token(self) -> bool:
        """Ping /auth/ — returns True on 204."""
        resp = self._client.get(READWISE_AUTH_URL)
        return resp.status_code == 204

    def export(
        self,
        *,
        updated_after: datetime | None = None,
        ids: list[int] | None = None,
        include_deleted: bool = False,
        page_cursor: str | None = None,
    ) -> dict[str, Any]:
        """Fetch one page of the export endpoint.

        Returns the parsed JSON (``results`` + ``nextPageCursor``) as a dict.
        """
        params: dict[str, Any] = {}
        if updated_after is not None:
            # ISO 8601 as Readwise expects
            params["updatedAfter"] = updated_after.astimezone(UTC).isoformat()
        if ids:
            params["ids"] = ",".join(str(i) for i in ids)
        if include_deleted:
            params["includeDeleted"] = "true"
        if page_cursor:
            params["pageCursor"] = page_cursor

        # Simple retry loop for 429 rate-limit
        for attempt in range(4):
            resp = self._client.get(READWISE_EXPORT_URL, params=params)
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", "2"))
                logger.warning(
                    f"Readwise 429 rate-limit; sleeping {retry_after}s (attempt {attempt + 1}/4)"
                )
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError("Readwise export: exhausted retries on 429 rate-limit")

    def iter_export(
        self,
        *,
        updated_after: datetime | None = None,
        include_deleted: bool = False,
        source_types: list[str] | None = None,
    ) -> Any:
        """Paginate through the export endpoint, yielding book records.

        Args:
            updated_after: Only fetch books/highlights updated after this time.
            include_deleted: Include tombstones (for soft-delete sync).
            source_types: Restrict to these Readwise upstreams (empty = all).
        """
        cursor: str | None = None
        while True:
            page = self.export(
                updated_after=updated_after,
                include_deleted=include_deleted,
                page_cursor=cursor,
            )
            for book in page.get("results", []):
                if source_types and book.get("source") not in source_types:
                    continue
                yield book
            cursor = page.get("nextPageCursor")
            if not cursor:
                break

    def close(self) -> None:
        self._client.close()


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def _book_source_id(user_book_id: int | str) -> str:
    """Stable source_id for a Readwise book."""
    return f"readwise:{user_book_id}"


def _book_markdown(book: dict[str, Any]) -> str:
    """Render a Readwise book + highlights into markdown.

    This is a deliberately simple rendering — the canonical signal is the
    highlights themselves, which also land in the ``highlights`` table for
    structured retrieval. The markdown here exists so summarization / search /
    theme-analysis can consume the same Content surface as other sources.
    """
    parts: list[str] = []
    title = book.get("title") or "(untitled)"
    author = book.get("author") or ""
    source = book.get("source") or ""
    category = book.get("category") or ""

    header = f"# {title}"
    if author:
        header += f"\n\n*by {author}*"
    meta_bits = [b for b in (source, category) if b]
    if meta_bits:
        header += f"\n\n> Readwise source: {' · '.join(meta_bits)}"
    parts.append(header)

    highlights = book.get("highlights") or []
    if highlights:
        parts.append("\n## Highlights\n")
        for hl in highlights:
            if hl.get("is_deleted"):
                continue
            text = (hl.get("text") or "").strip()
            if not text:
                continue
            bullet = f"- {text}"
            note = (hl.get("note") or "").strip()
            if note:
                bullet += f"\n  > {note}"
            parts.append(bullet)

    return "\n".join(parts)


def _parse_dt(value: Any) -> datetime | None:
    """Parse a Readwise ISO timestamp into an aware datetime."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _highlight_fingerprint(hl: dict[str, Any]) -> str:
    """Fallback id for highlights without a stable Readwise id."""
    basis = f"{hl.get('text', '')}|{hl.get('highlighted_at', '')}|{hl.get('location', '')}"
    return hashlib.sha256(basis.encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ReadwiseContentIngestionService:
    """Service for importing Readwise books + highlights into ACA."""

    def __init__(self, api_key: str | None = None) -> None:
        self.client = ReadwiseClient(api_key=api_key)

    def ingest_content(
        self,
        *,
        updated_after: datetime | None = None,
        source_types: list[str] | None = None,
        include_deleted: bool | None = None,
        max_books: int | None = None,
        force_reprocess: bool = False,
    ) -> ReadwiseIngestResult:
        """Sync books + highlights from Readwise.

        Args:
            updated_after: Only fetch items updated after this time (incremental sync).
            source_types: Restrict to Readwise upstream sources (kindle, instapaper,
                pocket, apple_books, airr, reader, podcast, supplemental).
                None/empty = all.
            include_deleted: Include highlight tombstones for soft-delete sync.
                None falls back to ``settings.readwise_include_deleted``.
            max_books: Stop after ingesting this many books. None = no cap beyond
                the configured ``settings.readwise_max_entries``.
            force_reprocess: Re-summarize existing content by re-setting
                ``status=PENDING`` on the Content row.

        Returns:
            ReadwiseIngestResult with per-category counters and the latest
            ``updated_at`` seen (for caller-managed cursor persistence).
        """
        result = ReadwiseIngestResult()
        include_del = (
            include_deleted if include_deleted is not None else settings.readwise_include_deleted
        )
        cap = max_books if max_books is not None else settings.readwise_max_entries
        start = time.time()

        logger.info(
            "Starting Readwise ingest "
            f"(updated_after={updated_after}, source_types={source_types}, "
            f"include_deleted={include_del}, max_books={cap})"
        )

        books_seen = 0
        for book in self.client.iter_export(
            updated_after=updated_after,
            include_deleted=include_del,
            source_types=source_types,
        ):
            if books_seen >= cap:
                logger.info(f"Readwise ingest: hit max_books cap ({cap})")
                break
            books_seen += 1
            try:
                self._upsert_book(book, result, force_reprocess=force_reprocess)
            except Exception as exc:
                msg = f"Book '{book.get('title', '?')}' failed: {exc}"
                logger.warning(msg, exc_info=True)
                result.errors.append(msg)

            book_updated = _parse_dt(book.get("last_highlight_at") or book.get("updated"))
            if book_updated and (
                result.latest_updated_at is None or book_updated > result.latest_updated_at
            ):
                result.latest_updated_at = book_updated

        result.pages_fetched = (books_seen // 100) + 1  # rough — export pages ~100
        elapsed = time.time() - start
        logger.info(
            "Readwise ingest complete: "
            f"{result.books_ingested} new books, {result.books_updated} updated, "
            f"{result.books_skipped} skipped, {result.highlights_created} new highlights, "
            f"{result.highlights_updated} highlights updated, "
            f"{result.highlights_soft_deleted} soft-deleted, "
            f"{elapsed:.1f}s elapsed"
        )
        return result

    # ------------------------------------------------------------------
    # Per-book upsert
    # ------------------------------------------------------------------

    def _upsert_book(
        self,
        book: dict[str, Any],
        result: ReadwiseIngestResult,
        *,
        force_reprocess: bool,
    ) -> None:
        user_book_id = book.get("user_book_id") or book.get("id")
        if not user_book_id:
            result.books_skipped += 1
            return

        source_id = _book_source_id(user_book_id)
        title = book.get("title") or "(untitled Readwise book)"
        author = book.get("author") or None
        source_url = book.get("source_url") or None
        readwise_source = book.get("source") or ""
        category = book.get("category") or ""
        published = _parse_dt(book.get("published_date"))

        markdown = _book_markdown(book)
        content_hash = generate_markdown_hash(markdown)

        metadata = {
            "readwise": {
                "user_book_id": user_book_id,
                "source": readwise_source,
                "category": category,
                "num_highlights": len(book.get("highlights") or []),
                "book_tags": book.get("book_tags") or [],
                "cover_image_url": book.get("cover_image_url"),
                "readable_title": book.get("readable_title"),
                "unique_url": book.get("unique_url"),
                "asin": book.get("asin"),
                "document_note": book.get("document_note"),
            }
        }

        with get_db() as db:
            existing: Content | None = (
                db.query(Content)
                .filter(
                    Content.source_type == ContentSource.READWISE,
                    Content.source_id == source_id,
                )
                .one_or_none()
            )

            if existing is None:
                content = Content(
                    source_type=ContentSource.READWISE,
                    source_id=source_id,
                    source_url=source_url,
                    title=title[:1000],
                    author=author[:500] if author else None,
                    publication=readwise_source[:500] if readwise_source else None,
                    published_date=published,
                    markdown_content=markdown,
                    content_hash=content_hash,
                    status=ContentStatus.PENDING,
                    metadata_json=metadata,
                    ingested_at=datetime.now(UTC),
                )
                db.add(content)
                db.flush()
                result.books_ingested += 1
                logger.debug(f"Readwise: created content id={content.id} source_id={source_id}")
            else:
                content = existing
                changed = content.content_hash != content_hash
                if changed or force_reprocess:
                    content.title = title[:1000]
                    content.author = author[:500] if author else None
                    content.publication = readwise_source[:500] if readwise_source else None
                    content.published_date = published
                    content.source_url = source_url
                    content.markdown_content = markdown
                    content.content_hash = content_hash
                    content.metadata_json = metadata
                    if force_reprocess:
                        content.status = ContentStatus.PENDING
                    result.books_updated += 1
                else:
                    result.books_skipped += 1

            # Sync highlights (insert/update/soft-delete)
            self._sync_highlights(db, content, book.get("highlights") or [], result)
            db.commit()

    # ------------------------------------------------------------------
    # Highlight sync
    # ------------------------------------------------------------------

    def _sync_highlights(
        self,
        db: Any,
        content: Content,
        highlights: list[dict[str, Any]],
        result: ReadwiseIngestResult,
    ) -> None:
        for hl in highlights:
            readwise_id = str(hl.get("id") or _highlight_fingerprint(hl))
            is_deleted = bool(hl.get("is_deleted"))

            existing: Highlight | None = (
                db.query(Highlight)
                .filter(Highlight.readwise_id == readwise_id)
                .one_or_none()
            )

            if is_deleted:
                if existing and existing.deleted_at is None:
                    existing.deleted_at = datetime.now(UTC)
                    result.highlights_soft_deleted += 1
                continue

            text = (hl.get("text") or "").strip()
            if not text:
                continue

            note = (hl.get("note") or None)
            color = hl.get("color") or None
            location = hl.get("location")
            location_type = hl.get("location_type") or None
            highlighted_at = _parse_dt(hl.get("highlighted_at"))
            tags = [t.get("name") for t in (hl.get("tags") or []) if t.get("name")]
            source_url = hl.get("readwise_url") or hl.get("url") or None

            if existing is None:
                row = Highlight(
                    content_id=content.id,
                    target_kind="content",
                    target_id=content.id,
                    text=text,
                    note=note,
                    color=color,
                    location=location if isinstance(location, int) else None,
                    location_type=location_type,
                    tags=tags,
                    source="readwise",
                    readwise_id=readwise_id,
                    source_url=source_url,
                    highlighted_at=highlighted_at,
                )
                db.add(row)
                result.highlights_created += 1
            else:
                dirty = False
                for field_name, new_val in (
                    ("text", text),
                    ("note", note),
                    ("color", color),
                    ("location", location if isinstance(location, int) else None),
                    ("location_type", location_type),
                    ("source_url", source_url),
                    ("highlighted_at", highlighted_at),
                ):
                    if getattr(existing, field_name) != new_val:
                        setattr(existing, field_name, new_val)
                        dirty = True
                if existing.tags != tags:
                    existing.tags = tags
                    dirty = True
                if existing.deleted_at is not None:
                    # Un-delete if Readwise resurrected it
                    existing.deleted_at = None
                    dirty = True
                if dirty:
                    existing.updated_at = datetime.now(UTC)
                    result.highlights_updated += 1

    def close(self) -> None:
        self.client.close()
