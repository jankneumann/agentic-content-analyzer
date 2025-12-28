"""CLI script to ingest newsletters from Gmail."""

import argparse
from datetime import datetime, timedelta

from src.ingestion.gmail import GmailIngestionService
from src.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)


def main() -> None:
    """Run Gmail ingestion."""
    parser = argparse.ArgumentParser(description="Ingest newsletters from Gmail")
    parser.add_argument(
        "--query",
        type=str,
        default="label:newsletters-ai",
        help="Gmail search query (default: label:newsletters-ai)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=10,
        help="Maximum number of newsletters to fetch (default: 10)",
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Only fetch newsletters from the last N days",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocessing of existing newsletters (updates data and resets status to pending)",
    )

    args = parser.parse_args()

    # Calculate after_date if days specified
    after_date = None
    if args.days:
        after_date = datetime.now() - timedelta(days=args.days)
        logger.info(f"Fetching newsletters from the last {args.days} days")

    if args.force:
        logger.info("Force reprocessing enabled - will update existing newsletters")

    # Run ingestion
    service = GmailIngestionService()

    try:
        count = service.ingest_newsletters(
            query=args.query,
            max_results=args.max,
            after_date=after_date,
            force_reprocess=args.force,
        )

        print(f"\n✓ Successfully ingested {count} newsletters")
        print("\nYou can now view them in the database:")
        print("  docker exec -it newsletter-postgres psql -U newsletter_user -d newsletters")
        print("  SELECT id, title, publication, published_date, status FROM newsletters;")

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        print(f"\n❌ Error: {e}")
        return


if __name__ == "__main__":
    main()
