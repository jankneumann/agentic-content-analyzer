"""Content processing tasks for the queue worker.

These tasks handle background operations like URL content extraction,
summarization, and other content processing pipelines.
"""

from typing import TYPE_CHECKING

from pgqueuer import PgQueuer
from pgqueuer.models import Job

from src.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


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

        content_id = job.payload.get("content_id")
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
        content_id = job.payload.get("content_id")
        task_type = job.payload.get("task_type", "summarize")

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

        labels = job.payload.get("labels", ["newsletters"])
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

    logger.info("Content tasks registered with PGQueuer")
