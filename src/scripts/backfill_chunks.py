"""Backfill chunks and embeddings for existing content.

Processes content records that have no associated chunks, chunking from
the existing markdown_content and generating embeddings in batches.

Usage:
    python -m src.scripts.backfill_chunks [--batch-size 100] [--delay 1.0] [--dry-run]
    aca manage backfill-chunks [--batch-size 100] [--delay 1.0] [--dry-run]
"""

from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.services.chunking import ChunkingService
from src.services.embedding import embed_chunks, get_embedding_provider

logger = logging.getLogger(__name__)


async def backfill_chunks(
    *,
    batch_size: int = 100,
    delay: float = 1.0,
    dry_run: bool = False,
    embed_only: bool = False,
    content_id: int | None = None,
) -> dict:
    """Backfill document chunks and embeddings for existing content.

    Args:
        batch_size: Number of content records to process per batch.
        delay: Seconds to wait between embedding batches (rate limiting).
        dry_run: If True, only report what would be done without writing.
        embed_only: If True, only generate embeddings for existing chunks
                    that are missing them (skip chunking).
        content_id: If set, only process this specific content record.

    Returns:
        Summary dict with counts of content processed, chunks created, etc.
    """
    from src.storage.database import get_db_session

    settings = get_settings()

    if not settings.enable_search_indexing:
        logger.warning("Search indexing is disabled (ENABLE_SEARCH_INDEXING=false)")
        return {"skipped": True, "reason": "search_indexing_disabled"}

    db = get_db_session()
    stats = {
        "content_processed": 0,
        "chunks_created": 0,
        "embeddings_generated": 0,
        "errors": 0,
        "skipped": 0,
    }

    try:
        if embed_only:
            stats = await _backfill_embeddings_only(db, batch_size, delay, dry_run, stats)
        else:
            stats = await _backfill_full(
                db,
                batch_size,
                delay,
                dry_run,
                content_id,
                stats,
            )
    finally:
        db.close()

    return stats


async def _backfill_full(
    db: Session,
    batch_size: int,
    delay: float,
    dry_run: bool,
    content_id: int | None,
    stats: dict,
) -> dict:
    """Backfill both chunks and embeddings for unchunked content."""
    chunking_service = ChunkingService()
    provider = get_embedding_provider()

    # Find content with no chunks
    if content_id:
        stmt = text("""
            SELECT c.id, c.title
            FROM contents c
            LEFT JOIN document_chunks dc ON dc.content_id = c.id
            WHERE c.id = :content_id AND dc.id IS NULL
              AND c.markdown_content IS NOT NULL
              AND c.markdown_content != ''
        """)
        result = db.execute(stmt, {"content_id": content_id})
    else:
        stmt = text("""
            SELECT c.id, c.title
            FROM contents c
            LEFT JOIN document_chunks dc ON dc.content_id = c.id
            WHERE dc.id IS NULL
              AND c.markdown_content IS NOT NULL
              AND c.markdown_content != ''
            ORDER BY c.id
        """)
        result = db.execute(stmt)

    unchunked = list(result)
    total = len(unchunked)
    logger.info(f"Found {total} content records needing chunks")

    if dry_run:
        logger.info(f"[DRY RUN] Would process {total} content records")
        stats["content_processed"] = total
        return stats

    for i, row in enumerate(unchunked):
        start = time.monotonic()
        try:
            # Load full content record
            from src.models.content import Content

            content = db.query(Content).get(row.id)
            if not content or not content.markdown_content:
                stats["skipped"] += 1
                continue

            # Chunk content
            chunks = chunking_service.chunk_content(content)
            if not chunks:
                stats["skipped"] += 1
                continue

            # Save chunks
            for chunk in chunks:
                db.add(chunk)
            db.flush()

            stats["chunks_created"] += len(chunks)

            # Generate embeddings
            try:
                embeddings = await embed_chunks(chunks, provider)
                for chunk, embedding in zip(chunks, embeddings, strict=False):
                    db.execute(
                        text("""
                            UPDATE document_chunks
                            SET embedding = :embedding::vector
                            WHERE id = :id
                        """),
                        {
                            "embedding": str(
                                list(embedding) if not isinstance(embedding, list) else embedding
                            ),
                            "id": chunk.id,
                        },
                    )
                stats["embeddings_generated"] += len(embeddings)
            except Exception:
                logger.warning(
                    f"Embedding failed for content {row.id}, chunks saved without embeddings",
                    exc_info=True,
                )

            db.commit()
            stats["content_processed"] += 1

            elapsed = time.monotonic() - start
            logger.info(
                f"[{i + 1}/{total}] Processed content {row.id} "
                f"({row.title[:50]}): {len(chunks)} chunks in {elapsed:.1f}s"
            )

            # Rate limit between batches
            if (i + 1) % batch_size == 0 and delay > 0:
                logger.info(f"Rate limiting: waiting {delay}s before next batch")
                await asyncio.sleep(delay)

        except Exception:
            logger.error(f"Error processing content {row.id}", exc_info=True)
            db.rollback()
            stats["errors"] += 1

    return stats


async def _backfill_embeddings_only(
    db: Session,
    batch_size: int,
    delay: float,
    dry_run: bool,
    stats: dict,
) -> dict:
    """Generate embeddings for existing chunks that are missing them."""
    provider = get_embedding_provider()

    # Find chunks without embeddings
    stmt = text("""
        SELECT id, chunk_text FROM document_chunks
        WHERE embedding IS NULL
        ORDER BY id
    """)
    result = db.execute(stmt)
    missing = list(result)
    total = len(missing)

    logger.info(f"Found {total} chunks needing embeddings")

    if dry_run:
        logger.info(f"[DRY RUN] Would generate embeddings for {total} chunks")
        stats["embeddings_generated"] = total
        return stats

    # Process in batches
    for batch_start in range(0, total, batch_size):
        batch = missing[batch_start : batch_start + batch_size]
        texts = [row.chunk_text for row in batch]

        try:
            embeddings = await provider.embed_batch(texts)
            for row, embedding in zip(batch, embeddings, strict=False):
                db.execute(
                    text("""
                        UPDATE document_chunks
                        SET embedding = :embedding::vector
                        WHERE id = :id
                    """),
                    {
                        "embedding": str(
                            list(embedding) if not isinstance(embedding, list) else embedding
                        ),
                        "id": row.id,
                    },
                )
            db.commit()
            stats["embeddings_generated"] += len(embeddings)

            processed = min(batch_start + batch_size, total)
            logger.info(f"Embedded {processed}/{total} chunks")

        except Exception:
            logger.error(
                f"Embedding batch failed at offset {batch_start}",
                exc_info=True,
            )
            db.rollback()
            stats["errors"] += 1

        if delay > 0 and batch_start + batch_size < total:
            await asyncio.sleep(delay)

    return stats


def main() -> None:
    """CLI entry point for standalone execution."""
    import argparse

    parser = argparse.ArgumentParser(description="Backfill document chunks and embeddings")
    parser.add_argument("--batch-size", type=int, default=100, help="Records per batch")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between batches")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    parser.add_argument("--embed-only", action="store_true", help="Only fill missing embeddings")
    parser.add_argument("--content-id", type=int, help="Process specific content ID")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    result = asyncio.run(
        backfill_chunks(
            batch_size=args.batch_size,
            delay=args.delay,
            dry_run=args.dry_run,
            embed_only=args.embed_only,
            content_id=args.content_id,
        )
    )
    print(f"\nBackfill complete: {result}")


if __name__ == "__main__":
    main()
