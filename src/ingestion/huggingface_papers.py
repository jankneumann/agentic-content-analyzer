"""HuggingFace Papers ingestion service.

Discovers and ingests daily papers from https://huggingface.co/papers/.
Two-phase approach following the blog scraper pattern:
  1. Link discovery: fetch the papers listing page, extract individual paper URLs
  2. Content extraction: fetch each paper page, extract metadata and abstract

Papers are stored with source_type=HUGGINGFACE_PAPERS. Deduplication uses the
arXiv ID (extracted from the paper URL path) as source_id for idempotency.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from src.ingestion.gmail import ContentData
from src.models.content import Content, ContentSource, ContentStatus
from src.storage.database import get_db
from src.utils.content_hash import generate_markdown_hash
from src.utils.logging import get_logger

if TYPE_CHECKING:
    from src.config.sources import HuggingFacePapersSource

logger = get_logger(__name__)

# Regex to match HuggingFace paper paths like /papers/2401.12345
_PAPER_PATH_RE = re.compile(r"/papers/(\d{4}\.\d{4,5}(?:v\d+)?)")

# Base URL for resolving relative links
_HF_BASE_URL = "https://huggingface.co"

# Date formats encountered on HuggingFace and academic pages
_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%B %d, %Y",
    "%b %d, %Y",
]


def _parse_date(date_str: str) -> datetime | None:
    """Parse a date string in various formats."""
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)  # noqa: DTZ007
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SourceFetchResult:
    """Tracks the outcome of fetching a single source."""

    url: str
    name: str | None = None
    success: bool = True
    items_fetched: int = 0
    error: str | None = None
    error_type: str | None = None


@dataclass
class IngestionResult:
    """Aggregated result of a HuggingFace Papers ingestion run."""

    items_ingested: int = 0
    source_results: list[SourceFetchResult] = field(default_factory=list)

    @property
    def failed_sources(self) -> list[SourceFetchResult]:
        return [r for r in self.source_results if not r.success]


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


@dataclass
class DiscoveredPaper:
    """A paper discovered from the HuggingFace papers listing page."""

    url: str
    arxiv_id: str
    title_hint: str | None = None


class HuggingFacePapersClient:
    """Client for discovering and extracting HuggingFace daily papers.

    Phase 1: Fetch papers listing page, discover individual paper links.
    Phase 2: Fetch each paper page, extract title, authors, abstract.
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "ACA-HFPapers/1.0"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HuggingFacePapersClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def fetch_listing_page(self, url: str) -> str:
        """Fetch the HuggingFace papers listing page.

        Args:
            url: Papers listing URL (e.g. https://huggingface.co/papers).

        Returns:
            HTML content of the listing page.

        Raises:
            httpx.HTTPError: On network or HTTP errors.
        """
        response = self._client.get(url)
        response.raise_for_status()
        return response.text

    def discover_paper_links(
        self,
        html: str,
        base_url: str,
        *,
        max_papers: int = 30,
    ) -> list[DiscoveredPaper]:
        """Extract paper URLs from the HuggingFace papers listing page.

        Looks for links matching /papers/<arxiv_id> pattern.

        Args:
            html: Raw HTML of the listing page.
            base_url: Base URL for resolving relative links.
            max_papers: Maximum number of papers to return.

        Returns:
            List of discovered papers with arXiv IDs.
        """
        soup = BeautifulSoup(html, "html.parser")
        seen_ids: set[str] = set()
        papers: list[DiscoveredPaper] = []

        for link in soup.find_all("a", href=True):
            href = str(link["href"])
            match = _PAPER_PATH_RE.search(href)
            if not match:
                continue

            arxiv_id = match.group(1)

            # Strip version suffix for dedup (2401.12345v2 -> 2401.12345)
            base_id = re.sub(r"v\d+$", "", arxiv_id)
            if base_id in seen_ids:
                continue
            seen_ids.add(base_id)

            absolute_url = urljoin(base_url, href)

            # Try to get a title hint from the link text
            title_hint = link.get_text(strip=True) or None
            # Skip very short or generic text
            if title_hint and len(title_hint) < 10:
                title_hint = None

            papers.append(
                DiscoveredPaper(
                    url=absolute_url,
                    arxiv_id=base_id,
                    title_hint=title_hint,
                )
            )

            if len(papers) >= max_papers:
                break

        return papers

    def extract_paper_content(self, paper: DiscoveredPaper) -> ContentData | None:
        """Fetch and extract content from a single HuggingFace paper page.

        Extracts title, authors, abstract, and links to arXiv/PDF.

        Args:
            paper: Discovered paper with URL and arXiv ID.

        Returns:
            ContentData if extraction succeeds, None otherwise.
        """
        try:
            response = self._client.get(paper.url)
            response.raise_for_status()
            raw_html = response.text
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch paper page {paper.url}: {e}")
            return None

        soup = BeautifulSoup(raw_html, "html.parser")

        # Extract title
        title = self._extract_title(soup, paper.title_hint)

        # Extract authors
        author = self._extract_authors(soup)

        # Extract abstract
        abstract = self._extract_abstract(soup)
        if not abstract:
            logger.warning(f"No abstract found for {paper.url}")
            # Fall back to full page text extraction
            abstract = self._extract_page_text(soup)

        if not abstract or len(abstract.strip()) < 50:
            logger.warning(f"Insufficient content extracted from {paper.url}")
            return None

        # Build markdown content
        markdown_parts = [f"# {title}\n"]
        if author:
            markdown_parts.append(f"**Authors:** {author}\n")
        markdown_parts.append(f"**Source:** [HuggingFace Papers]({paper.url})\n")

        arxiv_url = f"https://arxiv.org/abs/{paper.arxiv_id}"
        pdf_url = f"https://arxiv.org/pdf/{paper.arxiv_id}"
        markdown_parts.append(f"**arXiv:** [{paper.arxiv_id}]({arxiv_url})")
        markdown_parts.append(f" | [PDF]({pdf_url})\n")

        markdown_parts.append(f"\n## Abstract\n\n{abstract}\n")

        markdown_content = "\n".join(markdown_parts)

        # Collect links
        links = [paper.url, arxiv_url, pdf_url]

        # Build metadata
        metadata = {
            "arxiv_id": paper.arxiv_id,
            "hf_url": paper.url,
            "arxiv_url": arxiv_url,
            "pdf_url": pdf_url,
        }

        # Extract upvotes if present
        upvotes = self._extract_upvotes(soup)
        if upvotes is not None:
            metadata["upvotes"] = upvotes

        # Extract published date (HTML metadata → arXiv ID fallback → None)
        published_date = self._extract_published_date(soup, paper.arxiv_id)

        content_hash = generate_markdown_hash(markdown_content)

        return ContentData(
            source_type=ContentSource.HUGGINGFACE_PAPERS,
            source_id=f"hf-paper:{paper.arxiv_id}",
            source_url=paper.url,
            title=title,
            author=author,
            publication="HuggingFace Papers",
            published_date=published_date,
            markdown_content=markdown_content,
            links_json=links,
            metadata_json=metadata,
            raw_content=raw_html,
            raw_format="html",
            parser_used="HFPapersClient",
            content_hash=content_hash,
        )

    # --- Private helpers ---

    @staticmethod
    def _extract_title(soup: BeautifulSoup, title_hint: str | None) -> str:
        """Extract paper title from the page."""
        # Try main heading
        h1 = soup.find("h1")
        if h1:
            text = h1.get_text(strip=True)
            if text and len(text) > 10:
                return text

        # Try OG title
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            return str(og["content"]).strip()

        # Try <title> tag
        title_el = soup.find("title")
        if title_el:
            text = title_el.get_text(strip=True)
            # Strip common suffixes like " - Hugging Face"
            text = re.sub(r"\s*[-|]\s*Hugg?ing\s*Face.*$", "", text)
            if text:
                return text

        # Fall back to link hint
        if title_hint:
            return title_hint

        return "Untitled Paper"

    @staticmethod
    def _extract_authors(soup: BeautifulSoup) -> str | None:
        """Extract author names from the paper page."""
        # Look for author links or spans — HF paper pages often have author
        # information in specific containers
        author_elements = soup.find_all("a", href=re.compile(r"/(profile|users?)/"))
        if author_elements:
            authors = []
            seen = set()
            for el in author_elements:
                name = el.get_text(strip=True)
                if name and name not in seen and len(name) > 1:
                    seen.add(name)
                    authors.append(name)
            if authors:
                return ", ".join(authors)

        # Look for meta author tag
        meta = soup.find("meta", attrs={"name": "author"})
        if meta and meta.get("content"):
            return str(meta["content"]).strip()

        # Look for citation_author meta tags (common in academic pages)
        citation_authors = soup.find_all("meta", attrs={"name": "citation_author"})
        if citation_authors:
            return ", ".join(
                str(m["content"]).strip()
                for m in citation_authors
                if m.get("content")
            )

        return None

    @staticmethod
    def _extract_abstract(soup: BeautifulSoup) -> str | None:
        """Extract paper abstract from the page."""
        # Look for common abstract containers
        for selector in [
            "[class*='abstract']",
            "[data-target='abstract']",
            "blockquote",
        ]:
            el = soup.select_one(selector)
            if el:
                text = el.get_text(strip=True)
                if text and len(text) > 50:
                    return text

        # Try OG description (often contains the abstract)
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            desc = str(og_desc["content"]).strip()
            if len(desc) > 50:
                return desc

        # Try meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            desc = str(meta_desc["content"]).strip()
            if len(desc) > 50:
                return desc

        return None

    @staticmethod
    def _extract_page_text(soup: BeautifulSoup) -> str | None:
        """Fallback: extract main text content from the page."""
        main = soup.find("main") or soup.find("article") or soup.find("body")
        if main:
            text = main.get_text(separator="\n", strip=True)
            # Take first ~2000 chars as summary
            if text and len(text) > 50:
                return text[:2000]
        return None

    @staticmethod
    def _extract_upvotes(soup: BeautifulSoup) -> int | None:
        """Extract upvote count if present."""
        # Look for upvote elements
        for el in soup.find_all(attrs={"class": re.compile(r"upvote|like|vote")}):
            text = el.get_text(strip=True)
            if text.isdigit():
                return int(text)
        return None

    @staticmethod
    def _extract_published_date(
        soup: BeautifulSoup, arxiv_id: str
    ) -> datetime | None:
        """Extract publication date from page metadata or arXiv ID.

        Tries in order:
        1. <time datetime> element
        2. citation_date / citation_publication_date meta tags
        3. article:published_time Open Graph meta
        4. arXiv ID prefix (YYMM → year-month, day=1)
        5. None (ingested_at will be set automatically by the DB)
        """
        # Strategy 1: <time datetime> element
        time_el = soup.find("time", attrs={"datetime": True})
        if time_el and time_el.get("datetime"):
            dt = _parse_date(str(time_el["datetime"]))
            if dt:
                return dt

        # Strategy 2: citation_date meta tags (common on academic pages)
        for name in ("citation_date", "citation_publication_date", "DC.date"):
            meta = soup.find("meta", attrs={"name": name})
            if meta and meta.get("content"):
                dt = _parse_date(str(meta["content"]))
                if dt:
                    return dt

        # Strategy 3: Open Graph article:published_time
        og_time = soup.find("meta", property="article:published_time")
        if og_time and og_time.get("content"):
            dt = _parse_date(str(og_time["content"]))
            if dt:
                return dt

        # Strategy 4: Derive approximate date from arXiv ID prefix
        # Format: YYMM.NNNNN → year=20YY, month=MM
        match = re.match(r"(\d{2})(\d{2})\.", arxiv_id)
        if match:
            try:
                year = 2000 + int(match.group(1))
                month = int(match.group(2))
                if 1 <= month <= 12:
                    return datetime(year, month, 1, tzinfo=UTC)
            except (ValueError, OverflowError):
                pass

        return None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class HuggingFacePapersContentIngestionService:
    """Service for ingesting papers from HuggingFace daily papers page.

    Follows the client-service pattern: HuggingFacePapersClient handles
    HTTP fetching and content extraction, this service handles source
    resolution, deduplication, and database persistence.
    """

    def __init__(self) -> None:
        self.client = HuggingFacePapersClient()

    def close(self) -> None:
        self.client.close()

    def ingest_content(
        self,
        sources: list[HuggingFacePapersSource] | None = None,
        *,
        max_papers: int = 30,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
    ) -> IngestionResult:
        """Discover and ingest papers from configured HuggingFace sources.

        Args:
            sources: HF Papers sources to ingest. None = load from config.
            max_papers: Maximum papers per source.
            after_date: Skip papers older than this date (limited applicability
                       since daily papers page only shows recent papers).
            force_reprocess: Re-ingest even if already exists.

        Returns:
            IngestionResult with counts and per-source diagnostics.
        """
        if sources is None:
            sources = self._load_sources()

        if not sources:
            logger.warning("No HuggingFace Papers sources configured")
            return IngestionResult()

        result = IngestionResult()

        try:
            for source in sources:
                if not source.enabled:
                    continue

                source_result = self._ingest_source(
                    source,
                    max_papers=source.max_entries or max_papers,
                    after_date=after_date,
                    force_reprocess=force_reprocess,
                )
                result.source_results.append(source_result)
                result.items_ingested += source_result.items_fetched
        finally:
            self.close()

        return result

    def _ingest_source(
        self,
        source: HuggingFacePapersSource,
        *,
        max_papers: int,
        after_date: datetime | None,
        force_reprocess: bool,
    ) -> SourceFetchResult:
        """Ingest papers from a single HuggingFace Papers source."""
        source_url = source.url
        source_name = source.name
        fetch_result = SourceFetchResult(url=source_url, name=source_name)

        try:
            # Phase 1: Discover paper links
            html = self.client.fetch_listing_page(source_url)
            papers = self.client.discover_paper_links(
                html, source_url, max_papers=max_papers
            )

            if not papers:
                logger.info(f"No paper links found on {source_url}")
                return fetch_result

            logger.info(
                f"Discovered {len(papers)} papers from {source_name or source_url}"
            )

            # Phase 2: Extract content from each paper page
            request_delay = source.request_delay
            contents: list[ContentData] = []

            for i, paper in enumerate(papers):
                if i > 0 and request_delay > 0:
                    time.sleep(request_delay)

                content_data = self.client.extract_paper_content(paper)
                if content_data is None:
                    continue

                contents.append(content_data)

            # Phase 3: Persist with deduplication
            count = self._persist_contents(contents, force_reprocess=force_reprocess)
            fetch_result.items_fetched = count

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching {source_url}: {e}")
            fetch_result.success = False
            fetch_result.error = str(e)
            fetch_result.error_type = type(e).__name__
        except Exception as e:
            logger.error(f"Error processing HuggingFace Papers source {source_url}: {e}")
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
                    # Level 1: source_type + source_id (arXiv ID based)
                    existing = (
                        db.query(Content)
                        .filter(
                            Content.source_type == content_data.source_type,
                            Content.source_id == content_data.source_id,
                        )
                        .first()
                    )

                    # Level 2: Check if same arXiv paper already ingested
                    # from ARXIV source type
                    arxiv_duplicate = None
                    if not existing and content_data.metadata_json:
                        arxiv_id = content_data.metadata_json.get("arxiv_id")
                        if arxiv_id:
                            arxiv_duplicate = (
                                db.query(Content)
                                .filter(
                                    Content.source_type == ContentSource.ARXIV,
                                    Content.source_id == arxiv_id,
                                )
                                .first()
                            )

                    # Level 3: content_hash (cross-source)
                    content_duplicate = None
                    if not existing and not arxiv_duplicate and content_data.content_hash:
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
                            existing.content_hash = content_data.content_hash
                            existing.status = ContentStatus.PARSED
                            existing.error_message = None
                            db.flush()
                            count += 1
                            logger.info(f"Updated for reprocessing: {content_data.title}")
                        else:
                            logger.debug(f"Already exists: {content_data.source_id}")
                        continue

                    if arxiv_duplicate:
                        # Link as duplicate with canonical reference to arXiv version
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
                            canonical_id=arxiv_duplicate.id,
                            status=ContentStatus.COMPLETED,
                        )
                        db.add(content)
                        db.flush()
                        count += 1
                        logger.info(
                            f"Linked HF paper to arXiv canonical ID {arxiv_duplicate.id}: "
                            f"{content_data.title}"
                        )
                        continue

                    if content_duplicate:
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
                        logger.info(
                            f"Linked duplicate to canonical ID {content_duplicate.id}"
                        )
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
                    logger.info(f"Ingested HF paper: {content_data.title}")

                except Exception as e:
                    logger.error(
                        f"Failed to persist {content_data.source_url}: {e}"
                    )
                    continue

        return count

    @staticmethod
    def _load_sources() -> list:
        """Load HuggingFace Papers sources from sources.d/huggingface_papers.yaml."""
        try:
            from src.config.sources import load_sources_config

            config = load_sources_config()
            return config.get_huggingface_papers_sources()
        except Exception as e:
            logger.error(f"Failed to load HuggingFace Papers sources: {e}")
            return []
