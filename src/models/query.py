"""Content query models for batch operations.

Provides a shared ContentQuery model that encapsulates filter criteria
for content selection, used across CLI, API, and frontend. Enables
dry-run previews and targeted batch operations (summarize, digest).
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from src.models.content import ContentSource, ContentStatus

# Validated against this allowlist — matches content_routes.py CONTENT_SORT_FIELDS
CONTENT_SORT_FIELDS = {
    "id",
    "title",
    "source_type",
    "publication",
    "status",
    "published_date",
    "ingested_at",
}

PREVIEW_SAMPLE_LIMIT = 10  # Max sample titles in preview


class ContentQuery(BaseModel):
    """Reusable content selection criteria for batch operations.

    Null field semantics: None means "no filter" (match all).
    Empty list [] is treated the same as None.
    """

    source_types: list[ContentSource] | None = None
    statuses: list[ContentStatus] | None = None
    publications: list[str] | None = None
    publication_search: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    search: str | None = None
    limit: int | None = Field(default=None, gt=0)
    sort_by: str = Field(default="published_date")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v: str) -> str:
        if v not in CONTENT_SORT_FIELDS:
            raise ValueError(f"Invalid sort_by '{v}'. Valid fields: {sorted(CONTENT_SORT_FIELDS)}")
        return v


class ContentQueryPreview(BaseModel):
    """Preview result showing what a query would match."""

    total_count: int
    by_source: dict[str, int]  # {source_type: count}, alphabetical by key
    by_status: dict[str, int]  # {status: count}, alphabetical by key
    date_range: dict[str, str | None]  # {earliest: ISO str | None, latest: ISO str | None}
    sample_titles: list[str]  # Up to PREVIEW_SAMPLE_LIMIT titles, most recent first
    query: ContentQuery  # Echo back the query for confirmation
