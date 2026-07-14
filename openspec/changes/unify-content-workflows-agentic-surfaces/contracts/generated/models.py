"""Generated from contracts/openapi/v1.yaml; do not edit."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_SHA256 = "ea9a21f15ab2f3f455c0b3d4262b79f08423aec16a8b16e3519391155311a3af"

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


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Problem(StrictModel):
    type: str
    title: str
    status: Annotated[int, Field(ge=400, le=599)]
    detail: str
    instance: str | None = None
    code: str | None = None
    errors: list[dict[str, Any]] | None = None


class ResourceReference(StrictModel):
    type: Literal[
        "content",
        "ingestion_run",
        "summary_batch",
        "theme_analysis",
        "digest",
        "pipeline_run",
        "podcast_script",
        "podcast",
        "audio_digest",
    ]
    id: str
    url: str


class IngestionResult(StrictModel):
    command_key: str
    resolved_route: str
    emitted_sources: Annotated[list[str], Field(min_length=1)]
    items_ingested: Annotated[int, Field(ge=0)]
    content_ids: list[int]
    warnings: list[str] | None = None
    details: dict[str, Any] | None = None


class OperationHandle(StrictModel):
    schema_version: Literal[2]
    operation_id: str
    operation_type: OperationType
    status: OperationStatus
    progress: Annotated[int, Field(ge=0, le=100)]
    message: str
    cancellable: bool
    retry_count: Annotated[int, Field(ge=0)]
    status_url: str
    events_url: str
    resource: ResourceReference | None = None
    result: dict[str, Any] | None = None
    problem: Problem | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class OperationEvent(StrictModel):
    schema_version: Literal[2]
    event_id: str
    operation_id: str
    operation_type: OperationType
    status: OperationStatus
    progress: Annotated[int, Field(ge=0, le=100)]
    message: str
    resource: ResourceReference | None = None
    problem: Problem | None = None
    occurred_at: datetime


class UploadReference(StrictModel):
    id: str
    filename: str
    media_type: str
    size_bytes: Annotated[int, Field(ge=0)]


class CapabilityField(StrictModel):
    name: str
    type: str
    required: bool
    description: str | None = None
    enum: list[str] | None = None
    default: Any | None = None


class SourceCapability(StrictModel):
    key: str
    display_name: str
    emitted_sources: Annotated[list[str], Field(min_length=1)]
    scheduled: bool
    transports: list[Literal["cli", "http", "mcp", "frontend"]]
    fields: list[CapabilityField]


class CapabilityDocument(StrictModel):
    contract_version: str
    source_commands: list[SourceCapability]
    operation_types: list[str]
    resource_types: list[str]


class ContentQuery(StrictModel):
    source_types: (
        list[
            Literal[
                "gmail",
                "rss",
                "file_upload",
                "youtube",
                "podcast",
                "substack",
                "manual",
                "webpage",
                "xsearch",
                "perplexity",
                "blog",
                "scholar",
                "arxiv",
                "huggingface_papers",
                "readwise",
                "other",
            ]
        ]
        | None
    ) = None
    statuses: (
        list[
            Literal[
                "pending", "parsing", "parsed", "processing", "completed", "failed", "filtered_out"
            ]
        ]
        | None
    ) = None
    publications: list[str] | None = None
    publication_search: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    date_basis: Literal["published_date", "ingested_at"] = "published_date"
    search: str | None = None
    limit: int | None = Field(None, ge=1)
    sort_by: Literal[
        "id", "title", "source_type", "publication", "status", "published_date", "ingested_at"
    ] = "published_date"
    sort_order: Literal["asc", "desc"] = "desc"
    canonical_only: bool = True
    require_summary: bool = True


class ConfiguredSourceCommandBase(StrictModel):
    max_items: int | None = Field(None, ge=1)
    days_back: int | None = Field(None, ge=0)
    force_reprocess: bool = False


class GmailIngestCommand(ConfiguredSourceCommandBase):
    kind: Literal["gmail"]
    query: str | None = None
    max_items: int | None = Field(None, ge=1)
    days_back: int | None = Field(None, ge=0)
    force_reprocess: bool = False


class RssIngestCommand(StrictModel):
    kind: Literal["rss"]
    max_items: int | None = Field(None, ge=1)
    days_back: int | None = Field(None, ge=0)
    force_reprocess: bool = False


class BlogIngestCommand(StrictModel):
    kind: Literal["blog"]
    max_items: int | None = Field(None, ge=1)
    days_back: int | None = Field(None, ge=0)
    force_reprocess: bool = False


class SubstackIngestCommand(StrictModel):
    kind: Literal["substack"]
    max_items: int | None = Field(None, ge=1)
    days_back: int | None = Field(None, ge=0)
    force_reprocess: bool = False


class YouTubePlaylistIngestCommand(StrictModel):
    kind: Literal["youtube_playlist"]
    max_items: int | None = Field(None, ge=1)
    days_back: int | None = Field(None, ge=0)
    force_reprocess: bool = False
    public_only: bool = False


class YouTubeRssIngestCommand(StrictModel):
    kind: Literal["youtube_rss"]
    max_items: int | None = Field(None, ge=1)
    days_back: int | None = Field(None, ge=0)
    force_reprocess: bool = False


class PodcastIngestCommand(StrictModel):
    kind: Literal["podcast"]
    max_items: int | None = Field(None, ge=1)
    days_back: int | None = Field(None, ge=0)
    force_reprocess: bool = False
    transcribe: bool = True


class XSearchIngestCommand(StrictModel):
    kind: Literal["x_search"]
    prompt: str | None = None
    max_threads: int | None = Field(None, ge=1)
    force_reprocess: bool = False


class PerplexitySearchIngestCommand(StrictModel):
    kind: Literal["perplexity_search"]
    prompt: str | None = None
    max_items: int | None = Field(None, ge=1)
    recency: Literal["hour", "day", "week", "month"] | None = None
    context_size: Literal["low", "medium", "high"] | None = None
    force_reprocess: bool = False


class FilesIngestCommand(StrictModel):
    kind: Literal["files"]
    upload_ids: Annotated[list[str], Field(min_length=1)]
    force_reprocess: bool = False


class UrlIngestCommand(StrictModel):
    kind: Literal["url"]
    url: str
    title: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
    routing_mode: Literal["auto", "webpage"] = "auto"
    force_reprocess: bool = False


class ScholarSearchIngestCommand(StrictModel):
    kind: Literal["scholar_search"]
    max_items: int = Field(20, ge=1)


class ScholarPaperIngestCommand(StrictModel):
    kind: Literal["scholar_paper"]
    identifier: Annotated[str, Field(min_length=1)]
    with_references: bool = False


class ScholarReferencesIngestCommand(StrictModel):
    kind: Literal["scholar_references"]
    after: datetime | None = None
    before: datetime | None = None
    source_types: list[str] | None = None
    dry_run: bool = False
    limit: int | None = Field(None, ge=1)


class ArxivSearchIngestCommand(StrictModel):
    kind: Literal["arxiv_search"]
    max_items: int = Field(20, ge=1)
    days_back: int | None = Field(None, ge=0)
    force_reprocess: bool = False
    extract_pdf: bool = True


class ArxivPaperIngestCommand(StrictModel):
    kind: Literal["arxiv_paper"]
    identifier: Annotated[str, Field(min_length=1)]
    extract_pdf: bool = True
    force_reprocess: bool = False


class HuggingFacePapersIngestCommand(StrictModel):
    kind: Literal["huggingface_papers"]
    max_items: int = Field(30, ge=1)
    days_back: int | None = Field(None, ge=0)
    force_reprocess: bool = False


class ReadwiseIngestCommand(StrictModel):
    kind: Literal["readwise"]
    updated_after: datetime | None = None
    source_types: list[str] | None = None
    include_deleted: bool = False
    max_books: int | None = Field(None, ge=1)
    force_reprocess: bool = False


class SummarizationRequest(StrictModel):
    content_ids: list[int] | None = Field(None, min_length=1)
    query: ContentQuery | None = None
    force_reprocess: bool = False


class ThemeAnalysisRequest(StrictModel):
    query: ContentQuery
    max_themes: int = Field(10, ge=1, le=50)


class DigestCreateRequest(StrictModel):
    digest_type: Literal["daily", "weekly"]
    period_start: datetime
    period_end: datetime
    query: ContentQuery | None = None
    include_historical_context: bool = True


class PipelineRequest(StrictModel):
    period: Literal["daily", "weekly"]
    period_start: datetime
    period_end: datetime
    sources: list[str] | None = None
    continue_on_source_error: bool = True


class PodcastScriptRequest(StrictModel):
    digest_id: Annotated[int, Field(ge=1)]
    length: Literal["brief", "standard", "extended"] = "standard"
    enable_web_search: bool = True
    custom_focus_topics: list[str] | None = None
    custom_instructions: str | None = None


class PodcastAudioRequest(StrictModel):
    script_id: Annotated[int, Field(ge=1)]
    voice_provider: Literal["elevenlabs", "google_tts", "aws_polly", "openai_tts"] = "openai_tts"
    alex_voice: Literal["alex_male", "alex_female"] = "alex_male"
    sam_voice: Literal["sam_male", "sam_female"] = "sam_female"


class AudioDigestRequest(StrictModel):
    digest_id: Annotated[int, Field(ge=1)]
    provider: str = "openai"
    voice: str = "nova"
    speed: float = Field(1.0, ge=0.5, le=2.0)


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
