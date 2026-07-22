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

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from src.api.dependencies import verify_admin_key
from src.api.middleware.audit import audited
from src.api.schemas.references import (
    ReferencesExtractRequest,
    ReferencesExtractResponse,
    ReferencesResolveRequest,
    ReferencesResolveResponse,
    problem_detail,
)
from src.services.reference_workflow_service import (
    REFERENCE_BATCH_TIMEOUT_S,
    ReferenceWorkflowService,
)

router = APIRouter(
    prefix="/api/v1/references",
    tags=["references"],
    dependencies=[Depends(verify_admin_key)],
)


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


_reference_workflows = ReferenceWorkflowService()
_run_extraction = _reference_workflows.extract
_run_resolution = _reference_workflows.resolve


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
