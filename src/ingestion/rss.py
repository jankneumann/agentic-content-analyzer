"""Generic RSS feed ingestion.

Provides both legacy Newsletter ingestion and new Content model ingestion.
The Content-based ingestion (RSSContentIngestionService) is the preferred
approach for new code as part of the unified content model refactor.
"""

import hashlib
from datetime import datetime
from urllib.parse import urlparse

import feedparser
import httpx

from src.config import settings
from src.ingestion.gmail import ContentData, html_to_markdown
from src.models.content import Content, ContentSource, ContentStatus
from src.models.newsletter import Newsletter, NewsletterData, NewsletterSource, ProcessingStatus
from src.storage.database import get_db
from src.utils.content_hash import generate_content_hash, generate_markdown_hash
from src.utils.html_parser import extract_links, html_to_text
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RSSClient:
    """Client for fetching newsletters from RSS feeds."""

    def __init__(self, timeout: int = 30) -> None:
        """
        Initialize RSS client.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
        logger.info("RSS client initialized")

    def close(self) -> None:
        """Close HTTP client."""
        self.client.close()
        logger.info("RSS client closed")

    def fetch_feed(
        self,
        feed_url: str,
        max_entries: int = 10,
        after_date: datetime | None = None,
    ) -> list[NewsletterData]:
        """
        Fetch newsletters from a single RSS feed.

        Args:
            feed_url: RSS feed URL
            max_entries: Maximum number of entries to fetch
            after_date: Only fetch entries published after this date

        Returns:
            List of NewsletterData objects
        """
        logger.info(f"Fetching RSS feed: {feed_url}")

        try:
            # Fetch feed with timeout
            response = self.client.get(feed_url)
            response.raise_for_status()

            # Parse RSS feed
            feed = feedparser.parse(response.content)

            if feed.bozo:
                logger.warning(
                    f"Feed parsing error for {feed_url}: {feed.get('bozo_exception', 'Unknown error')}"
                )

            # Extract publication name from feed metadata
            publication_name = self._extract_publication_name(feed, feed_url)
            logger.info(f"Found publication: {publication_name}")

            # Process entries
            newsletters = []
            for entry in feed.entries[:max_entries]:
                # Check date filter
                if after_date:
                    entry_date = self._parse_entry_date(entry)
                    if entry_date and entry_date < after_date:
                        logger.debug(f"Skipping old entry: {entry.get('title', 'Unknown')}")
                        continue

                # Convert entry to NewsletterData
                try:
                    newsletter = self._parse_entry(entry, publication_name, feed_url)
                    newsletters.append(newsletter)
                    logger.debug(f"Parsed entry: {newsletter.title}")
                except Exception as e:
                    logger.error(
                        f"Error parsing entry '{entry.get('title', 'Unknown')}': {e}",
                        exc_info=True,
                    )
                    continue

            logger.info(f"Fetched {len(newsletters)} newsletters from {feed_url}")
            return newsletters

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching feed {feed_url}: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching feed {feed_url}: {e}", exc_info=True)
            return []

    def fetch_multiple_feeds(
        self,
        feed_urls: list[str],
        max_entries_per_feed: int = 10,
        after_date: datetime | None = None,
    ) -> list[NewsletterData]:
        """
        Fetch newsletters from multiple RSS feeds.

        Args:
            feed_urls: List of RSS feed URLs
            max_entries_per_feed: Maximum entries to fetch per feed
            after_date: Only fetch entries published after this date

        Returns:
            Combined list of NewsletterData objects from all feeds
        """
        logger.info(f"Fetching {len(feed_urls)} RSS feeds")

        all_newsletters = []
        for feed_url in feed_urls:
            newsletters = self.fetch_feed(
                feed_url=feed_url,
                max_entries=max_entries_per_feed,
                after_date=after_date,
            )
            all_newsletters.extend(newsletters)

        logger.info(
            f"Fetched total of {len(all_newsletters)} newsletters from {len(feed_urls)} feeds"
        )
        return all_newsletters

    def fetch_content(
        self,
        feed_url: str,
        max_entries: int = 10,
        after_date: datetime | None = None,
    ) -> list[ContentData]:
        """
        Fetch content from an RSS feed as ContentData (unified Content model).

        Args:
            feed_url: RSS feed URL
            max_entries: Maximum number of entries to fetch
            after_date: Only fetch entries published after this date

        Returns:
            List of ContentData objects ready for Content table
        """
        logger.info(f"Fetching RSS content: {feed_url}")

        try:
            # Fetch feed with timeout
            response = self.client.get(feed_url)
            response.raise_for_status()

            # Parse RSS feed
            feed = feedparser.parse(response.content)

            if feed.bozo:
                logger.warning(
                    f"Feed parsing error for {feed_url}: {feed.get('bozo_exception', 'Unknown error')}"
                )

            # Extract publication name from feed metadata
            publication_name = self._extract_publication_name(feed, feed_url)
            logger.info(f"Found publication: {publication_name}")

            # Process entries
            contents = []
            for entry in feed.entries[:max_entries]:
                # Check date filter
                if after_date:
                    entry_date = self._parse_entry_date(entry)
                    if entry_date and entry_date < after_date:
                        logger.debug(f"Skipping old entry: {entry.get('title', 'Unknown')}")
                        continue

                # Convert entry to ContentData
                try:
                    content = self._parse_entry_content(entry, publication_name, feed_url)
                    contents.append(content)
                    logger.debug(f"Parsed content: {content.title}")
                except Exception as e:
                    logger.error(
                        f"Error parsing entry '{entry.get('title', 'Unknown')}': {e}",
                        exc_info=True,
                    )
                    continue

            logger.info(f"Fetched {len(contents)} content items from {feed_url}")
            return contents

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching feed {feed_url}: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching feed {feed_url}: {e}", exc_info=True)
            return []

    def fetch_multiple_contents(
        self,
        feed_urls: list[str],
        max_entries_per_feed: int = 10,
        after_date: datetime | None = None,
    ) -> list[ContentData]:
        """
        Fetch content from multiple RSS feeds as ContentData.

        Args:
            feed_urls: List of RSS feed URLs
            max_entries_per_feed: Maximum entries to fetch per feed
            after_date: Only fetch entries published after this date

        Returns:
            Combined list of ContentData objects from all feeds
        """
        logger.info(f"Fetching {len(feed_urls)} RSS feeds for Content model")

        all_contents = []
        for feed_url in feed_urls:
            contents = self.fetch_content(
                feed_url=feed_url,
                max_entries=max_entries_per_feed,
                after_date=after_date,
            )
            all_contents.extend(contents)

        logger.info(
            f"Fetched total of {len(all_contents)} content items from {len(feed_urls)} feeds"
        )
        return all_contents

    def _parse_entry_content(
        self,
        entry: feedparser.FeedParserDict,
        publication_name: str,
        feed_url: str,
    ) -> ContentData:
        """
        Parse a feed entry into a ContentData object.

        Args:
            entry: Feed entry
            publication_name: Name of the publication
            feed_url: Feed URL

        Returns:
            ContentData object
        """
        # Extract basic metadata
        title = entry.get("title", "Untitled")
        link = entry.get("link", feed_url)
        author = entry.get("author", publication_name)

        # Parse publication date
        published_date = self._parse_entry_date(entry) or datetime.now()

        # Extract content (HTML)
        raw_html = self._extract_entry_content(entry)

        # Convert HTML to markdown
        markdown_content = ""
        if raw_html:
            markdown_content = html_to_markdown(raw_html)
        if not markdown_content:
            # Fallback: use plain text
            markdown_content = html_to_text(raw_html) if raw_html else ""

        # Extract links from HTML
        links = extract_links(raw_html) if raw_html else []

        # Generate unique source_id from link or content hash
        source_id = self._generate_source_id(entry)

        # Generate content hash from normalized markdown
        content_hash = generate_markdown_hash(markdown_content) if markdown_content else ""

        return ContentData(
            source_type=ContentSource.RSS,
            source_id=source_id,
            source_url=link,
            title=title,
            author=author,
            publication=publication_name,
            published_date=published_date,
            markdown_content=markdown_content,
            links_json=links if links else None,
            metadata_json={
                "feed_url": feed_url,
                "entry_id": entry.get("id"),
            },
            raw_content=raw_html,
            raw_format="html" if raw_html else "text",
            parser_used="markitdown",
            content_hash=content_hash,
        )

    def _extract_publication_name(self, feed: feedparser.FeedParserDict, feed_url: str) -> str:
        """
        Extract publication name from feed metadata.

        Tries multiple sources: feed.title, feed.subtitle, domain name.

        Args:
            feed: Parsed feed object
            feed_url: Feed URL (fallback for extracting name)

        Returns:
            Publication name
        """
        # Try feed title first
        if hasattr(feed, "feed") and hasattr(feed.feed, "title"):
            return feed.feed.title

        # Try feed subtitle
        if hasattr(feed, "feed") and hasattr(feed.feed, "subtitle"):
            return feed.feed.subtitle

        # Fallback to domain name from URL
        parsed_url = urlparse(feed_url)
        domain = parsed_url.netloc or parsed_url.path
        return domain.title()

    def _parse_entry_date(self, entry: feedparser.FeedParserDict) -> datetime | None:
        """
        Parse entry publication date.

        Tries multiple date fields: published_parsed, updated_parsed.

        Args:
            entry: Feed entry

        Returns:
            Publication datetime or None if not found
        """
        # Try published_parsed first
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                return datetime(*entry.published_parsed[:6])
            except (ValueError, TypeError):
                pass

        # Try updated_parsed
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            try:
                return datetime(*entry.updated_parsed[:6])
            except (ValueError, TypeError):
                pass

        # Fallback to current time
        logger.warning(f"Could not parse date for entry: {entry.get('title', 'Unknown')}")
        return None

    def _parse_entry(
        self,
        entry: feedparser.FeedParserDict,
        publication_name: str,
        feed_url: str,
    ) -> NewsletterData:
        """
        Parse a feed entry into a NewsletterData object.

        Args:
            entry: Feed entry
            publication_name: Name of the publication
            feed_url: Feed URL

        Returns:
            NewsletterData object
        """
        # Extract basic metadata
        title = entry.get("title", "Untitled")
        link = entry.get("link", feed_url)
        author = entry.get("author", publication_name)

        # Parse publication date
        published_date = self._parse_entry_date(entry) or datetime.now()

        # Extract content
        raw_html = self._extract_entry_content(entry)
        raw_text = html_to_text(raw_html) if raw_html else ""
        links = extract_links(raw_html) if raw_html else []

        # Generate unique source_id from link or content hash
        source_id = self._generate_source_id(entry)

        # Generate content hash for deduplication
        content_hash = generate_content_hash(raw_text) if raw_text else None

        return NewsletterData(
            source=NewsletterSource.RSS,
            source_id=source_id,
            title=title,
            sender=author,
            publication=publication_name,
            published_date=published_date,
            url=link,
            raw_html=raw_html,
            raw_text=raw_text,
            extracted_links=links,
            content_hash=content_hash,
            status=ProcessingStatus.PENDING,
        )

    def _extract_entry_content(self, entry: feedparser.FeedParserDict) -> str:
        """
        Extract full content from feed entry.

        Tries multiple content fields: content, summary, description.
        Prefers HTML content over plain text.

        Args:
            entry: Feed entry

        Returns:
            HTML content string
        """
        # Try content field first (usually full article)
        if hasattr(entry, "content") and entry.content:
            # Content is a list of dicts with 'type' and 'value'
            for content_item in entry.content:
                if content_item.get("type") == "text/html":
                    return content_item.get("value", "")
                # Fallback to any content type
                return content_item.get("value", "")

        # Try summary_detail (may have HTML)
        if hasattr(entry, "summary_detail") and entry.summary_detail:
            if entry.summary_detail.get("type") == "text/html":
                return entry.summary_detail.get("value", "")

        # Try summary (may be plain text or HTML)
        if hasattr(entry, "summary") and entry.summary:
            return entry.summary

        # Try description
        if hasattr(entry, "description") and entry.description:
            return entry.description

        logger.warning(f"No content found for entry: {entry.get('title', 'Unknown')}")
        return ""

    def _generate_source_id(self, entry: feedparser.FeedParserDict) -> str:
        """
        Generate unique source ID for the entry.

        Uses entry.id if available, otherwise generates hash from link or title.

        Args:
            entry: Feed entry

        Returns:
            Unique source ID
        """
        # Use entry ID if available (GUID)
        if hasattr(entry, "id") and entry.id:
            return entry.id

        # Use link if available
        if hasattr(entry, "link") and entry.link:
            return entry.link

        # Fallback: hash of title + published date
        title = entry.get("title", "")
        date = entry.get("published", "")
        hash_input = f"{title}:{date}"
        return f"rss-{hashlib.sha256(hash_input.encode()).hexdigest()[:16]}"

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class RSSIngestionService:
    """Service for ingesting newsletters from RSS feeds."""

    def __init__(self) -> None:
        """Initialize RSS ingestion service."""
        self.client = RSSClient()

    def ingest_newsletters(
        self,
        feed_urls: list[str] | None = None,
        max_entries_per_feed: int = 10,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
    ) -> int:
        """
        Ingest newsletters from RSS feeds and store in database.

        Args:
            feed_urls: List of RSS feed URLs (defaults to config)
            max_entries_per_feed: Maximum entries per feed
            after_date: Only fetch after this date
            force_reprocess: If True, reprocess existing newsletters (updates data and resets status)

        Returns:
            Number of newsletters ingested
        """

        logger.info("Starting RSS newsletter ingestion...")

        # Get feed URLs from config if not provided
        if feed_urls is None:
            feed_urls = settings.get_rss_feed_urls()

        if not feed_urls:
            logger.warning(
                "No RSS feed URLs configured. Please set RSS_FEEDS or create rss_feeds.txt"
            )
            return 0

        logger.info(f"Fetching from {len(feed_urls)} RSS feeds")

        # Fetch newsletters from all feeds
        newsletters = self.client.fetch_multiple_feeds(
            feed_urls=feed_urls,
            max_entries_per_feed=max_entries_per_feed,
            after_date=after_date,
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

    def close(self) -> None:
        """Close RSS client."""
        self.client.close()


class RSSContentIngestionService:
    """Service for ingesting RSS feeds into the unified Content model.

    This is the preferred ingestion service for new code. It creates Content
    records with markdown as the primary format, enabling the unified content
    pipeline for summarization and digest creation.
    """

    def __init__(self) -> None:
        """Initialize RSS content ingestion service."""
        self.client = RSSClient()

    def ingest_content(
        self,
        feed_urls: list[str] | None = None,
        max_entries_per_feed: int = 10,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
    ) -> int:
        """
        Ingest content from RSS feeds and store as Content records.

        Args:
            feed_urls: List of RSS feed URLs (defaults to config)
            max_entries_per_feed: Maximum entries per feed
            after_date: Only fetch after this date
            force_reprocess: If True, reprocess existing content

        Returns:
            Number of content items ingested
        """
        logger.info("Starting RSS content ingestion (unified Content model)...")

        # Get feed URLs from config if not provided
        if feed_urls is None:
            feed_urls = settings.get_rss_feed_urls()

        if not feed_urls:
            logger.warning(
                "No RSS feed URLs configured. Please set RSS_FEEDS or create rss_feeds.txt"
            )
            return 0

        logger.info(f"Fetching from {len(feed_urls)} RSS feeds for Content model")

        # Fetch content from all feeds
        contents = self.client.fetch_multiple_contents(
            feed_urls=feed_urls,
            max_entries_per_feed=max_entries_per_feed,
            after_date=after_date,
        )

        if not contents:
            logger.info("No content found")
            return 0

        # Store in database
        count = 0
        with get_db() as db:
            for content_data in contents:
                try:
                    # Check if already exists by source_type + source_id
                    existing = (
                        db.query(Content)
                        .filter(
                            Content.source_type == content_data.source_type,
                            Content.source_id == content_data.source_id,
                        )
                        .first()
                    )

                    # Check by content_hash for cross-source duplicates
                    content_duplicate = None
                    if not existing and content_data.content_hash:
                        content_duplicate = (
                            db.query(Content)
                            .filter(Content.content_hash == content_data.content_hash)
                            .first()
                        )

                    if existing:
                        if force_reprocess:
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

                    elif content_duplicate:
                        logger.info(
                            f"Content duplicate detected: '{content_data.title}' "
                            f"matches existing content ID {content_duplicate.id}"
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
                            canonical_id=content_duplicate.id,
                            status=ContentStatus.COMPLETED,
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
                        status=ContentStatus.PARSED,
                    )

                    db.add(content)
                    count += 1
                    logger.info(f"Ingested: {content_data.title}")

                except Exception as e:
                    logger.error(f"Error storing content: {e}")
                    db.rollback()
                    continue

        logger.info(f"Successfully ingested {count} content items")
        return count

    def close(self) -> None:
        """Close RSS client."""
        self.client.close()
