"""Gmail newsletter ingestion."""

import base64
import os.path
from datetime import datetime
from typing import Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.config import settings
from src.models.newsletter import Newsletter, NewsletterData, NewsletterSource, ProcessingStatus
from src.storage.database import get_db
from src.utils.content_hash import generate_content_hash, should_skip_duplicate
from src.utils.html_parser import extract_links, html_to_text
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Gmail API scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


class GmailClient:
    """Gmail API client for fetching newsletters."""

    def __init__(self) -> None:
        """Initialize Gmail client."""
        self.service = None
        self._authenticate()

    def _authenticate(self) -> None:
        """Authenticate with Gmail API using OAuth2."""
        creds = None

        # Load existing credentials
        if os.path.exists(settings.gmail_token_file):
            creds = Credentials.from_authorized_user_file(settings.gmail_token_file, SCOPES)

        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing Gmail credentials...")
                creds.refresh(Request())
            else:
                if not os.path.exists(settings.gmail_credentials_file):
                    raise FileNotFoundError(
                        f"Gmail credentials file not found: {settings.gmail_credentials_file}"
                    )
                logger.info("Starting Gmail OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    settings.gmail_credentials_file, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save credentials
            with open(settings.gmail_token_file, "w") as token:
                token.write(creds.to_json())
            logger.info("Gmail credentials saved")

        self.service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail API client initialized")

    def fetch_newsletters(
        self,
        query: str = "label:newsletters-ai",
        max_results: int = 10,
        after_date: Optional[datetime] = None,
    ) -> list[NewsletterData]:
        """
        Fetch newsletters from Gmail.

        Args:
            query: Gmail search query (default: emails with 'newsletters' label)
            max_results: Maximum number of emails to fetch
            after_date: Only fetch emails after this date

        Returns:
            List of NewsletterData objects
        """
        try:
            # Build query with date filter if provided
            full_query = query
            if after_date:
                date_str = after_date.strftime("%Y/%m/%d")
                full_query = f"{query} after:{date_str}"

            logger.info(f"Fetching newsletters with query: {full_query}")

            # List messages
            results = (
                self.service.users()
                .messages()
                .list(userId="me", q=full_query, maxResults=max_results)
                .execute()
            )

            messages = results.get("messages", [])
            logger.info(f"Found {len(messages)} messages")

            if not messages:
                return []

            # Fetch and parse each message
            newsletters = []
            for msg in messages:
                try:
                    newsletter_data = self._fetch_and_parse_message(msg["id"])
                    if newsletter_data:
                        newsletters.append(newsletter_data)
                except Exception as e:
                    logger.error(f"Error parsing message {msg['id']}: {e}")
                    continue

            logger.info(f"Successfully parsed {len(newsletters)} newsletters")
            return newsletters

        except HttpError as error:
            logger.error(f"Gmail API error: {error}")
            raise

    def _fetch_and_parse_message(self, message_id: str) -> Optional[NewsletterData]:
        """
        Fetch and parse a single Gmail message.

        Args:
            message_id: Gmail message ID

        Returns:
            NewsletterData object or None if parsing fails
        """
        try:
            # Get full message
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            # Extract headers
            headers = {h["name"]: h["value"] for h in message["payload"]["headers"]}

            # Extract key metadata
            subject = headers.get("Subject", "No Subject")
            sender = headers.get("From", "Unknown")
            date_str = headers.get("Date", "")
            message_id_header = headers.get("Message-ID", message_id)

            # Parse date
            published_date = self._parse_date(date_str)

            # Extract sender name and email
            sender_email = sender
            publication = self._extract_publication_name(sender)

            # Extract body (HTML and text)
            html_body, text_body = self._extract_body(message["payload"])

            # Extract links from HTML
            links = extract_links(html_body) if html_body else []

            # Generate content hash for deduplication
            content_hash = generate_content_hash(text_body) if text_body else None

            # Create newsletter data
            newsletter_data = NewsletterData(
                source=NewsletterSource.GMAIL,
                source_id=message_id_header,
                title=subject,
                sender=sender_email,
                publication=publication,
                published_date=published_date,
                url=None,  # Gmail messages don't have a direct URL
                raw_html=html_body,
                raw_text=text_body,
                extracted_links=links,
                content_hash=content_hash,
                status=ProcessingStatus.PENDING,
            )

            logger.debug(f"Parsed newsletter: {subject} from {publication}")
            return newsletter_data

        except Exception as e:
            logger.error(f"Error fetching message {message_id}: {e}")
            return None

    def _extract_body(self, payload: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        """
        Extract HTML and plain text body from message payload.

        Args:
            payload: Gmail message payload

        Returns:
            Tuple of (html_body, text_body)
        """
        html_body = None
        text_body = None

        def extract_parts(part: dict[str, Any]) -> None:
            """Recursively extract parts from message."""
            nonlocal html_body, text_body

            mime_type = part.get("mimeType", "")
            body = part.get("body", {})
            data = body.get("data", "")

            # Decode base64 data if present
            if data:
                decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                if mime_type == "text/html":
                    html_body = decoded
                elif mime_type == "text/plain":
                    text_body = decoded

            # Recurse into multipart
            if "parts" in part:
                for subpart in part["parts"]:
                    extract_parts(subpart)

        extract_parts(payload)

        # If no text body but we have HTML, convert HTML to text
        if html_body and not text_body:
            text_body = html_to_text(html_body)

        return html_body, text_body

    def _parse_date(self, date_str: str) -> datetime:
        """
        Parse email date header.

        Args:
            date_str: RFC 2822 date string

        Returns:
            datetime object
        """
        from email.utils import parsedate_to_datetime

        try:
            return parsedate_to_datetime(date_str)
        except Exception as e:
            logger.warning(f"Error parsing date '{date_str}': {e}, using current time")
            return datetime.utcnow()

    def _extract_publication_name(self, sender: str) -> str:
        """
        Extract publication name from sender string.

        Args:
            sender: Email sender string (e.g., "Newsletter Name <email@example.com>")

        Returns:
            Publication name
        """
        # Try to extract name from "Name <email>" format
        if "<" in sender:
            name = sender.split("<")[0].strip()
            # Remove quotes if present
            name = name.strip('"').strip("'")
            if name:
                return name

        # Extract from email domain
        if "@" in sender:
            # Get email part
            email = sender.split("<")[-1].strip(">").strip()
            domain = email.split("@")[-1].split(".")[0]
            return domain.capitalize()

        return sender


class GmailIngestionService:
    """Service for ingesting newsletters from Gmail."""

    def __init__(self) -> None:
        """Initialize Gmail ingestion service."""
        self.client = GmailClient()

    def ingest_newsletters(
        self,
        query: str = "label:newsletters-ai",
        max_results: int = 10,
        after_date: Optional[datetime] = None,
        force_reprocess: bool = False,
    ) -> int:
        """
        Ingest newsletters from Gmail and store in database.

        Args:
            query: Gmail search query
            max_results: Maximum number to fetch
            after_date: Only fetch after this date
            force_reprocess: If True, reprocess existing newsletters (updates data and resets status)

        Returns:
            Number of newsletters ingested
        """
        logger.info("Starting Gmail newsletter ingestion...")

        # Fetch newsletters
        newsletters = self.client.fetch_newsletters(
            query=query, max_results=max_results, after_date=after_date
        )

        if not newsletters:
            logger.info("No newsletters found")
            return 0

        # Store in database
        count = 0
        with get_db() as db:
            for newsletter_data in newsletters:
                try:
                    # Check if already exists by source_id (exact match)
                    existing = (
                        db.query(Newsletter)
                        .filter(Newsletter.source_id == newsletter_data.source_id)
                        .first()
                    )

                    # If not found by source_id, check by content_hash (cross-source duplicate)
                    content_duplicate = None
                    if not existing and newsletter_data.content_hash:
                        content_duplicate = (
                            db.query(Newsletter)
                            .filter(Newsletter.content_hash == newsletter_data.content_hash)
                            .first()
                        )

                    if existing:
                        if force_reprocess:
                            # Update existing newsletter and reset status for reprocessing
                            existing.title = newsletter_data.title
                            existing.sender = newsletter_data.sender
                            existing.publication = newsletter_data.publication
                            existing.published_date = newsletter_data.published_date
                            existing.url = newsletter_data.url
                            existing.raw_html = newsletter_data.raw_html
                            existing.raw_text = newsletter_data.raw_text
                            existing.extracted_links = newsletter_data.extracted_links
                            existing.content_hash = newsletter_data.content_hash
                            existing.status = ProcessingStatus.PENDING
                            existing.error_message = None
                            count += 1
                            logger.info(f"Updated for reprocessing: {newsletter_data.title}")
                            continue
                        else:
                            logger.debug(
                                f"Newsletter already exists (use --force to reprocess): {newsletter_data.source_id}"
                            )
                            continue

                    elif content_duplicate:
                        # Found duplicate by content hash from different source
                        logger.info(
                            f"Content duplicate detected: '{newsletter_data.title}' "
                            f"matches existing newsletter ID {content_duplicate.id} "
                            f"(source: {content_duplicate.source.value})"
                        )

                        # Create newsletter but link to canonical version
                        newsletter = Newsletter(
                            source=newsletter_data.source,
                            source_id=newsletter_data.source_id,
                            title=newsletter_data.title,
                            sender=newsletter_data.sender,
                            publication=newsletter_data.publication,
                            published_date=newsletter_data.published_date,
                            url=newsletter_data.url,
                            raw_html=newsletter_data.raw_html,
                            raw_text=newsletter_data.raw_text,
                            extracted_links=newsletter_data.extracted_links,
                            content_hash=newsletter_data.content_hash,
                            canonical_newsletter_id=content_duplicate.id,  # Link to canonical
                            status=ProcessingStatus.COMPLETED,  # Mark as completed (duplicate)
                        )
                        db.add(newsletter)
                        count += 1
                        logger.info(f"Linked duplicate to canonical ID {content_duplicate.id}")
                        continue

                    # Create new newsletter
                    newsletter = Newsletter(
                        source=newsletter_data.source,
                        source_id=newsletter_data.source_id,
                        title=newsletter_data.title,
                        sender=newsletter_data.sender,
                        publication=newsletter_data.publication,
                        published_date=newsletter_data.published_date,
                        url=newsletter_data.url,
                        raw_html=newsletter_data.raw_html,
                        raw_text=newsletter_data.raw_text,
                        extracted_links=newsletter_data.extracted_links,
                        content_hash=newsletter_data.content_hash,
                        status=newsletter_data.status,
                    )

                    db.add(newsletter)
                    count += 1
                    logger.info(f"Ingested: {newsletter_data.title}")

                except Exception as e:
                    logger.error(f"Error storing newsletter: {e}")
                    db.rollback()
                    continue

        logger.info(f"Successfully ingested {count} newsletters")
        return count
