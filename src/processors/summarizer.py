"""Newsletter summarization processor."""

from typing import Optional

from src.agents.base import SummarizationAgent
from src.agents.claude import ClaudeAgent
from src.config import settings
from src.models.newsletter import Newsletter, ProcessingStatus
from src.models.summary import NewsletterSummary
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)


class NewsletterSummarizer:
    """Service for summarizing newsletters."""

    def __init__(self, agent: Optional[SummarizationAgent] = None) -> None:
        """
        Initialize summarizer.

        Args:
            agent: Summarization agent to use (defaults to ClaudeAgent)
        """
        if agent is None:
            agent = ClaudeAgent(api_key=settings.anthropic_api_key)
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
                    relevance_scores=summary_data.relevance_scores,
                    agent_framework=summary_data.agent_framework,
                    model_used=summary_data.model_used,
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

    def summarize_pending_newsletters(self, limit: Optional[int] = None) -> int:
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

        count = 0
        for newsletter_id in pending_ids:
            if self.summarize_newsletter(newsletter_id):
                count += 1

        logger.info(f"Successfully summarized {count}/{len(pending_ids)} newsletters")
        return count
