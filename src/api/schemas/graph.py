"""Pydantic schemas for graph query and extract-entities endpoints.

Shapes mirror ``contracts/openapi/v1.yaml`` for ``/api/v1/graph/*``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GraphQueryRequest(BaseModel):
    """Request body for ``POST /api/v1/graph/query``."""

    query: str = Field(..., min_length=1, examples=["mixture of experts"])
    limit: int = Field(default=20, ge=1, le=100)


class GraphEntity(BaseModel):
    id: str
    name: str
    type: str = Field(..., examples=["Model"])
    score: float


class GraphRelationship(BaseModel):
    source_id: str
    target_id: str
    type: str = Field(..., examples=["USES"])
    score: float


class GraphQueryResponse(BaseModel):
    """Response body for ``POST /api/v1/graph/query``."""

    entities: list[GraphEntity]
    relationships: list[GraphRelationship]


class GraphExtractRequest(BaseModel):
    """Request body for ``POST /api/v1/graph/extract-entities``."""

    model_config = ConfigDict(extra="forbid")

    content_id: int = Field(..., ge=1, examples=[42])


class GraphExtractResponse(BaseModel):
    """Response body for ``POST /api/v1/graph/extract-entities``."""

    entities_added: int
    relationships_added: int
    graph_episode_id: str
