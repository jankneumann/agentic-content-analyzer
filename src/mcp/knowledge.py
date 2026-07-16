"""Knowledge graph, knowledge base, and reference MCP tools."""

from __future__ import annotations

from typing import Any, Literal

from src.mcp import runtime


@runtime.tool_boundary
async def search_knowledge_graph(query: str, limit: int = 10) -> Any:
    """Search graph entities and relationships."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return runtime.request_json(
            "POST", "/api/v1/graph/query", json={"query": query, "limit": limit}
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
    return {"entities": entities, "relationships": relationships}


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
    content_ids: list[int] | None = None,
    since: str | None = None,
    until: str | None = None,
    batch_size: int = 50,
) -> Any:
    """Extract and persist references in a bounded batch."""
    if content_ids is None and since is None:
        raise ValueError("Provide content_ids or since")
    if content_ids is not None and (since is not None or until is not None):
        raise ValueError("content_ids and since/until are mutually exclusive")
    body = {
        key: value
        for key, value in {
            "content_ids": content_ids,
            "since": since,
            "until": until,
            "batch_size": batch_size,
        }.items()
        if value is not None
    }
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return runtime.request_json("POST", "/api/v1/references/extract", json=body)
    from src.models.content import Content
    from src.services.reference_extractor import ReferenceExtractor
    from src.storage.database import get_db

    extractor = ReferenceExtractor()
    with get_db() as db:
        query = db.query(Content).order_by(Content.ingested_at.asc(), Content.id.asc())
        if content_ids:
            query = query.filter(Content.id.in_(content_ids))
        if since:
            query = query.filter(Content.ingested_at >= since)
        if until:
            query = query.filter(Content.ingested_at <= until)
        rows = query.limit(batch_size + 1).all()
        has_more = len(rows) > batch_size
        rows = rows[:batch_size]
        extracted = 0
        per_content = []
        for content in rows:
            references = extractor.extract_from_content(content, db)
            if content.id is None:
                raise ValueError("Persisted content is missing an ID")
            stored = extractor.store_references(content.id, references, db) if references else 0
            extracted += stored
            per_content.append({"content_id": content.id, "references_found": len(references)})
    return {
        "references_extracted": extracted,
        "content_processed": len(rows),
        "has_more": has_more,
        "per_content": per_content,
    }


@runtime.tool_boundary
async def resolve_references(batch_size: int = 100) -> Any:
    """Resolve persisted references in a bounded batch."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return runtime.request_json(
            "POST", "/api/v1/references/resolve", json={"batch_size": batch_size}
        )
    from src.models.content_reference import ContentReference, ResolutionStatus
    from src.services.reference_resolver import ReferenceResolver
    from src.storage.database import get_db

    with get_db() as db:
        resolved = ReferenceResolver(db).resolve_batch(batch_size)
        remaining = (
            db.query(ContentReference)
            .filter(ContentReference.resolution_status == ResolutionStatus.UNRESOLVED)
            .count()
        )
    return {
        "resolved_count": int(resolved),
        "still_unresolved_count": remaining,
        "has_more": remaining > 0,
    }


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
    search_knowledge_base,
    get_topic,
    get_kb_index,
    compile_knowledge_base,
    get_content_references,
    extract_references,
    resolve_references,
    ingest_reference,
)
