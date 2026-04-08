"""arXiv API client for paper search and PDF download.

Uses the arXiv Atom API (export.arxiv.org/api/query) for metadata and
streaming PDF download from arxiv.org/pdf/. Synchronous HTTP via httpx,
matching existing ingestion client patterns.

Rate limiting: 3s between API requests, 1s between PDF downloads.
"""

from __future__ import annotations

import re
import struct
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import feedparser
import httpx

from src.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARXIV_API_BASE = "https://export.arxiv.org/api/query"
ARXIV_PDF_BASE = "https://arxiv.org/pdf"
ARXIV_ABS_BASE = "https://arxiv.org/abs"

# Rate limits
API_DELAY_SECONDS = 3.0
PDF_DELAY_SECONDS = 1.0
RETRY_BASE_SECONDS = 5.0
RETRY_MAX_SECONDS = 60.0
MAX_RETRIES = 3

# Download limits
DEFAULT_MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB
DEFAULT_TIMEOUT_SECONDS = 60

# arXiv ID patterns
# New-style: 2301.12345 (optionally v3)
# Old-style: hep-th/9901001 (optionally v2)
_NEW_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?$")
_OLD_ID_RE = re.compile(r"([a-z-]+/\d{7})(v\d+)?$")
_DOI_ARXIV_RE = re.compile(r"10\.48550/arXiv\.(\d{4}\.\d{4,5})")
_URL_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([a-z-]+/\d{7}|\d{4}\.\d{4,5})")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ArxivAuthor:
    name: str
    affiliation: str | None = None


@dataclass
class ArxivPaper:
    arxiv_id: str  # base ID without version
    version: int
    title: str
    abstract: str
    authors: list[ArxivAuthor] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    primary_category: str = ""
    published: datetime | None = None
    updated: datetime | None = None
    pdf_url: str = ""
    doi: str | None = None
    journal_ref: str | None = None
    comment: str | None = None


# ---------------------------------------------------------------------------
# ID normalisation
# ---------------------------------------------------------------------------


def normalize_arxiv_id(identifier: str) -> str:
    """Extract base arXiv ID from various input formats.

    Accepts: bare ID, arXiv:prefix, URL, or DOI. Returns the base ID
    without version suffix.  Raises ValueError on unrecognised formats.

    SSRF prevention: only the extracted ID is returned, never a URL.
    """
    identifier = identifier.strip()

    # Strip arXiv: prefix
    if identifier.lower().startswith("arxiv:"):
        identifier = identifier[6:]

    # DOI (10.48550/arXiv.XXXX.XXXXX)
    m = _DOI_ARXIV_RE.search(identifier)
    if m:
        return m.group(1)

    # URL (arxiv.org/abs/... or arxiv.org/pdf/...)
    m = _URL_RE.search(identifier)
    if m:
        raw = m.group(1)
        # Strip version suffix
        raw = re.sub(r"v\d+$", "", raw)
        return raw

    # New-style ID
    m = _NEW_ID_RE.search(identifier)
    if m:
        return m.group(1)

    # Old-style ID
    m = _OLD_ID_RE.search(identifier)
    if m:
        return m.group(1)

    raise ValueError(
        f"Cannot parse arXiv ID from: {identifier!r}. "
        "Expected: 2301.12345, arXiv:2301.12345, "
        "https://arxiv.org/abs/2301.12345, or DOI 10.48550/arXiv.2301.12345"
    )


def extract_version(identifier: str) -> int:
    """Extract version number from an arXiv ID string. Returns 1 if absent."""
    m = re.search(r"v(\d+)", identifier)
    return int(m.group(1)) if m else 1


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ArxivClient:
    """Synchronous arXiv API client with rate limiting."""

    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        api_delay: float = API_DELAY_SECONDS,
        pdf_delay: float = PDF_DELAY_SECONDS,
    ) -> None:
        self._client = http_client or httpx.Client(
            timeout=DEFAULT_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        self._owns_client = http_client is None
        self._api_delay = api_delay
        self._pdf_delay = pdf_delay
        self._last_api_call: float = 0.0
        self._last_pdf_call: float = 0.0

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # ------------------------------------------------------------------
    # Rate limiting helpers
    # ------------------------------------------------------------------

    def _wait_api(self) -> None:
        elapsed = time.monotonic() - self._last_api_call
        if elapsed < self._api_delay:
            time.sleep(self._api_delay - elapsed)
        self._last_api_call = time.monotonic()

    def _wait_pdf(self) -> None:
        elapsed = time.monotonic() - self._last_pdf_call
        if elapsed < self._pdf_delay:
            time.sleep(self._pdf_delay - elapsed)
        self._last_pdf_call = time.monotonic()

    def _request_with_retry(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """Execute GET with exponential backoff on 429/503.

        Makes 1 initial attempt + MAX_RETRIES retries = 4 total attempts.
        """
        last_resp: httpx.Response | None = None
        for attempt in range(MAX_RETRIES + 1):
            self._wait_api()
            resp = self._client.get(url, params=params)
            if resp.status_code not in (429, 503):
                resp.raise_for_status()
                return resp

            last_resp = resp

            # Don't sleep after the last attempt
            if attempt >= MAX_RETRIES:
                break

            # Respect Retry-After header
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                delay = float(retry_after)
            else:
                delay = min(RETRY_BASE_SECONDS * (2**attempt), RETRY_MAX_SECONDS)
            logger.warning(
                f"arXiv API returned {resp.status_code}, retrying in {delay:.0f}s "
                f"(attempt {attempt + 1}/{MAX_RETRIES})"
            )
            time.sleep(delay)

        # All retries exhausted
        assert last_resp is not None
        last_resp.raise_for_status()
        return last_resp  # unreachable, but keeps type checker happy

    # ------------------------------------------------------------------
    # Atom feed parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_time_struct(ts: Any) -> datetime | None:
        """Convert feedparser time_struct to UTC-aware datetime.

        Feedparser dates are naive — MUST convert to UTC per CLAUDE.md gotcha.
        """
        if ts is None:
            return None
        try:
            from calendar import timegm

            return datetime.fromtimestamp(timegm(ts), tz=UTC)
        except (OverflowError, OSError, ValueError, struct.error):
            return None

    def _parse_entry(self, entry: Any) -> ArxivPaper:
        """Parse a single Atom feed entry into an ArxivPaper."""
        # Extract arXiv ID and version from entry.id
        raw_id = entry.get("id", "")
        # entry.id is like http://arxiv.org/abs/2301.12345v3
        base_id = normalize_arxiv_id(raw_id)
        version = extract_version(raw_id)

        # Authors
        authors: list[ArxivAuthor] = []
        for a in entry.get("authors", []):
            name = a.get("name", "Unknown")
            affil = None
            arxiv_affil = a.get("arxiv_affiliation")
            if arxiv_affil:
                affil = arxiv_affil
            authors.append(ArxivAuthor(name=name, affiliation=affil))

        # Categories
        tags = entry.get("tags", [])
        categories = [t.get("term", "") for t in tags if t.get("term")]
        primary_cat = entry.get("arxiv_primary_category", {}).get("term", "")
        if not primary_cat and categories:
            primary_cat = categories[0]

        # Title: collapse whitespace (Optimized: string split/join is faster than regex)
        title = " ".join(entry.get("title", "").split())

        # Abstract: collapse whitespace (Optimized: string split/join is faster than regex)
        abstract = " ".join(entry.get("summary", "").split())

        return ArxivPaper(
            arxiv_id=base_id,
            version=version,
            title=title,
            abstract=abstract,
            authors=authors,
            categories=categories,
            primary_category=primary_cat,
            published=self._parse_time_struct(entry.get("published_parsed")),
            updated=self._parse_time_struct(entry.get("updated_parsed")),
            pdf_url=f"{ARXIV_PDF_BASE}/{base_id}v{version}",
            doi=entry.get("arxiv_doi"),
            journal_ref=entry.get("arxiv_journal_ref"),
            comment=entry.get("arxiv_comment"),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search_papers(
        self,
        *,
        query: str | None = None,
        categories: list[str] | None = None,
        sort_by: str = "submittedDate",
        max_results: int = 20,
        start: int = 0,
    ) -> list[ArxivPaper]:
        """Search arXiv via the Atom API.

        Args:
            query: Keyword search string.
            categories: arXiv category codes (e.g. ["cs.AI"]).
            sort_by: One of relevance, lastUpdatedDate, submittedDate.
            max_results: Maximum papers to return.
            start: Pagination offset.

        Returns:
            List of ArxivPaper objects.
        """
        # Build query string
        parts: list[str] = []
        if categories:
            cat_parts = [f"cat:{c}" for c in categories]
            if len(cat_parts) > 1:
                parts.append("(" + "+OR+".join(cat_parts) + ")")
            else:
                parts.append(cat_parts[0])
        if query:
            parts.append(f"all:{query}")

        search_query = "+AND+".join(parts) if parts else "all:*"

        params = {
            "search_query": search_query,
            "sortBy": sort_by,
            "sortOrder": "descending",
            "start": start,
            "max_results": max_results,
        }

        resp = self._request_with_retry(ARXIV_API_BASE, params=params)
        feed = feedparser.parse(resp.text)

        papers = []
        for entry in feed.entries:
            try:
                papers.append(self._parse_entry(entry))
            except Exception as exc:
                logger.warning(f"Failed to parse arXiv entry: {exc}")
        if not papers:
            logger.info(f"arXiv search returned 0 results for query: {search_query}")
        return papers

    def get_paper(self, arxiv_id: str) -> ArxivPaper | None:
        """Look up a single paper by arXiv ID.

        Args:
            arxiv_id: Base arXiv ID (e.g. 2301.12345).

        Returns:
            ArxivPaper or None if not found.
        """
        params = {"id_list": arxiv_id, "max_results": 1}
        resp = self._request_with_retry(ARXIV_API_BASE, params=params)
        feed = feedparser.parse(resp.text)

        if not feed.entries:
            return None

        entry = feed.entries[0]
        # arXiv returns an error entry when ID is not found
        if "id" not in entry or "arxiv.org" not in entry.get("id", ""):
            return None

        return self._parse_entry(entry)

    def download_pdf(
        self,
        arxiv_id: str,
        dest_path: Path,
        *,
        max_bytes: int = DEFAULT_MAX_PDF_BYTES,
    ) -> bool:
        """Stream-download a PDF to dest_path.

        Args:
            arxiv_id: Full arXiv ID with version (e.g. 2301.12345v3).
            dest_path: File path to write the PDF.
            max_bytes: Abort download if size exceeds this.

        Returns:
            True if download succeeded, False if aborted.
        """
        url = f"{ARXIV_PDF_BASE}/{arxiv_id}"
        self._wait_pdf()

        try:
            with self._client.stream("GET", url) as resp:
                resp.raise_for_status()
                total = 0
                with open(dest_path, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=8192):
                        total += len(chunk)
                        if total > max_bytes:
                            logger.warning(
                                f"PDF for {arxiv_id} exceeds {max_bytes / 1024 / 1024:.0f}MB limit, aborting"
                            )
                            f.close()
                            dest_path.unlink(missing_ok=True)
                            return False
                        f.write(chunk)
            return True
        except httpx.HTTPError as exc:
            logger.error(f"PDF download failed for {arxiv_id}: {exc}")
            dest_path.unlink(missing_ok=True)
            return False
