"""Share management API routes.

Enables sharing, gets share status, and disables sharing for
content, summaries, and digests. All endpoints require authentication.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.dependencies import verify_admin_key
from src.models.content import Content, ShareResponse
from src.models.digest import Digest
from src.models.summary import Summary
from src.storage.database import get_db
from src.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1",
    tags=["sharing"],
    dependencies=[Depends(verify_admin_key)],
)

# Map resource type to ORM model and URL path segment
_RESOURCE_MAP: dict[str, tuple[type, str]] = {
    "contents": (Content, "content"),
    "summaries": (Summary, "summary"),
    "digests": (Digest, "digest"),
}


def _build_share_url(request: Request, resource_path: str, token: str) -> str:
    """Build the public share URL from the request context."""
    base = str(request.base_url).rstrip("/")
    return f"{base}/shared/{resource_path}/{token}"


def _get_record(db, model: type, record_id: int):
    """Fetch a record by ID or raise 404."""
    record = db.query(model).filter(model.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return record


@router.post("/{resource}/{record_id}/share", response_model=ShareResponse)
async def enable_sharing(
    resource: str,
    record_id: int,
    request: Request,
) -> ShareResponse:
    """Enable sharing for a resource. Generates a share token if one doesn't exist."""
    if resource not in _RESOURCE_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown resource type: {resource}")

    model, url_path = _RESOURCE_MAP[resource]

    with get_db() as db:
        record = _get_record(db, model, record_id)

        if not record.share_token:
            record.share_token = str(uuid4())
        record.is_public = True

        share_url = _build_share_url(request, url_path, record.share_token)

    logger.info("Sharing enabled for %s/%s", resource, record_id)
    return ShareResponse(
        is_public=True,
        share_token=record.share_token,
        share_url=share_url,
    )


@router.get("/{resource}/{record_id}/share", response_model=ShareResponse)
async def get_share_status(
    resource: str,
    record_id: int,
    request: Request,
) -> ShareResponse:
    """Get the current sharing status of a resource."""
    if resource not in _RESOURCE_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown resource type: {resource}")

    model, url_path = _RESOURCE_MAP[resource]

    with get_db() as db:
        record = _get_record(db, model, record_id)

        share_url = None
        if record.share_token:
            share_url = _build_share_url(request, url_path, record.share_token)

    return ShareResponse(
        is_public=record.is_public,
        share_token=record.share_token,
        share_url=share_url,
    )


@router.delete("/{resource}/{record_id}/share", response_model=ShareResponse)
async def disable_sharing(
    resource: str,
    record_id: int,
) -> ShareResponse:
    """Disable sharing for a resource. Preserves token for re-enabling."""
    if resource not in _RESOURCE_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown resource type: {resource}")

    model, _url_path = _RESOURCE_MAP[resource]

    with get_db() as db:
        record = _get_record(db, model, record_id)
        record.is_public = False

    logger.info("Sharing disabled for %s/%s", resource, record_id)
    return ShareResponse(
        is_public=False,
        share_token=record.share_token,
        share_url=None,
    )
