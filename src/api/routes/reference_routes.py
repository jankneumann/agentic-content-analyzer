"""``POST /api/v1/references/{extract,resolve}`` — bounded-batch extraction
and resolution endpoints for content references.

Both handlers are audited (`references.extract` / `references.resolve`) and
wrap their work in a 60-second `asyncio.wait_for` window. On timeout we
return ``504 Gateway Timeout`` with an RFC 7807 Problem body (design.md
D11). Extractor / resolver calls are sync — we run them inside a thread via
``asyncio.to_thread`` so the timeout actually cancels them.

The module is distinct from the existing ``src/api/reference_routes.py``
(which hosts ``/api/v1/contents/{id}/references`` — unrelated scope).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.api.dependencies import verify_admin_key
from src.api.middleware.audit import audited
from src.api.schemas.references import (
    PerContentItem,
    ReferencesExtractRequest,
    ReferencesExtractResponse,
    ReferencesResolveRequest,
    ReferencesResolveResponse,
    problem_detail,
)
from src.models.content import Content
from src.models.content_reference import ContentReference, ResolutionStatus
from src.storage.database import get_db

router = APIRouter(
    prefix="/api/v1/references",
    tags=["references"],
    dependencies=[Depends(verify_admin_key)],
)


REFERENCE_BATCH_TIMEOUT_S = 60.0

# Threshold above which we OMIT per_content enrichment to keep the response small.
_PER_CONTENT_MAX = 100


def _timeout_response(*, operation: str) -> JSONResponse:
    body = problem_detail(
        title="Gateway Timeout",
        status=504,
        detail=f"{operation} exceeded {int(REFERENCE_BATCH_TIMEOUT_S)}s timeout",
    )
    return JSONResponse(
        status_code=504,
        content=body,
        media_type="application/problem+json",
    )


def _select_contents(
    db: Session,
    *,
    content_ids: list[int] | None,
    since: datetime | None,
    until: datetime | None,
    batch_size: int,
) -> list[Content]:
    """Resolve the target contents for an extraction call."""
    if content_ids:
        return (
            db.query(Content)
            .filter(Content.id.in_(content_ids))
            .order_by(Content.ingested_at.asc(), Content.id.asc())
            .all()
        )

    query = db.query(Content)
    if since is not None:
        query = query.filter(Content.ingested_at >= since)
    if until is not None:
        query = query.filter(Content.ingested_at <= until)
    return (
        query.order_by(Content.ingested_at.asc(), Content.id.asc())
        .limit(batch_size + 1)  # +1 so we can detect has_more cheaply
        .all()
    )


def _run_extraction(
    *,
    content_ids: list[int] | None,
    since: datetime | None,
    until: datetime | None,
    batch_size: int,
) -> dict[str, Any]:
    """Synchronous extraction path — invoked via ``asyncio.to_thread``."""
    from src.services.reference_extractor import ReferenceExtractor

    extractor = ReferenceExtractor()

    with get_db() as db:
        selected = _select_contents(
            db,
            content_ids=content_ids,
            since=since,
            until=until,
            batch_size=batch_size,
        )
        # For the date-range form, ``selected`` may hold up to batch_size + 1
        # rows — peel off the overflow and use it as the has_more signal.
        has_more = False
        next_cursor: datetime | None = None
        if content_ids is None and len(selected) > batch_size:
            has_more = True
            # We processed exactly batch_size items; the (batch_size+1)th is
            # the anchor for the next call.
            overflow = selected[batch_size]
            processed = selected[:batch_size]
            next_cursor = overflow.ingested_at
            if next_cursor is not None and next_cursor.tzinfo is None:
                next_cursor = next_cursor.replace(tzinfo=UTC)
        else:
            processed = selected
            if content_ids is not None and len(selected) < len(content_ids):
                # Some IDs were invalid/missing — don't flag has_more for that.
                has_more = False

        per_content: list[PerContentItem] = []
        total_refs = 0
        for content in processed:
            refs = extractor.extract_from_content(content, db)
            stored = extractor.store_references(content.id, refs, db) if refs else 0
            total_refs += stored
            per_content.append(
                PerContentItem(content_id=content.id, references_found=stored),
            )

    return {
        "references_extracted": total_refs,
        "content_processed": len(per_content),
        "has_more": has_more,
        "next_cursor": next_cursor,
        "per_content": per_content,
    }


def _run_resolution(*, batch_size: int) -> dict[str, Any]:
    """Synchronous resolve path — invoked via ``asyncio.to_thread``."""
    from src.services.reference_resolver import ReferenceResolver

    with get_db() as db:
        resolver = ReferenceResolver(db)
        resolved = resolver.resolve_batch(batch_size=batch_size)
        unresolved_remaining = (
            db.query(ContentReference)
            .filter(ContentReference.resolution_status == ResolutionStatus.UNRESOLVED)
            .count()
        )

    return {
        "resolved_count": int(resolved),
        "still_unresolved_count": int(unresolved_remaining),
        "has_more": unresolved_remaining > 0,
    }


@router.post("/extract", response_model=ReferencesExtractResponse)
@audited(operation="references.extract")
async def extract_references(
    body: ReferencesExtractRequest,
    request: Request,
) -> ReferencesExtractResponse | JSONResponse:
    del request  # used by @audited
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                _run_extraction,
                content_ids=body.content_ids,
                since=body.since,
                until=body.until,
                batch_size=body.batch_size,
            ),
            timeout=REFERENCE_BATCH_TIMEOUT_S,
        )
    except TimeoutError:
        return _timeout_response(operation="references.extract")

    per_content = result["per_content"]
    # Omit per_content on very large batches to keep the payload bounded.
    emit_per_content = len(per_content) <= _PER_CONTENT_MAX
    return ReferencesExtractResponse(
        references_extracted=result["references_extracted"],
        content_processed=result["content_processed"],
        has_more=result["has_more"],
        next_cursor=result["next_cursor"] if result["has_more"] else None,
        per_content=per_content if emit_per_content else None,
    )


@router.post("/resolve", response_model=ReferencesResolveResponse)
@audited(operation="references.resolve")
async def resolve_references(
    request: Request,
    body: ReferencesResolveRequest | None = None,
) -> ReferencesResolveResponse | JSONResponse:
    del request  # used by @audited
    effective = body or ReferencesResolveRequest()
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_run_resolution, batch_size=effective.batch_size),
            timeout=REFERENCE_BATCH_TIMEOUT_S,
        )
    except TimeoutError:
        return _timeout_response(operation="references.resolve")

    return ReferencesResolveResponse(**result)
