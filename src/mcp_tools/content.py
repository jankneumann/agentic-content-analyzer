"""Read-only content and generated-resource MCP tools."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from src.mcp_tools import runtime
from src.models.content import ContentResponse
from src.models.search import SearchResponse


class PodcastDialogueResource(BaseModel):
    speaker: str
    text: str
    emphasis: str | None = None
    pause_after: float | None = None


class PodcastSectionResource(BaseModel):
    index: int
    type: str
    title: str
    word_count: int
    dialogue: list[PodcastDialogueResource]
    sources_cited: list[int]


class PodcastScriptResource(BaseModel):
    id: int
    digest_id: int
    title: str
    length: str
    word_count: int
    estimated_duration: str
    estimated_duration_seconds: int
    status: str
    revision_count: int
    created_at: datetime | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    sections: list[PodcastSectionResource]
    sources_summary: list[dict[str, Any]]
    revision_history: list[dict[str, Any]]
    newsletter_ids_fetched: list[int]
    web_search_queries: list[str]
    tool_call_count: int


class DigestResource(BaseModel):
    id: int
    digest_type: str
    title: str
    period_start: datetime
    period_end: datetime
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    markdown_content: str | None = None
    source_content_ids: list[int] | None = None
    revision_count: int


def _csv(value: str | None) -> list[str] | None:
    return [item.strip() for item in value.split(",") if item.strip()] if value else None


def _resource_json(path: str, resource_name: str) -> Any:
    try:
        return runtime.request_json("GET", path)
    except runtime.ProblemError as exc:
        if exc.problem.status == 404:
            raise runtime.ResourceNotFoundError(f"{resource_name} not found") from exc
        raise


@runtime.tool_boundary
async def list_content(
    source_types: str | None = None,
    status: str | None = None,
    publication: str | None = None,
    search: str | None = None,
    after_date: str | None = None,
    before_date: str | None = None,
    limit: int = 20,
    sort_by: str = "published_date",
    sort_order: str = "desc",
) -> Any:
    """List canonical content with filters suitable for agent selection."""
    parsed_sources = _csv(source_types)
    if parsed_sources and len(parsed_sources) > 1:
        raise ValueError(
            "list_content accepts one source type; use search_content for combinations"
        )
    params = {
        key: value
        for key, value in {
            "source_type": parsed_sources[0] if parsed_sources else None,
            "status": status,
            "publication": publication,
            "search": search,
            "start_date": after_date,
            "end_date": before_date,
            "page_size": min(limit, 100),
            "sort_by": sort_by,
            "sort_order": sort_order,
        }.items()
        if value is not None
    }
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return runtime.request_json("GET", "/api/v1/contents", params=params)

    from src.models.query import ContentQuery
    from src.services.content_query import ContentQueryService
    from src.storage.database import get_db

    query = ContentQuery(
        source_types=_csv(source_types),
        statuses=[status] if status else None,
        publications=[publication] if publication else None,
        search=search,
        start_date=after_date,
        end_date=before_date,
        limit=min(limit, 100),
        sort_by=sort_by,
        sort_order=sort_order,
        require_summary=False,
    )
    with get_db() as db:
        return runtime.native(ContentQueryService().build_query(db, query).all())


@runtime.tool_boundary
async def get_content(content_id: int) -> ContentResponse:
    """Get one canonical content record by stable ID."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return ContentResponse.model_validate(
            _resource_json(f"/api/v1/contents/{content_id}", f"Content {content_id}")
        )
    from src.services.content_service import ContentService
    from src.storage.database import get_db

    with get_db() as db:
        content = ContentService(db).get(content_id)
        if content is None:
            raise runtime.ResourceNotFoundError(f"Content {content_id} not found")
        return ContentResponse.model_validate(content)


@runtime.tool_boundary
async def search_content(
    query: str,
    search_type: str = "hybrid",
    source_types: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    publications: str | None = None,
    limit: int = 20,
) -> SearchResponse:
    """Search content using the canonical hybrid search service."""
    body = {
        "query": query,
        "type": search_type,
        "filters": {
            key: value
            for key, value in {
                "source_types": _csv(source_types),
                "date_from": date_from,
                "date_to": date_to,
                "publications": _csv(publications),
            }.items()
            if value is not None
        }
        or None,
        "limit": min(limit, 100),
    }
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return SearchResponse.model_validate(
            runtime.request_json("POST", "/api/v1/search", json=body)
        )
    from src.models.search import SearchQuery
    from src.services.search import HybridSearchService
    from src.storage.database import get_db

    with get_db() as db:
        return await HybridSearchService(session=db).search(SearchQuery(**body))


async def _resource_get(path: str, model: type[Any], resource_id: int) -> Any:
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return runtime.request_json("GET", path)
    from src.storage.database import get_db

    with get_db() as db:
        value = db.get(model, resource_id)
        if value is None:
            raise ValueError(f"{model.__name__} {resource_id} not found")
        return runtime.native(value)


@runtime.tool_boundary
async def get_summary(summary_id: int) -> Any:
    from src.models.summary import Summary

    return await _resource_get(f"/api/v1/summaries/{summary_id}", Summary, summary_id)


@runtime.tool_boundary
async def get_digest(digest_id: int) -> DigestResource:
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return DigestResource.model_validate(
            _resource_json(f"/api/v1/digests/{digest_id}", f"Digest {digest_id}")
        )
    from src.services.review_service import ReviewService

    digest = await ReviewService().get_digest(digest_id)
    if digest is None:
        raise runtime.ResourceNotFoundError(f"Digest {digest_id} not found")
    if digest.digest_type is None or digest.status is None:
        raise RuntimeError(f"Digest {digest_id} has incomplete persisted metadata")
    return DigestResource(
        id=digest.id,
        digest_type=digest.digest_type.value,
        title=digest.title,
        period_start=digest.period_start,
        period_end=digest.period_end,
        status=digest.status.value,
        created_at=digest.created_at,
        completed_at=digest.completed_at,
        markdown_content=digest.markdown_content,
        source_content_ids=digest.source_content_ids,
        revision_count=digest.revision_count or 0,
    )


@runtime.tool_boundary
async def get_podcast_script(script_id: int) -> PodcastScriptResource:
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return PodcastScriptResource.model_validate(
            _resource_json(f"/api/v1/scripts/{script_id}", f"Podcast script {script_id}")
        )
    from src.services.script_review_service import ScriptReviewService

    try:
        result = ScriptReviewService().get_script_for_review(script_id)
    except ValueError as exc:
        raise runtime.ResourceNotFoundError(f"Podcast script {script_id} not found") from exc
    return PodcastScriptResource.model_validate(result)


@runtime.tool_boundary
async def list_digests(
    digest_type: str | None = None, status: str | None = None, limit: int = 10
) -> Any:
    params = {
        key: value
        for key, value in {"digest_type": digest_type, "status": status, "limit": limit}.items()
        if value is not None
    }
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return runtime.request_json("GET", "/api/v1/digests", params=params)
    from src.models.digest import Digest, DigestStatus, DigestType
    from src.storage.database import get_db

    with get_db() as db:
        query = db.query(Digest).order_by(Digest.created_at.desc())
        if digest_type:
            query = query.filter(Digest.digest_type == DigestType(digest_type))
        if status:
            query = query.filter(Digest.status == DigestStatus(status))
        return runtime.native(query.limit(limit).all())


TOOLS = (search_content, get_content, get_digest, get_podcast_script)
