"""Generated contract models for blog scraping ingestion.

These Pydantic models define the interfaces between work packages.
Agent implementations MUST conform to these signatures.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

# --- Source Configuration Contract (wp-config) ---


class BlogSource(BaseModel):
    """Blog source configuration model.

    Added to Source discriminated union in src/config/sources.py.
    Inherits from SourceBase (name, tags, enabled, max_entries, content_filter_*).
    """

    type: Literal["blog"] = "blog"
    url: str
    name: str | None = None
    tags: list[str] = []
    enabled: bool = True
    max_entries: int | None = None
    link_selector: str | None = None
    link_pattern: str | None = None
    request_delay: float = 1.0
    # Inherited content filter fields
    content_filter_strategy: str | None = None
    content_filter_topics: list[str] | None = None
    content_filter_excerpt_chars: int | None = None


# --- Content Data Contract (wp-scraper ↔ wp-integration) ---


@dataclass
class BlogPostData:
    """Data extracted from a single blog post.

    Produced by BlogScrapingClient, consumed by BlogContentIngestionService.
    """

    url: str
    title: str
    author: str | None
    publication: str | None
    published_date: datetime | None
    markdown_content: str
    raw_html: str | None
    content_hash: str
    links: list[str]
    metadata: dict | None = None


@dataclass
class DiscoveredLink:
    """A link discovered from a blog index page."""

    url: str
    title_hint: str | None = None


# --- Service Result Contracts (wp-scraper) ---


@dataclass
class SourceFetchResult:
    """Per-source fetch result (reuses existing pattern from rss.py)."""

    url: str
    name: str | None = None
    success: bool = True
    items_fetched: int = 0
    error: str | None = None
    error_type: str | None = None


@dataclass
class IngestionResult:
    """Overall ingestion result (reuses existing pattern from rss.py)."""

    items_ingested: int = 0
    source_results: list[SourceFetchResult] = field(default_factory=list)


# --- Service Interface Contracts ---


@runtime_checkable
class BlogScrapingClientInterface(Protocol):
    """Contract for BlogScrapingClient.

    wp-scraper MUST implement all methods with these signatures.
    """

    def fetch_index_page(self, url: str, *, timeout: float = 30.0) -> str:
        """Fetch blog index page HTML. SSRF-protected."""
        ...

    def discover_post_links(
        self,
        html: str,
        base_url: str,
        *,
        link_selector: str | None = None,
        link_pattern: str | None = None,
        max_links: int = 10,
    ) -> list[DiscoveredLink]:
        """Extract and filter post URLs from index page HTML."""
        ...

    def extract_post_content(self, url: str) -> BlogPostData | None:
        """Fetch and extract content from a single blog post URL."""
        ...

    def extract_published_date(self, html: str) -> datetime | None:
        """Multi-strategy date extraction from HTML."""
        ...


@runtime_checkable
class BlogContentIngestionServiceInterface(Protocol):
    """Contract for BlogContentIngestionService.

    wp-scraper MUST implement with this signature.
    """

    def ingest_content(
        self,
        sources: list[BlogSource] | None = None,
        *,
        max_entries_per_source: int = 10,
        after_date: datetime | None = None,
        force_reprocess: bool = False,
    ) -> IngestionResult:
        """Discover and ingest blog posts from configured sources."""
        ...


# --- Orchestrator Interface Contract (wp-orchestrator) ---


def ingest_blog(
    *,
    max_entries_per_source: int = 10,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    on_result: Callable[[IngestionResult], None] | None = None,
) -> int:
    """Orchestrator function signature.

    Lazy-imports BlogContentIngestionService, calls ingest_content(),
    invokes on_result callback if provided, returns items_ingested count.
    """
    raise NotImplementedError("Contract stub — implemented in src/ingestion/orchestrator.py")
