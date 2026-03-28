"""Contract types for add-academic-paper-insights.

These types define the interfaces between work packages. Each package
MUST conform to these types when producing or consuming data.

Note: S2 API response models use snake_case field names. The actual
Pydantic implementation should use model_config with alias_generator
to map camelCase API responses to snake_case Python fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# ── Semantic Scholar API Response Models ──


@dataclass
class S2Author:
    name: str
    author_id: str | None = None  # API: authorId


@dataclass
class S2Paper:
    paper_id: str  # API: paperId
    title: str
    abstract: str | None = None
    year: int | None = None
    venue: str | None = None
    citation_count: int = 0  # API: citationCount
    influential_citation_count: int = 0  # API: influentialCitationCount
    fields_of_study: list[str] = field(default_factory=list)  # API: fieldsOfStudy
    authors: list[S2Author] = field(default_factory=list)
    publication_types: list[str] = field(default_factory=list)  # API: publicationTypes
    external_ids: dict[str, str] = field(default_factory=dict)  # API: externalIds
    open_access_pdf: dict[str, str] | None = None  # API: openAccessPdf
    tldr: dict[str, str] | None = None


@dataclass
class S2SearchResult:
    total: int
    offset: int
    data: list[S2Paper]


# ── Ingestion Result Types ──


@dataclass
class ScholarSearchResult:
    """Result from search-based ingestion."""

    source_name: str
    query: str
    papers_found: int
    papers_ingested: int
    papers_skipped_duplicate: int
    papers_skipped_filter: int
    papers_failed: int = 0


@dataclass
class ScholarPaperResult:
    """Result from single-paper ingestion."""

    identifier: str
    paper_id: str | None = None
    ingested: bool = False
    already_exists: bool = False
    refs_ingested: int = 0
    error: str | None = None


@dataclass
class ReferenceExtractionResult:
    """Result from reference extraction workflow."""

    content_scanned: int
    references_found: int
    references_resolved: int
    references_unresolved: int
    papers_ingested: int
    papers_skipped_duplicate: int


# ── Source Configuration Type ──


IngestionMode = Literal["search", "single_paper", "citation_traversal", "reference_extraction"]
