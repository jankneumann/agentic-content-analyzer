#!/usr/bin/env python3
"""Unified pipeline for newsletter processing.

This script orchestrates the full newsletter processing workflow:
1. Ingestion (Gmail + Substack RSS)
2. Summarization (individual newsletters)
3. Theme Analysis (embedded in digest creation)
4. Digest Generation (daily or weekly)

Usage:
    # Full pipeline (ingest + summarize + digest)
    python -m scripts.run_pipeline

    # Process yesterday's newsletters
    python -m scripts.run_pipeline --date 2025-12-28

    # Skip ingestion, only process existing newsletters
    python -m scripts.run_pipeline --skip-ingestion

    # Only ingest from Gmail
    python -m scripts.run_pipeline --sources gmail

    # Auto-approve digest (skip review)
    python -m scripts.run_pipeline --auto-approve

    # Weekly digest
    python -m scripts.run_pipeline --weekly
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.ingestion.gmail import GmailIngestionService
from src.ingestion.rss import RSSIngestionService
from src.models.digest import Digest, DigestData, DigestRequest, DigestStatus, DigestType
from src.models.newsletter import Newsletter, ProcessingStatus
from src.processors.digest_creator import DigestCreator
from src.processors.summarizer import NewsletterSummarizer
from src.storage.database import get_db

logger = logging.getLogger(__name__)


class NewsletterPipeline:
    """Orchestrate full newsletter processing pipeline."""

    def __init__(self, skip_ingestion: bool = False):
        self.skip_ingestion = skip_ingestion
        self.stats = {
            "ingested": 0,
            "summarized": 0,
            "digest_created": False,
            "digest_id": None,
            "errors": [],
        }

    async def run_daily_pipeline(
        self,
        date: datetime,
        sources: list[str] = ["gmail", "rss"],
        auto_approve: bool = False,
    ) -> dict:
        """
        Run full daily pipeline: ingest → summarize → digest.

        Args:
            date: Date to process
            sources: Which sources to ingest from
            auto_approve: Auto-approve digest (skip review)

        Returns:
            Statistics dictionary with counts and errors
        """
        logger.info(f"Starting daily pipeline for {date.date()}")

        # Step 1: Ingest newsletters (optional)
        if not self.skip_ingestion:
            self.stats["ingested"] = self._ingest_newsletters(sources, date)
        else:
            logger.info("Skipping ingestion (--skip-ingestion)")

        # Step 2: Summarize pending newsletters
        self.stats["summarized"] = self._summarize_pending()

        # Step 3: Generate daily digest
        period_start = datetime.combine(date.date(), datetime.min.time())
        period_end = datetime.combine(date.date(), datetime.max.time())

        digest_id = await self._create_digest(
            DigestType.DAILY, period_start, period_end, auto_approve
        )

        self.stats["digest_created"] = digest_id is not None
        self.stats["digest_id"] = digest_id

        # Report results
        self._print_summary()

        return self.stats

    async def run_weekly_pipeline(
        self,
        end_date: datetime,
        sources: list[str] = ["gmail", "rss"],
        auto_approve: bool = False,
    ) -> dict:
        """
        Run weekly pipeline for last 7 days.

        Args:
            end_date: End date of week
            sources: Which sources to ingest from
            auto_approve: Auto-approve digest (skip review)

        Returns:
            Statistics dictionary
        """
        start_date = end_date - timedelta(days=7)
        logger.info(f"Starting weekly pipeline for {start_date.date()} to {end_date.date()}")

        # Step 1: Ingest newsletters (optional)
        if not self.skip_ingestion:
            # Ingest for past 7 days
            for i in range(7):
                current_date = start_date + timedelta(days=i)
                ingested = self._ingest_newsletters(sources, current_date)
                self.stats["ingested"] += ingested
        else:
            logger.info("Skipping ingestion (--skip-ingestion)")

        # Step 2: Summarize pending newsletters
        self.stats["summarized"] = self._summarize_pending()

        # Step 3: Generate weekly digest
        period_start = datetime.combine(start_date.date(), datetime.min.time())
        period_end = datetime.combine(end_date.date(), datetime.max.time())

        digest_id = await self._create_digest(
            DigestType.WEEKLY, period_start, period_end, auto_approve
        )

        self.stats["digest_created"] = digest_id is not None
        self.stats["digest_id"] = digest_id

        # Report results
        self._print_summary()

        return self.stats

    def _ingest_newsletters(self, sources: list[str], date: datetime) -> int:
        """
        Ingest newsletters from specified sources.

        Args:
            sources: List of sources ('gmail', 'rss')
            date: Date to ingest for

        Returns:
            Total count of ingested newsletters
        """
        total_ingested = 0

        if "gmail" in sources:
            gmail = None
            try:
                logger.info("Ingesting from Gmail...")
                gmail = GmailIngestionService()
                # Calculate after_date (1 day before the target date)
                after_date = date - timedelta(days=1)
                count = gmail.ingest_newsletters(after_date=after_date)
                total_ingested += count
                logger.info(f"✓ Ingested {count} newsletters from Gmail")
            except Exception as e:
                logger.error(f"✗ Gmail ingestion failed: {e}", exc_info=True)
                self.stats["errors"].append(("gmail_ingestion", str(e)))
            finally:
                if gmail:
                    # GmailIngestionService doesn't have a close method, no cleanup needed
                    pass

        if "rss" in sources:
            rss = None
            try:
                logger.info("Ingesting from RSS feeds...")
                rss = RSSIngestionService()
                # Calculate after_date (1 day before the target date)
                after_date = date - timedelta(days=1)
                count = rss.ingest_newsletters(after_date=after_date)
                total_ingested += count
                logger.info(f"✓ Ingested {count} newsletters from RSS")
            except Exception as e:
                logger.error(f"✗ RSS ingestion failed: {e}", exc_info=True)
                self.stats["errors"].append(("rss_ingestion", str(e)))
            finally:
                if rss:
                    rss.close()

        return total_ingested

    def _summarize_pending(self) -> int:
        """
        Summarize all pending newsletters.

        Returns:
            Count of successfully summarized newsletters
        """
        try:
            logger.info("Summarizing pending newsletters...")
            summarizer = NewsletterSummarizer()
            count = summarizer.summarize_pending_newsletters()
            logger.info(f"✓ Summarized {count} newsletters")
            return count
        except Exception as e:
            logger.error(f"✗ Summarization failed: {e}", exc_info=True)
            self.stats["errors"].append(("summarization", str(e)))
            return 0

    async def _create_digest(
        self,
        digest_type: DigestType,
        period_start: datetime,
        period_end: datetime,
        auto_approve: bool,
    ) -> Optional[int]:
        """
        Create and save digest.

        Args:
            digest_type: DAILY or WEEKLY
            period_start: Start of period
            period_end: End of period
            auto_approve: Whether to auto-approve (skip review)

        Returns:
            Digest ID if successful, None otherwise
        """
        try:
            logger.info(f"Creating {digest_type.value} digest...")

            request = DigestRequest(
                digest_type=digest_type,
                period_start=period_start,
                period_end=period_end,
                max_strategic_insights=5,
                max_technical_developments=5,
                max_emerging_trends=3,
                include_historical_context=True,
            )

            creator = DigestCreator()
            digest_data = await creator.create_digest(request)

            # Save to database
            with get_db() as db:
                db_digest = Digest(**digest_data.model_dump())

                if auto_approve:
                    db_digest.status = DigestStatus.APPROVED
                    logger.info("Auto-approving digest")
                else:
                    db_digest.status = DigestStatus.PENDING_REVIEW
                    logger.info("Digest saved as PENDING_REVIEW")

                db.add(db_digest)
                db.commit()
                db.refresh(db_digest)

                digest_id = db_digest.id
                logger.info(f"✓ Created digest ID {digest_id} (status: {db_digest.status.value})")

                return digest_id

        except Exception as e:
            logger.error(f"✗ Digest creation failed: {e}", exc_info=True)
            self.stats["errors"].append(("digest_creation", str(e)))
            return None

    def _print_summary(self):
        """Print pipeline execution summary."""
        print("\n" + "=" * 70)
        print("PIPELINE EXECUTION SUMMARY")
        print("=" * 70)
        print(f"Newsletters ingested:  {self.stats['ingested']}")
        print(f"Newsletters summarized: {self.stats['summarized']}")
        print(
            f"Digest created:        {'✓ (ID: ' + str(self.stats['digest_id']) + ')' if self.stats['digest_created'] else '✗'}"
        )

        if self.stats["errors"]:
            print(f"\n⚠ Errors encountered: {len(self.stats['errors'])}")
            for step, error in self.stats["errors"]:
                print(f"  - {step}: {error[:100]}...")
        else:
            print("\n✓ Pipeline completed successfully!")

        print("=" * 70 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run newsletter processing pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline (ingest + summarize + digest)
  python -m scripts.run_pipeline

  # Process yesterday's newsletters
  python -m scripts.run_pipeline --date 2025-12-28

  # Skip ingestion, only process existing newsletters
  python -m scripts.run_pipeline --skip-ingestion

  # Only ingest from Gmail
  python -m scripts.run_pipeline --sources gmail

  # Auto-approve digest (skip review)
  python -m scripts.run_pipeline --auto-approve

  # Weekly digest
  python -m scripts.run_pipeline --weekly
        """,
    )

    parser.add_argument(
        "--date",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
        default=datetime.now(),
        help="Date to process (YYYY-MM-DD, default: today)",
    )

    parser.add_argument(
        "--skip-ingestion",
        action="store_true",
        help="Skip ingestion, only process existing newsletters",
    )

    parser.add_argument(
        "--sources",
        nargs="+",
        default=["gmail", "rss"],
        choices=["gmail", "rss"],
        help="Which sources to ingest from (default: both)",
    )

    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve digest (skip review step)",
    )

    parser.add_argument(
        "--weekly",
        action="store_true",
        help="Generate weekly digest instead of daily",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (DEBUG level)",
    )

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Run pipeline
    pipeline = NewsletterPipeline(skip_ingestion=args.skip_ingestion)

    try:
        if args.weekly:
            # Weekly: last 7 days ending on specified date
            stats = asyncio.run(
                pipeline.run_weekly_pipeline(
                    end_date=args.date,
                    sources=args.sources,
                    auto_approve=args.auto_approve,
                )
            )
        else:
            # Daily: single day
            stats = asyncio.run(
                pipeline.run_daily_pipeline(
                    date=args.date,
                    sources=args.sources,
                    auto_approve=args.auto_approve,
                )
            )

        # Exit with error code if pipeline had errors
        if stats["errors"]:
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\nPipeline interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Pipeline failed with unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
