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
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from src.contracts.operation_context import OperationOutcome, OperationStage
from src.ingestion.gmail import ContentData
from src.ingestion.result import (
    IngestionError,
    IngestionResponse,
    SourceFetchResult,
    build_response_from_source_results,
)
from src.models.content import Content, ContentSource, ContentStatus
from src.parsers.html_markdown import convert_html_to_markdown, convert_html_with_result
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.html_parser import extract_links
from src.utils.logging import get_logger
from src.workflows.stage_observability import operation_stage

logger = get_logger(__name__)


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


@dataclass
class DiscoveredLink:
    """A link discovered from a blog index page."""

    url: str
    title_hint: str | None = None


@dataclass(frozen=True, slots=True)
class BlogItemOutcome:
    """One bounded source/article outcome using the shared vocabulary."""

    outcome: OperationOutcome
    stage: OperationStage
    error_code: str | None = None
    retryable: bool | None = None
    fallback_from: str | None = None

    @classmethod
    def succeeded(cls, stage: OperationStage) -> BlogItemOutcome:
        return cls(OperationOutcome.SUCCEEDED, stage)

    @classmethod
    def partial(
        cls,
        stage: OperationStage,
        *,
        error_code: str,
        fallback_from: str,
    ) -> BlogItemOutcome:
        return cls(OperationOutcome.PARTIAL, stage, error_code, False, fallback_from)

    @classmethod
    def filtered(cls) -> BlogItemOutcome:
        return cls(OperationOutcome.FILTERED, OperationStage.FILTER, "blog_filtered", False)

    @classmethod
    def skipped_policy(cls, error_code: str) -> BlogItemOutcome:
        return cls(OperationOutcome.SKIPPED_POLICY, OperationStage.FILTER, error_code, False)

    @classmethod
    def skipped_duplicate(cls) -> BlogItemOutcome:
        return cls(
            OperationOutcome.SKIPPED_DUPLICATE,
            OperationStage.DEDUPLICATE,
            "blog_duplicate",
            False,
        )

    @classmethod
    def failed(
        cls,
        *,
        stage: OperationStage,
        error_code: str,
        retryable: bool,
    ) -> BlogItemOutcome:
        return cls(
            OperationOutcome.RETRYABLE_FAILURE if retryable else OperationOutcome.PERMANENT_FAILURE,
            stage,
            error_code,
            retryable,
        )

    @property
    def is_failure(self) -> bool:
        return self.outcome in {
            OperationOutcome.RETRYABLE_FAILURE,
            OperationOutcome.PERMANENT_FAILURE,
        }


@dataclass(frozen=True, slots=True)
class BlogExtractionResult:
    content: ContentData | None
    outcome: BlogItemOutcome


@dataclass
class BlogSourceResult(SourceFetchResult):
    item_outcomes: list[BlogItemOutcome] = field(default_factory=list)


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

    def extract_post(self, url: str) -> BlogExtractionResult:
        """Fetch and extract one post with a truthful typed stage outcome.

        A caller-overridden legacy ``extract_post_content`` remains supported so
        existing integrations can migrate without losing truthful aggregation.
        """
        legacy_method = self.extract_post_content
        if getattr(legacy_method, "__func__", None) is not BlogScrapingClient.extract_post_content:
            content = legacy_method(url)
            if content is not None:
                return BlogExtractionResult(
                    content=content,
                    outcome=BlogItemOutcome.succeeded(OperationStage.EXTRACT),
                )
            return BlogExtractionResult(
                content=None,
                outcome=BlogItemOutcome.failed(
                    stage=OperationStage.EXTRACT,
                    error_code="blog_extraction_failed",
                    retryable=False,
                ),
            )

        return self._extract_post_result(url)

    def _extract_post_result(self, url: str) -> BlogExtractionResult:
        """Fetch and extract one post using the typed converter result.

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
        except httpx.HTTPError:
            logger.warning("Failed to fetch blog post")
            return BlogExtractionResult(
                content=None,
                outcome=BlogItemOutcome.failed(
                    stage=OperationStage.FETCH,
                    error_code="blog_fetch_failed",
                    retryable=True,
                ),
            )

        # Retain the selected extractor so fallback decisions stay diagnosable.
        conversion = convert_html_with_result(html=raw_html, url=url)
        markdown = conversion.markdown or ""
        if not markdown or len(markdown.strip()) < 100:
            logger.warning(f"Insufficient content extracted from {url}")
            return BlogExtractionResult(
                content=None,
                outcome=BlogItemOutcome.failed(
                    stage=OperationStage.EXTRACT,
                    error_code="blog_extraction_failed",
                    retryable=False,
                ),
            )

        # Extract metadata from HTML
        soup = BeautifulSoup(raw_html, "html.parser")
        title = self._extract_title(soup, url)
        author = self._extract_author(soup)
        published_date = self.extract_published_date(raw_html)
        links = extract_links(raw_html)

        content = ContentData(
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
        if conversion.method == "crawl4ai":
            outcome = BlogItemOutcome.partial(
                OperationStage.FALLBACK,
                error_code="blog_preferred_extractor_failed",
                fallback_from="trafilatura",
            )
        else:
            outcome = BlogItemOutcome.succeeded(OperationStage.EXTRACT)
        return BlogExtractionResult(content=content, outcome=outcome)

    def extract_post_content(self, url: str) -> ContentData | None:
        """Backward-compatible content-only wrapper for legacy callers."""
        try:
            response = self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            logger.warning("Failed to fetch blog post")
            return None
        markdown = convert_html_to_markdown(html=response.text, url=url)
        if not markdown or len(markdown.strip()) < 100:
            logger.warning("Insufficient content extracted from blog post")
            return None
        soup = BeautifulSoup(response.text, "html.parser")
        title = self._extract_title(soup, url)
        author = self._extract_author(soup)
        published_date = self.extract_published_date(response.text)
        return ContentData(
            source_type=ContentSource.BLOG,
            source_id=f"blog:{url}",
            source_url=url,
            title=title or "Untitled",
            author=author,
            publication=urlparse(url).netloc,
            published_date=published_date,
            markdown_content=markdown,
            links_json=extract_links(response.text),
            raw_content=None,
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

        for source in sources:
            if not source.enabled:
                continue

            source_result = self._ingest_source(
                source,
                max_entries=source.max_entries or max_entries_per_source,
                after_date=after_date,
                force_reprocess=force_reprocess,
            )
            source_results.append(source_result)
            items_ingested += source_result.items_fetched

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
        fetch_result = BlogSourceResult(url=source_url, name=source_name)
        current_stage = OperationStage.DISCOVER

        try:
            # Phase 1: Link discovery
            with operation_stage("blog.discover", OperationStage.DISCOVER):
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
            content_filter = self._content_filter_for_source(source)

            request_delay = getattr(source, "request_delay", 1.0)
            contents: list[ContentData] = []

            for i, link in enumerate(links):
                if i > 0 and request_delay > 0:
                    time.sleep(request_delay)

                current_stage = OperationStage.EXTRACT
                with operation_stage("blog.extract", OperationStage.EXTRACT) as evidence:
                    extraction = self.client.extract_post(link.url)
                    fallback_attributes = (
                        {
                            "blog.fallback_from": extraction.outcome.fallback_from,
                            "blog.selected_extractor": "crawl4ai",
                        }
                        if extraction.outcome.fallback_from
                        else None
                    )
                    evidence.finish(
                        extraction.outcome.outcome,
                        error_code=extraction.outcome.error_code,
                        retryable=extraction.outcome.retryable,
                        attributes=fallback_attributes,
                    )
                if extraction.outcome.outcome == OperationOutcome.PARTIAL:
                    with operation_stage(
                        "blog.fallback",
                        OperationStage.FALLBACK,
                        attributes=fallback_attributes,
                    ) as fallback_evidence:
                        fallback_evidence.finish(
                            OperationOutcome.SUCCEEDED,
                            attributes=fallback_attributes,
                        )
                content_data = extraction.content
                if content_data is None:
                    self._record_item_outcome(fetch_result, extraction.outcome, link.url)
                    continue
                if extraction.outcome.outcome == OperationOutcome.PARTIAL:
                    fetch_result.item_outcomes.append(extraction.outcome)

                # Use title hint from link if extraction didn't find one
                if link.title_hint and content_data.title == "Untitled":
                    content_data.title = link.title_hint

                # Set publication from source name
                content_data.publication = source_name or urlparse(source_url).netloc

                # Date filtering
                if after_date and content_data.published_date:
                    if content_data.published_date < after_date:
                        logger.debug(f"Skipping old post: {content_data.title}")
                        self._record_item_outcome(
                            fetch_result,
                            BlogItemOutcome.skipped_policy("blog_date_policy"),
                            link.url,
                        )
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
                            self._record_item_outcome(
                                fetch_result, BlogItemOutcome.filtered(), link.url
                            )
                            continue
                    except Exception:
                        logger.debug("Content filter error, keeping post")

                contents.append(content_data)

            # Phase 3: Database persistence with deduplication
            current_stage = OperationStage.PERSIST
            with operation_stage("blog.persist", OperationStage.PERSIST):
                count, persist_outcomes = self._persist_contents(
                    contents, force_reprocess=force_reprocess
                )
            fetch_result.items_fetched = count
            for outcome in persist_outcomes:
                self._record_item_outcome(fetch_result, outcome, source_url)

        except httpx.HTTPError:
            logger.error("HTTP error discovering blog source")
            fetch_result.success = False
            fetch_result.error = "Blog source discovery failed"
            fetch_result.error_type = "blog_discovery_failed"
            fetch_result.item_outcomes.append(
                BlogItemOutcome.failed(
                    stage=OperationStage.DISCOVER,
                    error_code="blog_discovery_failed",
                    retryable=True,
                )
            )
        except Exception:
            error_code = f"blog_{current_stage.value}_failed"
            logger.error("Blog source processing failed", extra={"error_code": error_code})
            fetch_result.success = False
            fetch_result.error = f"Blog {current_stage.value} stage failed"
            fetch_result.error_type = error_code
            fetch_result.item_outcomes.append(
                BlogItemOutcome.failed(
                    stage=current_stage,
                    error_code=error_code,
                    retryable=current_stage != OperationStage.EXTRACT,
                )
            )

        return fetch_result

    def _persist_contents(
        self,
        contents: list[ContentData],
        *,
        force_reprocess: bool = False,
    ) -> tuple[int, list[BlogItemOutcome]]:
        """Persist content and return one bounded outcome per non-persisted item."""
        count = 0
        outcomes: list[BlogItemOutcome] = []

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
                            outcomes.append(BlogItemOutcome.skipped_duplicate())
                        continue

                    if url_duplicate:
                        logger.debug(f"URL duplicate: {content_data.source_url}")
                        outcomes.append(BlogItemOutcome.skipped_duplicate())
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

                except Exception:
                    logger.error("Failed to persist blog article")
                    outcomes.append(
                        BlogItemOutcome.failed(
                            stage=OperationStage.PERSIST,
                            error_code="blog_persistence_failed",
                            retryable=True,
                        )
                    )
                    continue

        return count, outcomes

    @staticmethod
    def _record_item_outcome(
        result: BlogSourceResult,
        outcome: BlogItemOutcome,
        url: str,
    ) -> None:
        result.item_outcomes.append(outcome)
        if outcome.outcome == OperationOutcome.FILTERED:
            result.items_filtered += 1
        elif outcome.outcome in {
            OperationOutcome.SKIPPED_POLICY,
            OperationOutcome.SKIPPED_DUPLICATE,
        }:
            result.items_skipped += 1
        elif outcome.is_failure:
            result.items_failed += 1
            result.item_errors.append(
                IngestionError(
                    code=outcome.error_code or "blog_item_failed",
                    message=f"Blog {outcome.stage.value} stage failed",
                    url=url,
                )
            )

    @staticmethod
    def _content_filter_for_source(source: object) -> object | None:
        try:
            from src.services.content_filter import create_content_filter

            return create_content_filter(source)
        except Exception:
            logger.debug("Content filter not available, proceeding without filtering")
            return None

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
