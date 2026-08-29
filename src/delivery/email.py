"""Email delivery for digests."""

import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.contracts.operation_context import OperationStage
from src.ingestion.gmail import GmailClient
from src.models.digest import Digest
from src.utils.digest_formatter import DigestFormatter
from src.utils.logging import get_logger
from src.workflows.stage_observability import operation_stage

logger = get_logger(__name__)


class GmailDeliveryService:
    """Service for delivering digests via Gmail."""

    def __init__(self) -> None:
        """Initialize Gmail delivery service."""
        self.gmail_client = GmailClient()
        logger.info("Gmail delivery service initialized")

    def send_digest(
        self,
        digest: Digest,
        recipient_email: str,
        subject: str | None = None,
    ) -> bool:
        """
        Send digest via Gmail.

        Args:
            digest: Digest to send
            recipient_email: Email address to send to
            subject: Optional custom subject (defaults to digest title)

        Returns:
            True if successful, False otherwise
        """
        with operation_stage("delivery.gmail", OperationStage.DELIVER) as evidence:
            try:
                return self._send_digest(digest, recipient_email, subject)
            except Exception as error:
                evidence.fail(error, error_code="gmail_delivery_failed", retryable=True)
                logger.error("Failed to deliver digest", exc_info=True)
                return False

    def _send_digest(
        self,
        digest: Digest,
        recipient_email: str,
        subject: str | None,
    ) -> bool:
        formatter = DigestFormatter()
        html_content = formatter.to_html(digest)  # type: ignore[arg-type]
        message = MIMEMultipart("alternative")
        message["To"] = recipient_email
        message["From"] = "me"
        message["Subject"] = subject or digest.title or ""
        message.attach(MIMEText(html_content, "html"))
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        sent_message = (
            self.gmail_client.service.users()  # type: ignore[attr-defined]
            .messages()
            .send(userId="me", body={"raw": raw_message})
            .execute()
        )
        logger.info("Successfully delivered digest", extra={"message_id": sent_message["id"]})
        return True
