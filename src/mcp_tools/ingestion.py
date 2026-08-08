"""MCP ingestion tools for every executable source descriptor."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AnyUrl, Field, TypeAdapter

from src.contracts.workflow_models import IngestCommand, OperationHandle, UploadReference
from src.ingestion.registry import SOURCE_REGISTRY, configured_source_version
from src.mcp_tools import runtime
from src.models.jobs import OperationType
from src.services.operation_service import OperationService
from src.services.upload_service import UploadService

_INGEST_COMMAND: TypeAdapter[IngestCommand] = TypeAdapter(IngestCommand)
PositiveInt = Annotated[int, Field(ge=1)]
OptionalPositiveInt = Annotated[int | None, Field(ge=1)]
OptionalObsidianMaxItems = Annotated[int | None, Field(ge=1, le=10_000)]
OptionalNonNegativeInt = Annotated[int | None, Field(ge=0)]
NonEmptyString = Annotated[str, Field(min_length=1)]
NonEmptyStringList = Annotated[list[str], Field(min_length=1)]
OpaqueSourceKey = Annotated[str, Field(pattern=r"^src_[a-f0-9]{20}$")]


def _payload(kind: str, **values: Any) -> dict[str, Any]:
    return {"kind": kind, **{key: value for key, value in values.items() if value is not None}}


async def _submit(command: dict[str, Any], idempotency_key: str | None = None) -> OperationHandle:
    validated = _INGEST_COMMAND.validate_python(command)
    public_payload = validated.model_dump(mode="json", exclude_none=True)
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        client = runtime.create_workflow_client()
        try:
            return client.submit_ingestion(public_payload, idempotency_key=idempotency_key)
        finally:
            client.close()

    descriptor = SOURCE_REGISTRY.get(validated.kind)
    if descriptor.config_accessor is not None:
        from src.config.settings import get_settings

        settings = get_settings()
        secret = settings.get_configured_source_key_secret()
        configured = SOURCE_REGISTRY.resolve_configured_sources(
            validated,
            settings.get_sources_config(),
            secret=secret,
        )
        if validated.kind == "obsidian_vault":
            public_payload["configured_source_version"] = configured_source_version(
                configured[0],
                secret=secret,
            )
        else:
            public_payload["configured_sources"] = [
                source.model_dump(mode="json") for source in configured
            ]
    handle = await OperationService().submit(
        OperationType.INGESTION_EXECUTE,
        public_payload,
        idempotency_key=idempotency_key,
    )
    return OperationHandle.model_validate(handle.model_dump(mode="json"))


@runtime.tool_boundary
async def upload_content(
    filename: NonEmptyString,
    content_base64: NonEmptyString,
    media_type: NonEmptyString,
    title: str | None = None,
    publication: str | None = None,
) -> UploadReference:
    """Store caller-provided bytes and return an upload ID for ``ingest_files``."""
    try:
        data = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("content_base64 must be valid base64") from exc
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        client = runtime.create_workflow_client()
        try:
            return client.upload_bytes(
                filename,
                data,
                media_type,
                title=title,
                publication=publication,
            )
        finally:
            client.close()
    upload = await UploadService().store(
        data,
        filename,
        media_type,
        title=title,
        publication=publication,
    )
    return upload


@runtime.tool_boundary
async def ingest_gmail(
    query: str | None = None,
    max_items: OptionalPositiveInt = None,
    days_back: OptionalNonNegativeInt = None,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    idempotency_key: str | None = None,
) -> OperationHandle:
    return await _submit(
        _payload(
            "gmail",
            query=query,
            max_items=max_items,
            days_back=days_back,
            after_date=after_date,
            force_reprocess=force_reprocess,
        ),
        idempotency_key,
    )


async def _scheduled(
    kind: str,
    max_items: int | None,
    days_back: int | None,
    after_date: datetime | None,
    force_reprocess: bool,
    idempotency_key: str | None,
    **extra: Any,
) -> OperationHandle:
    return await _submit(
        _payload(
            kind,
            max_items=max_items,
            days_back=days_back,
            after_date=after_date,
            force_reprocess=force_reprocess,
            **extra,
        ),
        idempotency_key,
    )


@runtime.tool_boundary
async def ingest_rss(
    max_items: OptionalPositiveInt = None,
    days_back: OptionalNonNegativeInt = None,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    idempotency_key: str | None = None,
) -> OperationHandle:
    return await _scheduled(
        "rss", max_items, days_back, after_date, force_reprocess, idempotency_key
    )


@runtime.tool_boundary
async def ingest_blog(
    max_items: OptionalPositiveInt = None,
    days_back: OptionalNonNegativeInt = None,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    idempotency_key: str | None = None,
) -> OperationHandle:
    return await _scheduled(
        "blog", max_items, days_back, after_date, force_reprocess, idempotency_key
    )


@runtime.tool_boundary
async def ingest_substack(
    max_items: OptionalPositiveInt = None,
    days_back: OptionalNonNegativeInt = None,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    idempotency_key: str | None = None,
) -> OperationHandle:
    return await _scheduled(
        "substack", max_items, days_back, after_date, force_reprocess, idempotency_key
    )


@runtime.tool_boundary
async def ingest_youtube_playlist(
    max_items: OptionalPositiveInt = None,
    days_back: OptionalNonNegativeInt = None,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    public_only: bool = False,
    idempotency_key: str | None = None,
) -> OperationHandle:
    return await _scheduled(
        "youtube_playlist",
        max_items,
        days_back,
        after_date,
        force_reprocess,
        idempotency_key,
        public_only=public_only,
    )


@runtime.tool_boundary
async def ingest_youtube_rss(
    max_items: OptionalPositiveInt = None,
    days_back: OptionalNonNegativeInt = None,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    idempotency_key: str | None = None,
) -> OperationHandle:
    return await _scheduled(
        "youtube_rss", max_items, days_back, after_date, force_reprocess, idempotency_key
    )


@runtime.tool_boundary
async def ingest_podcast(
    max_items: OptionalPositiveInt = None,
    days_back: OptionalNonNegativeInt = None,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    transcribe: bool = True,
    idempotency_key: str | None = None,
) -> OperationHandle:
    return await _scheduled(
        "podcast",
        max_items,
        days_back,
        after_date,
        force_reprocess,
        idempotency_key,
        transcribe=transcribe,
    )


@runtime.tool_boundary
async def ingest_x_search(
    prompt: str | None = None,
    max_threads: OptionalPositiveInt = None,
    force_reprocess: bool = False,
    idempotency_key: str | None = None,
) -> OperationHandle:
    return await _submit(
        _payload(
            "x_search", prompt=prompt, max_threads=max_threads, force_reprocess=force_reprocess
        ),
        idempotency_key,
    )


@runtime.tool_boundary
async def ingest_perplexity_search(
    prompt: str | None = None,
    max_items: OptionalPositiveInt = None,
    recency: Literal["hour", "day", "week", "month"] | None = None,
    context_size: Literal["low", "medium", "high"] | None = None,
    force_reprocess: bool = False,
    idempotency_key: str | None = None,
) -> OperationHandle:
    return await _submit(
        _payload(
            "perplexity_search",
            prompt=prompt,
            max_items=max_items,
            recency=recency,
            context_size=context_size,
            force_reprocess=force_reprocess,
        ),
        idempotency_key,
    )


@runtime.tool_boundary
async def ingest_files(
    upload_ids: NonEmptyStringList,
    force_reprocess: bool = False,
    idempotency_key: str | None = None,
) -> OperationHandle:
    return await _submit(
        _payload("files", upload_ids=upload_ids, force_reprocess=force_reprocess), idempotency_key
    )


@runtime.tool_boundary
async def ingest_url(
    url: AnyUrl,
    title: str | None = None,
    tags: list[str] | None = None,
    notes: str | None = None,
    routing_mode: Literal["auto", "webpage"] = "auto",
    force_reprocess: bool = False,
    idempotency_key: str | None = None,
) -> OperationHandle:
    return await _submit(
        _payload(
            "url",
            url=url,
            title=title,
            tags=tags,
            notes=notes,
            routing_mode=routing_mode,
            force_reprocess=force_reprocess,
        ),
        idempotency_key,
    )


@runtime.tool_boundary
async def ingest_scholar_search(
    max_items: PositiveInt = 20, idempotency_key: str | None = None
) -> OperationHandle:
    return await _submit(_payload("scholar_search", max_items=max_items), idempotency_key)


@runtime.tool_boundary
async def ingest_scholar_paper(
    identifier: NonEmptyString,
    with_references: bool = False,
    idempotency_key: str | None = None,
) -> OperationHandle:
    return await _submit(
        _payload("scholar_paper", identifier=identifier, with_references=with_references),
        idempotency_key,
    )


@runtime.tool_boundary
async def ingest_scholar_references(
    after: datetime | None = None,
    before: datetime | None = None,
    source_types: list[str] | None = None,
    dry_run: bool = False,
    limit: OptionalPositiveInt = None,
    idempotency_key: str | None = None,
) -> OperationHandle:
    return await _submit(
        _payload(
            "scholar_references",
            after=after,
            before=before,
            source_types=source_types,
            dry_run=dry_run,
            limit=limit,
        ),
        idempotency_key,
    )


@runtime.tool_boundary
async def ingest_arxiv_search(
    max_items: PositiveInt = 20,
    days_back: OptionalNonNegativeInt = None,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    extract_pdf: bool = True,
    idempotency_key: str | None = None,
) -> OperationHandle:
    return await _submit(
        _payload(
            "arxiv_search",
            max_items=max_items,
            days_back=days_back,
            after_date=after_date,
            force_reprocess=force_reprocess,
            extract_pdf=extract_pdf,
        ),
        idempotency_key,
    )


@runtime.tool_boundary
async def ingest_arxiv_paper(
    identifier: NonEmptyString,
    extract_pdf: bool = True,
    force_reprocess: bool = False,
    idempotency_key: str | None = None,
) -> OperationHandle:
    return await _submit(
        _payload(
            "arxiv_paper",
            identifier=identifier,
            extract_pdf=extract_pdf,
            force_reprocess=force_reprocess,
        ),
        idempotency_key,
    )


@runtime.tool_boundary
async def ingest_huggingface_papers(
    max_items: PositiveInt = 30,
    days_back: OptionalNonNegativeInt = None,
    after_date: datetime | None = None,
    force_reprocess: bool = False,
    idempotency_key: str | None = None,
) -> OperationHandle:
    return await _submit(
        _payload(
            "huggingface_papers",
            max_items=max_items,
            days_back=days_back,
            after_date=after_date,
            force_reprocess=force_reprocess,
        ),
        idempotency_key,
    )


@runtime.tool_boundary
async def ingest_readwise(
    updated_after: datetime | None = None,
    source_types: list[str] | None = None,
    include_deleted: bool = False,
    max_books: OptionalPositiveInt = None,
    force_reprocess: bool = False,
    idempotency_key: str | None = None,
) -> OperationHandle:
    return await _submit(
        _payload(
            "readwise",
            updated_after=updated_after,
            source_types=source_types,
            include_deleted=include_deleted,
            max_books=max_books,
            force_reprocess=force_reprocess,
        ),
        idempotency_key,
    )


@runtime.tool_boundary
async def ingest_obsidian_vault(
    source_key: OpaqueSourceKey,
    max_items: OptionalObsidianMaxItems = None,
    force_reprocess: bool = False,
    idempotency_key: str | None = None,
) -> OperationHandle:
    """Queue one bounded scan for an opaque configured Obsidian vault source."""

    return await _submit(
        _payload(
            "obsidian_vault",
            source_key=source_key,
            max_items=max_items,
            force_reprocess=force_reprocess,
        ),
        idempotency_key,
    )


INGESTION_TOOL_BY_SOURCE = {
    "gmail": ingest_gmail,
    "rss": ingest_rss,
    "blog": ingest_blog,
    "substack": ingest_substack,
    "youtube_playlist": ingest_youtube_playlist,
    "youtube_rss": ingest_youtube_rss,
    "podcast": ingest_podcast,
    "x_search": ingest_x_search,
    "perplexity_search": ingest_perplexity_search,
    "files": ingest_files,
    "url": ingest_url,
    "scholar_search": ingest_scholar_search,
    "scholar_paper": ingest_scholar_paper,
    "scholar_references": ingest_scholar_references,
    "arxiv_search": ingest_arxiv_search,
    "arxiv_paper": ingest_arxiv_paper,
    "huggingface_papers": ingest_huggingface_papers,
    "readwise": ingest_readwise,
    "obsidian_vault": ingest_obsidian_vault,
}

TOOLS = (upload_content, *INGESTION_TOOL_BY_SOURCE.values())
