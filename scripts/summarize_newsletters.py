"""CLI script to summarize newsletters."""

import argparse

from src.processors.summarizer import NewsletterSummarizer
from src.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)


def main() -> None:
    """Run newsletter summarization."""
    parser = argparse.ArgumentParser(description="Summarize newsletters using Claude")
    parser.add_argument(
        "--id",
        type=int,
        help="Summarize a specific newsletter by ID",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Summarize all pending newsletters",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of newsletters to process (with --all)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="claude-haiku-4-5-20251001",
        help="Claude model to use (default: claude-haiku-4-5-20251001)",
    )

    args = parser.parse_args()

    # Create summarizer
    summarizer = NewsletterSummarizer()

    try:
        if args.id:
            # Summarize specific newsletter
            logger.info(f"Summarizing newsletter ID: {args.id}")
            success = summarizer.summarize_newsletter(args.id)

            if success:
                print(f"\n✓ Successfully summarized newsletter {args.id}")
                print("\nView summary:")
                print(f"  docker exec newsletter-postgres psql -U newsletter_user -d newsletters \\")
                print(f"    -c \"SELECT executive_summary, key_themes FROM newsletter_summaries WHERE newsletter_id = {args.id};\"")
            else:
                print(f"\n❌ Failed to summarize newsletter {args.id}")
                return

        elif args.all:
            # Summarize all pending
            logger.info("Summarizing all pending newsletters")
            count = summarizer.summarize_pending_newsletters(limit=args.limit)

            print(f"\n✓ Successfully summarized {count} newsletters")
            if count > 0:
                print("\nView summaries:")
                print("  docker exec newsletter-postgres psql -U newsletter_user -d newsletters \\")
                print("    -c \"SELECT ns.id, n.title, ns.executive_summary FROM newsletter_summaries ns JOIN newsletters n ON ns.newsletter_id = n.id;\"")

        else:
            print("Error: Must specify either --id or --all")
            parser.print_help()
            return

    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        print(f"\n❌ Error: {e}")
        return


if __name__ == "__main__":
    main()
