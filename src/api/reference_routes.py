"""Reference tracking API routes.

Provides endpoints for listing outgoing references (citations FROM a content item)
and incoming references (citations TO a content item).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import verify_admin_key
from src.models.content_reference import (
    ContentReference,
    ReferenceListResponse,
    ReferenceResponse,
    ResolutionStatus,
)
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/contents",
    tags=["references"],
    dependencies=[Depends(verify_admin_key)],
)


@router.get("/{content_id}/references", response_model=ReferenceListResponse)
def get_references(
    content_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List references FROM this content (outgoing citations)."""
    with get_db() as db:
        query = db.query(ContentReference).filter(
            ContentReference.source_content_id == content_id,
        )

        total = query.count()
        refs = (
            query.order_by(ContentReference.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        items = []
        for ref in refs:
            item = ReferenceResponse(
                id=ref.id,
                source_content_id=ref.source_content_id,
                reference_type=ref.reference_type,
                target_content_id=ref.target_content_id,
                external_url=ref.external_url,
                external_id=ref.external_id,
                external_id_type=ref.external_id_type,
                resolution_status=ref.resolution_status,
                resolved_at=ref.resolved_at,
                source_chunk_id=ref.source_chunk_id,
                confidence=ref.confidence,
                context_snippet=ref.context_snippet,
                created_at=ref.created_at,
                target_title=ref.target_content.title if ref.target_content else None,
                target_source_type=ref.target_content.source_type.value
                if ref.target_content
                else None,
            )
            items.append(item)

        return ReferenceListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get("/{content_id}/cited-by", response_model=ReferenceListResponse)
def get_cited_by(
    content_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List references TO this content (incoming citations)."""
    with get_db() as db:
        query = db.query(ContentReference).filter(
            ContentReference.target_content_id == content_id,
            ContentReference.resolution_status == ResolutionStatus.RESOLVED,
        )

        total = query.count()
        refs = (
            query.order_by(ContentReference.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        items = []
        for ref in refs:
            item = ReferenceResponse(
                id=ref.id,
                source_content_id=ref.source_content_id,
                reference_type=ref.reference_type,
                target_content_id=ref.target_content_id,
                external_url=ref.external_url,
                external_id=ref.external_id,
                external_id_type=ref.external_id_type,
                resolution_status=ref.resolution_status,
                resolved_at=ref.resolved_at,
                source_chunk_id=ref.source_chunk_id,
                confidence=ref.confidence,
                context_snippet=ref.context_snippet,
                created_at=ref.created_at,
                target_title=ref.target_content.title if ref.target_content else None,
                target_source_type=ref.target_content.source_type.value
                if ref.target_content
                else None,
            )
            items.append(item)

        return ReferenceListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
