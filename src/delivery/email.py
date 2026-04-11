"""Email delivery for digests."""

import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.ingestion.gmail import GmailClient
from src.models.digest import Digest
from src.utils.digest_formatter import DigestFormatter
from src.utils.logging import get_logger

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
        try:
            # Format digest as HTML
            formatter = DigestFormatter()
            html_content = formatter.to_html(digest)  # type: ignore[arg-type]

            # Create email message
            message = MIMEMultipart("alternative")
            message["To"] = recipient_email
            message["From"] = "me"  # Gmail API uses 'me' for authenticated user
            message["Subject"] = subject or digest.title or ""

            # Attach HTML content
            html_part = MIMEText(html_content, "html")
            message.attach(html_part)

            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

            # Send via Gmail API
            sent_message = (
                self.gmail_client.service.users()  # type: ignore[attr-defined]
                .messages()
                .send(userId="me", body={"raw": raw_message})
                .execute()
            )

            logger.info(
                f"Successfully sent digest #{digest.id} to {recipient_email}. "
                f"Message ID: {sent_message['id']}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send digest #{digest.id}: {e}", exc_info=True)
            return False
