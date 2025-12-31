"""CLI script to summarize newsletters."""

import argparse
from datetime import datetime

from src.models.newsletter import Newsletter, ProcessingStatus
from src.models.summary import NewsletterSummary
from src.processors.summarizer import NewsletterSummarizer
from src.storage.database import get_db
from src.utils.logging import get_logger, setup_logging
from src.utils.summary_formatter import SummaryFormatter

# Setup logging
setup_logging()
logger = get_logger(__name__)


def list_pending_newsletters(after_date=None, before_date=None):
    """List pending newsletters with optional date filtering."""
    with get_db() as db:
        query = db.query(Newsletter).filter(Newsletter.status == ProcessingStatus.PENDING)

        if after_date:
            query = query.filter(Newsletter.published_date >= after_date)
        if before_date:
            query = query.filter(Newsletter.published_date <= before_date)

        newsletters = query.order_by(Newsletter.published_date.desc()).all()

        if not newsletters:
            print("\nNo pending newsletters found.")
            return

        print(f"\n{'='*120}")
        print(f"PENDING NEWSLETTERS ({len(newsletters)} total)")
        print(f"{'='*120}")
        print(f"{'ID':<6} | {'Title':<50} | {'Publication':<25} | {'Published Date':<12} | {'Status'}")
        print(f"{'-'*120}")

        for n in newsletters:
            title = (n.title[:47] + '...') if len(n.title) > 50 else n.title
            pub = (n.publication[:22] + '...') if n.publication and len(n.publication) > 25 else (n.publication or 'N/A')
            date_str = n.published_date.strftime('%Y-%m-%d')
            print(f"{n.id:<6} | {title:<50} | {pub:<25} | {date_str:<12} | {n.status.value}")


def list_summaries(newsletter_id=None, after_date=None, before_date=None, format_type="text"):
    """List existing newsletter summaries with optional filtering."""
    with get_db() as db:
        query = db.query(NewsletterSummary, Newsletter).join(
            Newsletter, NewsletterSummary.newsletter_id == Newsletter.id
        )

        if newsletter_id:
            query = query.filter(Newsletter.id == newsletter_id)
        if after_date:
            query = query.filter(Newsletter.published_date >= after_date)
        if before_date:
            query = query.filter(Newsletter.published_date <= before_date)

        results = query.order_by(Newsletter.published_date.desc()).all()

        if not results:
            print("\nNo summaries found.")
            return

        print(f"\n{'='*140}")
        print(f"NEWSLETTER SUMMARIES ({len(results)} total)")
        print(f"{'='*140}")
        print(f"{'ID':<6} | {'Title':<40} | {'Publication':<20} | {'Published':<12} | {'Key Themes'}")
        print(f"{'-'*140}")

        for summary, newsletter in results:
            title = (newsletter.title[:37] + '...') if len(newsletter.title) > 40 else newsletter.title
            pub = (newsletter.publication[:17] + '...') if newsletter.publication and len(newsletter.publication) > 20 else (newsletter.publication or 'N/A')
            date_str = newsletter.published_date.strftime('%Y-%m-%d')
            themes = ', '.join(summary.key_themes[:3])  # Show first 3 themes
            if len(summary.key_themes) > 3:
                themes += '...'
            themes = (themes[:45] + '...') if len(themes) > 48 else themes
            print(f"{newsletter.id:<6} | {title:<40} | {pub:<20} | {date_str:<12} | {themes}")

        # If showing a specific summary, display formatted output
        if newsletter_id and results:
            summary, newsletter = results[0]

            # Use formatter based on format_type
            if format_type == "markdown":
                output = SummaryFormatter.to_markdown(summary, newsletter)
            elif format_type == "html":
                output = SummaryFormatter.to_html(summary, newsletter)
            else:  # text
                output = SummaryFormatter.to_plain_text(summary, newsletter)

            print(output)


def main() -> None:
    """Run newsletter summarization."""
    parser = argparse.ArgumentParser(description="Summarize newsletters using Claude")

    # Action arguments
    parser.add_argument(
        "--id",
        type=int,
        help="Summarize a specific newsletter by ID (or view summary with --list-summaries)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Summarize all pending newsletters",
    )
    parser.add_argument(
        "--list-pending",
        action="store_true",
        help="List pending newsletters (without summarizing)",
    )
    parser.add_argument(
        "--list-summaries",
        action="store_true",
        help="List existing newsletter summaries",
    )

    # Filter arguments
    parser.add_argument(
        "--after",
        type=str,
        help="Filter newsletters published after or on this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--before",
        type=str,
        help="Filter newsletters published before or on this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of newsletters to process (with --all)",
    )

    # Model argument
    parser.add_argument(
        "--model",
        type=str,
        default="claude-haiku-4-5-20251001",
        help="Claude model to use (default: claude-haiku-4-5-20251001)",
    )

    # Output format argument
    parser.add_argument(
        "--format",
        type=str,
        choices=["text", "markdown", "html"],
        default="text",
        help="Output format for summary display (default: text)",
    )

    args = parser.parse_args()

    # Parse dates
    after_date = None
    before_date = None
    if args.after:
        try:
            after_date = datetime.fromisoformat(args.after)
        except ValueError:
            print(f"Error: Invalid date format for --after: {args.after}. Use YYYY-MM-DD")
            return

    if args.before:
        try:
            before_date = datetime.fromisoformat(args.before)
            # Set to end of day
            before_date = before_date.replace(hour=23, minute=59, second=59)
        except ValueError:
            print(f"Error: Invalid date format for --before: {args.before}. Use YYYY-MM-DD")
            return

    try:
        if args.list_pending:
            # List pending newsletters
            list_pending_newsletters(after_date=after_date, before_date=before_date)

        elif args.list_summaries:
            # List summaries
            list_summaries(
                newsletter_id=args.id,
                after_date=after_date,
                before_date=before_date,
                format_type=args.format,
            )

        elif args.id:
            # Summarize specific newsletter
            logger.info(f"Summarizing newsletter ID: {args.id}")
            summarizer = NewsletterSummarizer()
            success = summarizer.summarize_newsletter(args.id)

            if success:
                print(f"\n✓ Successfully summarized newsletter {args.id}")
                print("\nView summary:")
                print(f"  python -m scripts.summarize_newsletters --list-summaries --id {args.id}")
            else:
                print(f"\n❌ Failed to summarize newsletter {args.id}")
                return

        elif args.all:
            # Summarize all pending (with optional date filters)
            logger.info("Summarizing pending newsletters")
            summarizer = NewsletterSummarizer()

            # Get newsletters matching filters
            with get_db() as db:
                query = db.query(Newsletter).filter(Newsletter.status == ProcessingStatus.PENDING)
                if after_date:
                    query = query.filter(Newsletter.published_date >= after_date)
                if before_date:
                    query = query.filter(Newsletter.published_date <= before_date)
                if args.limit:
                    query = query.limit(args.limit)

                newsletter_ids = [n.id for n in query.all()]

            if not newsletter_ids:
                print("\nNo pending newsletters found matching the filters.")
                return

            # Summarize each
            count = 0
            for nid in newsletter_ids:
                if summarizer.summarize_newsletter(nid):
                    count += 1

            print(f"\n✓ Successfully summarized {count}/{len(newsletter_ids)} newsletters")
            if count > 0:
                print("\nView summaries:")
                print("  python -m scripts.summarize_newsletters --list-summaries")

        else:
            print("Error: Must specify one of: --id, --all, --list-pending, --list-summaries")
            parser.print_help()
            return

    except Exception as e:
        logger.error(f"Operation failed: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        return


if __name__ == "__main__":
    main()
