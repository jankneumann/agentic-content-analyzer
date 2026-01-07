"""Newsletter summarization processor."""

from src.agents.base import SummarizationAgent
from src.agents.claude import ClaudeAgent
from src.config import settings
from src.config.models import ModelConfig
from src.models.newsletter import Newsletter, ProcessingStatus
from src.models.summary import NewsletterSummary
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


class NewsletterSummarizer:
    """Service for summarizing newsletters."""

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

    def summarize_newsletter(self, newsletter_id: int) -> bool:
        """
        Summarize a single newsletter.

        Args:
            newsletter_id: Newsletter ID to summarize

        Returns:
            True if successful, False otherwise
        """
        with get_db() as db:
            # Get newsletter
            newsletter = db.query(Newsletter).filter(Newsletter.id == newsletter_id).first()

            if not newsletter:
                logger.error(f"Newsletter {newsletter_id} not found")
                return False

            # Check if already summarized
            existing = (
                db.query(NewsletterSummary)
                .filter(NewsletterSummary.newsletter_id == newsletter_id)
                .first()
            )

            if existing:
                logger.info(f"Newsletter {newsletter_id} already summarized")
                return True

            # Update status
            newsletter.status = ProcessingStatus.PROCESSING
            db.commit()

            try:
                # Summarize
                logger.info(f"Summarizing: {newsletter.title}")
                response = self.agent.summarize_newsletter(newsletter)

                if not response.success:
                    newsletter.status = ProcessingStatus.FAILED
                    newsletter.error_message = response.error
                    db.commit()
                    logger.error(f"Summarization failed: {response.error}")
                    return False

                # Store summary
                summary_data = response.data
                summary = NewsletterSummary(
                    newsletter_id=newsletter_id,
                    executive_summary=summary_data.executive_summary,
                    key_themes=summary_data.key_themes,
                    strategic_insights=summary_data.strategic_insights,
                    technical_details=summary_data.technical_details,
                    actionable_items=summary_data.actionable_items,
                    notable_quotes=summary_data.notable_quotes,
                    relevant_links=summary_data.relevant_links,
                    relevance_scores=summary_data.relevance_scores,
                    agent_framework=summary_data.agent_framework,
                    model_used=summary_data.model_used,
                    model_version=summary_data.model_version,
                    token_usage=summary_data.token_usage,
                    processing_time_seconds=summary_data.processing_time_seconds,
                )

                db.add(summary)
                newsletter.status = ProcessingStatus.COMPLETED
                db.commit()

                logger.info(
                    f"Successfully summarized newsletter {newsletter_id}: {newsletter.title}"
                )
                return True

            except Exception as e:
                db.rollback()
                newsletter.status = ProcessingStatus.FAILED
                newsletter.error_message = str(e)
                db.commit()
                logger.error(f"Error summarizing newsletter {newsletter_id}: {e}")
                return False

    def summarize_newsletters(self, newsletter_ids: list[int]) -> dict[str, int | list[int]]:
        """
        Summarize multiple newsletters with detailed tracking.

        Args:
            newsletter_ids: List of newsletter IDs to summarize

        Returns:
            Dictionary with:
                - 'created_count': Number of successfully created summaries
                - 'failed_ids': List of newsletter IDs that failed
                - 'skipped_count': Number of newsletters already summarized (skipped)
        """
        created_count = 0
        failed_ids = []
        skipped_count = 0

        logger.info(f"Starting batch summarization for {len(newsletter_ids)} newsletters")

        for i, newsletter_id in enumerate(newsletter_ids, 1):
            logger.info(f"Processing newsletter {i}/{len(newsletter_ids)} (ID: {newsletter_id})...")

            try:
                # Check if already summarized (summarize_newsletter does this, but we track it)
                with get_db() as db:
                    existing = (
                        db.query(NewsletterSummary)
                        .filter(NewsletterSummary.newsletter_id == newsletter_id)
                        .first()
                    )

                if existing:
                    skipped_count += 1
                    logger.info(f"Newsletter {newsletter_id} already has summary, skipping")
                    continue

                # Create summary
                success = self.summarize_newsletter(newsletter_id)

                if success:
                    created_count += 1
                    logger.info(f"✓ Successfully created summary for newsletter {newsletter_id}")
                else:
                    failed_ids.append(newsletter_id)
                    logger.error(f"✗ Failed to create summary for newsletter {newsletter_id}")

            except Exception as e:
                failed_ids.append(newsletter_id)
                logger.error(
                    f"✗ Exception creating summary for newsletter {newsletter_id}: {e}",
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

    def summarize_pending_newsletters(self, limit: int | None = None) -> int:
        """
        Summarize all pending newsletters.

        Args:
            limit: Maximum number to process (None = all)

        Returns:
            Number of newsletters successfully summarized
        """
        # Query for IDs only to avoid nested session issues
        with get_db() as db:
            query = db.query(Newsletter.id).filter(Newsletter.status == ProcessingStatus.PENDING)

            if limit:
                query = query.limit(limit)

            pending_ids = [row[0] for row in query.all()]
            logger.info(f"Found {len(pending_ids)} pending newsletters to summarize")

        # Use new batch summarization method
        result = self.summarize_newsletters(pending_ids)

        logger.info(
            f"Successfully summarized {result['created_count']}/{len(pending_ids)} newsletters"
        )
        return result["created_count"]

    def summarize_with_feedback(self, newsletter_id: int, feedback_context: str) -> dict | None:
        """
        Regenerate a summary with user feedback (preview mode - doesn't save to DB).

        Args:
            newsletter_id: Newsletter ID to summarize
            feedback_context: Formatted feedback and context selections from user

        Returns:
            Dictionary with summary fields if successful, None otherwise
        """
        with get_db() as db:
            # Get newsletter
            newsletter = db.query(Newsletter).filter(Newsletter.id == newsletter_id).first()

            if not newsletter:
                logger.error(f"Newsletter {newsletter_id} not found")
                return None

            try:
                # Summarize with feedback
                logger.info(f"Regenerating with feedback: {newsletter.title}")
                response = self.agent.summarize_newsletter_with_feedback(
                    newsletter, feedback_context
                )

                if not response.success:
                    logger.error(f"Regeneration failed: {response.error}")
                    return None

                # Return summary data as dict (without saving to DB)
                summary_data = response.data
                return {
                    "newsletter_id": newsletter_id,
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
                logger.error(f"Error regenerating newsletter {newsletter_id}: {e}")
                return None
