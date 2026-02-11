"""Gmail newsletter ingestion.

Provides Content model ingestion for Gmail newsletters using the unified
content model. Creates Content records with markdown as the primary format.
"""

import base64
import os.path
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel

from src.config import settings
from src.models.content import Content, ContentSource, ContentStatus
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.html_parser import extract_links, html_to_text
from src.utils.logging import get_logger
from src.utils.substack import (
    extract_substack_canonical_url,
    find_existing_substack_content,
    normalize_substack_url,
)

logger = get_logger(__name__)

# Gmail API scopes
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


class ContentData(BaseModel):
    """Data model for Gmail content ingestion (unified Content model)."""

    source_type: ContentSource
    source_id: str
    source_url: str | None = None

    title: str
    author: str | None = None
    publication: str | None = None
    published_date: datetime | None = None

    markdown_content: str
    links_json: list[str] | None = None
    metadata_json: dict | None = None

    raw_content: str | None = None  # Original HTML
    raw_format: str = "html"

    parser_used: str = "markitdown"
    content_hash: str


def html_to_markdown(html: str) -> str:
    """Convert HTML to markdown using Trafilatura-based converter.

    Uses a two-tier extraction approach:
    - Primary: Trafilatura for fast, high-quality extraction (~50ms)
    - Fallback: MarkItDown if Trafilatura is unavailable

    Args:
        html: HTML content to convert

    Returns:
        Markdown representation of the HTML
    """
    if not html:
        return ""

    try:
        from src.parsers.html_markdown import convert_html_to_markdown

        result = convert_html_to_markdown(html=html)
        if result:
            return result

        # If converter returned empty, fall back to text
        logger.debug("HTML-to-markdown converter returned empty, using text fallback")
        return html_to_text(html)

    except ImportError:
        # Trafilatura not installed, use legacy MarkItDown approach
        logger.debug("Trafilatura not available, using MarkItDown fallback")
        return _html_to_markdown_markitdown(html)
    except Exception as e:
        logger.warning(f"HTML-to-markdown conversion failed, falling back to text: {e}")
        return html_to_text(html)


def _html_to_markdown_markitdown(html: str) -> str:
    """Legacy MarkItDown-based HTML to markdown conversion.

    Used as fallback when Trafilatura is not available.

    Args:
        html: HTML content to convert

    Returns:
        Markdown representation of the HTML
    """
    try:
        from src.parsers.markitdown_parser import MarkItDownParser

        parser = MarkItDownParser()

        # MarkItDown can parse HTML directly, but we need to write to a temp file
        # because the API expects a file path for HTML
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as f:
            f.write(html)
            temp_path = f.name

        try:
            import asyncio

            # Run the async parse method
            result = asyncio.get_event_loop().run_until_complete(
                parser.parse(Path(temp_path), format_hint="html")
            )
            return result.markdown_content or ""
        finally:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)

    except Exception as e:
        logger.warning(f"MarkItDown conversion failed, falling back to text: {e}")
        return html_to_text(html)


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

    def _extract_body(self, payload: dict[str, Any]) -> tuple[str | None, str | None]:
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

    def fetch_content(
        self,
        query: str = "label:newsletters-ai",
        max_results: int = 10,
        after_date: datetime | None = None,
    ) -> list[ContentData]:
        """
        Fetch newsletters from Gmail as ContentData (unified Content model).

        Args:
            query: Gmail search query (default: emails with 'newsletters' label)
            max_results: Maximum number of emails to fetch
            after_date: Only fetch emails after this date

        Returns:
            List of ContentData objects ready for Content table
        """
        try:
            # Build query with date filter if provided
            full_query = query
            if after_date:
                date_str = after_date.strftime("%Y/%m/%d")
                full_query = f"{query} after:{date_str}"

            logger.info(f"Fetching content with query: {full_query}")

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
            contents = []
            for msg in messages:
                try:
                    content_data = self._fetch_and_parse_content(msg["id"])
                    if content_data:
                        contents.append(content_data)
                except Exception as e:
                    logger.error(f"Error parsing message {msg['id']}: {e}")
                    continue

            logger.info(f"Successfully parsed {len(contents)} content items")
            return contents

        except HttpError as error:
            logger.error(f"Gmail API error: {error}")
            raise

    def _fetch_and_parse_content(self, message_id: str) -> ContentData | None:
        """
        Fetch and parse a single Gmail message as ContentData.

        Args:
            message_id: Gmail message ID

        Returns:
            ContentData object or None if parsing fails
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

            # Convert HTML to markdown (primary content format)
            # Track which parser was used for metadata
            markdown_content = ""
            parser_used = "trafilatura"

            if html_body:
                try:
                    from src.parsers.html_markdown import convert_html_to_markdown

                    markdown_content = convert_html_to_markdown(html=html_body)
                    if markdown_content:
                        logger.debug(
                            f"Trafilatura extraction successful for {subject}: "
                            f"{len(markdown_content)} chars"
                        )
                    else:
                        # Trafilatura returned empty, fall back to text
                        markdown_content = html_to_text(html_body)
                        parser_used = "text_fallback"
                except ImportError:
                    # Trafilatura not installed, use legacy MarkItDown
                    markdown_content = html_to_markdown(html_body)
                    parser_used = "markitdown"
            elif text_body:
                # If no HTML, use plain text as markdown
                markdown_content = text_body
                parser_used = "plaintext"

            if not markdown_content:
                logger.warning(f"No content found for message {message_id}")
                return None

            # Extract links from HTML
            links = extract_links(html_body) if html_body else []

            canonical_substack_url = extract_substack_canonical_url(links=links)

            # Generate content hash from normalized markdown
            content_hash = generate_markdown_hash(markdown_content)

            # Create content data
            content_data = ContentData(
                source_type=ContentSource.GMAIL,
                source_id=message_id_header,
                source_url=canonical_substack_url,
                title=subject,
                author=sender_email,
                publication=publication,
                published_date=published_date,
                markdown_content=markdown_content,
                links_json=links if links else None,
                metadata_json={
                    "gmail_message_id": message_id,
                    "has_html": bool(html_body),
                    "has_text": bool(text_body),
                    **({"substack_url": canonical_substack_url} if canonical_substack_url else {}),
                },
                raw_content=html_body,  # Preserve original HTML
                raw_format="html" if html_body else "text",
                parser_used=parser_used,
                content_hash=content_hash,
            )

            logger.debug(f"Parsed content: {subject} from {publication}")
            return content_data

        except Exception as e:
            logger.error(f"Error fetching message {message_id}: {e}")
            return None


class GmailContentIngestionService:
    """Service for ingesting Gmail newsletters into the unified Content model.

    This is the preferred ingestion service for new code. It creates Content
    records with markdown as the primary format, enabling the unified content
    pipeline for summarization and digest creation.
    """

    def __init__(self) -> None:
        """Initialize Gmail content ingestion service."""
        self.client = GmailClient()

    def ingest_content(
        self,
        query: str = "label:newsletters-ai",
        max_results: int = 10,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
    ) -> int:
        """
        Ingest newsletters from Gmail and store as Content records.

        Args:
            query: Gmail search query
            max_results: Maximum number to fetch
            after_date: Only fetch after this date
            force_reprocess: If True, reprocess existing content (updates data and resets status)

        Returns:
            Number of content items ingested
        """
        logger.info("Starting Gmail content ingestion (unified Content model)...")

        # Fetch content
        contents = self.client.fetch_content(
            query=query, max_results=max_results, after_date=after_date
        )

        if not contents:
            logger.info("No content found")
            return 0

        # Store in database
        count = 0
        with get_db() as db:
            # --- Bulk query optimization ---
            source_ids = [c.source_id for c in contents if c.source_id]
            content_hashes = [c.content_hash for c in contents if c.content_hash]

            # Bulk fetch existing content by source_id
            existing_by_source_id = {
                (c.source_type, c.source_id): c
                for c in db.query(Content)
                .filter(
                    Content.source_type == ContentSource.GMAIL,
                    Content.source_id.in_(source_ids),
                )
                .all()
            }

            # Bulk fetch existing content by content_hash
            existing_by_content_hash = {
                c.content_hash: c
                for c in db.query(Content).filter(Content.content_hash.in_(content_hashes)).all()
            }
            # --- End of optimization ---

            for content_data in contents:
                try:
                    # Check if already exists by source_type + source_id (unique composite)
                    existing = existing_by_source_id.get(
                        (content_data.source_type, content_data.source_id)
                    )

                    substack_duplicate = None
                    if not existing and content_data.source_url:
                        canonical_url = normalize_substack_url(content_data.source_url)
                        substack_duplicate = find_existing_substack_content(db, canonical_url)

                    # If not found by source_id, check by content_hash (cross-source duplicate)
                    content_duplicate = None
                    if not existing and not substack_duplicate and content_data.content_hash:
                        content_duplicate = existing_by_content_hash.get(content_data.content_hash)

                    if existing:
                        if force_reprocess:
                            # Update existing content and reset status for reprocessing
                            existing.title = content_data.title
                            existing.author = content_data.author
                            existing.publication = content_data.publication
                            existing.published_date = content_data.published_date
                            existing.markdown_content = content_data.markdown_content
                            existing.links_json = content_data.links_json
                            existing.metadata_json = content_data.metadata_json
                            existing.raw_content = content_data.raw_content
                            existing.raw_format = content_data.raw_format
                            existing.parser_used = content_data.parser_used
                            existing.content_hash = content_data.content_hash
                            existing.status = ContentStatus.PARSED
                            existing.error_message = None
                            count += 1
                            logger.info(f"Updated for reprocessing: {content_data.title}")
                            continue
                        else:
                            logger.debug(
                                f"Content already exists (use --force to reprocess): "
                                f"{content_data.source_id}"
                            )
                            continue

                    elif substack_duplicate:
                        logger.info(
                            f"Substack URL duplicate detected: '{content_data.title}' "
                            f"matches existing content ID {substack_duplicate.id}"
                        )

                        content = Content(
                            source_type=content_data.source_type,
                            source_id=content_data.source_id,
                            source_url=content_data.source_url,
                            title=content_data.title,
                            author=content_data.author,
                            publication=content_data.publication,
                            published_date=content_data.published_date,
                            markdown_content=content_data.markdown_content,
                            links_json=content_data.links_json,
                            metadata_json=content_data.metadata_json,
                            raw_content=content_data.raw_content,
                            raw_format=content_data.raw_format,
                            parser_used=content_data.parser_used,
                            content_hash=content_data.content_hash,
                            canonical_id=substack_duplicate.id,
                            status=ContentStatus.COMPLETED,
                        )
                        db.add(content)
                        count += 1
                        logger.info(
                            f"Linked Substack duplicate to canonical ID {substack_duplicate.id}"
                        )
                        continue

                    elif content_duplicate:
                        # Found duplicate by content hash from different source
                        logger.info(
                            f"Content duplicate detected: '{content_data.title}' "
                            f"matches existing content ID {content_duplicate.id} "
                            f"(source: {content_duplicate.source_type.value})"
                        )

                        # Create content but link to canonical version
                        content = Content(
                            source_type=content_data.source_type,
                            source_id=content_data.source_id,
                            source_url=content_data.source_url,
                            title=content_data.title,
                            author=content_data.author,
                            publication=content_data.publication,
                            published_date=content_data.published_date,
                            markdown_content=content_data.markdown_content,
                            links_json=content_data.links_json,
                            metadata_json=content_data.metadata_json,
                            raw_content=content_data.raw_content,
                            raw_format=content_data.raw_format,
                            parser_used=content_data.parser_used,
                            content_hash=content_data.content_hash,
                            canonical_id=content_duplicate.id,  # Link to canonical
                            status=ContentStatus.COMPLETED,  # Mark as completed (duplicate)
                        )
                        db.add(content)
                        count += 1
                        logger.info(f"Linked duplicate to canonical ID {content_duplicate.id}")
                        continue

                    # Create new content
                    content = Content(
                        source_type=content_data.source_type,
                        source_id=content_data.source_id,
                        source_url=content_data.source_url,
                        title=content_data.title,
                        author=content_data.author,
                        publication=content_data.publication,
                        published_date=content_data.published_date,
                        markdown_content=content_data.markdown_content,
                        links_json=content_data.links_json,
                        metadata_json=content_data.metadata_json,
                        raw_content=content_data.raw_content,
                        raw_format=content_data.raw_format,
                        parser_used=content_data.parser_used,
                        content_hash=content_data.content_hash,
                        status=ContentStatus.PARSED,  # Ready for summarization
                    )

                    db.add(content)
                    db.flush()  # Ensure content.id is assigned for indexing

                    # Index for search (fail-safe — never blocks ingestion)
                    from src.services.indexing import index_content

                    index_content(content, db)

                    count += 1
                    logger.info(f"Ingested: {content_data.title}")

                except Exception as e:
                    logger.error(f"Error storing content: {e}")
                    db.rollback()
                    continue

        logger.info(f"Successfully ingested {count} content items")
        return count
