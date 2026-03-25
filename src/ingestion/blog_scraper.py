"""Blog page scraping ingestion.

Discovers and ingests blog posts by scraping blog index/listing pages.
Two-phase approach: link discovery from index page, then content extraction
from individual post URLs.

Uses the established client-service pattern from RSS/podcast ingestion.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from src.ingestion.gmail import ContentData
from src.models.content import Content, ContentSource, ContentStatus
from src.parsers.html_markdown import convert_html_to_markdown
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.html_parser import extract_links
from src.utils.logging import get_logger

logger = get_logger(__name__)


# --- Result Dataclasses ---


@dataclass
class SourceFetchResult:
    """Tracks the outcome of fetching a single blog source."""

    url: str
    name: str | None = None
    success: bool = True
    items_fetched: int = 0
    error: str | None = None
    error_type: str | None = None


@dataclass
class IngestionResult:
    """Aggregated result of a blog ingestion run."""

    items_ingested: int = 0
    source_results: list[SourceFetchResult] = field(default_factory=list)

    @property
    def failed_sources(self) -> list[SourceFetchResult]:
        return [r for r in self.source_results if not r.success]


# --- Link Discovery ---

# Heuristic selectors tried in priority order when no link_selector configured
BLOG_POST_SELECTORS = [
    "article a[href]",
    "main a[href]",
    ".post a[href]",
    ".blog-post a[href]",
    "[class*='post'] a[href]",
    "[class*='article'] a[href]",
    "[class*='entry'] a[href]",
]

# URL path segments that indicate non-article pages
_NON_ARTICLE_PATTERNS = re.compile(
    r"/(tag|category|categories|author|authors|page|about|contact|search|login|signup|privacy|terms)(/|$)",
    re.IGNORECASE,
)

# Fragments and anchors
_FRAGMENT_PATTERN = re.compile(r"^#")


@dataclass
class DiscoveredLink:
    """A link discovered from a blog index page."""

    url: str
    title_hint: str | None = None


class BlogScrapingClient:
    """Client for discovering and extracting blog post content.

    Phase 1: Fetch index page, discover post links via CSS selectors or heuristics.
    Phase 2: Fetch individual posts, extract content via Trafilatura.
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "ACA-BlogScraper/1.0"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> BlogScrapingClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def fetch_index_page(self, url: str) -> str:
        """Fetch blog index page HTML.

        Args:
            url: Blog index page URL.

        Returns:
            HTML content of the page.

        Raises:
            httpx.HTTPError: On network or HTTP errors.
        """
        response = self._client.get(url)
        response.raise_for_status()
        return response.text

    def discover_post_links(
        self,
        html: str,
        base_url: str,
        *,
        link_selector: str | None = None,
        link_pattern: str | None = None,
        max_links: int = 10,
    ) -> list[DiscoveredLink]:
        """Extract and filter post URLs from index page HTML.

        Uses configured CSS selector if provided, otherwise falls back
        to heuristic detection trying multiple common blog post selectors.

        Args:
            html: Raw HTML of the index page.
            base_url: Base URL for resolving relative links.
            link_selector: Optional CSS selector for post links.
            link_pattern: Optional regex pattern to filter URLs.
            max_links: Maximum number of links to return.

        Returns:
            Ordered list of discovered links (page position order).
        """
        soup = BeautifulSoup(html, "html.parser")
        raw_links: list[DiscoveredLink] = []

        if link_selector:
            raw_links = self._extract_with_selector(soup, link_selector, base_url)
        else:
            raw_links = self._extract_with_heuristics(soup, base_url)

        # Filter and deduplicate
        seen_urls: set[str] = set()
        filtered: list[DiscoveredLink] = []
        parsed_base = urlparse(base_url)

        for link in raw_links:
            # Skip fragments and anchors
            if _FRAGMENT_PATTERN.match(link.url):
                continue

            # Resolve relative URLs
            absolute_url = urljoin(base_url, link.url)
            parsed = urlparse(absolute_url)

            # Must be HTTP(S)
            if parsed.scheme not in ("http", "https"):
                continue

            # Same domain or subdomain only
            if not self._is_same_domain(parsed.netloc, parsed_base.netloc):
                continue

            # Exclude non-article paths
            if _NON_ARTICLE_PATTERNS.search(parsed.path):
                continue

            # Must have a path deeper than the index page
            if len(parsed.path.rstrip("/")) <= len(parsed_base.path.rstrip("/")):
                continue

            # Apply URL pattern filter if configured
            if link_pattern and not re.search(link_pattern, absolute_url):
                continue

            # Deduplicate
            normalized = absolute_url.rstrip("/")
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)

            filtered.append(DiscoveredLink(url=absolute_url, title_hint=link.title_hint))

            if len(filtered) >= max_links:
                break

        return filtered

    def extract_post_content(self, url: str) -> ContentData | None:
        """Fetch and extract content from a single blog post URL.

        Uses Trafilatura via HtmlMarkdownConverter for extraction.

        Args:
            url: Blog post URL.

        Returns:
            ContentData if extraction succeeds, None otherwise.
        """
        try:
            response = self._client.get(url)
            response.raise_for_status()
            raw_html = response.text
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch blog post {url}: {e}")
            return None

        # Extract markdown via Trafilatura
        markdown = convert_html_to_markdown(html=raw_html, url=url)
        if not markdown or len(markdown.strip()) < 100:
            logger.warning(f"Insufficient content extracted from {url}")
            return None

        # Extract metadata from HTML
        soup = BeautifulSoup(raw_html, "html.parser")
        title = self._extract_title(soup, url)
        author = self._extract_author(soup)
        published_date = self.extract_published_date(raw_html)
        links = extract_links(raw_html)

        return ContentData(
            source_type=ContentSource.BLOG,
            source_id=f"blog:{url}",
            source_url=url,
            title=title,
            author=author,
            publication=None,  # Set by service from source config
            published_date=published_date,
            markdown_content=markdown,
            links_json=links if links else None,
            metadata_json=None,
            raw_content=raw_html,
            raw_format="html",
            parser_used="BlogScraper",
            content_hash=generate_markdown_hash(markdown),
        )

    def extract_published_date(self, html: str) -> datetime | None:
        """Multi-strategy date extraction from HTML.

        Tries in order:
        1. Open Graph article:published_time
        2. <time datetime> elements
        3. <meta name="date"> or <meta name="DC.date">
        4. JSON-LD datePublished
        5. Returns None (caller uses ingestion timestamp as fallback)
        """
        soup = BeautifulSoup(html, "html.parser")

        # Strategy 1: Open Graph
        og_time = soup.find("meta", property="article:published_time")
        if og_time and og_time.get("content"):
            dt = self._parse_date(og_time["content"])
            if dt:
                return dt

        # Strategy 2: <time datetime>
        time_el = soup.find("time", attrs={"datetime": True})
        if time_el and time_el.get("datetime"):
            dt = self._parse_date(time_el["datetime"])
            if dt:
                return dt

        # Strategy 3: <meta name="date"> or DC.date
        for name in ("date", "DC.date", "DC.Date"):
            meta = soup.find("meta", attrs={"name": name})
            if meta and meta.get("content"):
                dt = self._parse_date(meta["content"])
                if dt:
                    return dt

        # Strategy 4: JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    data = data[0] if data else {}
                date_str = data.get("datePublished")
                if date_str:
                    dt = self._parse_date(date_str)
                    if dt:
                        return dt
            except (json.JSONDecodeError, TypeError, IndexError):
                continue

        return None

    # --- Private helpers ---

    def _extract_with_selector(
        self, soup: BeautifulSoup, selector: str, base_url: str
    ) -> list[DiscoveredLink]:
        """Extract links using a configured CSS selector."""
        links: list[DiscoveredLink] = []
        for el in soup.select(selector):
            href = el.get("href")
            if href:
                title = el.get_text(strip=True) or None
                links.append(DiscoveredLink(url=str(href), title_hint=title))
        return links

    def _extract_with_heuristics(self, soup: BeautifulSoup, base_url: str) -> list[DiscoveredLink]:
        """Extract links using heuristic selectors in priority order."""
        for selector in BLOG_POST_SELECTORS:
            links = self._extract_with_selector(soup, selector, base_url)
            if links:
                return links

        # Ultimate fallback: all links in <body>
        body = soup.find("body")
        if body:
            return self._extract_with_selector(body, "a[href]", base_url)
        return []

    @staticmethod
    def _is_same_domain(netloc1: str, netloc2: str) -> bool:
        """Check if two netlocs are the same domain or subdomain."""
        d1 = netloc1.lower().removeprefix("www.")
        d2 = netloc2.lower().removeprefix("www.")
        return d1 == d2 or d1.endswith(f".{d2}") or d2.endswith(f".{d1}")

    @staticmethod
    def _extract_title(soup: BeautifulSoup, fallback_url: str) -> str:
        """Extract title from HTML metadata or headings."""
        # Try OG title first
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            return str(og["content"]).strip()

        # Try <h1>
        h1 = soup.find("h1")
        if h1:
            text = h1.get_text(strip=True)
            if text:
                return text

        # Try <title>
        title_el = soup.find("title")
        if title_el:
            text = title_el.get_text(strip=True)
            if text:
                return text

        # Fallback to URL path
        path = urlparse(fallback_url).path.rstrip("/").split("/")[-1]
        return path.replace("-", " ").replace("_", " ").title() or "Untitled"

    @staticmethod
    def _extract_author(soup: BeautifulSoup) -> str | None:
        """Extract author from HTML metadata."""
        # Meta author tag
        meta = soup.find("meta", attrs={"name": "author"})
        if meta and meta.get("content"):
            return str(meta["content"]).strip()

        # JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    data = data[0] if data else {}
                author = data.get("author")
                if isinstance(author, dict):
                    return author.get("name")
                if isinstance(author, str):
                    return author
            except (json.JSONDecodeError, TypeError, IndexError):
                continue

        return None

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        """Parse a date string in various formats."""
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%d",
            "%B %d, %Y",
            "%b %d, %Y",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)  # noqa: DTZ007
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt
            except ValueError:
                continue
        return None


# --- Ingestion Service ---


class BlogContentIngestionService:
    """Service for ingesting blog posts from configured sources.

    Follows the client-service pattern: BlogScrapingClient handles
    HTTP fetching and content extraction, this service handles
    source resolution, deduplication, and database persistence.
    """

    def __init__(self) -> None:
        self.client = BlogScrapingClient()

    def ingest_content(
        self,
        sources: list | None = None,
        *,
        max_entries_per_source: int = 10,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
    ) -> IngestionResult:
        """Discover and ingest blog posts from configured sources.

        Args:
            sources: Blog sources to ingest. None = load from sources.d/blogs.yaml.
            max_entries_per_source: Max posts per source.
            after_date: Skip posts older than this date.
            force_reprocess: Re-ingest even if already exists.

        Returns:
            IngestionResult with counts and per-source diagnostics.
        """
        if sources is None:
            sources = self._load_sources()

        if not sources:
            logger.warning("No blog sources configured")
            return IngestionResult()

        result = IngestionResult()

        for source in sources:
            if not source.enabled:
                continue

            source_result = self._ingest_source(
                source,
                max_entries=source.max_entries or max_entries_per_source,
                after_date=after_date,
                force_reprocess=force_reprocess,
            )
            result.source_results.append(source_result)
            result.items_ingested += source_result.items_fetched

        return result

    def _ingest_source(
        self,
        source: object,
        *,
        max_entries: int,
        after_date: datetime | None,
        force_reprocess: bool,
    ) -> SourceFetchResult:
        """Ingest posts from a single blog source."""
        source_url = getattr(source, "url", "")
        source_name = getattr(source, "name", None)
        fetch_result = SourceFetchResult(url=source_url, name=source_name)

        try:
            # Phase 1: Link discovery
            html = self.client.fetch_index_page(source_url)
            links = self.client.discover_post_links(
                html,
                source_url,
                link_selector=getattr(source, "link_selector", None),
                link_pattern=getattr(source, "link_pattern", None),
                max_links=max_entries,
            )

            if not links:
                logger.info(f"No post links found on {source_url}")
                return fetch_result

            logger.info(f"Discovered {len(links)} links from {source_name or source_url}")

            # Phase 2: Content extraction with optional filtering
            content_filter = None
            try:
                from src.services.content_filter import create_content_filter

                content_filter = create_content_filter(source)
            except Exception:
                logger.debug("Content filter not available, proceeding without filtering")

            request_delay = getattr(source, "request_delay", 1.0)
            contents: list[ContentData] = []

            for i, link in enumerate(links):
                if i > 0 and request_delay > 0:
                    time.sleep(request_delay)

                content_data = self.client.extract_post_content(link.url)
                if content_data is None:
                    continue

                # Use title hint from link if extraction didn't find one
                if link.title_hint and content_data.title == "Untitled":
                    content_data.title = link.title_hint

                # Set publication from source name
                content_data.publication = source_name or urlparse(source_url).netloc

                # Date filtering
                if after_date and content_data.published_date:
                    if content_data.published_date < after_date:
                        logger.debug(f"Skipping old post: {content_data.title}")
                        continue

                # Content relevance filtering
                if content_filter:
                    try:
                        filter_result = content_filter.is_relevant(
                            content_data.title,
                            content_data.markdown_content[:1000],
                        )
                        if not filter_result.relevant:
                            logger.debug(
                                f"Filtered out: {content_data.title} "
                                f"(strategy: {filter_result.strategy_used})"
                            )
                            continue
                    except Exception as e:
                        logger.debug(f"Content filter error, keeping post: {e}")

                contents.append(content_data)

            # Phase 3: Database persistence with deduplication
            count = self._persist_contents(contents, force_reprocess=force_reprocess)
            fetch_result.items_fetched = count

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching {source_url}: {e}")
            fetch_result.success = False
            fetch_result.error = str(e)
            fetch_result.error_type = type(e).__name__
        except Exception as e:
            logger.error(f"Error processing blog source {source_url}: {e}")
            fetch_result.success = False
            fetch_result.error = str(e)
            fetch_result.error_type = type(e).__name__

        return fetch_result

    def _persist_contents(
        self,
        contents: list[ContentData],
        *,
        force_reprocess: bool = False,
    ) -> int:
        """Persist content to database with 3-level deduplication."""
        count = 0

        with get_db() as db:
            for content_data in contents:
                try:
                    # Level 1: source_type + source_id
                    existing = (
                        db.query(Content)
                        .filter(
                            Content.source_type == content_data.source_type,
                            Content.source_id == content_data.source_id,
                        )
                        .first()
                    )

                    # Level 2: source_url
                    url_duplicate = None
                    if not existing and content_data.source_url:
                        url_duplicate = (
                            db.query(Content)
                            .filter(Content.source_url == content_data.source_url)
                            .first()
                        )

                    # Level 3: content_hash (cross-source)
                    content_duplicate = None
                    if not existing and not url_duplicate and content_data.content_hash:
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
                            existing.raw_content = content_data.raw_content
                            existing.raw_format = content_data.raw_format
                            existing.content_hash = content_data.content_hash
                            existing.status = ContentStatus.PARSED
                            existing.error_message = None
                            db.flush()
                            count += 1
                            logger.info(f"Updated for reprocessing: {content_data.title}")
                        else:
                            logger.debug(f"Already exists: {content_data.source_id}")
                        continue

                    if url_duplicate:
                        logger.debug(f"URL duplicate: {content_data.source_url}")
                        continue

                    if content_duplicate:
                        # Link as duplicate with canonical reference
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

                    # New content
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

                    # Index for search (fail-safe)
                    try:
                        from src.services.indexing import index_content

                        index_content(content, db)
                    except Exception:
                        pass

                    count += 1
                    logger.info(f"Ingested blog post: {content_data.title}")

                except Exception as e:
                    logger.error(f"Failed to persist {content_data.source_url}: {e}")
                    continue

        return count

    @staticmethod
    def _load_sources() -> list:
        """Load blog sources from sources.d/blogs.yaml."""
        try:
            from src.config.sources import load_sources_config

            config = load_sources_config()
            return config.get_blog_sources()
        except Exception as e:
            logger.error(f"Failed to load blog sources: {e}")
            return []
