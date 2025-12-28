"""CLI script to extract entities from newsletter summaries into Graphiti."""

import argparse
import asyncio

from src.models.newsletter import Newsletter
from src.models.summary import NewsletterSummary
from src.storage.database import get_db
from src.storage.graphiti_client import GraphitiClient
from src.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def extract_all_summaries(limit: int | None = None) -> int:
    """
    Extract entities from all newsletter summaries.

    Args:
        limit: Maximum number to process (None = all)

    Returns:
        Number of summaries processed
    """
    # Query for summary IDs
    with get_db() as db:
        query = (
            db.query(NewsletterSummary.newsletter_id, Newsletter.id)
            .join(Newsletter, NewsletterSummary.newsletter_id == Newsletter.id)
            .order_by(Newsletter.published_date)
        )

        if limit:
            query = query.limit(limit)

        summary_ids = [row[0] for row in query.all()]
        logger.info(f"Found {len(summary_ids)} summaries to process")

    # Process each summary
    count = 0
    async with GraphitiClient() as graphiti:
        for newsletter_id in summary_ids:
            try:
                with get_db() as db:
                    newsletter = db.query(Newsletter).filter(
                        Newsletter.id == newsletter_id
                    ).first()
                    summary = db.query(NewsletterSummary).filter(
                        NewsletterSummary.newsletter_id == newsletter_id
                    ).first()

                    if not newsletter or not summary:
                        logger.warning(f"Skipping newsletter {newsletter_id}: missing data")
                        continue

                    logger.info(f"Extracting entities from: {newsletter.title}")
                    # Call graphiti while session is still active
                    episode_id = await graphiti.add_newsletter_summary(newsletter, summary)

                logger.info(
                    f"Created episode {episode_id} for newsletter {newsletter_id}"
                )
                count += 1

            except Exception as e:
                logger.error(f"Error processing newsletter {newsletter_id}: {e}")
                continue

    return count


async def extract_single_summary(newsletter_id: int) -> bool:
    """
    Extract entities from a single newsletter summary.

    Args:
        newsletter_id: Newsletter ID to process

    Returns:
        True if successful, False otherwise
    """
    async with GraphitiClient() as graphiti:
        try:
            with get_db() as db:
                newsletter = db.query(Newsletter).filter(
                    Newsletter.id == newsletter_id
                ).first()
                summary = db.query(NewsletterSummary).filter(
                    NewsletterSummary.newsletter_id == newsletter_id
                ).first()

                if not newsletter:
                    logger.error(f"Newsletter {newsletter_id} not found")
                    return False

                if not summary:
                    logger.error(f"Summary for newsletter {newsletter_id} not found")
                    return False

                logger.info(f"Extracting entities from: {newsletter.title}")
                # Call graphiti while session is still active
                episode_id = await graphiti.add_newsletter_summary(newsletter, summary)

            logger.info(
                f"Created episode {episode_id} for newsletter {newsletter_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return False


async def main() -> None:
    """Run entity extraction."""
    parser = argparse.ArgumentParser(
        description="Extract entities from newsletter summaries into Graphiti knowledge graph"
    )
    parser.add_argument(
        "--id",
        type=int,
        help="Extract entities from a specific newsletter by ID",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Extract entities from all newsletters with summaries",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of newsletters to process (with --all)",
    )

    args = parser.parse_args()

    try:
        if args.id:
            # Extract from specific newsletter
            logger.info(f"Extracting entities from newsletter ID: {args.id}")
            success = await extract_single_summary(args.id)

            if success:
                print(f"\n✓ Successfully extracted entities from newsletter {args.id}")
                print("\nYou can now query the knowledge graph using:")
                print("  python scripts/query_knowledge_graph.py --query 'AI trends'")
            else:
                print(f"\n❌ Failed to extract entities from newsletter {args.id}")
                return

        elif args.all:
            # Extract from all summaries
            logger.info("Extracting entities from all newsletter summaries")
            count = await extract_all_summaries(limit=args.limit)

            print(f"\n✓ Successfully processed {count} newsletters")
            if count > 0:
                print("\nEntities extracted and stored in Neo4j knowledge graph")
                print("\nQuery the graph:")
                print("  python scripts/query_knowledge_graph.py --query 'AI trends'")

        else:
            print("Error: Must specify either --id or --all")
            parser.print_help()
            return

    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
        print(f"\n❌ Error: {e}")
        return


if __name__ == "__main__":
    asyncio.run(main())
