#!/usr/bin/env python3
"""
Migrate existing Summary records to populate markdown_content and theme_tags.

This script:
1. Reads existing Summary records
2. Generates markdown_content from JSON fields using generate_summary_markdown()
3. Extracts theme_tags from the summary data
4. Updates the records with the new fields
5. Supports dry-run mode for validation

Usage:
    # Dry run (validate without changes)
    python -m src.scripts.migrate_summaries_markdown --dry-run

    # Full migration
    python -m src.scripts.migrate_summaries_markdown

    # Migrate specific summary IDs
    python -m src.scripts.migrate_summaries_markdown --summary-ids 1,2,3

    # Force regenerate (overwrite existing markdown_content)
    python -m src.scripts.migrate_summaries_markdown --force
"""

from __future__ import annotations

import argparse
import sys
from typing import TypedDict

from src.models.summary import Summary
from src.storage.database import get_db
from src.utils.logging import get_logger
from src.utils.summary_markdown import (
    extract_summary_theme_tags,
    generate_summary_markdown,
)


class SummaryMigrationStats(TypedDict):
    """Type definition for summary migration statistics."""

    summaries_processed: int
    summaries_updated: int
    summaries_skipped: int
    errors: list[str]


class SummaryRollbackStats(TypedDict):
    """Type definition for summary rollback statistics."""

    summaries_rolled_back: int
    errors: list[str]


logger = get_logger(__name__)


def migrate_summary(
    summary: Summary,
    dry_run: bool = False,
    force: bool = False,
) -> bool:
    """
    Migrate a single Summary record to add markdown_content and theme_tags.

    Args:
        summary: Summary record to migrate
        dry_run: If True, don't update the record
        force: If True, overwrite existing markdown_content

    Returns:
        True if migration was performed, False if skipped
    """
    # Skip if already has markdown_content (unless force)
    if summary.markdown_content and not force:
        logger.debug(f"Summary {summary.id} already has markdown_content, skipping")
        return False

    # Build summary dict from existing fields
    summary_dict = {
        "executive_summary": summary.executive_summary,
        "key_themes": summary.key_themes or [],
        "strategic_insights": summary.strategic_insights or [],
        "technical_details": summary.technical_details or [],
        "actionable_items": summary.actionable_items or [],
        "notable_quotes": summary.notable_quotes or [],
        "relevant_links": summary.relevant_links or [],
        "relevance_scores": summary.relevance_scores or {},
    }

    # Generate markdown content
    markdown_content = generate_summary_markdown(summary_dict)

    # Extract theme tags
    theme_tags = extract_summary_theme_tags(summary_dict)

    if dry_run:
        logger.info(
            f"[DRY RUN] Would update Summary {summary.id}: "
            f"markdown_content length={len(markdown_content)}, "
            f"theme_tags={theme_tags[:5]}{'...' if len(theme_tags) > 5 else ''}"
        )
        return True

    # Update the record
    summary.markdown_content = markdown_content
    summary.theme_tags = theme_tags

    logger.debug(
        f"Updated Summary {summary.id}: "
        f"markdown_content length={len(markdown_content)}, "
        f"theme_tags count={len(theme_tags)}"
    )

    return True


def run_migration(
    dry_run: bool = False,
    summary_ids: list[int] | None = None,
    force: bool = False,
    batch_size: int = 100,
) -> SummaryMigrationStats:
    """
    Run the Summary markdown migration.

    Args:
        dry_run: If True, validate without making changes
        summary_ids: Optional list of specific summary IDs to migrate
        force: If True, overwrite existing markdown_content
        batch_size: Number of records to process per batch

    Returns:
        Dictionary with migration statistics
    """
    stats: SummaryMigrationStats = {
        "summaries_processed": 0,
        "summaries_updated": 0,
        "summaries_skipped": 0,
        "errors": [],
    }

    logger.info(f"Starting Summary markdown migration (dry_run={dry_run}, force={force})")

    with get_db() as db:
        # Get summaries to migrate
        query = db.query(Summary)

        if summary_ids:
            query = query.filter(Summary.id.in_(summary_ids))

        # If not forcing, only get records without markdown_content
        if not force:
            query = query.filter(
                (Summary.markdown_content.is_(None)) | (Summary.markdown_content == "")
            )

        summaries = query.all()
        total = len(summaries)
        logger.info(f"Found {total} summaries to migrate")

        # Process summaries
        for i, summary in enumerate(summaries):
            try:
                updated = migrate_summary(summary, dry_run, force)

                if updated:
                    stats["summaries_updated"] += 1
                else:
                    stats["summaries_skipped"] += 1

                stats["summaries_processed"] += 1

                # Commit in batches
                if not dry_run and (i + 1) % batch_size == 0:
                    db.commit()
                    logger.info(f"Processed {i + 1}/{total} summaries")

            except Exception as e:
                error_msg = f"Error migrating Summary {summary.id}: {e}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)
                db.rollback()

        # Final commit
        if not dry_run:
            db.commit()

    logger.info("Migration complete!")
    logger.info(f"Statistics: {stats}")

    return stats


def rollback_migration(summary_ids: list[int] | None = None) -> SummaryRollbackStats:
    """
    Rollback the migration by clearing markdown_content and theme_tags.

    Args:
        summary_ids: Optional list of specific summary IDs to rollback

    Returns:
        Dictionary with rollback statistics
    """
    stats: SummaryRollbackStats = {
        "summaries_rolled_back": 0,
        "errors": [],
    }

    logger.info("Starting rollback")

    with get_db() as db:
        query = db.query(Summary)

        if summary_ids:
            query = query.filter(Summary.id.in_(summary_ids))
        else:
            # Only rollback records that have markdown_content
            query = query.filter(Summary.markdown_content.isnot(None))

        summaries = query.all()

        for summary in summaries:
            try:
                summary.markdown_content = None
                summary.theme_tags = None
                stats["summaries_rolled_back"] += 1
            except Exception as e:
                error_msg = f"Error rolling back Summary {summary.id}: {e}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)

        db.commit()

    logger.info(f"Rollback complete! Cleared {stats['summaries_rolled_back']} summaries")

    return stats


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate Summary records to add markdown_content and theme_tags"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate migration without making changes",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback migration (clear markdown_content and theme_tags)",
    )
    parser.add_argument(
        "--summary-ids",
        type=str,
        help="Comma-separated list of specific summary IDs to migrate",
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

    summary_ids = None
    if args.summary_ids:
        summary_ids = [int(x.strip()) for x in args.summary_ids.split(",")]

    if args.rollback:
        rollback_stats = rollback_migration(summary_ids)
        if rollback_stats.get("errors"):
            logger.error(f"Rollback completed with {len(rollback_stats['errors'])} errors")
            sys.exit(1)
    else:
        migration_stats = run_migration(
            dry_run=args.dry_run,
            summary_ids=summary_ids,
            force=args.force,
            batch_size=args.batch_size,
        )

        # Exit with error if there were failures
        if migration_stats.get("errors"):
            logger.error(f"Migration completed with {len(migration_stats['errors'])} errors")
            sys.exit(1)


if __name__ == "__main__":
    main()
