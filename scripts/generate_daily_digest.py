"""CLI script to generate daily digests."""

import argparse
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from src.models.digest import Digest, DigestData, DigestRequest, DigestStatus, DigestType
from src.processors.digest_creator import DigestCreator
from src.storage.database import get_db
from src.utils.digest_formatter import DigestFormatter
from src.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def main_async(args) -> None:
    """Generate daily digest (async)."""
    # Calculate date range
    if args.date:
        target_date = datetime.fromisoformat(args.date).date()
        period_start = datetime.combine(target_date, datetime.min.time())
        period_end = datetime.combine(target_date, datetime.max.time())
    else:
        # Default to yesterday
        yesterday = (datetime.now() - timedelta(days=1)).date()
        period_start = datetime.combine(yesterday, datetime.min.time())
        period_end = datetime.combine(yesterday, datetime.max.time())

    logger.info(f"Generating daily digest for {period_start.date()}")

    # Create request
    request = DigestRequest(
        digest_type=DigestType.DAILY,
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
    print(f"DAILY DIGEST GENERATED")
    print(f"{'='*80}")
    print(f"\nDate: {period_start.date()}")
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
            technical_developments = [section.model_dump() for section in digest.technical_developments]
            emerging_trends = [section.model_dump() for section in digest.emerging_trends]

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
                status=DigestStatus.COMPLETED,
                completed_at=datetime.utcnow(),
                agent_framework=digest.agent_framework,
                model_used=digest.model_used,
                token_usage=digest.token_usage,
                processing_time_seconds=int(digest.processing_time_seconds) if digest.processing_time_seconds else None,
            )
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
        print(f"PERFORMANCE METRICS")
        print(f"{'='*80}")
        print(f"Processing Time: {digest.processing_time_seconds:.2f}s")
        print(f"Average per newsletter: {digest.processing_time_seconds / digest.newsletter_count:.2f}s")
    else:
        print(f"\n⚠️  No newsletters found for {period_start.date()}")


def main() -> None:
    """Generate daily digest (sync wrapper)."""
    parser = argparse.ArgumentParser(description="Generate daily newsletter digest")

    # Date options
    parser.add_argument(
        "--date",
        type=str,
        help="Date to generate digest for (YYYY-MM-DD). Defaults to yesterday.",
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
