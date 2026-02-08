"""Content processing tasks for the queue worker.

These tasks handle background operations like URL content extraction,
summarization, and other content processing pipelines.
"""

import asyncio
import json
from typing import TYPE_CHECKING, Any

from pgqueuer import PgQueuer
from pgqueuer.models import Job

from src.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Exponential backoff delays for rate limit retries (in seconds)
RATE_LIMIT_BACKOFF_DELAYS = [5, 10, 20]


def _decode_payload(job: Job) -> dict[str, Any]:
    """Decode job payload from bytes to dict.

    PGQueuer stores payloads as bytes (bytea in PostgreSQL).
    This helper decodes JSON bytes back to a Python dict.

    Args:
        job: The PGQueuer Job instance

    Returns:
        Decoded payload as dict, or empty dict if payload is None/empty
    """
    if job.payload is None:
        return {}
    try:
        result = json.loads(job.payload.decode("utf-8"))
        if isinstance(result, dict):
            return result
        logger.warning(f"Job payload is not a dict: {type(result)}")
        return {}
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning(f"Failed to decode job payload: {e}")
        return {}


def register_content_tasks(pgq: PgQueuer) -> None:
    """Register all content-related task entrypoints.

    Args:
        pgq: PGQueuer instance to register tasks with
    """

    @pgq.entrypoint("extract_url_content")
    async def extract_url_content(job: Job) -> None:
        """Extract content from a saved URL.

        This task fetches the URL, parses the HTML to markdown,
        and updates the Content record with the extracted content.

        Payload:
            content_id: int - ID of the Content record to process
        """
        # Import here to avoid circular imports
        from src.services.url_extractor import URLExtractor
        from src.storage.database import get_db

        payload = _decode_payload(job)
        content_id = payload.get("content_id")
        if not content_id:
            logger.error("extract_url_content: missing content_id in payload")
            return

        logger.info(f"Processing URL extraction for content_id={content_id}")

        try:
            with get_db() as db:
                extractor = URLExtractor(db)
                await extractor.extract_content(content_id)
                logger.info(f"URL extraction completed for content_id={content_id}")
        except Exception as e:
            logger.error(f"URL extraction failed for content_id={content_id}: {e}")
            raise

    @pgq.entrypoint("process_content")
    async def process_content(job: Job) -> None:
        """Generic content processing task.

        Routes to the appropriate processing based on task_type.

        Payload:
            content_id: int - ID of the Content record to process
            task_type: str - Type of processing (summarize, extract_entities, etc.)
        """
        payload = _decode_payload(job)
        content_id = payload.get("content_id")
        task_type = payload.get("task_type", "summarize")

        if not content_id:
            logger.error("process_content: missing content_id in payload")
            return

        logger.info(f"Processing content_id={content_id} with task_type={task_type}")

        try:
            if task_type == "summarize":
                from src.processors.summarizer import ContentSummarizer

                summarizer = ContentSummarizer()
                summarizer.summarize_content(content_id)
            else:
                logger.warning(f"Unknown task_type: {task_type}")

            logger.info(f"Content processing completed for content_id={content_id}")
        except Exception as e:
            logger.error(f"Content processing failed for content_id={content_id}: {e}")
            raise

    @pgq.entrypoint("scan_newsletters")
    async def scan_newsletters(job: Job) -> None:
        """Scan email for new newsletters.

        This task is typically triggered by pg_cron on a schedule.
        It fetches unread newsletter emails and enqueues them for processing.

        Payload: (optional)
            labels: list[str] - Gmail labels to scan (default: ["newsletters"])
        """
        payload = _decode_payload(job)
        labels = payload.get("labels", ["newsletters"])
        logger.info(f"Scanning newsletters with labels: {labels}")

        try:
            # Import Gmail ingestion service
            from src.ingestion.gmail import GmailContentIngestionService

            service = GmailContentIngestionService()
            # Ingest content from newsletters label
            count = service.ingest_content(query="label:newsletters-ai")

            logger.info(f"Newsletter scan completed: {count} new items")

        except Exception as e:
            logger.error(f"Newsletter scan failed: {e}")
            raise

    @pgq.entrypoint("summarize_content")
    async def summarize_content(job: Job) -> None:
        """Summarize a content item.

        This task is typically enqueued by enqueue_summarization_job()
        and processed by the worker pool.

        Payload:
            content_id: int - ID of the Content record to summarize
        """
        # Import here to avoid circular imports
        from anthropic import RateLimitError

        from src.processors.summarizer import ContentSummarizer
        from src.queue.setup import reconcile_batch_job_status, update_job_progress

        payload = _decode_payload(job)
        content_id = payload.get("content_id")
        if not content_id:
            logger.error("summarize_content: missing content_id in payload")
            return

        logger.info(f"Starting summarization for content_id={content_id}")

        # Update progress at start
        await update_job_progress(job.id, 10, "Starting summarization")

        # Retry loop with exponential backoff for rate limits
        last_error: Exception | None = None

        for attempt, delay in enumerate([*RATE_LIMIT_BACKOFF_DELAYS, None], start=1):
            try:
                summarizer = ContentSummarizer()
                success = summarizer.summarize_content(content_id)

                if success:
                    await update_job_progress(job.id, 100, "Completed")
                    logger.info(f"Summarization completed for content_id={content_id}")
                    # Check if this completes a batch job
                    await reconcile_batch_job_status(content_id)
                    return
                else:
                    # Summarization failed but not due to exception
                    raise RuntimeError(
                        f"Summarization returned failure for content_id={content_id}"
                    )

            except RateLimitError as e:
                last_error = e
                if delay is not None:
                    logger.warning(
                        f"Rate limited on attempt {attempt} for content_id={content_id}, "
                        f"retrying in {delay}s"
                    )
                    await update_job_progress(
                        job.id, 10, f"Rate limited, retrying in {delay}s (attempt {attempt})"
                    )
                    await asyncio.sleep(delay)
                else:
                    # All retries exhausted
                    logger.error(
                        f"Rate limit exceeded after {len(RATE_LIMIT_BACKOFF_DELAYS)} retries "
                        f"for content_id={content_id}"
                    )
                    raise

            except Exception as e:
                # Non-rate-limit errors should not be retried
                logger.error(f"Summarization failed for content_id={content_id}: {e}")
                raise

        # Should not reach here, but handle gracefully
        if last_error:
            raise last_error

    @pgq.entrypoint("ingest_content")
    async def ingest_content(job: Job) -> None:
        """Ingest content from a source.

        This task handles content ingestion from various sources
        (Gmail, RSS, YouTube, Podcast, Substack) via the job queue.
        Delegates to the shared orchestrator layer for service wiring.

        Payload:
            source: str - Content source type (gmail, rss, youtube, podcast, substack)
            max_results: int - Maximum items to fetch
            days_back: int - Days back to search
            force_reprocess: bool - Force reprocess existing content
        """
        from datetime import UTC, datetime, timedelta

        from src.ingestion.orchestrator import (
            ingest_gmail,
            ingest_podcast,
            ingest_rss,
            ingest_substack,
            ingest_youtube,
        )
        from src.queue.setup import update_job_progress

        payload = _decode_payload(job)
        source = payload.get("source", "gmail")
        max_results = payload.get("max_results", 50)
        days_back = payload.get("days_back", 7)
        force_reprocess = payload.get("force_reprocess", False)

        logger.info(f"Starting ingestion for source={source}")
        await update_job_progress(job.id, 10, f"Starting {source} ingestion")

        after_date = datetime.now(UTC) - timedelta(days=days_back)

        # Map source names to orchestrator functions with appropriate kwargs
        source_map: dict[str, tuple] = {
            "gmail": (ingest_gmail, {"max_results": max_results}),
            "rss": (ingest_rss, {"max_entries_per_feed": max_results}),
            "youtube": (ingest_youtube, {"max_videos": max_results}),
            "podcast": (ingest_podcast, {"max_entries_per_feed": max_results}),
            "substack": (ingest_substack, {"max_entries_per_source": max_results}),
        }

        if source not in source_map:
            logger.error(f"Unsupported source for ingestion: {source}")
            await update_job_progress(job.id, 0, f"Error: Unsupported source '{source}'")
            raise ValueError(f"Unsupported source: {source}")

        try:
            ingest_func, kwargs = source_map[source]
            count = await asyncio.to_thread(
                lambda: ingest_func(
                    after_date=after_date,
                    force_reprocess=force_reprocess,
                    **kwargs,
                )
            )

            await update_job_progress(job.id, 100, f"Ingested {count} items from {source}")
            logger.info(f"Ingestion completed for source={source}: {count} items")

        except Exception as e:
            logger.error(f"Ingestion failed for source={source}: {e}")
            raise

    logger.info("Content tasks registered with PGQueuer")
