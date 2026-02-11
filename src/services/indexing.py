"""Search indexing service for content ingestion integration.

Provides `index_content()` — a fail-safe helper that chunks content and
generates embeddings for search. Called after content is committed to
the database. Failures are logged but never propagated to the caller,
ensuring content ingestion succeeds even if search indexing fails.

Also provides `register_content_listeners()` for automatic rechunking
when `Content.markdown_content` is updated.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import event, text
from sqlalchemy.orm import Session

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


def index_content(
    content: object,  # Content model — use object to avoid circular import
    db: Session,
) -> None:
    """Chunk and embed content for search indexing.

    This is the main integration point for ingestion pipelines.
    Call after content is committed/flushed to the database.

    Behavior:
    - Gated behind ENABLE_SEARCH_INDEXING setting
    - Catches ALL exceptions — never raises to caller
    - On chunking failure: no chunks created, content preserved
    - On embedding failure: chunks saved without embeddings (BM25-searchable)

    Args:
        content: Content model instance (must have id and markdown_content)
        db: SQLAlchemy session (same session that holds the content)
    """
    settings = get_settings()
    if not settings.enable_search_indexing:
        return

    try:
        _index_content_impl(content, db)
    except Exception:
        logger.error(
            f"Search indexing failed for content {getattr(content, 'id', '?')}",
            exc_info=True,
        )


def _index_content_impl(content: object, db: Session) -> None:
    """Internal implementation — separated for testability."""
    content_id = getattr(content, "id", None)
    markdown = getattr(content, "markdown_content", None)

    if not content_id or not markdown:
        return

    from src.services.chunking import ChunkingService

    chunking_service = ChunkingService()
    chunks = chunking_service.chunk_content(content)  # type: ignore[arg-type]

    if not chunks:
        logger.debug(f"No chunks produced for content {content_id}")
        return

    # Save chunks to database
    for chunk in chunks:
        db.add(chunk)
    db.flush()  # Ensure chunk IDs are assigned

    logger.info(f"Created {len(chunks)} chunks for content {content_id}")

    # Generate embeddings (async, run in sync context)
    try:
        from src.services.embedding import embed_chunks, get_embedding_provider

        provider = get_embedding_provider()
        embeddings = asyncio.run(embed_chunks(chunks, provider))

        for chunk, embedding in zip(chunks, embeddings, strict=False):
            db.execute(
                text("""
                    UPDATE document_chunks
                    SET embedding = :embedding::vector
                    WHERE id = :id
                """),
                {"embedding": str(embedding), "id": chunk.id},
            )

        logger.info(f"Generated {len(embeddings)} embeddings for content {content_id}")
    except Exception:
        logger.warning(
            f"Embedding generation failed for content {content_id}, "
            f"chunks saved without embeddings (BM25-searchable only)",
            exc_info=True,
        )


def reindex_content(content: object, db: Session) -> None:
    """Delete existing chunks and re-index content.

    Called when markdown_content changes on an existing Content record.
    Deletes all existing chunks for the content, then re-chunks and
    re-embeds from the updated markdown_content.
    """
    settings = get_settings()
    if not settings.enable_search_indexing:
        return

    content_id = getattr(content, "id", None)
    if not content_id:
        return

    try:
        # Delete existing chunks (CASCADE handles embeddings)
        db.execute(
            text("DELETE FROM document_chunks WHERE content_id = :cid"),
            {"cid": content_id},
        )
        db.flush()
        logger.info(f"Deleted existing chunks for content {content_id}")

        # Re-index with fresh chunks
        _index_content_impl(content, db)
    except Exception:
        logger.error(
            f"Re-indexing failed for content {content_id}",
            exc_info=True,
        )


def register_content_listeners() -> None:
    """Register SQLAlchemy event listeners for automatic rechunking.

    Listens for updates to Content.markdown_content and triggers
    rechunking when the content changes. Call once at app startup.
    """
    from src.models.content import Content

    @event.listens_for(Content, "after_update")
    def _on_content_update(mapper, connection, target):  # type: ignore[no-untyped-def]
        """Rechunk content when markdown_content changes."""
        from sqlalchemy import inspect as sa_inspect

        state = sa_inspect(target)
        history = state.attrs.markdown_content.history

        # Only rechunk if markdown_content actually changed
        if not history.has_changes():
            return

        settings = get_settings()
        if not settings.enable_search_indexing:
            return

        # Schedule reindex — we can't modify the session inside after_update
        # with the same connection, so use after_commit instead
        @event.listens_for(state.session, "after_commit", once=True)
        def _reindex_after_commit(session):  # type: ignore[no-untyped-def]
            from src.storage.database import get_db_session

            new_db = get_db_session()
            try:
                from src.models.content import Content as ContentModel

                refreshed = new_db.query(ContentModel).get(target.id)
                if refreshed:
                    reindex_content(refreshed, new_db)
                    new_db.commit()
            except Exception:
                logger.error(f"Post-commit reindex failed for content {target.id}", exc_info=True)
                new_db.rollback()
            finally:
                new_db.close()
