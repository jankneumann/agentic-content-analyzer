"""Knowledge graph, knowledge base, and reference MCP tools."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field

from src.api.schemas.graph import GraphQueryResponse
from src.api.schemas.references import (
    ReferencesExtractRequest,
    ReferencesExtractResponse,
    ReferencesResolveRequest,
    ReferencesResolveResponse,
)
from src.mcp_tools import runtime


@runtime.tool_boundary
async def search_knowledge_graph(
    query: Annotated[str, Field(min_length=1)],
    limit: Annotated[int, Field(ge=1, le=100)] = 10,
) -> GraphQueryResponse:
    """Search graph entities and relationships."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return GraphQueryResponse.model_validate(
            runtime.request_json(
                "POST", "/api/v1/graph/query", json={"query": query, "limit": limit}
            )
        )
    from src.storage.graphiti_client import GraphitiClient

    client = await GraphitiClient.create()
    try:
        rows = await client.search_related_concepts(query, limit=limit)
    finally:
        client.close()
    entities: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    for row in rows or []:
        value = row if isinstance(row, dict) else vars(row)
        source_id = value.get("source_node_uuid") or value.get("source_id")
        target_id = value.get("target_node_uuid") or value.get("target_id")
        if source_id and target_id:
            relationships.append(
                {
                    "source_id": str(source_id),
                    "target_id": str(target_id),
                    "type": str(value.get("name") or value.get("type") or "RELATES_TO"),
                    "score": float(value.get("score") or 0),
                }
            )
        else:
            entities.append(
                {
                    "id": str(value.get("uuid") or value.get("id") or ""),
                    "name": str(value.get("name") or value.get("title") or ""),
                    "type": str(value.get("type") or value.get("labels") or "Entity"),
                    "score": float(value.get("score") or 0),
                }
            )
    return GraphQueryResponse(entities=entities, relationships=relationships)


@runtime.tool_boundary
async def search_knowledge_base(query: str, limit: int = 20) -> Any:
    """Search compiled knowledge-base topics."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return runtime.request_json("GET", "/api/v1/kb/search", params={"q": query, "limit": limit})
    from src.models.topic import Topic, TopicStatus
    from src.storage.database import get_db

    needle = f"%{query.strip()}%"
    with get_db() as db:
        rows = (
            db.query(Topic)
            .filter(Topic.status.notin_([TopicStatus.ARCHIVED, TopicStatus.MERGED]))
            .filter(
                (Topic.name.ilike(needle))
                | (Topic.slug.ilike(needle))
                | (Topic.summary.ilike(needle))
                | (Topic.article_md.ilike(needle))
            )
            .limit(limit)
            .all()
        )
    topics = [
        {
            "slug": topic.slug,
            "title": topic.name,
            "score": float(topic.relevance_score or 0),
            "excerpt": (topic.summary or topic.article_md or "")[:500],
            "last_compiled_at": runtime.native(
                topic.last_compiled_at or topic.updated_at or topic.created_at
            ),
        }
        for topic in rows
        if topic.last_compiled_at or topic.updated_at or topic.created_at
    ]
    return {"topics": topics, "total_count": len(topics)}


@runtime.tool_boundary
async def get_topic(slug: str) -> Any:
    """Get one compiled knowledge-base topic."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return runtime.request_json("GET", f"/api/v1/kb/topics/{slug}")
    from src.models.topic import Topic
    from src.storage.database import get_db

    with get_db() as db:
        topic = db.query(Topic).filter(Topic.slug == slug).first()
        if topic is None:
            raise ValueError(f"Topic '{slug}' not found")
        return runtime.native(topic)


@runtime.tool_boundary
async def get_kb_index(category: str | None = None) -> Any:
    """Get the generated knowledge-base index."""
    params = {"category": category} if category else None
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return runtime.request_json("GET", "/api/v1/kb/index", params=params)
    from src.models.topic import KBIndex
    from src.storage.database import get_db

    with get_db() as db:
        query = db.query(KBIndex)
        if category:
            query = query.filter(KBIndex.index_type == f"category_{category}")
        return runtime.native(query.all())


@runtime.tool_boundary
async def compile_knowledge_base() -> Any:
    """Compile persisted evidence into knowledge-base topics."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return runtime.request_json("POST", "/api/v1/kb/compile", json={})
    from src.services.knowledge_base import KnowledgeBaseService
    from src.storage.database import get_db

    with get_db() as db:
        return runtime.native(await KnowledgeBaseService(db).compile())


@runtime.tool_boundary
async def get_content_references(
    content_id: int, direction: Literal["outgoing", "incoming"] = "outgoing"
) -> Any:
    """List outgoing citations or incoming cited-by relationships."""
    suffix = "references" if direction == "outgoing" else "cited-by"
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return runtime.request_json("GET", f"/api/v1/contents/{content_id}/{suffix}")
    from src.models.content_reference import ContentReference, ResolutionStatus
    from src.storage.database import get_db

    with get_db() as db:
        if direction == "incoming":
            query = db.query(ContentReference).filter(
                ContentReference.target_content_id == content_id,
                ContentReference.resolution_status == ResolutionStatus.RESOLVED,
            )
        else:
            query = db.query(ContentReference).filter(
                ContentReference.source_content_id == content_id
            )
        references = query.all()
    return {
        "references": runtime.native(references),
        "count": len(references),
        "direction": direction,
    }


@runtime.tool_boundary
async def extract_references(
    content_ids: Annotated[list[int] | None, Field(min_length=1, max_length=500)] = None,
    since: datetime | None = None,
    until: datetime | None = None,
    batch_size: Annotated[int, Field(ge=1, le=500)] = 50,
) -> ReferencesExtractResponse:
    """Extract and persist references in a bounded batch."""
    request = ReferencesExtractRequest(
        content_ids=content_ids,
        since=since,
        until=until,
        batch_size=batch_size,
    )
    body = request.model_dump(mode="json", exclude_none=True)
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return ReferencesExtractResponse.model_validate(
            runtime.request_json("POST", "/api/v1/references/extract", json=body)
        )
    from src.services.reference_workflow_service import (
        REFERENCE_BATCH_TIMEOUT_S,
        ReferenceWorkflowService,
    )

    result = await asyncio.wait_for(
        asyncio.to_thread(
            ReferenceWorkflowService().extract,
            content_ids=request.content_ids,
            since=request.since,
            until=request.until,
            batch_size=request.batch_size,
        ),
        timeout=REFERENCE_BATCH_TIMEOUT_S,
    )
    if len(result["per_content"]) > 100:
        result["per_content"] = None
    if not result["has_more"]:
        result["next_cursor"] = None
    return ReferencesExtractResponse.model_validate(result)


@runtime.tool_boundary
async def resolve_references(
    batch_size: Annotated[int, Field(ge=1, le=1000)] = 100,
) -> ReferencesResolveResponse:
    """Resolve persisted references in a bounded batch."""
    request = ReferencesResolveRequest(batch_size=batch_size)
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return ReferencesResolveResponse.model_validate(
            runtime.request_json(
                "POST",
                "/api/v1/references/resolve",
                json=request.model_dump(mode="json"),
            )
        )
    from src.services.reference_workflow_service import (
        REFERENCE_BATCH_TIMEOUT_S,
        ReferenceWorkflowService,
    )

    result = await asyncio.wait_for(
        asyncio.to_thread(ReferenceWorkflowService().resolve, batch_size=request.batch_size),
        timeout=REFERENCE_BATCH_TIMEOUT_S,
    )
    return ReferencesResolveResponse.model_validate(result)


@runtime.tool_boundary
async def ingest_reference(reference_id: int) -> Any:
    """Explicitly ingest one unresolved structured reference."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        raise runtime.configuration_error(
            "ingest_reference has no declared HTTP operation; use ingest_scholar_paper or ingest_arxiv_paper"
        )
    from src.config.settings import get_settings
    from src.models.content_reference import ContentReference, ResolutionStatus
    from src.services.reference_auto_ingest import AutoIngestTrigger
    from src.storage.database import get_db

    with get_db() as db:
        reference = db.get(ContentReference, reference_id)
        if reference is None:
            raise ValueError(f"Reference {reference_id} not found")
        if reference.resolution_status == ResolutionStatus.RESOLVED:
            return {
                "status": "already_resolved",
                "target_content_id": reference.target_content_id,
            }
        if not reference.external_id or not reference.external_id_type:
            raise ValueError("Reference has no structured ID for ingestion")
        content = await AutoIngestTrigger(
            db=db,
            enabled=True,
            max_depth=get_settings().reference_auto_ingest_max_depth,
        ).maybe_ingest(reference)
        return {
            "status": "ingested" if content else "ingestion_failed",
            "content_id": getattr(content, "id", None),
        }


TOOLS = (
    search_knowledge_graph,
    extract_references,
    resolve_references,
)
