"""Post-ingestion hook for content reference extraction.

Called after content ingestion to extract references, store them, and
trigger background resolution.  Every public function in this module is
**fail-safe** — errors are logged but never propagate to callers.

Integration approach
--------------------
The orchestrator functions return plain ``int`` counts and do not expose
the underlying ``Content`` objects.  Modifying every ingestion service's
persist method would be too invasive.  Instead, the hook is designed to
be called:

1. **Explicitly** — from ingestion code paths that *do* have access to a
   ``Content`` object (e.g. ``ingest_url``, individual service persist
   methods that are amended over time).
2. **Via backfill** — the ``aca manage backfill-refs`` CLI command
   (or queue worker entrypoint ``resolve_references``) processes content
   that was ingested without the hook.

This keeps the change minimal and non-breaking.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from src.models.content import Content

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Primary hook
# ---------------------------------------------------------------------------


def on_content_ingested(content: Content, db: Session) -> None:
    """Extract and store references after content ingestion.

    Fail-safe: errors are logged but never block ingestion.

    Steps:
    1. Check if extraction is enabled
    2. Extract references from content
    3. Store to content_references table
    4. Enqueue background resolution job
    5. Run reverse resolution (check if new content resolves existing
       unresolved refs)
    """
    try:
        from src.config.settings import get_settings

        settings = get_settings()
        if not settings.reference_extraction_enabled:
            return

        from src.services.reference_extractor import ReferenceExtractor

        extractor = ReferenceExtractor()

        # Extract references
        refs = extractor.extract_from_content(content, db)
        if not refs:
            return

        # Filter by confidence threshold
        min_confidence = settings.reference_min_confidence
        refs = [r for r in refs if r.confidence >= min_confidence]
        if not refs:
            return

        # Store references
        stored = extractor.store_references(content.id, refs, db)
        if stored > 0:
            logger.info(
                "Extracted %d references from content %d (%s)",
                stored,
                content.id,
                (content.title or "")[:50],
            )

        # Enqueue background resolution
        _enqueue_resolution(content.id)

        # Reverse resolution — check if this new content resolves
        # existing unresolved refs
        _run_reverse_resolution(content, db)

    except Exception:
        logger.warning(
            "Reference extraction failed for content %d, continuing ingestion",
            content.id,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Chunk re-anchoring hook
# ---------------------------------------------------------------------------


def reanchor_references(content_id: int, db: Session) -> int:
    """Re-anchor references that have no ``source_chunk_id`` to chunks.

    Called after chunk indexing completes for a content item.  Finds all
    ``ContentReference`` rows for *content_id* where ``source_chunk_id``
    is ``NULL`` and attempts to match them to ``DocumentChunk`` rows using
    the reference's ``context_snippet`` or ``external_id`` against the
    chunk text.

    Returns the number of references successfully re-anchored.

    Fail-safe: never raises.
    """
    try:
        from src.models.chunk import DocumentChunk
        from src.models.content_reference import ContentReference

        # Load unanchored refs
        refs = (
            db.query(ContentReference)
            .filter(
                ContentReference.source_content_id == content_id,
                ContentReference.source_chunk_id.is_(None),
            )
            .all()
        )
        if not refs:
            return 0

        # Load chunks ordered by index
        chunks = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.content_id == content_id)
            .order_by(DocumentChunk.chunk_index)
            .all()
        )
        if not chunks:
            return 0

        anchored = 0
        for ref in refs:
            chunk = _find_chunk_for_ref(ref, chunks)
            if chunk is not None:
                ref.source_chunk_id = chunk.id
                anchored += 1

        if anchored > 0:
            db.commit()
            logger.info(
                "Re-anchored %d references for content %d",
                anchored,
                content_id,
            )

        return anchored

    except Exception:
        logger.warning(
            "Reference re-anchoring failed for content %d",
            content_id,
            exc_info=True,
        )
        return 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_chunk_for_ref(ref: object, chunks: list) -> object | None:
    """Return the chunk that contains the reference's identifier or snippet.

    Search strategy:
    1. If ``context_snippet`` is present, find the chunk whose text
       contains a substantial substring of the snippet.
    2. If ``external_id`` is present, find the chunk whose text contains
       the literal ID string.
    """
    snippet = getattr(ref, "context_snippet", None)
    ext_id = getattr(ref, "external_id", None)

    for chunk in chunks:
        chunk_text = getattr(chunk, "text", "") or ""
        if not chunk_text:
            continue

        # Strategy 1: snippet match (use middle portion to avoid boundary noise)
        if snippet and len(snippet) > 20:
            mid = snippet[10:-10]
            if mid in chunk_text:
                return chunk

        # Strategy 2: literal external_id match
        if ext_id and ext_id in chunk_text:
            return chunk

    return None


def _enqueue_resolution(content_id: int) -> None:
    """Enqueue a ``resolve_references`` job for this content."""
    try:
        import asyncio

        from src.queue.setup import enqueue_queue_job

        # Best-effort enqueue — don't fail if queue is unavailable
        try:
            loop = asyncio.get_running_loop()
            _task = loop.create_task(  # noqa: RUF006
                enqueue_queue_job("resolve_references", {"content_id": content_id})
            )
        except RuntimeError:
            # No running loop — run synchronously
            asyncio.run(enqueue_queue_job("resolve_references", {"content_id": content_id}))
    except Exception:
        logger.debug("Could not enqueue resolution job for content %d", content_id)


def _run_reverse_resolution(content: Content, db: Session) -> None:
    """Check if new content resolves existing unresolved references."""
    try:
        from src.services.reference_resolver import ReferenceResolver

        resolver = ReferenceResolver(db)
        resolved = resolver.resolve_incoming(content)
        if resolved > 0:
            logger.info(
                "Reverse resolution: %d existing references now resolved by content %d",
                resolved,
                content.id,
            )
    except Exception:
        logger.debug(
            "Reverse resolution failed for content %d",
            content.id,
            exc_info=True,
        )
