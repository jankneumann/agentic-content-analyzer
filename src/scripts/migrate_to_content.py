#!/usr/bin/env python3
"""
Migrate Newsletter and Document records to the unified Content model.

This script:
1. Reads Newsletter records and their associated Document records
2. Creates Content records with merged data
3. Handles orphaned Documents (no Newsletter)
4. Handles Newsletters without Documents (converts raw_html to markdown)
5. Supports dry-run mode for validation
6. Provides rollback capability

Usage:
    # Dry run (validate without changes)
    python -m src.scripts.migrate_to_content --dry-run

    # Full migration
    python -m src.scripts.migrate_to_content

    # Rollback (delete migrated Content records)
    python -m src.scripts.migrate_to_content --rollback

    # Migrate specific newsletter IDs
    python -m src.scripts.migrate_to_content --newsletter-ids 1,2,3
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.models.content import Content, ContentSource, ContentStatus
from src.models.newsletter import Newsletter, NewsletterSource
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.logging import get_logger


class MigrationStats(TypedDict):
    """Type definition for migration statistics."""

    newsletters_processed: int
    newsletters_with_documents: int
    newsletters_without_documents: int
    orphaned_documents: int
    contents_created: int
    contents_skipped: int
    errors: list[str]


class RollbackStats(TypedDict):
    """Type definition for rollback statistics."""

    contents_deleted: int
    errors: list[str]


logger = get_logger(__name__)

# Mapping from NewsletterSource to ContentSource
SOURCE_MAPPING = {
    NewsletterSource.GMAIL: ContentSource.GMAIL,
    NewsletterSource.RSS: ContentSource.RSS,
    NewsletterSource.SUBSTACK_RSS: ContentSource.RSS,  # Deprecated, map to RSS
    NewsletterSource.FILE_UPLOAD: ContentSource.FILE_UPLOAD,
    NewsletterSource.YOUTUBE: ContentSource.YOUTUBE,
    NewsletterSource.OTHER: ContentSource.OTHER,
}


def html_to_markdown_simple(html: str) -> str:
    """
    Simple HTML to markdown conversion for migration.

    Uses MarkItDown parser if available, otherwise returns raw text.
    """
    if not html:
        return ""

    try:
        from src.parsers.markitdown_parser import MarkItDownParser

        parser = MarkItDownParser()
        # Write HTML to temp file for parser
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as f:
            f.write(html)
            temp_path = f.name

        try:
            # Parser is async, run it synchronously
            result = asyncio.run(parser.parse(temp_path))
            return result.markdown_content
        finally:
            Path(temp_path).unlink(missing_ok=True)

    except Exception as e:
        logger.warning(f"Failed to convert HTML to markdown: {e}")
        # Fallback: strip HTML tags using simple regex
        text = re.sub(r"<[^>]+>", "", html)
        return text.strip()


def get_document_for_newsletter(db: Session, newsletter_id: int) -> dict | None:
    """
    Get the Document record associated with a Newsletter.

    Returns dict with document data or None if no document exists.
    """
    result = db.execute(
        text("""
            SELECT id, markdown_content, tables_json, metadata_json, links_json,
                   parser_used, status, filename, source_format
            FROM documents
            WHERE newsletter_id = :newsletter_id
            LIMIT 1
        """),
        {"newsletter_id": newsletter_id},
    )
    row = result.fetchone()

    if row:
        return {
            "id": row[0],
            "markdown_content": row[1],
            "tables_json": row[2],
            "metadata_json": row[3],
            "links_json": row[4],
            "parser_used": row[5],
            "status": row[6],
            "filename": row[7],
            "source_format": row[8],
        }
    return None


def migrate_newsletter_to_content(
    db: Session,
    newsletter: Newsletter,
    document: dict | None,
    dry_run: bool = False,
) -> Content | None:
    """
    Migrate a single Newsletter (with optional Document) to Content.

    Args:
        db: Database session
        newsletter: Newsletter record to migrate
        document: Associated Document record (or None)
        dry_run: If True, don't create the Content record

    Returns:
        Created Content record (or None for dry run)
    """
    # Determine markdown content
    if document and document.get("markdown_content"):
        markdown_content = document["markdown_content"]
        parser_used = document.get("parser_used") or "unknown"
        tables_json = document.get("tables_json")
        links_json = document.get("links_json")
        metadata_json = document.get("metadata_json")
    else:
        # Convert raw_html/raw_text to markdown
        if newsletter.raw_html:
            markdown_content = html_to_markdown_simple(newsletter.raw_html)
            parser_used = "html_migration"
        elif newsletter.raw_text:
            markdown_content = newsletter.raw_text
            parser_used = "text_migration"
        else:
            markdown_content = f"# {newsletter.title}\n\nNo content available."
            parser_used = "empty_migration"

        tables_json = None
        links_json = newsletter.extracted_links
        metadata_json = None

    # Generate content hash
    content_hash = generate_markdown_hash(markdown_content)

    # Map source type (with null safety)
    if newsletter.source:
        source_type = SOURCE_MAPPING.get(newsletter.source, ContentSource.OTHER)
    else:
        source_type = ContentSource.OTHER

    # Map status (with null safety)
    status_value = newsletter.status.value if newsletter.status else "pending"
    if status_value == "completed":
        status = ContentStatus.COMPLETED
    elif status_value == "processing":
        status = ContentStatus.PROCESSING
    elif status_value == "failed":
        status = ContentStatus.FAILED
    else:
        status = ContentStatus.PENDING

    if dry_run:
        logger.info(
            f"[DRY RUN] Would create Content for Newsletter {newsletter.id}: "
            f"{(newsletter.title or 'Untitled')[:50]}... (source: {source_type.value})"
        )
        return None

    # Check if Content already exists for this source
    existing = (
        db.query(Content)
        .filter(
            Content.source_type == source_type,
            Content.source_id == newsletter.source_id,
        )
        .first()
    )

    if existing:
        logger.info(
            f"Content already exists for Newsletter {newsletter.id} "
            f"(Content ID: {existing.id}), skipping"
        )
        return existing

    # Create Content record
    content = Content(
        source_type=source_type,
        source_id=newsletter.source_id,
        source_url=newsletter.url,
        title=newsletter.title,
        author=newsletter.sender,
        publication=newsletter.publication,
        published_date=newsletter.published_date,
        markdown_content=markdown_content,
        tables_json=tables_json,
        links_json=links_json,
        metadata_json=metadata_json,
        raw_content=newsletter.raw_html or newsletter.raw_text,
        raw_format="html" if newsletter.raw_html else "text",
        parser_used=parser_used,
        content_hash=content_hash,
        status=status,
        error_message=newsletter.error_message,
        ingested_at=newsletter.ingested_at,
        processed_at=newsletter.processed_at,
    )

    db.add(content)
    return content


def migrate_orphaned_document(
    db: Session,
    document: dict,
    dry_run: bool = False,
) -> Content | None:
    """
    Migrate an orphaned Document (no newsletter_id) to Content.

    Args:
        db: Database session
        document: Document record dict
        dry_run: If True, don't create the Content record

    Returns:
        Created Content record (or None for dry run)
    """
    markdown_content = document.get("markdown_content") or ""
    content_hash = generate_markdown_hash(markdown_content)

    # Use filename as title and source_id
    filename = document.get("filename", f"document_{document['id']}")
    title = filename

    if dry_run:
        logger.info(
            f"[DRY RUN] Would create Content for orphaned Document {document['id']}: " f"{filename}"
        )
        return None

    # Check if Content already exists
    existing = (
        db.query(Content)
        .filter(
            Content.source_type == ContentSource.FILE_UPLOAD,
            Content.source_id == f"doc_{document['id']}",
        )
        .first()
    )

    if existing:
        logger.info(
            f"Content already exists for Document {document['id']} "
            f"(Content ID: {existing.id}), skipping"
        )
        return existing

    # Create Content record
    content = Content(
        source_type=ContentSource.FILE_UPLOAD,
        source_id=f"doc_{document['id']}",
        title=title,
        markdown_content=markdown_content,
        tables_json=document.get("tables_json"),
        links_json=document.get("links_json"),
        metadata_json=document.get("metadata_json"),
        parser_used=document.get("parser_used") or "unknown",
        content_hash=content_hash,
        status=ContentStatus.COMPLETED
        if document.get("status") == "completed"
        else ContentStatus.PENDING,
        ingested_at=datetime.utcnow(),
    )

    db.add(content)
    return content


def run_migration(
    dry_run: bool = False,
    newsletter_ids: list[int] | None = None,
    batch_size: int = 100,
) -> MigrationStats:
    """
    Run the Newsletter → Content migration.

    Args:
        dry_run: If True, validate without making changes
        newsletter_ids: Optional list of specific newsletter IDs to migrate
        batch_size: Number of records to process per batch

    Returns:
        Dictionary with migration statistics
    """
    stats: MigrationStats = {
        "newsletters_processed": 0,
        "newsletters_with_documents": 0,
        "newsletters_without_documents": 0,
        "orphaned_documents": 0,
        "contents_created": 0,
        "contents_skipped": 0,
        "errors": [],
    }

    logger.info(f"Starting migration (dry_run={dry_run})")

    with get_db() as db:
        # Get newsletters to migrate
        query = db.query(Newsletter)
        if newsletter_ids:
            query = query.filter(Newsletter.id.in_(newsletter_ids))

        newsletters = query.all()
        total = len(newsletters)
        logger.info(f"Found {total} newsletters to migrate")

        # Process newsletters in batches
        for i, newsletter in enumerate(newsletters):
            try:
                # Skip if newsletter has no ID (shouldn't happen)
                if newsletter.id is None:
                    logger.warning(f"Newsletter without ID at index {i}, skipping")
                    continue

                # Get associated document
                document = get_document_for_newsletter(db, newsletter.id)

                if document:
                    stats["newsletters_with_documents"] += 1
                else:
                    stats["newsletters_without_documents"] += 1

                # Migrate
                content = migrate_newsletter_to_content(db, newsletter, document, dry_run)

                if content:
                    stats["contents_created"] += 1
                elif not dry_run:
                    stats["contents_skipped"] += 1

                stats["newsletters_processed"] += 1

                # Commit in batches
                if not dry_run and (i + 1) % batch_size == 0:
                    db.commit()
                    logger.info(f"Processed {i + 1}/{total} newsletters")

            except Exception as e:
                error_msg = f"Error migrating Newsletter {newsletter.id}: {e}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)
                db.rollback()

        # Process orphaned documents (documents without newsletter_id)
        result = db.execute(
            text("""
                SELECT id, markdown_content, tables_json, metadata_json, links_json,
                       parser_used, status, filename, source_format
                FROM documents
                WHERE newsletter_id IS NULL
            """)
        )
        orphaned_docs = result.fetchall()

        logger.info(f"Found {len(orphaned_docs)} orphaned documents")

        for row in orphaned_docs:
            try:
                doc = {
                    "id": row[0],
                    "markdown_content": row[1],
                    "tables_json": row[2],
                    "metadata_json": row[3],
                    "links_json": row[4],
                    "parser_used": row[5],
                    "status": row[6],
                    "filename": row[7],
                    "source_format": row[8],
                }

                content = migrate_orphaned_document(db, doc, dry_run)

                if content:
                    stats["contents_created"] += 1
                    stats["orphaned_documents"] += 1

            except Exception as e:
                error_msg = f"Error migrating orphaned Document {row[0]}: {e}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)

        # Final commit
        if not dry_run:
            db.commit()

    logger.info("Migration complete!")
    logger.info(f"Statistics: {stats}")

    return stats


def rollback_migration() -> RollbackStats:
    """
    Rollback the migration by deleting Content records created from newsletters.

    This deletes Content records where the source_id matches a Newsletter source_id.

    Returns:
        Dictionary with rollback statistics
    """
    stats: RollbackStats = {
        "contents_deleted": 0,
        "errors": [],
    }

    logger.info("Starting rollback")

    with get_db() as db:
        # Get all newsletter source_ids
        newsletters = db.query(Newsletter.source_id).all()
        source_ids = {n.source_id for n in newsletters}

        # Delete matching Content records
        contents = db.query(Content).filter(Content.source_id.in_(source_ids)).all()

        for content in contents:
            try:
                db.delete(content)
                stats["contents_deleted"] += 1
            except Exception as e:
                error_msg = f"Error deleting Content {content.id}: {e}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)

        # Also delete orphaned document migrations
        orphan_contents = db.query(Content).filter(Content.source_id.like("doc_%")).all()

        for content in orphan_contents:
            try:
                db.delete(content)
                stats["contents_deleted"] += 1
            except Exception as e:
                error_msg = f"Error deleting Content {content.id}: {e}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)

        db.commit()

    logger.info(f"Rollback complete! Deleted {stats['contents_deleted']} Content records")

    return stats


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate Newsletter records to unified Content model"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate migration without making changes",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback migration (delete created Content records)",
    )
    parser.add_argument(
        "--newsletter-ids",
        type=str,
        help="Comma-separated list of specific newsletter IDs to migrate",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of records to process per batch (default: 100)",
    )

    args = parser.parse_args()

    if args.rollback:
        rollback_stats = rollback_migration()
        if rollback_stats.get("errors"):
            logger.error(f"Rollback completed with {len(rollback_stats['errors'])} errors")
            sys.exit(1)
    else:
        newsletter_ids = None
        if args.newsletter_ids:
            newsletter_ids = [int(x.strip()) for x in args.newsletter_ids.split(",")]

        migration_stats = run_migration(
            dry_run=args.dry_run,
            newsletter_ids=newsletter_ids,
            batch_size=args.batch_size,
        )

        # Exit with error if there were failures
        if migration_stats.get("errors"):
            logger.error(f"Migration completed with {len(migration_stats['errors'])} errors")
            sys.exit(1)


if __name__ == "__main__":
    main()
