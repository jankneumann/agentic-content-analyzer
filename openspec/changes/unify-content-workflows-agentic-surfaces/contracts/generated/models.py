"""Generated-contract stub for canonical workflow models.

Implementation SHALL regenerate this module from contracts/openapi/v1.yaml.
Do not import it into production before generation is wired into the build.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProblemField(StrictModel):
    path: list[str | int]
    code: str
    message: str


class Problem(StrictModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str | None = None
    code: str | None = None
    errors: list[ProblemField] = Field(default_factory=list)


OperationStatus = Literal["queued", "in_progress", "completed", "failed", "cancelled"]
OperationType = Literal[
    "ingestion.execute",
    "summarization.run",
    "theme_analysis.create",
    "digest.create",
    "pipeline.run",
    "podcast_script.create",
    "podcast_audio.create",
    "audio_digest.create",
]


class ResourceReference(StrictModel):
    type: str
    id: str
    url: str


class OperationHandle(StrictModel):
    schema_version: Literal[2] = 2
    operation_id: str
    operation_type: OperationType
    status: OperationStatus
    progress: int = Field(ge=0, le=100)
    message: str
    cancellable: bool
    retry_count: int = Field(ge=0)
    status_url: str
    events_url: str
    resource: ResourceReference | None = None
    result: dict[str, Any] | None = None
    problem: Problem | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ContentQuery(StrictModel):
    source_types: list[str] | None = None
    statuses: list[str] | None = None
    publications: list[str] | None = None
    publication_search: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    date_basis: Literal["published_date", "ingested_at"] = "published_date"
    search: str | None = None
    limit: int | None = Field(default=None, ge=1)
    sort_by: str = "published_date"
    sort_order: Literal["asc", "desc"] = "desc"
    canonical_only: bool = True
    require_summary: bool = True


class ConfiguredIngestCommand(StrictModel):
    max_items: int | None = Field(default=None, ge=1)
    days_back: int | None = Field(default=None, ge=0)
    force_reprocess: bool = False


class GmailIngestCommand(ConfiguredIngestCommand):
    kind: Literal["gmail"]
    query: str | None = None


class RssIngestCommand(ConfiguredIngestCommand):
    kind: Literal["rss"]


class BlogIngestCommand(ConfiguredIngestCommand):
    kind: Literal["blog"]


class SubstackIngestCommand(ConfiguredIngestCommand):
    kind: Literal["substack"]


class YouTubePlaylistIngestCommand(ConfiguredIngestCommand):
    kind: Literal["youtube_playlist"]
    public_only: bool = False


class YouTubeRssIngestCommand(ConfiguredIngestCommand):
    kind: Literal["youtube_rss"]


class PodcastIngestCommand(ConfiguredIngestCommand):
    kind: Literal["podcast"]
    transcribe: bool = True


class XSearchIngestCommand(StrictModel):
    kind: Literal["x_search"]
    prompt: str | None = None
    max_threads: int | None = Field(default=None, ge=1)
    force_reprocess: bool = False


class PerplexitySearchIngestCommand(StrictModel):
    kind: Literal["perplexity_search"]
    prompt: str | None = None
    max_items: int | None = Field(default=None, ge=1)
    recency: Literal["hour", "day", "week", "month"] | None = None
    context_size: Literal["low", "medium", "high"] | None = None
    force_reprocess: bool = False


class FilesIngestCommand(StrictModel):
    kind: Literal["files"]
    upload_ids: list[str] = Field(min_length=1)
    force_reprocess: bool = False


class UrlIngestCommand(StrictModel):
    kind: Literal["url"]
    url: str
    title: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    force_reprocess: bool = False


class ScholarSearchIngestCommand(StrictModel):
    kind: Literal["scholar_search"]
    max_items: int = Field(default=20, ge=1)


class ScholarPaperIngestCommand(StrictModel):
    kind: Literal["scholar_paper"]
    identifier: str
    with_references: bool = False


class ScholarReferencesIngestCommand(StrictModel):
    kind: Literal["scholar_references"]
    after: datetime | None = None
    before: datetime | None = None
    source_types: list[str] | None = None
    dry_run: bool = False
    limit: int | None = Field(default=None, ge=1)


class ArxivSearchIngestCommand(ConfiguredIngestCommand):
    kind: Literal["arxiv_search"]
    extract_pdf: bool = True


class ArxivPaperIngestCommand(StrictModel):
    kind: Literal["arxiv_paper"]
    identifier: str
    extract_pdf: bool = True
    force_reprocess: bool = False


class HuggingFacePapersIngestCommand(ConfiguredIngestCommand):
    kind: Literal["huggingface_papers"]


class ReadwiseIngestCommand(StrictModel):
    kind: Literal["readwise"]
    updated_after: datetime | None = None
    source_types: list[str] | None = None
    include_deleted: bool = False
    max_books: int | None = Field(default=None, ge=1)
    force_reprocess: bool = False


IngestCommand = Annotated[
    GmailIngestCommand
    | RssIngestCommand
    | BlogIngestCommand
    | SubstackIngestCommand
    | YouTubePlaylistIngestCommand
    | YouTubeRssIngestCommand
    | PodcastIngestCommand
    | XSearchIngestCommand
    | PerplexitySearchIngestCommand
    | FilesIngestCommand
    | UrlIngestCommand
    | ScholarSearchIngestCommand
    | ScholarPaperIngestCommand
    | ScholarReferencesIngestCommand
    | ArxivSearchIngestCommand
    | ArxivPaperIngestCommand
    | HuggingFacePapersIngestCommand
    | ReadwiseIngestCommand,
    Field(discriminator="kind"),
]


class CapabilityField(StrictModel):
    name: str
    type: str
    required: bool
    description: str | None = None
    enum: list[str] = Field(default_factory=list)
    default: Any = None


class SourceCapability(StrictModel):
    key: str
    display_name: str
    emitted_source: str
    scheduled: bool
    transports: list[Literal["cli", "http", "mcp", "frontend"]]
    fields: list[CapabilityField]


class CapabilityDocument(StrictModel):
    contract_version: str
    source_commands: list[SourceCapability]
    operation_types: list[str]
    resource_types: list[str]
