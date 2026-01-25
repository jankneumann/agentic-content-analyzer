"""CLI script to extract entities from content summaries into Graphiti.

.. deprecated::
    This script uses the legacy Newsletter model. Consider using Content-based
    workflows for new entity extraction.
"""

import argparse
import asyncio
import warnings

from src.models.content import Content
from src.models.summary import Summary
from src.storage.database import get_db
from src.storage.graphiti_client import GraphitiClient
from src.utils.logging import get_logger, setup_logging

# Emit deprecation warning
warnings.warn(
    "extract_entities.py uses legacy Newsletter patterns. "
    "Consider migrating to Content-based workflows.",
    DeprecationWarning,
    stacklevel=1,
)

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def extract_all_summaries(limit: int | None = None) -> int:
    """
    Extract entities from all content summaries.

    Args:
        limit: Maximum number to process (None = all)

    Returns:
        Number of summaries processed
    """
    # Query for summaries with content
    with get_db() as db:
        query = (
            db.query(Summary.content_id, Content.id)
            .join(Content, Summary.content_id == Content.id)
            .order_by(Content.published_date)
        )

        if limit:
            query = query.limit(limit)

        content_ids = [row[0] for row in query.all()]
        logger.info(f"Found {len(content_ids)} summaries to process")

    # Process each summary
    count = 0
    async with GraphitiClient() as graphiti:
        for content_id in content_ids:
            try:
                with get_db() as db:
                    content = db.query(Content).filter(Content.id == content_id).first()
                    summary = db.query(Summary).filter(Summary.content_id == content_id).first()

                    if not content or not summary:
                        logger.warning(f"Skipping content {content_id}: missing data")
                        continue

                    logger.info(f"Extracting entities from: {content.title}")
                    # Call graphiti while session is still active
                    episode_id = await graphiti.add_content_summary(content, summary)

                logger.info(f"Created episode {episode_id} for content {content_id}")
                count += 1

            except Exception as e:
                logger.error(f"Error processing content {content_id}: {e}")
                continue

    return count


async def extract_single_summary(content_id: int) -> bool:
    """
    Extract entities from a single content summary.

    Args:
        content_id: Content ID to process

    Returns:
        True if successful, False otherwise
    """
    async with GraphitiClient() as graphiti:
        try:
            with get_db() as db:
                content = db.query(Content).filter(Content.id == content_id).first()
                summary = db.query(Summary).filter(Summary.content_id == content_id).first()

                if not content:
                    logger.error(f"Content {content_id} not found")
                    return False

                if not summary:
                    logger.error(f"Summary for content {content_id} not found")
                    return False

                logger.info(f"Extracting entities from: {content.title}")
                episode_id = await graphiti.add_content_summary(content, summary)

            logger.info(f"Created episode {episode_id} for content {content_id}")
            return True

        except Exception as e:
            logger.error(f"Error processing content {content_id}: {e}")
            return False


def main() -> None:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Extract entities from content summaries into Graphiti"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all summaries",
    )
    parser.add_argument(
        "--id",
        type=int,
        help="Process specific content ID",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number to process",
    )

    args = parser.parse_args()

    if args.id:
        success = asyncio.run(extract_single_summary(args.id))
        if success:
            print(f"✓ Successfully extracted entities for content {args.id}")
        else:
            print(f"✗ Failed to extract entities for content {args.id}")
    elif args.all:
        count = asyncio.run(extract_all_summaries(args.limit))
        print(f"✓ Successfully extracted entities for {count} summaries")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
