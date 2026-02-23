"""CLI script to analyze themes across newsletters."""

import argparse
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

from src.models.theme import ThemeAnalysis, ThemeAnalysisRequest
from src.processors.theme_analyzer import ThemeAnalyzer
from src.storage.database import get_db
from src.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def main_async(args) -> None:
    """Run theme analysis (async)."""
    # Calculate date range
    if args.days:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days)
    else:
        start_date = datetime.fromisoformat(args.start_date)
        end_date = datetime.fromisoformat(args.end_date)

    logger.info(f"Analyzing themes from {start_date} to {end_date}")

    # Create request
    request = ThemeAnalysisRequest(
        start_date=start_date,
        end_date=end_date,
        min_newsletters=args.min_newsletters,
        max_themes=args.max_themes,
        relevance_threshold=args.relevance_threshold,
        use_large_context_model=args.use_large_context,
    )

    # Run analysis
    analyzer = ThemeAnalyzer(
        use_large_context=args.use_large_context,
        model_override=args.model,
    )

    result = await analyzer.analyze_themes(
        request,
        include_historical_context=not args.no_history,
    )

    # Display results
    print(f"\n{'=' * 80}")
    print("THEME ANALYSIS RESULTS")
    print(f"{'=' * 80}")
    print(f"\nDate Range: {start_date.date()} to {end_date.date()}")
    print(f"Newsletters Analyzed: {result.newsletter_count}")
    print(f"Total Themes Found: {result.total_themes}")
    print(f"Emerging Themes: {result.emerging_themes_count}")
    print(f"Processing Time: {result.processing_time_seconds:.2f}s")
    print(f"Model Used: {result.model_used}")
    print(f"\n{'=' * 80}")

    if result.themes:
        print("\nTOP THEMES (sorted by relevance):\n")

        for i, theme in enumerate(result.themes, 1):
            print(f"{i}. {theme.name}")
            print(f"   Category: {theme.category.value}")
            print(f"   Trend: {theme.trend.value}")
            print(f"   Mentions: {theme.mention_count} newsletters")
            print(
                f"   Relevance: {theme.relevance_score:.2f} "
                f"(Strategic: {theme.strategic_relevance:.2f}, "
                f"Tactical: {theme.tactical_relevance:.2f})"
            )
            print(f"   Novelty: {theme.novelty_score:.2f}")
            print(f"   Description: {theme.description}")

            if theme.key_points:
                print("   Key Points:")
                for point in theme.key_points[:3]:  # Show top 3
                    print(f"   • {point}")

            if theme.related_themes:
                print(f"   Related: {', '.join(theme.related_themes[:3])}")

            # Show historical context (NEW)
            if theme.continuity_text:
                print(f"\n   {theme.continuity_text}")

            if theme.historical_context:
                hist = theme.historical_context
                print(
                    f"   Historical: {hist.total_mentions} mentions since "
                    f"{hist.first_mention.strftime('%Y-%m-%d')} ({hist.mention_frequency})"
                )
                if hist.previous_discussions:
                    print("   Previous Points:")
                    for prev in hist.previous_discussions[:2]:
                        print(f"   • {prev}")

            print()

    # Save to database if requested
    if args.save:
        logger.info("Saving analysis to database...")
        with get_db() as db:
            # Convert ThemeData to dicts with datetime serialization
            themes_json = [
                {
                    **t.model_dump(),
                    "first_seen": t.first_seen.isoformat(),
                    "last_seen": t.last_seen.isoformat(),
                }
                for t in result.themes
            ]

            analysis = ThemeAnalysis(
                start_date=result.start_date,
                end_date=result.end_date,
                newsletter_count=result.newsletter_count,
                newsletter_ids=result.newsletter_ids,
                themes=themes_json,
                total_themes=result.total_themes,
                emerging_themes_count=result.emerging_themes_count,
                top_theme=result.top_theme,
                agent_framework=result.agent_framework,
                model_used=result.model_used,
                processing_time_seconds=result.processing_time_seconds,
                token_usage=result.token_usage,
            )
            db.add(analysis)
            db.commit()

        print(f"✓ Analysis saved to database (ID: {analysis.id})")

    # Export to JSON if requested
    if args.output:
        json_content = json.dumps(result.model_dump(), indent=2, default=str)
        Path(args.output).write_text(json_content)
        print(f"✓ Results exported to {args.output}")

    # Performance metrics
    print(f"\n{'=' * 80}")
    print("PERFORMANCE METRICS")
    print(f"{'=' * 80}")
    print(f"Processing Time: {result.processing_time_seconds:.2f}s")
    print(f"Newsletters/second: {result.newsletter_count / result.processing_time_seconds:.2f}")
    print(
        f"Average time per newsletter: {result.processing_time_seconds / result.newsletter_count:.2f}s"
    )

    # Check if we should recommend Gemini Flash
    if result.processing_time_seconds > 30 and not args.use_large_context:
        print(f"\n⚠️  RECOMMENDATION: Processing took {result.processing_time_seconds:.0f}s")
        print("   Consider using --use-large-context flag to enable Gemini Flash")
        print("   for faster processing with large context windows.")

    if result.newsletter_count > 50 and not args.use_large_context:
        print(f"\n⚠️  RECOMMENDATION: Analyzing {result.newsletter_count} newsletters")
        print("   Consider using --use-large-context flag for better performance")
        print("   with large batches.")


def main() -> None:
    """Run theme analysis (sync wrapper)."""
    parser = argparse.ArgumentParser(description="Analyze themes across newsletters")

    # Date range options
    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument(
        "--days",
        type=int,
        help="Analyze newsletters from the last N days",
    )
    date_group.add_argument(
        "--range",
        nargs=2,
        metavar=("START", "END"),
        dest="date_range",
        help="Analyze newsletters in date range (YYYY-MM-DD YYYY-MM-DD)",
    )

    # Analysis options
    parser.add_argument(
        "--max-themes",
        type=int,
        default=20,
        help="Maximum themes to extract (default: 20)",
    )
    parser.add_argument(
        "--min-newsletters",
        type=int,
        default=1,
        help="Minimum newsletters required (default: 1)",
    )
    parser.add_argument(
        "--relevance-threshold",
        type=float,
        default=0.3,
        help="Minimum relevance score 0-1 (default: 0.3)",
    )

    # Model options
    parser.add_argument(
        "--use-large-context",
        action="store_true",
        help="Use large context model (Gemini Flash) for better performance with many newsletters",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Override model (e.g., claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Skip historical context enrichment (faster but less continuity)",
    )

    # Output options
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save analysis results to database",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Export results to JSON file",
    )

    args = parser.parse_args()

    # Parse date range
    if args.date_range:
        args.start_date = args.date_range[0]
        args.end_date = args.date_range[1]
        args.days = None

    # Run async main
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
