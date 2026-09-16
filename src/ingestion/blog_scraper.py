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
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from src.ingestion.gmail import ContentData
from src.ingestion.result import (
    IngestionError,
    IngestionResponse,
    SourceFetchResult,
    build_response_from_source_results,
)
from src.ingestion.rss import RSSClient
from src.models.content import Content, ContentSource, ContentStatus
from src.parsers.html_markdown import convert_html_to_markdown
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.html_parser import extract_links
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Match RSS: do not walk the rest of blogs.yaml after a cluster of dead hosts.
MAX_CONSECUTIVE_TRANSPORT_FAILURES = 8
_TRANSPORT_ERROR_TYPES = frozenset(
    {
        "ConnectTimeout",
        "ReadTimeout",
        "WriteTimeout",
        "PoolTimeout",
        "TimeoutException",
    }
)

# Same guesses the source curator uses when a listing page has no <link rel=alternate>.
FEED_CANDIDATE_PATHS = ("/feed", "/rss", "/feed.xml", "/rss.xml", "/index.xml", "/atom.xml")
MAX_FEED_CANDIDATES = 6


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

# Browser-like headers. A custom bot UA is the first thing Cloudflare/Akamai
# "bot fight" modes reject; a realistic browser UA + Accept headers behave
# identically on permissive sites and avoid 403s if a source enables protection.
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def feed_candidate_urls(index_url: str) -> list[str]:
    """Guess common feed URLs from a blog index URL.

    Path-prefixed candidates (``/blog/feed``) are listed before origin-level
    ones (``/feed``). Callers cap how many are probed.
    """
    parsed = urlparse(index_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return []
    origin = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path.rstrip("/")
    bases = [f"{origin}{path}"] if path else []
    bases.append(origin)
    urls: list[str] = []
    seen: set[str] = set()
    for base in bases:
        for suffix in FEED_CANDIDATE_PATHS:
            candidate = base + suffix
            if candidate in seen:
                continue
            seen.add(candidate)
            urls.append(candidate)
    return urls


def _optional_str(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            return stripped
    return None


def _optional_str_list(value: object) -> list[str] | None:
    if isinstance(value, list) and value and all(isinstance(item, str) for item in value):
        return value
    return None


def _as_blog_content(content: ContentData, *, source_name: str | None) -> ContentData:
    """Re-home an RSS entry as a blog post so scrape and feed fallback share identity."""
    content.source_type = ContentSource.BLOG
    if content.source_url:
        content.source_id = f"blog:{content.source_url}"
    if source_name:
        content.publication = source_name
    metadata = dict(content.metadata_json or {})
    metadata["rss_fallback"] = True
    content.metadata_json = metadata
    return content


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
            headers=_DEFAULT_HEADERS,
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

            # Resolve relative URLs and drop fragments (e.g. WordPress "#Comments"
            # anchors that would otherwise crawl the same post twice)
            absolute_url, _ = urldefrag(urljoin(base_url, link.url))
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

    def discover_alternate_feeds(self, html: str, base_url: str) -> list[str]:
        """Return RSS/Atom URLs advertised as ``<link rel="alternate">`` on the index."""
        soup = BeautifulSoup(html, "html.parser")
        feeds: list[str] = []
        seen: set[str] = set()
        for tag in soup.find_all("link"):
            rels = [str(rel).lower() for rel in tag.get("rel") or []]
            if "alternate" not in rels:
                continue
            type_ = str(tag.get("type") or "").lower()
            if "rss" not in type_ and "atom" not in type_:
                continue
            href = tag.get("href")
            if not href:
                continue
            absolute, _ = urldefrag(urljoin(base_url, str(href)))
            if urlparse(absolute).scheme not in ("http", "https"):
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            feeds.append(absolute)
        return feeds

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
    ) -> IngestionResponse:
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
            return build_response_from_source_results(
                command="ingest.blog",
                source="blog",
                items_ingested=0,
                source_results=[],
            )

        source_results: list[SourceFetchResult] = []
        items_ingested = 0
        consecutive_transport_failures = 0

        for source in sources:
            if not source.enabled:
                continue

            if consecutive_transport_failures >= MAX_CONSECUTIVE_TRANSPORT_FAILURES:
                skipped = SourceFetchResult(
                    url=getattr(source, "url", ""),
                    name=getattr(source, "name", None),
                )
                skipped.success = False
                skipped.error_type = "ingest_budget_exhausted"
                skipped.error = (
                    f"Skipped after {MAX_CONSECUTIVE_TRANSPORT_FAILURES} "
                    "consecutive blog transport timeouts"
                )
                source_results.append(skipped)
                continue

            source_result = self._ingest_source(
                source,
                max_entries=source.max_entries or max_entries_per_source,
                after_date=after_date,
                force_reprocess=force_reprocess,
            )
            source_results.append(source_result)
            items_ingested += source_result.items_fetched
            if source_result.error_type in _TRANSPORT_ERROR_TYPES:
                consecutive_transport_failures += 1
            elif source_result.success:
                consecutive_transport_failures = 0

        return build_response_from_source_results(
            command="ingest.blog",
            source="blog",
            items_ingested=items_ingested,
            source_results=source_results,
        )

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

        rss_url = _optional_str(getattr(source, "rss_url", None))
        html = ""
        links: list[DiscoveredLink] = []

        try:
            try:
                html = self.client.fetch_index_page(source_url)
                links = self.client.discover_post_links(
                    html,
                    source_url,
                    link_selector=getattr(source, "link_selector", None),
                    link_pattern=getattr(source, "link_pattern", None),
                    max_links=max_entries,
                )
            except httpx.HTTPError:
                if not rss_url:
                    raise
                logger.info(
                    "Index fetch failed for %s; falling back to rss_url",
                    source_url,
                )

            if links:
                logger.info(f"Discovered {len(links)} links from {source_name or source_url}")
                self._ingest_discovered_links(
                    links,
                    fetch_result,
                    source=source,
                    source_url=source_url,
                    source_name=source_name if isinstance(source_name, str) else None,
                    after_date=after_date,
                    force_reprocess=force_reprocess,
                )
                return fetch_result

            feed_urls = self._resolve_feed_urls(source_url, html=html, rss_url=rss_url)
            if not feed_urls:
                logger.info(f"No post links found on {source_url}")
                return fetch_result

            self._ingest_from_feeds(
                feed_urls,
                fetch_result,
                source=source,
                source_name=source_name if isinstance(source_name, str) else None,
                max_entries=max_entries,
                after_date=after_date,
                force_reprocess=force_reprocess,
                explicit_feed=rss_url is not None,
            )

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

    def _resolve_feed_urls(self, source_url: str, *, html: str, rss_url: str | None) -> list[str]:
        """Prefer an explicit rss_url, then <link rel=alternate>, then common paths."""
        if rss_url:
            return [rss_url]
        discovered = self.client.discover_alternate_feeds(html, source_url) if html else []
        if discovered:
            return discovered
        return feed_candidate_urls(source_url)

    def _ingest_discovered_links(
        self,
        links: list[DiscoveredLink],
        fetch_result: SourceFetchResult,
        *,
        source: object,
        source_url: str,
        source_name: str | None,
        after_date: datetime | None,
        force_reprocess: bool,
    ) -> None:
        content_filter = None
        try:
            from src.services.content_filter import create_content_filter

            content_filter = create_content_filter(source)
        except Exception:
            logger.debug("Content filter not available, proceeding without filtering")

        request_delay = getattr(source, "request_delay", 1.0)
        if not isinstance(request_delay, (int, float)):
            request_delay = 0
        contents: list[ContentData] = []

        for i, link in enumerate(links):
            if i > 0 and request_delay > 0:
                time.sleep(request_delay)

            content_data = self.client.extract_post_content(link.url)
            if content_data is None:
                fetch_result.items_failed += 1
                fetch_result.item_errors.append(
                    IngestionError(
                        code="extraction_failed",
                        message="Failed to extract post content (HTTP error or insufficient content)",
                        url=link.url,
                    )
                )
                continue

            if link.title_hint and content_data.title == "Untitled":
                content_data.title = link.title_hint

            content_data.publication = source_name or urlparse(source_url).netloc

            if after_date and content_data.published_date:
                if content_data.published_date < after_date:
                    logger.debug(f"Skipping old post: {content_data.title}")
                    continue

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

        count, persist_errors = self._persist_contents(contents, force_reprocess=force_reprocess)
        fetch_result.items_fetched = count
        fetch_result.items_failed += len(persist_errors)
        fetch_result.item_errors.extend(persist_errors)

    def _ingest_from_feeds(
        self,
        feed_urls: list[str],
        fetch_result: SourceFetchResult,
        *,
        source: object,
        source_name: str | None,
        max_entries: int,
        after_date: datetime | None,
        force_reprocess: bool,
        explicit_feed: bool = False,
    ) -> None:
        content_filter = None
        try:
            from src.services.content_filter import create_content_filter

            content_filter = create_content_filter(source)
        except Exception:
            logger.debug("Content filter not available, proceeding without filtering")

        rss_client = RSSClient(timeout=int(self.client.timeout) or 30)
        last_error: SourceFetchResult | None = None
        try:
            for feed_url in feed_urls[:MAX_FEED_CANDIDATES]:
                contents, rss_result = rss_client.fetch_content(
                    feed_url=feed_url,
                    max_entries=max_entries,
                    after_date=after_date,
                    source_name=source_name,
                    source_tags=_optional_str_list(getattr(source, "tags", None)),
                )
                if not contents:
                    if rss_result.success:
                        logger.info("Feed %s returned no posts", feed_url)
                        return
                    last_error = rss_result
                    continue

                blog_contents: list[ContentData] = []
                for content_data in contents:
                    remapped = _as_blog_content(content_data, source_name=source_name)
                    if content_filter:
                        try:
                            filter_result = content_filter.is_relevant(
                                remapped.title,
                                remapped.markdown_content[:1000],
                            )
                            if not filter_result.relevant:
                                continue
                        except Exception as e:
                            logger.debug(f"Content filter error, keeping post: {e}")
                    blog_contents.append(remapped)

                count, persist_errors = self._persist_contents(
                    blog_contents, force_reprocess=force_reprocess
                )
                fetch_result.items_fetched = count
                fetch_result.items_failed += len(persist_errors) + rss_result.items_failed
                fetch_result.item_errors.extend(persist_errors)
                fetch_result.item_errors.extend(rss_result.item_errors)
                if rss_result.redirected_to:
                    fetch_result.redirected_to = rss_result.redirected_to
                logger.info(
                    "RSS fallback ingested %s posts from %s",
                    count,
                    feed_url,
                )
                return

            if last_error is not None and explicit_feed:
                fetch_result.success = last_error.success
                fetch_result.error = last_error.error
                fetch_result.error_type = last_error.error_type
            else:
                logger.info("No post links or usable feed found for %s", fetch_result.url)
        finally:
            rss_client.close()

    def _persist_contents(
        self,
        contents: list[ContentData],
        *,
        force_reprocess: bool = False,
    ) -> tuple[int, list[IngestionError]]:
        """Persist content to database with 3-level deduplication.

        Returns:
            (count of items persisted, list of per-item persistence errors).
        """
        count = 0
        errors: list[IngestionError] = []

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
                    errors.append(
                        IngestionError(
                            code="persistence_error",
                            message=str(e),
                            url=content_data.source_url,
                        )
                    )
                    continue

        return count, errors

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
