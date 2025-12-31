"""CLI script to ingest newsletters from RSS feeds."""

import argparse
from datetime import datetime, timedelta

from src.ingestion.rss import RSSIngestionService
from src.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)


def main() -> None:
    """Run RSS ingestion."""
    parser = argparse.ArgumentParser(description="Ingest newsletters from RSS feeds")
    parser.add_argument(
        "--feeds",
        type=str,
        nargs="+",
        help="RSS feed URLs (space-separated). If not provided, uses config from .env or rss_feeds.txt",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=10,
        help="Maximum number of entries to fetch per feed (default: 10)",
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
    service = RSSIngestionService()

    try:
        count = service.ingest_newsletters(
            feed_urls=args.feeds,  # None if not provided, will use config
            max_entries_per_feed=args.max,
            after_date=after_date,
            force_reprocess=args.force,
        )

        print(f"\n✓ Successfully ingested {count} newsletters from RSS feeds")
        print("\nYou can now view them in the database:")
        print("  docker exec -it newsletter-postgres psql -U newsletter_user -d newsletters")
        print("  SELECT id, title, publication, published_date, status FROM newsletters WHERE source = 'RSS';")

        if count == 0:
            print("\nℹ️  No new newsletters found. Make sure you have:")
            print("  1. Set RSS_FEEDS in .env (comma-separated URLs), or")
            print("  2. Created rss_feeds.txt with feed URLs (one per line), or")
            print("  3. Provided --feeds argument with URLs")
            print("\nExample RSS feeds to try:")
            print("  python -m scripts.ingest_rss --feeds https://www.latent.space/feed")

    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        return
    finally:
        service.close()


if __name__ == "__main__":
    main()
