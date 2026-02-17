"""Switch embedding provider: clear embeddings, rebuild index, optional backfill.

This script safely orchestrates switching between embedding providers by:
1. Validating the target provider can be instantiated
2. NULLing all existing embeddings and metadata
3. Dropping and recreating the HNSW index (if it exists)
4. Optionally triggering a backfill with the new provider

Usage:
    aca manage switch-embeddings --provider openai --model text-embedding-3-small
    aca manage switch-embeddings --dry-run  # Preview what would happen
"""

from __future__ import annotations

import logging

from sqlalchemy import text

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


async def switch_embeddings(
    *,
    provider: str | None = None,
    model: str | None = None,
    batch_size: int = 100,
    delay: float = 1.0,
    skip_backfill: bool = False,
    dry_run: bool = False,
) -> dict:
    """Switch embedding provider: clear embeddings, rebuild index, backfill.

    Args:
        provider: Target provider name (default: from settings)
        model: Target model name (default: from settings)
        batch_size: Batch size for backfill (if not skipped)
        delay: Delay between backfill batches
        skip_backfill: If True, only clear embeddings without re-embedding
        dry_run: If True, only report what would be done

    Returns:
        Summary dict with operation details
    """
    from src.storage.database import get_db_session

    settings = get_settings()
    target_provider = provider or settings.embedding_provider
    target_model = model or settings.embedding_model

    # Validate the target provider can be instantiated
    from src.services.embedding import get_embedding_provider

    try:
        embedding_provider = get_embedding_provider(target_provider, target_model)
        target_dimensions = embedding_provider.dimensions
    except Exception as e:
        return {"error": f"Cannot create provider {target_provider}/{target_model}: {e}"}

    db = get_db_session()
    try:
        # Count existing embeddings
        count_result = db.execute(
            text("SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL")
        )
        existing_count = count_result.scalar() or 0

        total_result = db.execute(text("SELECT COUNT(*) FROM document_chunks"))
        total_chunks = total_result.scalar() or 0

        summary = {
            "target_provider": target_provider,
            "target_model": target_model,
            "target_dimensions": target_dimensions,
            "existing_embeddings": existing_count,
            "total_chunks": total_chunks,
            "dry_run": dry_run,
            "skip_backfill": skip_backfill,
        }

        if dry_run:
            logger.info(
                f"[DRY RUN] Would switch to {target_provider}/{target_model} "
                f"({target_dimensions}d). {existing_count} embeddings would be cleared."
            )
            return summary

        # Step 1: NULL all embeddings and metadata
        logger.info(f"Clearing {existing_count} embeddings...")
        db.execute(
            text("""
                UPDATE document_chunks
                SET embedding = NULL,
                    embedding_provider = NULL,
                    embedding_model = NULL
                WHERE embedding IS NOT NULL
            """)
        )
        db.commit()
        logger.info("Embeddings cleared")

        # Step 2: Drop and recreate HNSW index (if it exists)
        logger.info("Rebuilding HNSW index...")
        db.execute(text("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw"))

        # Only create index if we'll have embeddings
        if not skip_backfill:
            db.execute(
                text("""
                    CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
                    ON document_chunks USING hnsw (embedding vector_cosine_ops)
                """)
            )
        db.commit()
        logger.info("HNSW index rebuilt")

        summary["embeddings_cleared"] = existing_count
        summary["index_rebuilt"] = True

        # Step 3: Backfill (optional)
        if not skip_backfill:
            logger.info("Starting backfill with new provider...")
            from src.scripts.backfill_chunks import backfill_chunks

            backfill_result = await backfill_chunks(
                batch_size=batch_size,
                delay=delay,
                dry_run=False,
                embed_only=True,
                provider=target_provider,
                model=target_model,
            )
            summary["backfill"] = backfill_result
        else:
            logger.info(
                "Backfill skipped. Run 'aca manage backfill-chunks --embed-only' "
                "when ready to re-embed. The HNSW index will be rebuilt automatically."
            )

        return summary

    finally:
        db.close()
