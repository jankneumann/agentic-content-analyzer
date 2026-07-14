"""Content query models for batch operations.

Provides a shared ContentQuery model that encapsulates filter criteria
for content selection, used across CLI, API, and frontend. Enables
dry-run previews and targeted batch operations (summarize, digest).
"""

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
SELECTION_SCHEMA_VERSION = 1


class DateBasis(StrEnum):
    """Timestamp used to evaluate a workflow period."""

    PUBLISHED_DATE = "published_date"
    INGESTED_AT = "ingested_at"


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
    date_basis: DateBasis = DateBasis.PUBLISHED_DATE
    search: str | None = None
    limit: int | None = Field(default=None, gt=0)
    sort_by: str = Field(default="published_date")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
    canonical_only: bool = True
    require_summary: bool = True

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v: str) -> str:
        if v not in CONTENT_SORT_FIELDS:
            raise ValueError(f"Invalid sort_by '{v}'. Valid fields: {sorted(CONTENT_SORT_FIELDS)}")
        return v


class SelectionExclusionReason(StrEnum):
    """Stable diagnostic reasons for workflow selection exclusions."""

    DUPLICATE_ALIAS = "duplicate_alias"
    MISSING_SUMMARY = "missing_summary"
    FILTERED_OUT = "filtered_out"
    FAILED = "failed"
    OUTSIDE_PERIOD = "outside_period"
    UNSUPPORTED_STATUS = "unsupported_status"


class SelectionPolicy(BaseModel):
    """Normalized and immutable policy used for one workflow resolution."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = SELECTION_SCHEMA_VERSION
    source_types: tuple[ContentSource, ...] = ()
    statuses: tuple[ContentStatus, ...] = (ContentStatus.COMPLETED,)
    publications: tuple[str, ...] = ()
    publication_search: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    date_basis: DateBasis = DateBasis.PUBLISHED_DATE
    search: str | None = None
    limit: int | None = Field(default=None, gt=0)
    sort_by: str = "published_date"
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
    canonical_only: bool = True
    require_summary: bool = True


class ResolvedContentItem(BaseModel):
    """One canonical content and persisted summary pair."""

    model_config = ConfigDict(frozen=True)

    content_id: int
    summary_id: int
    source_type: ContentSource
    title: str
    publication: str | None = None
    selection_date: datetime


class SelectionExclusion(BaseModel):
    """One candidate excluded from workflow content resolution."""

    model_config = ConfigDict(frozen=True)

    content_id: int
    reason: SelectionExclusionReason
    canonical_content_id: int | None = None


class ResolvedContentSet(BaseModel):
    """Immutable selection snapshot passed to workflow execution."""

    model_config = ConfigDict(frozen=True)

    policy: SelectionPolicy
    items: tuple[ResolvedContentItem, ...] = ()
    exclusions: tuple[SelectionExclusion, ...] = ()
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @property
    def content_ids(self) -> tuple[int, ...]:
        return tuple(item.content_id for item in self.items)

    @property
    def summary_ids(self) -> tuple[int, ...]:
        return tuple(item.summary_id for item in self.items)

    @property
    def eligible_content_count(self) -> int:
        return len(self.items)

    @property
    def eligible_summary_count(self) -> int:
        return len(self.summary_ids)

    @property
    def exclusions_by_reason(
        self,
    ) -> dict[SelectionExclusionReason, tuple[SelectionExclusion, ...]]:
        grouped: dict[SelectionExclusionReason, list[SelectionExclusion]] = {}
        for exclusion in self.exclusions:
            grouped.setdefault(exclusion.reason, []).append(exclusion)
        return {reason: tuple(items) for reason, items in sorted(grouped.items())}

    @property
    def exclusion_counts(self) -> dict[SelectionExclusionReason, int]:
        return {reason: len(items) for reason, items in self.exclusions_by_reason.items()}


def compute_selection_fingerprint(
    policy: SelectionPolicy | dict[str, Any],
    content_ids: tuple[int, ...] | list[int],
    summary_ids: tuple[int, ...] | list[int],
) -> str:
    """Hash a normalized policy and ordered persisted identifiers."""

    normalized_policy = (
        policy.model_dump(mode="json") if isinstance(policy, SelectionPolicy) else policy
    )
    payload = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "policy": normalized_policy,
        "content_ids": list(content_ids),
        "summary_ids": list(summary_ids),
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class ContentQueryPreview(BaseModel):
    """Preview result showing what a query would match."""

    total_count: int
    by_source: dict[str, int]  # {source_type: count}, alphabetical by key
    by_status: dict[str, int]  # {status: count}, alphabetical by key
    date_range: dict[str, str | None]  # {earliest: ISO str | None, latest: ISO str | None}
    sample_titles: list[str]  # Up to PREVIEW_SAMPLE_LIMIT titles, most recent first
    query: ContentQuery  # Echo back the query for confirmation
