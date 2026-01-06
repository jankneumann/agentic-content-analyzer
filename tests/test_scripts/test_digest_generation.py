"""Test script to generate a digest and verify summary usage."""

import asyncio
from datetime import datetime

import pytest

from src.models.digest import DigestRequest, DigestType
from src.processors.digest_creator import DigestCreator
from src.utils.logging import get_logger

logger = get_logger(__name__)


@pytest.mark.skip(reason="Functional test requiring database - run manually")
@pytest.mark.asyncio
async def test_digest_generation():
    """Generate a test digest for December 26, 2025."""
    logger.info("=" * 80)
    logger.info("TESTING DIGEST GENERATION WITH NEWSLETTER SUMMARIES")
    logger.info("=" * 80)

    # Create digest request for Dec 26, 2025 (where we have summaries)
    request = DigestRequest(
        digest_type=DigestType.DAILY,
        period_start=datetime(2025, 12, 26, 0, 0, 0),
        period_end=datetime(2025, 12, 26, 23, 59, 59),
        max_strategic_insights=5,
        max_technical_developments=5,
        max_emerging_trends=3,
        include_historical_context=False,  # Disable for faster testing
    )

    # Create digest
    creator = DigestCreator()

    try:
        logger.info(f"\nGenerating {request.digest_type.value} digest...")
        logger.info(f"Period: {request.period_start.date()} to {request.period_end.date()}\n")

        digest = await creator.create_digest(request)

        logger.info("\n" + "=" * 80)
        logger.info("DIGEST GENERATED SUCCESSFULLY!")
        logger.info("=" * 80)
        logger.info(f"\nTitle: {digest.title}")
        logger.info(f"Newsletters processed: {digest.newsletter_count}")
        logger.info(f"Processing time: {digest.processing_time_seconds:.2f}s")
        logger.info(f"Is combined: {digest.is_combined}")
        logger.info(f"Model used: {digest.model_used}")

        logger.info("\n" + "-" * 80)
        logger.info("EXECUTIVE OVERVIEW:")
        logger.info("-" * 80)
        logger.info(digest.executive_overview)

        logger.info("\n" + "-" * 80)
        logger.info(f"STRATEGIC INSIGHTS ({len(digest.strategic_insights)}):")
        logger.info("-" * 80)
        for i, insight in enumerate(digest.strategic_insights, 1):
            logger.info(f"\n{i}. {insight.title}")
            logger.info(f"   {insight.summary}")
            if insight.details:
                logger.info(f"   Details: {len(insight.details)} points")

        logger.info("\n" + "-" * 80)
        logger.info(f"TECHNICAL DEVELOPMENTS ({len(digest.technical_developments)}):")
        logger.info("-" * 80)
        for i, dev in enumerate(digest.technical_developments, 1):
            logger.info(f"\n{i}. {dev.title}")
            logger.info(f"   {dev.summary}")

        logger.info("\n" + "-" * 80)
        logger.info(f"SOURCES ({len(digest.sources)}):")
        logger.info("-" * 80)
        for i, source in enumerate(digest.sources, 1):
            logger.info(f"{i}. [{source['id']}] {source['publication']} - {source['title']}")

        logger.info("\n" + "=" * 80)
        logger.info("VERIFICATION: Check the logs above for:")
        logger.info("  1. 'Fetched X summaries for Y newsletters' message")
        logger.info("  2. Summary content included in newsletter context")
        logger.info("  3. Rich insights derived from summary data")
        logger.info("=" * 80)

        return digest

    except Exception as e:
        logger.error(f"\nERROR generating digest: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(test_digest_generation())
