"""Digest and podcast review MCP tools."""

from __future__ import annotations

from typing import Any, Literal

from src.mcp_tools import runtime


@runtime.tool_boundary
async def list_pending_reviews() -> Any:
    """List digests awaiting human review."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return runtime.request_json("GET", "/api/v1/digests", params={"status": "PENDING_REVIEW"})
    from src.services.review_service import ReviewService

    return runtime.native(await ReviewService().list_pending_reviews())


@runtime.tool_boundary
async def finalize_review(
    digest_id: int,
    action: Literal["approve", "reject", "request_revision"],
    reviewer: str = "mcp-agent",
    review_notes: str | None = None,
) -> Any:
    """Submit an explicit review decision for a digest."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return runtime.request_json(
            "POST",
            f"/api/v1/digests/{digest_id}/review",
            json={
                "action": action,
                "reviewer": reviewer,
                "notes": review_notes,
            },
        )
    from src.services.review_service import ReviewService

    result = await ReviewService().finalize_review(
        digest_id=digest_id,
        action="save-draft" if action == "request_revision" else action,
        revision_history=None,
        reviewer=reviewer,
        review_notes=review_notes,
    )
    if result.id is None or result.status is None or result.reviewed_at is None:
        raise RuntimeError("Review service returned an incomplete persisted digest")
    return {
        "digest_id": result.id,
        "status": result.status.value,
        "reviewed_by": result.reviewed_by,
        "reviewed_at": result.reviewed_at.isoformat(),
    }


@runtime.tool_boundary
async def list_pending_podcast_reviews() -> Any:
    """List podcast scripts awaiting human review."""
    if runtime.transport_mode() is runtime.TransportMode.HTTP:
        return runtime.request_json("GET", "/api/v1/scripts/pending-review")
    from src.services.script_review_service import ScriptReviewService

    return runtime.native(await ScriptReviewService().list_pending_reviews())


TOOLS = (finalize_review,)
