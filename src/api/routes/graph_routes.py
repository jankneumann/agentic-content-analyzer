"""``POST /api/v1/graph/*`` — graph query and entity-extraction endpoints.

Both endpoints delegate to ``src.storage.graphiti_client.GraphitiClient``.
We wrap each graph call in ``asyncio.wait_for`` — 10s for reads, 30s for
writes — and map ``TimeoutError`` to ``504 Gateway Timeout`` with an RFC
7807 Problem body (per design.md D11).
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from src.api.dependencies import verify_admin_key
from src.api.middleware.audit import audited
from src.api.schemas.graph import (
    GraphEntity,
    GraphExtractRequest,
    GraphExtractResponse,
    GraphQueryRequest,
    GraphQueryResponse,
    GraphRelationship,
)
from src.api.schemas.references import problem_detail
from src.models.content import Content
from src.models.summary import Summary
from src.storage.database import get_db

router = APIRouter(
    prefix="/api/v1/graph",
    tags=["knowledge-graph"],
    dependencies=[Depends(verify_admin_key)],
)


GRAPH_READ_TIMEOUT_S = 10.0
GRAPH_WRITE_TIMEOUT_S = 30.0


def _timeout_response(*, operation: str) -> JSONResponse:
    """Build a 504 Problem response."""
    body = problem_detail(
        title="Gateway Timeout",
        status=504,
        detail=f"{operation} exceeded timeout",
    )
    return JSONResponse(
        status_code=504,
        content=body,
        media_type="application/problem+json",
    )


def _coerce_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _coerce_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _parse_graph_search_results(
    raw: list[Any],
) -> tuple[list[GraphEntity], list[GraphRelationship]]:
    """Translate Graphiti's hit list into the contract shape.

    Graphiti's ``search()`` returns a flat list whose element shape depends on
    the underlying backend. We handle dicts and objects; anything with a
    ``source_node_uuid``/``target_node_uuid`` pair is treated as a relationship
    (edge fact), anything else as an entity.
    """
    entities: list[GraphEntity] = []
    relationships: list[GraphRelationship] = []

    for hit in raw or []:
        if isinstance(hit, dict):
            getter = hit.get
        else:

            def getter(key: str, _obj: Any = hit) -> Any:
                return getattr(_obj, key, None)

        source_id = getter("source_node_uuid") or getter("source_id")
        target_id = getter("target_node_uuid") or getter("target_id")
        if source_id and target_id:
            relationships.append(
                GraphRelationship(
                    source_id=_coerce_str(source_id),
                    target_id=_coerce_str(target_id),
                    type=_coerce_str(getter("name") or getter("type"), default="RELATES_TO"),
                    score=_coerce_float(getter("score")),
                )
            )
            continue

        node_id = getter("uuid") or getter("id")
        if not node_id:
            continue
        entities.append(
            GraphEntity(
                id=_coerce_str(node_id),
                name=_coerce_str(getter("name") or getter("title"), default=""),
                type=_coerce_str(getter("type") or getter("labels") or "Entity", default="Entity"),
                score=_coerce_float(getter("score")),
            )
        )

    return entities, relationships


@router.post("/query", response_model=GraphQueryResponse)
async def query_knowledge_graph(body: GraphQueryRequest) -> GraphQueryResponse | JSONResponse:
    """Semantic read against the knowledge graph with a 10s timeout."""
    from src.storage.graphiti_client import GraphitiClient

    try:
        client = await asyncio.wait_for(
            GraphitiClient.create(),
            timeout=GRAPH_READ_TIMEOUT_S,
        )
    except TimeoutError:
        return _timeout_response(operation="graph.query.connect")
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=502, detail=f"graph backend error: {exc}") from exc

    try:
        try:
            raw = await asyncio.wait_for(
                client.search_related_concepts(body.query, limit=body.limit),
                timeout=GRAPH_READ_TIMEOUT_S,
            )
        except TimeoutError:
            return _timeout_response(operation="graph.query")
    finally:
        try:
            client.close()
        except Exception:  # pragma: no cover - defensive
            pass

    entities, relationships = _parse_graph_search_results(raw)
    return GraphQueryResponse(entities=entities, relationships=relationships)


@router.post("/extract-entities", response_model=GraphExtractResponse)
@audited(operation="graph.extract_entities")
async def extract_graph_entities(
    body: GraphExtractRequest,
    request: Request,
) -> GraphExtractResponse | JSONResponse:
    """Push a content's summary into the knowledge graph (30s timeout)."""
    # IR-007: attach structured audit notes so the audit_log row records which
    # content was operated on (spec knowledge-graph §"Extract entities for
    # existing content" expects `notes.content_id=<id>`).
    request.state.audit_notes = {"content_id": body.content_id}
    from src.storage.graphiti_client import GraphitiClient

    with get_db() as db:
        content = db.query(Content).filter(Content.id == body.content_id).first()
        if content is None:
            raise HTTPException(
                status_code=404,
                detail=f"content {body.content_id} not found",
            )
        summary = (
            db.query(Summary)
            .filter(Summary.content_id == body.content_id)
            .order_by(Summary.created_at.desc())
            .first()
        )
        if summary is None:
            raise HTTPException(
                status_code=409,
                detail="content has no summary; summarize first",
            )
        # Snapshot attributes for use outside the session scope.
        content_snapshot = content
        summary_snapshot = summary

    try:
        client = await asyncio.wait_for(
            GraphitiClient.create(),
            timeout=GRAPH_WRITE_TIMEOUT_S,
        )
    except TimeoutError:
        return _timeout_response(operation="graph.extract_entities.connect")
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=502, detail=f"graph backend error: {exc}") from exc

    try:
        try:
            episode_id = await asyncio.wait_for(
                client.add_content_summary(content_snapshot, summary_snapshot),
                timeout=GRAPH_WRITE_TIMEOUT_S,
            )
        except TimeoutError:
            return _timeout_response(operation="graph.extract_entities")
    finally:
        try:
            client.close()
        except Exception:  # pragma: no cover - defensive
            pass

    # Graphiti's add_episode does not surface per-request entity/relationship
    # counts synchronously — return 0/0 for now; the episode_id is the handle
    # callers use to follow up. Contract allows this.
    return GraphExtractResponse(
        entities_added=0,
        relationships_added=0,
        graph_episode_id=str(episode_id),
    )
