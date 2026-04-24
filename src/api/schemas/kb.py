"""Pydantic schemas for KB search and lint endpoints.

Shapes mirror ``contracts/openapi/v1.yaml`` for the
``/api/v1/kb/search``, ``/api/v1/kb/lint``, and ``/api/v1/kb/lint/fix`` paths.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class TopicSearchResult(BaseModel):
    """One matched topic from ``GET /api/v1/kb/search``."""

    slug: str = Field(..., examples=["mixture-of-experts"])
    title: str = Field(..., examples=["Mixture of Experts Architecture"])
    score: float = Field(..., examples=[0.87])
    excerpt: str = Field(..., examples=["Sparse MoE models activate only a subset..."])
    last_compiled_at: datetime


class KBSearchResponse(BaseModel):
    """Response body for ``GET /api/v1/kb/search``."""

    topics: list[TopicSearchResult]
    total_count: int = Field(..., examples=[42])


class KBLintIssueType(StrEnum):
    """Category discriminator for lint issues."""

    STALE = "stale"
    ORPHANED = "orphaned"
    SCORE_ANOMALY = "score_anomaly"


class LintIssue(BaseModel):
    """One finding from the KB lint scan."""

    slug: str
    issue_type: KBLintIssueType
    detail: str


class KBLintResponse(BaseModel):
    """Response body for ``GET /api/v1/kb/lint``."""

    stale_topics: list[LintIssue]
    orphaned_topics: list[LintIssue]
    score_anomalies: list[LintIssue]


class CorrectionApplied(BaseModel):
    """One auto-fix entry returned from ``POST /api/v1/kb/lint/fix``."""

    slug: str
    fix_type: str
    before: str | None = None
    after: str | None = None


class KBLintFixResponse(BaseModel):
    """Response body for ``POST /api/v1/kb/lint/fix``."""

    corrections_applied: list[CorrectionApplied]
