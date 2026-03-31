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


def _run_async(coro):  # type: ignore[no-untyped-def]
    """Run an async coroutine from sync code, handling nested event loops.

    asyncio.run() fails if an event loop is already running (e.g., inside
    FastAPI async handlers or task workers). In that case, we run the
    coroutine in a separate thread with its own event loop.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No event loop running — safe to use asyncio.run()
        return asyncio.run(coro)

    # Already in an async context — run in a new thread
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


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

    # Save chunks to database — resolve tree parent_chunk_id references
    flat_chunks = [c for c in chunks if c.tree_depth is None]
    tree_chunks = [c for c in chunks if c.tree_depth is not None]

    # Insert flat chunks first
    for chunk in flat_chunks:
        db.add(chunk)
    db.flush()

    # Insert tree chunks with parent FK resolution
    if tree_chunks:
        _insert_tree_chunks(tree_chunks, db)

    logger.info(
        f"Created {len(flat_chunks)} flat + {len(tree_chunks)} tree chunks for content {content_id}"
    )

    # Summarize tree nodes (async, fail-safe — delete tree on failure)
    if tree_chunks:
        try:
            summary_chunks = [c for c in tree_chunks if c.is_summary]
            if summary_chunks:
                _run_async(_summarize_tree_nodes(summary_chunks, tree_chunks, db))
        except Exception:
            logger.warning(
                f"Tree summarization failed for content {content_id}, "
                f"deleting tree chunks (flat chunks preserved)",
                exc_info=True,
            )
            db.execute(
                text(
                    "DELETE FROM document_chunks WHERE content_id = :cid AND tree_depth IS NOT NULL"
                ),
                {"cid": content_id},
            )
            db.flush()
            # Update chunks list to remove tree chunks
            chunks = flat_chunks

    # Generate embeddings (async, run in sync context)
    try:
        from src.services.embedding import embed_chunks, get_embedding_provider

        provider = get_embedding_provider()
        settings = get_settings()
        embeddings = _run_async(embed_chunks(chunks, provider))

        if len(embeddings) != len(chunks):
            logger.warning(
                f"Embedding count mismatch for content {content_id}: "
                f"{len(embeddings)} embeddings for {len(chunks)} chunks"
            )

        for chunk, embedding in zip(chunks, embeddings, strict=False):
            # Normalize to list[float] — handles numpy arrays, torch tensors, etc.
            vec = list(embedding) if not isinstance(embedding, list) else embedding
            db.execute(
                text("""
                    UPDATE document_chunks
                    SET embedding = CAST(:embedding AS vector),
                        embedding_provider = :provider,
                        embedding_model = :model
                    WHERE id = :id
                """),
                {
                    "embedding": str(vec),
                    "provider": provider.name,
                    "model": settings.embedding_model,
                    "id": chunk.id,
                },
            )

        logger.info(f"Generated {len(embeddings)} embeddings for content {content_id}")
    except Exception:
        logger.warning(
            f"Embedding generation failed for content {content_id}, "
            f"chunks saved without embeddings (BM25-searchable only)",
            exc_info=True,
        )


def _insert_tree_chunks(tree_chunks: list, db: Session) -> None:
    """Insert tree chunks resolving parent_chunk_id from _parent_index."""
    # Map _parent_index → assigned DB id
    index_to_id: dict[int, int] = {}
    all_chunks_in_order = tree_chunks  # Already in parent-before-child order

    for i, chunk in enumerate(all_chunks_in_order):
        parent_idx = getattr(chunk, "_parent_index", None)
        if parent_idx is not None and parent_idx in index_to_id:
            chunk.parent_chunk_id = index_to_id[parent_idx]

        db.add(chunk)
        db.flush()  # Get ID assigned
        # Store this chunk's position → DB id mapping
        # The _parent_index on children references the position in the original list
        # Find this chunk's position in the original tree_chunks list
        index_to_id[i] = chunk.id


async def _summarize_tree_nodes(
    summary_chunks: list,
    all_tree_chunks: list,
    db: Session,
) -> None:
    """Summarize internal tree nodes bottom-up with bounded concurrency."""
    settings = get_settings()
    semaphore = asyncio.Semaphore(settings.tree_summarization_max_concurrent)

    # Group by tree_depth for bottom-up processing
    max_depth = max((c.tree_depth for c in summary_chunks), default=0)

    # Build chunk_id → children text map
    children_text: dict[int, list[str]] = {}
    for chunk in all_tree_chunks:
        if chunk.parent_chunk_id:
            if chunk.parent_chunk_id not in children_text:
                children_text[chunk.parent_chunk_id] = []
            text_val = chunk.chunk_text or chunk.heading_text or ""
            if text_val:
                children_text[chunk.parent_chunk_id].append(text_val)

    async def _summarize_single(chunk) -> None:  # type: ignore[no-untyped-def]
        async with semaphore:
            child_texts = children_text.get(chunk.id, [])
            if not child_texts:
                chunk.chunk_text = chunk.heading_text or "Empty section"
                return

            # Use LLM to summarize children
            from src.config.models import ModelStep, get_model_config
            from src.services.llm_router import LLMRouter

            model_config = get_model_config()
            model = model_config.get_model_for_step(ModelStep.TREE_SUMMARIZATION)
            router = LLMRouter(model_config)

            prompt = (
                f"Summarize the following section titled '{chunk.heading_text or 'Section'}'.\n"
                f"Content from subsections:\n\n"
                + "\n---\n".join(child_texts[:10])  # Cap input
                + "\n\nProvide a concise 2-3 sentence summary."
            )

            try:
                response = await router.generate(
                    model=model,
                    system_prompt="You are a document section summarizer. Provide concise summaries.",
                    user_prompt=prompt,
                    max_tokens=256,
                    temperature=0.0,
                )
                chunk.chunk_text = response.content or chunk.heading_text or "Summary unavailable"
            except Exception as e:
                logger.warning(f"Failed to summarize chunk {chunk.id}: {e}")
                raise  # Propagate to trigger tree rollback

    for depth in range(max_depth, -1, -1):
        level_chunks = [c for c in summary_chunks if c.tree_depth == depth]
        if level_chunks:
            await asyncio.gather(*[_summarize_single(c) for c in level_chunks])

    # Update summaries in DB
    for chunk in summary_chunks:
        if chunk.chunk_text:
            db.execute(
                text("UPDATE document_chunks SET chunk_text = :txt WHERE id = :id"),
                {"txt": chunk.chunk_text, "id": chunk.id},
            )
    db.flush()


def build_tree_index(content_id: int, db: Session, force: bool = False) -> int:
    """Build tree index for a single content record (tree chunks only).

    Preserves flat chunks. Used by backfill command.

    Args:
        content_id: Content record ID
        db: SQLAlchemy session
        force: If True, delete existing tree chunks and rebuild

    Returns:
        Number of tree chunks created (0 if skipped)
    """
    from src.models.chunk import DocumentChunk

    # Check for existing tree chunks
    existing_tree = (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.content_id == content_id,
            DocumentChunk.tree_depth.isnot(None),
        )
        .count()
    )

    if existing_tree > 0 and not force:
        return 0

    if existing_tree > 0 and force:
        db.execute(
            text("DELETE FROM document_chunks WHERE content_id = :cid AND tree_depth IS NOT NULL"),
            {"cid": content_id},
        )
        db.flush()

    # Load content
    from src.models.content import Content

    content = db.query(Content).get(content_id)
    if not content or not content.markdown_content:
        return 0

    settings = get_settings()
    from src.services.chunking import (
        TreeIndexChunkingStrategy,
        _count_tokens,
        _detect_heading_depth,
    )

    # Check qualifications (unless force)
    tokens = _count_tokens(content.markdown_content)
    heading_depth = _detect_heading_depth(content.markdown_content)
    if not force and (
        tokens <= settings.tree_index_min_tokens
        or heading_depth < settings.tree_index_min_heading_depth
    ):
        return 0

    # Build tree chunks
    strategy = TreeIndexChunkingStrategy()
    tree_chunks = strategy.chunk(
        content=content.markdown_content,
        metadata={"content_id": content_id},
    )
    for tc in tree_chunks:
        tc.content_id = content_id

    if not tree_chunks:
        return 0

    # Insert tree chunks
    _insert_tree_chunks(tree_chunks, db)

    # Summarize
    summary_chunks = [c for c in tree_chunks if c.is_summary]
    if summary_chunks:
        try:
            _run_async(_summarize_tree_nodes(summary_chunks, tree_chunks, db))
        except Exception:
            logger.warning(
                f"Tree summarization failed for content {content_id} during backfill, "
                f"deleting tree chunks",
                exc_info=True,
            )
            db.execute(
                text(
                    "DELETE FROM document_chunks WHERE content_id = :cid AND tree_depth IS NOT NULL"
                ),
                {"cid": content_id},
            )
            db.flush()
            return 0

    # Generate embeddings for tree chunks
    try:
        from src.services.embedding import embed_chunks, get_embedding_provider

        provider = get_embedding_provider()
        embeddings = _run_async(embed_chunks(tree_chunks, provider))

        for chunk, embedding in zip(tree_chunks, embeddings, strict=False):
            vec = list(embedding) if not isinstance(embedding, list) else embedding
            db.execute(
                text("""
                    UPDATE document_chunks
                    SET embedding = CAST(:embedding AS vector),
                        embedding_provider = :provider,
                        embedding_model = :model
                    WHERE id = :id
                """),
                {
                    "embedding": str(vec),
                    "provider": provider.name,
                    "model": settings.embedding_model,
                    "id": chunk.id,
                },
            )
    except Exception:
        logger.warning(
            f"Embedding generation failed for tree chunks of content {content_id}",
            exc_info=True,
        )

    return len(tree_chunks)


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
    from src.storage.database import get_db_session  # Validate import at registration time

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
            new_db = get_db_session()
            try:
                refreshed = new_db.query(Content).get(target.id)
                if refreshed:
                    reindex_content(refreshed, new_db)
                    new_db.commit()
            except Exception:
                logger.error(f"Post-commit reindex failed for content {target.id}", exc_info=True)
                new_db.rollback()
            finally:
                new_db.close()
