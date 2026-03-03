"""Content summarization processor.

This module provides summarization for content using the unified Content model.
Includes OpenTelemetry instrumentation for per-item progress tracking.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.agents.base import SummarizationAgent
from src.agents.claude import ClaudeAgent
from src.config import settings
from src.config.models import ModelConfig
from src.models.content import Content, ContentStatus
from src.models.summary import Summary
from src.storage.database import get_db
from src.utils.logging import get_logger
from src.utils.summary_markdown import (
    extract_summary_theme_tags,
    generate_summary_markdown,
)

if TYPE_CHECKING:
    from opentelemetry.trace import Span

    from src.models.query import ContentQuery

logger = get_logger(__name__)


def _get_tracer():
    """Get OTel tracer if available, otherwise return None."""
    try:
        from opentelemetry import trace

        return trace.get_tracer("newsletter-aggregator")
    except ImportError:
        return None


@contextmanager
def _summarization_span(content_id: int, title: str) -> Generator[Span | None, None, None]:
    """Create an OTel span for content summarization.

    Creates a span named 'summarization.content' with attributes:
    - content_id: ID of the content being summarized
    - title: Title of the content
    - status: success|failure on completion
    - error_message: Present if failed

    Args:
        content_id: Content ID being summarized
        title: Content title for logging

    Yields:
        The span if OTel is available, None otherwise
    """
    tracer = _get_tracer()
    if tracer is None:
        yield None
        return

    with tracer.start_as_current_span("summarization.content") as span:
        span.set_attribute("content_id", content_id)
        span.set_attribute("title", title[:200])  # Truncate long titles
        try:
            yield span
            span.set_attribute("status", "success")
        except Exception as e:
            span.set_attribute("status", "failure")
            span.set_attribute("error_message", str(e))
            span.record_exception(e)
            raise


class ContentSummarizer:
    """Service for summarizing content.

    Works exclusively with the unified Content model.
    """

    def __init__(
        self,
        agent: SummarizationAgent | None = None,
        model_config: ModelConfig | None = None,
    ) -> None:
        """
        Initialize summarizer.

        Args:
            agent: Summarization agent to use (defaults to ClaudeAgent with ModelConfig)
            model_config: Model configuration (defaults to settings.get_model_config())
        """
        if agent is None:
            # Get model config from settings if not provided
            if model_config is None:
                model_config = settings.get_model_config()

            # Create default ClaudeAgent with model config
            agent = ClaudeAgent(model_config=model_config)

        self.agent = agent
        logger.info(f"Initialized summarizer with {agent.__class__.__name__}")

    def summarize_content(self, content_id: int) -> bool:
        """
        Summarize content from the unified Content model.

        Uses Content's markdown_content for improved summarization quality.
        Creates an OTel span for per-item progress tracking.

        Args:
            content_id: Content ID to summarize

        Returns:
            True if successful, False otherwise
        """
        with get_db() as db:
            # Get content
            content = db.query(Content).filter(Content.id == content_id).first()

            if not content:
                logger.error(f"Content {content_id} not found")
                return False

            # Check if already summarized using content_id FK
            existing = db.query(Summary).filter(Summary.content_id == content_id).first()

            if existing:
                logger.info(f"Content {content_id} already summarized")
                return True

            # Update status
            content.status = ContentStatus.PROCESSING
            db.commit()

            # Wrap summarization in OTel span for per-item tracking
            with _summarization_span(content_id, content.title or ""):
                try:
                    # Summarize using agent
                    logger.info(f"Summarizing content: {content.title}")
                    response = self.agent.summarize_content(content)

                    if not response.success:
                        content.status = ContentStatus.FAILED
                        content.error_message = response.error
                        db.commit()
                        logger.error(f"Summarization failed: {response.error}")
                        return False

                    # Store summary
                    summary_data = response.data

                    # Generate markdown content and extract theme tags
                    summary_dict = {
                        "executive_summary": summary_data.executive_summary,
                        "key_themes": summary_data.key_themes,
                        "strategic_insights": summary_data.strategic_insights,
                        "technical_details": summary_data.technical_details,
                        "actionable_items": summary_data.actionable_items,
                        "notable_quotes": summary_data.notable_quotes,
                        "relevant_links": summary_data.relevant_links,
                        "relevance_scores": summary_data.relevance_scores,
                    }
                    markdown_content = generate_summary_markdown(summary_dict)
                    theme_tags = extract_summary_theme_tags(summary_dict)

                    # Create summary record with content_id FK
                    summary = Summary(
                        content_id=content_id,
                        executive_summary=summary_data.executive_summary,
                        key_themes=summary_data.key_themes,
                        strategic_insights=summary_data.strategic_insights,
                        technical_details=summary_data.technical_details,
                        actionable_items=summary_data.actionable_items,
                        notable_quotes=summary_data.notable_quotes,
                        relevant_links=summary_data.relevant_links,
                        relevance_scores=summary_data.relevance_scores,
                        markdown_content=markdown_content,
                        theme_tags=theme_tags,
                        agent_framework=summary_data.agent_framework,
                        model_used=summary_data.model_used,
                        model_version=summary_data.model_version,
                        token_usage=summary_data.token_usage,
                        processing_time_seconds=summary_data.processing_time_seconds,
                    )

                    db.add(summary)
                    content.status = ContentStatus.COMPLETED
                    content.processed_at = datetime.now(UTC)
                    db.commit()

                    logger.info(f"Successfully summarized content {content_id}: {content.title}")
                    return True

                except Exception as e:
                    db.rollback()
                    # Check if this is a unique constraint violation (race condition)
                    # This happens when another process already created the summary
                    error_str = str(e)
                    if "UniqueViolation" in error_str or "unique constraint" in error_str.lower():
                        logger.info(
                            f"Content {content_id} was summarized by another process (race condition)"
                        )
                        # Update content status since summary exists
                        content.status = ContentStatus.COMPLETED
                        content.processed_at = datetime.now(UTC)
                        db.commit()
                        return True

                    content.status = ContentStatus.FAILED
                    content.error_message = str(e)
                    db.commit()
                    logger.error(f"Error summarizing content {content_id}: {e}")
                    return False

    def summarize_contents(self, content_ids: list[int]) -> dict[str, int | list[int]]:
        """
        Summarize multiple content records with detailed tracking.

        Args:
            content_ids: List of content IDs to summarize

        Returns:
            Dictionary with:
                - 'created_count': Number of successfully created summaries
                - 'failed_ids': List of content IDs that failed
                - 'skipped_count': Number of contents already summarized (skipped)
        """
        created_count = 0
        failed_ids = []
        skipped_count = 0

        logger.info(f"Starting batch summarization for {len(content_ids)} content records")

        for i, content_id in enumerate(content_ids, 1):
            logger.info(f"Processing content {i}/{len(content_ids)} (ID: {content_id})...")

            try:
                # Check if already summarized (by status or existing summary)
                with get_db() as db:
                    content = db.query(Content).filter(Content.id == content_id).first()
                    if content and content.status == ContentStatus.COMPLETED:
                        skipped_count += 1
                        logger.info(f"Content {content_id} already completed, skipping")
                        continue

                    # Also check if summary exists (in case status wasn't updated)
                    existing_summary = (
                        db.query(Summary).filter(Summary.content_id == content_id).first()
                    )
                    if existing_summary:
                        skipped_count += 1
                        logger.info(f"Content {content_id} already has summary, skipping")
                        # Update content status if not already completed
                        if content and content.status != ContentStatus.COMPLETED:
                            content.status = ContentStatus.COMPLETED
                            content.processed_at = datetime.now(UTC)
                            db.commit()
                        continue

                # Create summary
                success = self.summarize_content(content_id)

                if success:
                    created_count += 1
                    logger.info(f"✓ Successfully created summary for content {content_id}")
                else:
                    failed_ids.append(content_id)
                    logger.error(f"✗ Failed to create summary for content {content_id}")

            except Exception as e:
                failed_ids.append(content_id)
                logger.error(
                    f"✗ Exception creating summary for content {content_id}: {e}",
                    exc_info=True,
                )

        # Log final results
        logger.info(
            f"Batch summarization complete: "
            f"{created_count} created, {skipped_count} skipped, {len(failed_ids)} failed"
        )

        return {
            "created_count": created_count,
            "failed_ids": failed_ids,
            "skipped_count": skipped_count,
        }

    def summarize_pending_contents(
        self,
        limit: int | None = None,
        query: ContentQuery | None = None,
    ) -> int:
        """
        Summarize all pending content records.

        Args:
            limit: Maximum number to process (None = all)
            query: Optional ContentQuery for filtered selection

        Returns:
            Number of content records successfully summarized
        """
        if query:
            from src.services.content_query import ContentQueryService

            # Merge default status constraint if not specified
            if not query.statuses:
                query = query.model_copy(
                    update={"statuses": [ContentStatus.PENDING, ContentStatus.PARSED]}
                )
            svc = ContentQueryService()
            pending_ids = svc.resolve(query)
        else:
            # Original behavior — unchanged
            with get_db() as db:
                q = db.query(Content.id).filter(
                    Content.status.in_([ContentStatus.PENDING, ContentStatus.PARSED])
                )

                if limit:
                    q = q.limit(limit)

                pending_ids = [row[0] for row in q.all()]

        logger.info(f"Found {len(pending_ids)} pending content records to summarize")

        # Use batch summarization method
        result = self.summarize_contents(pending_ids)

        created_count = result["created_count"]
        logger.info(f"Successfully summarized {created_count}/{len(pending_ids)} content records")
        # created_count is always int from summarize_contents
        return int(created_count)  # type: ignore[arg-type]

    async def enqueue_pending_contents(
        self,
        limit: int | None = None,
        query: ContentQuery | None = None,
    ) -> dict[str, int | list[int]]:
        """
        Enqueue pending content for summarization via job queue.

        Instead of processing synchronously, this method enqueues jobs
        to the pgqueuer_jobs table for worker pool processing.

        Args:
            limit: Maximum number to enqueue (None = all)
            query: Optional ContentQuery for filtered selection

        Returns:
            Dictionary with:
                - 'enqueued_count': Number of jobs successfully enqueued
                - 'skipped_count': Number already in queue (idempotency)
                - 'job_ids': List of new job IDs created
        """
        from src.queue.setup import enqueue_summarization_job

        if query:
            from src.services.content_query import ContentQueryService

            # Merge default status constraint if not specified
            if not query.statuses:
                query = query.model_copy(
                    update={"statuses": [ContentStatus.PENDING, ContentStatus.PARSED]}
                )
            svc = ContentQueryService()
            pending_ids = svc.resolve(query)
        else:
            # Original behavior — unchanged
            with get_db() as db:
                q = db.query(Content.id).filter(
                    Content.status.in_([ContentStatus.PENDING, ContentStatus.PARSED])
                )

                if limit:
                    q = q.limit(limit)

                pending_ids = [row[0] for row in q.all()]

        logger.info(f"Found {len(pending_ids)} pending content records to enqueue")

        enqueued_count = 0
        skipped_count = 0
        job_ids: list[int] = []

        for content_id in pending_ids:
            job_id = await enqueue_summarization_job(content_id)
            if job_id is not None:
                enqueued_count += 1
                job_ids.append(job_id)
            else:
                skipped_count += 1

        logger.info(
            f"Enqueued {enqueued_count} summarization jobs "
            f"({skipped_count} skipped - already in queue)"
        )

        return {
            "enqueued_count": enqueued_count,
            "skipped_count": skipped_count,
            "job_ids": job_ids,
        }

    def summarize_content_with_feedback(
        self, content_id: int, feedback_context: str | None
    ) -> dict | None:
        """
        Regenerate a summary with user feedback (preview mode - doesn't save to DB).

        Args:
            content_id: Content ID to summarize
            feedback_context: Formatted feedback and context selections from user

        Returns:
            Dictionary with summary fields if successful, None otherwise
        """
        with get_db() as db:
            content = db.query(Content).filter(Content.id == content_id).first()

            if not content:
                logger.error(f"Content {content_id} not found")
                return None

            try:
                logger.info(f"Regenerating content with feedback: {content.title}")
                response = self.agent.summarize_content_with_feedback(content, feedback_context)

                if not response.success:
                    logger.error(f"Regeneration failed: {response.error}")
                    return None

                # Return summary data as dict (without saving to DB)
                summary_data = response.data
                return {
                    "content_id": content_id,
                    "executive_summary": summary_data.executive_summary,
                    "key_themes": summary_data.key_themes,
                    "strategic_insights": summary_data.strategic_insights,
                    "technical_details": summary_data.technical_details,
                    "actionable_items": summary_data.actionable_items,
                    "notable_quotes": summary_data.notable_quotes,
                    "relevant_links": summary_data.relevant_links,
                    "relevance_scores": summary_data.relevance_scores,
                    "agent_framework": summary_data.agent_framework,
                    "model_used": summary_data.model_used,
                    "model_version": summary_data.model_version,
                    "token_usage": summary_data.token_usage,
                    "processing_time_seconds": summary_data.processing_time_seconds,
                }

            except Exception as e:
                logger.error(f"Error regenerating content {content_id}: {e}")
                return None


# Backwards compatibility alias
NewsletterSummarizer = ContentSummarizer
