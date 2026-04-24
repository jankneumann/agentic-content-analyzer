"""Pydantic schemas for ``/api/v1/references/*`` endpoints.

Shapes mirror ``contracts/openapi/v1.yaml``. The extract request is modeled as
a single ``BaseModel`` with XOR validation in a ``model_validator`` rather than
a ``oneOf`` RootModel — this plays better with FastAPI's 422 body handling and
keeps the conflict-error message specific.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReferencesExtractRequest(BaseModel):
    """Request body for ``POST /api/v1/references/extract``.

    Either ``content_ids`` **XOR** a date range (``since`` with optional
    ``until``) must be provided — validated below.
    """

    model_config = ConfigDict(extra="forbid")

    content_ids: list[int] | None = Field(default=None, max_length=500, min_length=1)
    since: datetime | None = None
    until: datetime | None = None
    batch_size: int = Field(default=50, ge=1, le=500)

    @model_validator(mode="after")
    def _check_xor(self) -> ReferencesExtractRequest:
        has_ids = self.content_ids is not None
        has_range = self.since is not None or self.until is not None
        if has_ids and has_range:
            raise ValueError(
                "content_ids and since/until are mutually exclusive; provide exactly one form",
            )
        if not has_ids and not has_range:
            raise ValueError(
                "must provide either content_ids or a date range (since required)",
            )
        if has_ids and self.content_ids is not None:
            for cid in self.content_ids:
                if cid < 1:
                    raise ValueError("content_ids entries must be >= 1")
        if has_range and self.since is None:
            raise ValueError("since is required when using the date-range form")
        return self


class PerContentItem(BaseModel):
    content_id: int
    references_found: int


class ReferencesExtractResponse(BaseModel):
    """Response body for ``POST /api/v1/references/extract``."""

    references_extracted: int
    content_processed: int
    has_more: bool
    next_cursor: datetime | None = Field(
        default=None,
        description="When has_more=true, pass this as `since` for the next call.",
    )
    per_content: list[PerContentItem] | None = None


class ReferencesResolveRequest(BaseModel):
    """Request body for ``POST /api/v1/references/resolve`` (all fields optional)."""

    model_config = ConfigDict(extra="forbid")

    batch_size: int = Field(default=100, ge=1, le=1000)


class ReferencesResolveResponse(BaseModel):
    """Response body for ``POST /api/v1/references/resolve``."""

    resolved_count: int
    still_unresolved_count: int
    has_more: bool


def problem_detail(
    *,
    title: str,
    status: int,
    detail: str | None = None,
    type_: str | None = None,
    instance: str | None = None,
) -> dict[str, Any]:
    """Build an RFC 7807 problem detail body."""
    body: dict[str, Any] = {"title": title, "status": status}
    if detail is not None:
        body["detail"] = detail
    if type_ is not None:
        body["type"] = type_
    if instance is not None:
        body["instance"] = instance
    return body
