"""Search API routes for hybrid document search.

Provides GET (simple queries) and POST (complex queries with filters)
endpoints for searching across all ingested content using BM25,
vector, or hybrid search methods.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from src.api.dependencies import verify_admin_key
from src.models.search import (
    ChunkContentInfo,
    ChunkDetail,
    SearchFilter,
    SearchQuery,
    SearchResponse,
    SearchType,
)
from src.services.search import HybridSearchService
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/search",
    tags=["search"],
    dependencies=[Depends(verify_admin_key)],
)


@router.get("", response_model=SearchResponse)
async def search_get(
    q: str = Query(..., min_length=1, description="Search query text"),
    type: SearchType = Query(default=SearchType.HYBRID, description="Search method"),
    limit: int = Query(default=20, ge=1, le=100, description="Results per page"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    source_type: list[str] | None = Query(default=None, description="Filter by source types"),
    date_from: datetime | None = Query(default=None, description="Filter: published after"),
    date_to: datetime | None = Query(default=None, description="Filter: published before"),
    publication: list[str] | None = Query(default=None, description="Filter by publications"),
) -> SearchResponse:
    """Simple search via query parameters.

    Supports basic filtering via query params. For complex filters
    with weights and chunk_type filtering, use POST /api/v1/search.
    """
    filters = None
    if source_type or date_from or date_to or publication:
        filters = SearchFilter(
            source_types=source_type,
            date_from=date_from,
            date_to=date_to,
            publications=publication,
        )

    query = SearchQuery(
        query=q,
        type=type,
        filters=filters,
        limit=limit,
        offset=offset,
    )

    with get_db() as db:
        service = HybridSearchService(session=db)
        return await service.search(query)


@router.post("", response_model=SearchResponse)
async def search_post(
    query: SearchQuery,
) -> SearchResponse:
    """Advanced search with full filter and weight control.

    Accepts a JSON body with query, type, filters, weights,
    and pagination parameters.
    """
    with get_db() as db:
        service = HybridSearchService(session=db)
        return await service.search(query)


@router.get("/chunks/{chunk_id}", response_model=ChunkDetail)
async def get_chunk(
    chunk_id: int,
) -> ChunkDetail:
    """Retrieve a single chunk by ID with its content metadata."""
    with get_db() as db:
        stmt = text("""
            SELECT
                dc.id as chunk_id,
                dc.content_id,
                dc.chunk_text,
                dc.chunk_index,
                dc.section_path,
                dc.heading_text,
                dc.chunk_type,
                dc.page_number,
                dc.start_char,
                dc.end_char,
                dc.timestamp_start,
                dc.timestamp_end,
                dc.deep_link_url,
                dc.created_at,
                c.title as content_title,
                c.source_type,
                c.publication,
                c.published_date,
                c.source_url
            FROM document_chunks dc
            JOIN contents c ON c.id = dc.content_id
            WHERE dc.id = :chunk_id
        """)
        result = db.execute(stmt, {"chunk_id": chunk_id})
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Chunk not found")

    return ChunkDetail(
        chunk_id=row.chunk_id,
        content_id=row.content_id,
        chunk_text=row.chunk_text,
        chunk_index=row.chunk_index,
        section_path=row.section_path,
        heading_text=row.heading_text,
        chunk_type=row.chunk_type,
        page_number=row.page_number,
        start_char=row.start_char,
        end_char=row.end_char,
        timestamp_start=row.timestamp_start,
        timestamp_end=row.timestamp_end,
        deep_link_url=row.deep_link_url,
        created_at=row.created_at,
        content=ChunkContentInfo(
            id=row.content_id,
            title=row.content_title,
            source_type=row.source_type,
            publication=row.publication,
            published_date=row.published_date,
            source_url=row.source_url,
        ),
    )
