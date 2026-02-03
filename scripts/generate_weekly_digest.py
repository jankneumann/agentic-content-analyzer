"""CLI script to generate weekly digests."""

import argparse
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from src.models.digest import Digest, DigestRequest, DigestStatus, DigestType
from src.processors.digest_creator import DigestCreator
from src.storage.database import get_db
from src.utils.digest_formatter import DigestFormatter
from src.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def main_async(args) -> None:
    """Generate weekly digest (async)."""
    # Calculate date range
    if args.week:
        # Week ending on specified date
        end_date = datetime.fromisoformat(args.week).date()
        start_date = end_date - timedelta(days=6)
        period_start = datetime.combine(start_date, datetime.min.time())
        period_end = datetime.combine(end_date, datetime.max.time())
    elif args.range:
        start_date = datetime.fromisoformat(args.range[0]).date()
        end_date = datetime.fromisoformat(args.range[1]).date()
        period_start = datetime.combine(start_date, datetime.min.time())
        period_end = datetime.combine(end_date, datetime.max.time())
    else:
        # Default to last 7 days (ending yesterday)
        yesterday = (datetime.now() - timedelta(days=1)).date()
        week_ago = yesterday - timedelta(days=6)
        period_start = datetime.combine(week_ago, datetime.min.time())
        period_end = datetime.combine(yesterday, datetime.max.time())

    logger.info(f"Generating weekly digest for {period_start.date()} to {period_end.date()}")

    # Create request
    request = DigestRequest(
        digest_type=DigestType.WEEKLY,
        period_start=period_start,
        period_end=period_end,
        max_strategic_insights=args.max_strategic,
        max_technical_developments=args.max_technical,
        max_emerging_trends=args.max_emerging,
        include_historical_context=not args.no_history,
    )

    # Generate digest
    creator = DigestCreator(model=args.model)
    digest = await creator.create_digest(request)

    # Display results
    print(f"\n{'='*80}")
    print("WEEKLY DIGEST GENERATED")
    print(f"{'='*80}")
    print(f"\nPeriod: {period_start.date()} to {period_end.date()}")
    print(f"Newsletters Analyzed: {digest.newsletter_count}")
    print(f"Processing Time: {digest.processing_time_seconds:.2f}s")
    print(f"Model Used: {digest.model_used}")
    print(f"\n{'='*80}\n")

    # Display preview
    if not args.quiet:
        if args.format == "markdown":
            output = DigestFormatter.to_markdown(digest)
        elif args.format == "html":
            output = DigestFormatter.to_html(digest)
        else:
            output = DigestFormatter.to_plain_text(digest)

        print(output)

    # Save to database if requested
    if args.save:
        logger.info("Saving digest to database...")
        with get_db() as db:
            # Convert DigestSection objects to dicts
            strategic_insights = [section.model_dump() for section in digest.strategic_insights]
            technical_developments = [
                section.model_dump() for section in digest.technical_developments
            ]
            emerging_trends = [section.model_dump() for section in digest.emerging_trends]

            # Determine initial status (PENDING_REVIEW by default, APPROVED if auto-approved)
            initial_status = (
                DigestStatus.APPROVED if args.auto_approve else DigestStatus.PENDING_REVIEW
            )

            db_digest = Digest(
                digest_type=digest.digest_type,
                period_start=digest.period_start,
                period_end=digest.period_end,
                title=digest.title,
                executive_overview=digest.executive_overview,
                strategic_insights=strategic_insights,
                technical_developments=technical_developments,
                emerging_trends=emerging_trends,
                actionable_recommendations=digest.actionable_recommendations,
                sources=digest.sources,
                historical_context=digest.historical_context or [],
                newsletter_count=digest.newsletter_count,
                status=initial_status,
                completed_at=datetime.utcnow(),
                agent_framework=digest.agent_framework,
                model_used=digest.model_used,
                token_usage=digest.token_usage,
                processing_time_seconds=int(digest.processing_time_seconds)
                if digest.processing_time_seconds
                else None,
            )

            # Set review metadata if auto-approved
            if args.auto_approve:
                db_digest.reviewed_by = "auto-approval"
                db_digest.reviewed_at = datetime.utcnow()
            db.add(db_digest)
            db.commit()

        print(f"✓ Digest saved to database (ID: {db_digest.id})")

    # Export to file if requested
    if args.output:
        output_path = Path(args.output)

        # Determine format from extension or flag
        if output_path.suffix == ".md" or args.format == "markdown":
            content = DigestFormatter.to_markdown(digest)
        elif output_path.suffix == ".html" or args.format == "html":
            content = DigestFormatter.to_html(digest)
        else:
            content = DigestFormatter.to_plain_text(digest)

        output_path.write_text(content)
        print(f"✓ Digest exported to {args.output}")

    # Performance summary
    if digest.newsletter_count > 0:
        print(f"\n{'='*80}")
        print("PERFORMANCE METRICS")
        print(f"{'='*80}")
        print(f"Processing Time: {digest.processing_time_seconds:.2f}s")
        print(
            f"Average per newsletter: {digest.processing_time_seconds / digest.newsletter_count:.2f}s"
        )

        # Recommendations for large batches
        if digest.newsletter_count > 50:
            print(f"\n💡 Processing {digest.newsletter_count} newsletters")
            print("   Consider using daily digests for faster incremental processing")
    else:
        print(f"\n⚠️  No newsletters found for {period_start.date()} to {period_end.date()}")


def main() -> None:
    """Generate weekly digest (sync wrapper)."""
    parser = argparse.ArgumentParser(description="Generate weekly newsletter digest")

    # Date options
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument(
        "--week",
        type=str,
        help="Week ending on date (YYYY-MM-DD). Generates digest for 7 days ending on this date.",
    )
    date_group.add_argument(
        "--range",
        nargs=2,
        metavar=("START", "END"),
        help="Custom date range (YYYY-MM-DD YYYY-MM-DD)",
    )

    # Content options
    parser.add_argument(
        "--max-strategic",
        type=int,
        default=5,
        help="Maximum strategic insights (default: 5)",
    )
    parser.add_argument(
        "--max-technical",
        type=int,
        default=5,
        help="Maximum technical developments (default: 5)",
    )
    parser.add_argument(
        "--max-emerging",
        type=int,
        default=3,
        help="Maximum emerging trends (default: 3)",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Skip historical context enrichment (faster but less continuity)",
    )

    # Model options
    parser.add_argument(
        "--model",
        type=str,
        help="Override model (e.g., claude-sonnet-4-20250514)",
    )

    # Output options
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save digest to database",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Automatically approve digest (skip review). Sets status to APPROVED instead of PENDING_REVIEW.",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Export digest to file (use .md for markdown, .html for HTML, .txt for plain text)",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["markdown", "html", "text"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Don't display digest content, only metadata",
    )

    args = parser.parse_args()

    # Run async main
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
