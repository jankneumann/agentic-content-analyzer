"""Search request/response models for the document search API.

These Pydantic models define the API contract for search endpoints,
including query parameters, filters, results with chunk-level detail,
and metadata about the search strategy used.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SearchType(StrEnum):
    """Search method to use."""

    BM25 = "bm25"
    VECTOR = "vector"
    HYBRID = "hybrid"


# --- Request Models ---


class SearchFilter(BaseModel):
    """Filters to narrow search results."""

    source_types: list[str] | None = None  # e.g., ["gmail", "rss", "youtube"]
    date_from: datetime | None = None
    date_to: datetime | None = None
    publications: list[str] | None = None
    statuses: list[str] | None = None  # e.g., ["completed", "parsed"]
    chunk_types: list[str] | None = None  # e.g., ["paragraph", "table", "code"]


class SearchQuery(BaseModel):
    """Search query with optional filters and configuration."""

    query: str = Field(..., min_length=1, description="Search query text")
    type: SearchType = Field(default=SearchType.HYBRID, description="Search method")
    filters: SearchFilter | None = None
    bm25_weight: float | None = None  # Override default weight
    vector_weight: float | None = None  # Override default weight
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


# --- Response Models ---


class ChunkResult(BaseModel):
    """A matching chunk within a search result."""

    chunk_id: int
    content: str  # Chunk text
    section: str | None = None  # Section path or heading
    score: float
    highlight: str | None = None  # Text with <mark> tags around matches
    deep_link: str | None = None  # Direct link (e.g., YouTube timestamp URL)
    chunk_type: str


class SearchScores(BaseModel):
    """Individual scores from each search method."""

    bm25: float | None = None
    vector: float | None = None
    rrf: float | None = None
    rerank: float | None = None


class SearchResult(BaseModel):
    """A document-level search result with matching chunks."""

    id: int  # Content ID
    type: str = "content"
    title: str
    score: float  # Aggregated score (max chunk score)
    scores: SearchScores
    source: str  # Content source type (e.g., "gmail", "rss")
    publication: str | None = None
    published_date: datetime | None = None
    matching_chunks: list[ChunkResult] = Field(
        default_factory=list,
        description="Top matching chunks from this document (max 3)",
    )


class SearchMeta(BaseModel):
    """Metadata about the search execution for debugging and agent reasoning."""

    bm25_strategy: str  # "paradedb_bm25" or "postgres_native_fts"
    embedding_provider: str  # "openai", "local", etc.
    embedding_model: str
    rerank_provider: str | None = None  # None if reranking disabled
    rerank_model: str | None = None
    query_time_ms: int  # Total query execution time
    backend: str  # Database provider name


class SearchResponse(BaseModel):
    """Top-level search API response."""

    results: list[SearchResult]
    total: int  # Total matching results (for pagination)
    meta: SearchMeta
