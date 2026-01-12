#!/usr/bin/env python3
"""
Migrate existing Digest records to populate markdown_content, theme_tags, and source_content_ids.

This script:
1. Reads existing Digest records
2. Generates markdown_content from JSON fields using generate_digest_markdown()
3. Extracts theme_tags from the digest data
4. Populates source_content_ids from the sources JSON
5. Updates the records with the new fields
6. Supports dry-run mode for validation

Usage:
    # Dry run (validate without changes)
    python -m src.scripts.migrate_digests_markdown --dry-run

    # Full migration
    python -m src.scripts.migrate_digests_markdown

    # Migrate specific digest IDs
    python -m src.scripts.migrate_digests_markdown --digest-ids 1,2,3

    # Force regenerate (overwrite existing markdown_content)
    python -m src.scripts.migrate_digests_markdown --force
"""

from __future__ import annotations

import argparse
import sys
from typing import TypedDict

from sqlalchemy import text

from src.models.digest import Digest
from src.storage.database import get_db
from src.utils.digest_markdown import (
    extract_digest_theme_tags,
    extract_source_content_ids,
    generate_digest_markdown,
)
from src.utils.logging import get_logger


class DigestMigrationStats(TypedDict):
    """Type definition for digest migration statistics."""

    digests_processed: int
    digests_updated: int
    digests_skipped: int
    errors: list[str]


class DigestRollbackStats(TypedDict):
    """Type definition for digest rollback statistics."""

    digests_rolled_back: int
    errors: list[str]


class DigestLinkStats(TypedDict):
    """Type definition for digest link statistics."""

    digests_linked: int
    content_ids_linked: int
    errors: list[str]


logger = get_logger(__name__)


def get_newsletter_ids_from_sources(sources: list[dict] | None) -> list[int]:
    """
    Extract newsletter IDs from the sources JSON field.

    The sources field contains entries like:
    [{"title": "...", "publication": "...", "date": "...", "url": "..."}]

    We need to look up newsletter IDs from the newsletters table based on
    the publication and date.

    Args:
        sources: List of source dicts from digest

    Returns:
        List of newsletter IDs (may be empty if lookup fails)
    """
    if not sources:
        return []

    # For now, return empty - we'll use Content lookup later
    # The source_content_ids will be populated when Contents are created
    return []


def migrate_digest(
    digest: Digest,
    dry_run: bool = False,
    force: bool = False,
) -> bool:
    """
    Migrate a single Digest record to add markdown_content, theme_tags, and source_content_ids.

    Args:
        digest: Digest record to migrate
        dry_run: If True, don't update the record
        force: If True, overwrite existing markdown_content

    Returns:
        True if migration was performed, False if skipped
    """
    # Skip if already has markdown_content (unless force)
    if digest.markdown_content and not force:
        logger.debug(f"Digest {digest.id} already has markdown_content, skipping")
        return False

    # Build digest dict from existing fields (sections may be dicts or DigestSection objects)
    digest_dict = {
        "digest_type": digest.digest_type,
        "period_start": digest.period_start,
        "period_end": digest.period_end,
        "title": digest.title,
        "executive_overview": digest.executive_overview,
        "strategic_insights": digest.strategic_insights or [],
        "technical_developments": digest.technical_developments or [],
        "emerging_trends": digest.emerging_trends or [],
        "actionable_recommendations": digest.actionable_recommendations or {},
        "sources": digest.sources or [],
        "historical_context": digest.historical_context,
        "newsletter_count": digest.newsletter_count,
    }

    # Generate markdown content
    markdown_content = generate_digest_markdown(digest_dict)

    # Extract theme tags
    theme_tags = extract_digest_theme_tags(digest_dict)

    # Extract source content IDs (from sources)
    source_content_ids = extract_source_content_ids(digest_dict)

    if dry_run:
        logger.info(
            f"[DRY RUN] Would update Digest {digest.id}: "
            f"markdown_content length={len(markdown_content)}, "
            f"theme_tags={theme_tags[:5]}{'...' if len(theme_tags) > 5 else ''}, "
            f"source_content_ids count={len(source_content_ids)}"
        )
        return True

    # Update the record
    digest.markdown_content = markdown_content
    digest.theme_tags = theme_tags
    digest.source_content_ids = source_content_ids if source_content_ids else None

    logger.debug(
        f"Updated Digest {digest.id}: "
        f"markdown_content length={len(markdown_content)}, "
        f"theme_tags count={len(theme_tags)}, "
        f"source_content_ids count={len(source_content_ids)}"
    )

    return True


def run_migration(
    dry_run: bool = False,
    digest_ids: list[int] | None = None,
    force: bool = False,
    batch_size: int = 100,
) -> DigestMigrationStats:
    """
    Run the Digest markdown migration.

    Args:
        dry_run: If True, validate without making changes
        digest_ids: Optional list of specific digest IDs to migrate
        force: If True, overwrite existing markdown_content
        batch_size: Number of records to process per batch

    Returns:
        Dictionary with migration statistics
    """
    stats: DigestMigrationStats = {
        "digests_processed": 0,
        "digests_updated": 0,
        "digests_skipped": 0,
        "errors": [],
    }

    logger.info(f"Starting Digest markdown migration (dry_run={dry_run}, force={force})")

    with get_db() as db:
        # Get digests to migrate
        query = db.query(Digest)

        if digest_ids:
            query = query.filter(Digest.id.in_(digest_ids))

        # If not forcing, only get records without markdown_content
        if not force:
            query = query.filter(
                (Digest.markdown_content.is_(None)) | (Digest.markdown_content == "")
            )

        digests = query.all()
        total = len(digests)
        logger.info(f"Found {total} digests to migrate")

        # Process digests
        for i, digest in enumerate(digests):
            try:
                updated = migrate_digest(digest, dry_run, force)

                if updated:
                    stats["digests_updated"] += 1
                else:
                    stats["digests_skipped"] += 1

                stats["digests_processed"] += 1

                # Commit in batches
                if not dry_run and (i + 1) % batch_size == 0:
                    db.commit()
                    logger.info(f"Processed {i + 1}/{total} digests")

            except Exception as e:
                error_msg = f"Error migrating Digest {digest.id}: {e}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)
                db.rollback()

        # Final commit
        if not dry_run:
            db.commit()

    logger.info("Migration complete!")
    logger.info(f"Statistics: {stats}")

    return stats


def rollback_migration(digest_ids: list[int] | None = None) -> DigestRollbackStats:
    """
    Rollback the migration by clearing markdown_content, theme_tags, and source_content_ids.

    Args:
        digest_ids: Optional list of specific digest IDs to rollback

    Returns:
        Dictionary with rollback statistics
    """
    stats: DigestRollbackStats = {
        "digests_rolled_back": 0,
        "errors": [],
    }

    logger.info("Starting rollback")

    with get_db() as db:
        query = db.query(Digest)

        if digest_ids:
            query = query.filter(Digest.id.in_(digest_ids))
        else:
            # Only rollback records that have markdown_content
            query = query.filter(Digest.markdown_content.isnot(None))

        digests = query.all()

        for digest in digests:
            try:
                digest.markdown_content = None
                digest.theme_tags = None
                digest.source_content_ids = None
                stats["digests_rolled_back"] += 1
            except Exception as e:
                error_msg = f"Error rolling back Digest {digest.id}: {e}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)

        db.commit()

    logger.info(f"Rollback complete! Cleared {stats['digests_rolled_back']} digests")

    return stats


def link_source_content_ids() -> DigestLinkStats:
    """
    Link digest source_content_ids to actual Content records.

    This should be run after migrate_to_content.py has created Content records
    from newsletters. It updates digests to reference the new Content IDs.

    Returns:
        Dictionary with link statistics
    """
    stats: DigestLinkStats = {
        "digests_linked": 0,
        "content_ids_linked": 0,
        "errors": [],
    }

    logger.info("Linking digest source_content_ids to Content records")

    with get_db() as db:
        # Get all digests with sources
        digests = db.query(Digest).filter(Digest.sources.isnot(None)).all()

        for digest in digests:
            try:
                sources = digest.sources or []
                content_ids = []

                for source in sources:
                    # Try to find Content by publication + date
                    publication = source.get("publication")
                    date_str = source.get("date")

                    if publication and date_str:
                        # Look up Content record
                        result = db.execute(
                            text("""
                                SELECT id FROM contents
                                WHERE publication = :publication
                                AND DATE(published_date) = :pub_date
                                LIMIT 1
                            """),
                            {"publication": publication, "pub_date": date_str},
                        )
                        row = result.fetchone()
                        if row:
                            content_ids.append(row[0])
                            stats["content_ids_linked"] += 1

                if content_ids:
                    digest.source_content_ids = content_ids
                    stats["digests_linked"] += 1
                    logger.debug(f"Linked Digest {digest.id} to {len(content_ids)} Content records")

            except Exception as e:
                error_msg = f"Error linking Digest {digest.id}: {e}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)

        db.commit()

    logger.info(f"Linking complete! {stats['digests_linked']} digests linked")
    logger.info(f"Statistics: {stats}")

    return stats


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate Digest records to add markdown_content, theme_tags, and source_content_ids"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate migration without making changes",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback migration (clear markdown fields)",
    )
    parser.add_argument(
        "--link-content-ids",
        action="store_true",
        help="Link source_content_ids to Content records (run after migrate_to_content.py)",
    )
    parser.add_argument(
        "--digest-ids",
        type=str,
        help="Comma-separated list of specific digest IDs to migrate",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regenerate markdown_content even if it already exists",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of records to process per batch (default: 100)",
    )

    args = parser.parse_args()

    digest_ids = None
    if args.digest_ids:
        digest_ids = [int(x.strip()) for x in args.digest_ids.split(",")]

    if args.rollback:
        rollback_stats = rollback_migration(digest_ids)
        if rollback_stats.get("errors"):
            logger.error(f"Rollback completed with {len(rollback_stats['errors'])} errors")
            sys.exit(1)
    elif args.link_content_ids:
        link_stats = link_source_content_ids()
        if link_stats.get("errors"):
            logger.error(f"Linking completed with {len(link_stats['errors'])} errors")
            sys.exit(1)
    else:
        migration_stats = run_migration(
            dry_run=args.dry_run,
            digest_ids=digest_ids,
            force=args.force,
            batch_size=args.batch_size,
        )

        # Exit with error if there were failures
        if migration_stats.get("errors"):
            logger.error(f"Migration completed with {len(migration_stats['errors'])} errors")
            sys.exit(1)


if __name__ == "__main__":
    main()
