"""Generic RSS feed ingestion.

Provides Content model ingestion for RSS feeds using the unified content model.
Creates Content records with markdown as the primary format.

Supports both legacy URL-based ingestion and config-driven ingestion via
RSSSource objects from the unified source configuration system.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import feedparser
import httpx

from src.config import settings
from src.ingestion.gmail import ContentData
from src.models.content import Content, ContentSource, ContentStatus
from src.parsers.html_markdown import convert_html_to_markdown
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.html_parser import extract_links, html_to_text
from src.utils.logging import get_logger
from src.utils.substack import (
    extract_substack_canonical_url,
    find_existing_substack_content,
    normalize_substack_url,
)

if TYPE_CHECKING:
    from src.config.sources import RSSSource

logger = get_logger(__name__)


@dataclass
class SourceFetchResult:
    """Tracks the outcome of fetching a single RSS source."""

    url: str
    name: str | None = None
    success: bool = True
    items_fetched: int = 0
    error: str | None = None
    error_type: str | None = None
    redirected_to: str | None = None

    @property
    def is_redirect(self) -> bool:
        return self.redirected_to is not None


@dataclass
class IngestionResult:
    """Aggregated result of an RSS ingestion run."""

    items_ingested: int = 0
    source_results: list[SourceFetchResult] = field(default_factory=list)

    @property
    def failed_sources(self) -> list[SourceFetchResult]:
        return [r for r in self.source_results if not r.success]

    @property
    def redirected_sources(self) -> list[SourceFetchResult]:
        return [r for r in self.source_results if r.is_redirect]


class RSSClient:
    """Client for fetching newsletters from RSS feeds."""

    def __init__(self, timeout: int = 30) -> None:
        """
        Initialize RSS client.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)
        logger.info("RSS client initialized")

    def close(self) -> None:
        """Close HTTP client."""
        self.client.close()
        logger.info("RSS client closed")

    def fetch_content(
        self,
        feed_url: str,
        max_entries: int = 10,
        after_date: datetime | None = None,
        source_name: str | None = None,
        source_tags: list[str] | None = None,
    ) -> tuple[list[ContentData], SourceFetchResult]:
        """
        Fetch content from an RSS feed as ContentData (unified Content model).

        Args:
            feed_url: RSS feed URL
            max_entries: Maximum number of entries to fetch
            after_date: Only fetch entries published after this date
            source_name: Optional source name from config (included in metadata)
            source_tags: Optional source tags from config (included in metadata)

        Returns:
            Tuple of (list of ContentData objects, SourceFetchResult with fetch outcome)
        """
        logger.info(f"Fetching RSS content: {feed_url}")
        result = SourceFetchResult(url=feed_url, name=source_name)

        try:
            # Fetch feed with timeout (redirects are followed automatically)
            response = self.client.get(feed_url)
            response.raise_for_status()

            # Detect redirects — warn user to update source config
            if response.url != httpx.URL(feed_url):
                final_url = str(response.url)
                result.redirected_to = final_url
                logger.warning(
                    f"Feed redirected: {feed_url} -> {final_url} "
                    f"— consider updating source config to use the new URL"
                )

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
                    content = self._parse_entry_content(
                        entry,
                        publication_name,
                        feed_url,
                        source_name=source_name,
                        source_tags=source_tags,
                    )
                    contents.append(content)
                    logger.debug(f"Parsed content: {content.title}")
                except Exception as e:
                    logger.error(
                        f"Error parsing entry '{entry.get('title', 'Unknown')}': {e}",
                        exc_info=True,
                    )
                    continue

            result.items_fetched = len(contents)
            logger.info(f"Fetched {len(contents)} content items from {feed_url}")
            return contents, result

        except httpx.HTTPStatusError as e:
            result.success = False
            result.error = str(e)
            result.error_type = f"HTTP {e.response.status_code}"
            logger.warning(
                f"Feed unavailable {feed_url}: {e.response.status_code} {e.response.reason_phrase}"
            )
            return [], result
        except httpx.HTTPError as e:
            result.success = False
            result.error = str(e)
            result.error_type = type(e).__name__
            logger.warning(f"HTTP error fetching feed {feed_url}: {e}")
            return [], result
        except Exception as e:
            result.success = False
            result.error = str(e)
            result.error_type = type(e).__name__
            logger.error(f"Unexpected error fetching feed {feed_url}: {e}", exc_info=True)
            return [], result

    def fetch_multiple_contents(
        self,
        feed_urls: list[str],
        max_entries_per_feed: int = 10,
        after_date: datetime | None = None,
    ) -> tuple[list[ContentData], list[SourceFetchResult]]:
        """
        Fetch content from multiple RSS feeds as ContentData.

        Args:
            feed_urls: List of RSS feed URLs
            max_entries_per_feed: Maximum entries to fetch per feed
            after_date: Only fetch entries published after this date

        Returns:
            Tuple of (combined list of ContentData, list of SourceFetchResult)
        """
        logger.info(f"Fetching {len(feed_urls)} RSS feeds for Content model")

        all_contents = []
        all_results = []
        for feed_url in feed_urls:
            contents, result = self.fetch_content(
                feed_url=feed_url,
                max_entries=max_entries_per_feed,
                after_date=after_date,
            )
            all_contents.extend(contents)
            all_results.append(result)

        logger.info(
            f"Fetched total of {len(all_contents)} content items from {len(feed_urls)} feeds"
        )
        return all_contents, all_results

    def _parse_entry_content(
        self,
        entry: feedparser.FeedParserDict,
        publication_name: str,
        feed_url: str,
        source_name: str | None = None,
        source_tags: list[str] | None = None,
    ) -> ContentData:
        """
        Parse a feed entry into a ContentData object.

        Uses two-tier extraction:
        1. Primary: Fetch full article from URL using Trafilatura
        2. Fallback: Use feed content if URL extraction fails

        Args:
            entry: Feed entry
            publication_name: Name of the publication
            feed_url: Feed URL
            source_name: Optional source name from config (included in metadata)
            source_tags: Optional source tags from config (included in metadata)

        Returns:
            ContentData object
        """
        # Extract basic metadata
        title = entry.get("title", "Untitled")
        link = entry.get("link", feed_url)
        author = entry.get("author", publication_name)

        # Parse publication date
        published_date = self._parse_entry_date(entry) or datetime.now()

        # Extract feed content as fallback
        raw_html = self._extract_entry_content(entry)

        # Two-tier extraction: try URL first, fall back to feed content
        markdown_content = ""
        parser_used = "trafilatura"
        extraction_method = "url"

        # Primary: Try URL-based extraction for full article content
        if link and link != feed_url:
            try:
                url_markdown = convert_html_to_markdown(url=link)
                if url_markdown and len(url_markdown) >= 200:
                    markdown_content = url_markdown
                    logger.debug(f"URL extraction successful for {link}: {len(url_markdown)} chars")
                else:
                    logger.debug(
                        f"URL extraction returned insufficient content for {link}, "
                        f"falling back to feed content"
                    )
            except Exception as e:
                logger.debug(f"URL extraction failed for {link}: {e}, falling back to feed content")

        # Fallback: Use feed content if URL extraction didn't work
        if not markdown_content and raw_html:
            markdown_content = convert_html_to_markdown(html=raw_html)
            extraction_method = "feed"
            if not markdown_content:
                # Last resort: plain text
                markdown_content = html_to_text(raw_html)
                parser_used = "text_fallback"
                extraction_method = "text"

        # Extract links from HTML (feed content for consistency)
        links = extract_links(raw_html) if raw_html else []

        canonical_substack_url = extract_substack_canonical_url(links=links, source_url=link)
        if canonical_substack_url:
            link = canonical_substack_url

        # Generate unique source_id from link or content hash
        source_id = self._generate_source_id(entry)

        # Generate content hash from normalized markdown
        content_hash = generate_markdown_hash(markdown_content) if markdown_content else ""

        metadata: dict = {
            "feed_url": feed_url,
            "entry_id": entry.get("id"),
            "extraction_method": extraction_method,
        }
        if canonical_substack_url:
            metadata["substack_url"] = canonical_substack_url
        if source_name:
            metadata["source_name"] = source_name
        if source_tags:
            metadata["source_tags"] = source_tags

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
            metadata_json=metadata,
            raw_content=raw_html,
            raw_format="html" if raw_html else "text",
            parser_used=parser_used,
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
        Returns timezone-aware datetime in UTC for consistent comparisons.

        Args:
            entry: Feed entry

        Returns:
            Publication datetime (UTC-aware) or None if not found
        """
        # Try published_parsed first
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                # feedparser's parsed dates are in UTC, make them timezone-aware
                return datetime(*entry.published_parsed[:6], tzinfo=UTC)
            except (ValueError, TypeError):
                pass

        # Try updated_parsed
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            try:
                return datetime(*entry.updated_parsed[:6], tzinfo=UTC)
            except (ValueError, TypeError):
                pass

        # Fallback to current time
        logger.warning(f"Could not parse date for entry: {entry.get('title', 'Unknown')}")
        return None

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
        sources: list[RSSSource] | None = None,
        feed_urls: list[str] | None = None,
        max_entries_per_feed: int = 10,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
    ) -> IngestionResult:
        """
        Ingest content from RSS feeds and store as Content records.

        Source resolution order:
        1. ``sources`` parameter (RSSSource objects with metadata)
        2. ``feed_urls`` parameter (raw URL list, backward compatible)
        3. SourcesConfig YAML files (sources.d/ or sources.yaml)
        4. Legacy settings (RSS_FEEDS env var, rss_feeds.txt)

        Args:
            sources: List of RSSSource config objects (preferred)
            feed_urls: List of RSS feed URLs (backward compatible)
            max_entries_per_feed: Default max entries per feed
            after_date: Only fetch after this date
            force_reprocess: If True, reprocess existing content

        Returns:
            IngestionResult with item count and per-source fetch outcomes
        """
        logger.info("Starting RSS content ingestion (unified Content model)...")
        ingestion_result = IngestionResult()

        # Resolve sources with fallback chain
        if sources is None and feed_urls is None:
            # Try SourcesConfig first, fall back to legacy
            sources_config = settings.get_sources_config()
            sources = sources_config.get_rss_sources()

            if not sources:
                # Legacy fallback
                legacy_urls = settings.get_rss_feed_urls()
                if legacy_urls:
                    from src.config.sources import RSSSource as _RSSSource

                    sources = [_RSSSource(url=url) for url in legacy_urls]

        if sources is None and feed_urls is not None:
            # Convert raw URLs to RSSSource objects for uniform processing
            from src.config.sources import RSSSource as _RSSSource

            sources = [_RSSSource(url=url) for url in feed_urls]

        if not sources:
            logger.warning(
                "No RSS sources configured. Add sources to sources.d/rss.yaml, "
                "set RSS_FEEDS, or create rss_feeds.txt"
            )
            return ingestion_result

        enabled_sources = [s for s in sources if s.enabled]
        logger.info(
            f"Fetching from {len(enabled_sources)} RSS sources "
            f"({len(sources) - len(enabled_sources)} disabled)"
        )

        # Fetch content from all enabled sources with per-source settings
        contents: list[ContentData] = []
        for source in enabled_sources:
            max_entries = source.max_entries or max_entries_per_feed
            fetched, fetch_result = self.client.fetch_content(
                feed_url=source.url,
                max_entries=max_entries,
                after_date=after_date,
                source_name=source.name,
                source_tags=source.tags if source.tags else None,
            )
            contents.extend(fetched)
            ingestion_result.source_results.append(fetch_result)

        if not contents:
            logger.info("No content found")
            return ingestion_result

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

                    substack_duplicate = None
                    if not existing and content_data.source_url:
                        canonical_url = normalize_substack_url(content_data.source_url)
                        substack_duplicate = find_existing_substack_content(db, canonical_url)

                    # Check by content_hash for cross-source duplicates
                    content_duplicate = None
                    if not existing and not substack_duplicate and content_data.content_hash:
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
                        db.flush()
                        count += 1
                        logger.info(
                            f"Linked Substack duplicate to canonical ID {substack_duplicate.id}"
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
                        db.flush()
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
                    db.flush()

                    # Index for search (fail-safe — never blocks ingestion)
                    from src.services.indexing import index_content

                    index_content(content, db)

                    count += 1
                    logger.info(f"Ingested: {content_data.title}")

                except Exception as e:
                    logger.error(f"Error storing content: {e}")
                    db.rollback()
                    continue

        ingestion_result.items_ingested = count
        logger.info(f"Successfully ingested {count} content items")

        # Log summary of source health
        if ingestion_result.failed_sources:
            logger.warning(
                f"{len(ingestion_result.failed_sources)} source(s) failed during ingestion"
            )
        if ingestion_result.redirected_sources:
            logger.warning(
                f"{len(ingestion_result.redirected_sources)} source(s) have redirected URLs "
                f"— consider updating sources.d/rss.yaml"
            )

        return ingestion_result

    def close(self) -> None:
        """Close RSS client."""
        self.client.close()
