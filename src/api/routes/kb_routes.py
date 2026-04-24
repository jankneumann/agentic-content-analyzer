"""``GET/POST /api/v1/kb/lint*`` — KB health check and auto-fix.

The existing ``src/api/kb_routes.py`` module owns topic CRUD, compile, and
Q&A. This module hosts the ``cloud-db-source-of-truth`` additions: the
read-only lint scan and the audited fix endpoint.

Quantitative thresholds (per ``specs/knowledge-base/spec.md``):

- **stale**: ``last_compiled_at < now - 30 days`` (configurable via
  ``KB_LINT_STALE_DAYS``).
- **orphaned**: ``source_content_ids`` is empty **AND** the topic has zero
  outbound graph relationships (we proxy graph-degree with the count of
  ``related_topic_ids`` because the KB graph syncs related edges from the
  graph back into this list).
- **score_anomaly**: a topic whose ``relevance_score`` is more than 3 sigma from
  the category mean, requiring a minimum sample of 10 topics in that
  category (below the threshold we skip rather than emit noise).
"""

from __future__ import annotations

import math
import os
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.api.dependencies import verify_admin_key
from src.api.middleware.audit import audited
from src.api.schemas.kb import (
    CorrectionApplied,
    KBLintFixResponse,
    KBLintIssueType,
    KBLintResponse,
    LintIssue,
)
from src.models.topic import Topic, TopicStatus
from src.storage.database import get_db

router = APIRouter(
    prefix="/api/v1/kb",
    tags=["knowledge-base"],
    dependencies=[Depends(verify_admin_key)],
)


_MIN_CATEGORY_SAMPLE = 10
_SIGMA_THRESHOLD = 3.0


def _stale_threshold_days() -> int:
    """Read the staleness threshold in days (default 30)."""
    raw = os.getenv("KB_LINT_STALE_DAYS", "30")
    try:
        value = int(raw)
    except ValueError:
        return 30
    return value if value > 0 else 30


def _as_aware(dt: datetime | None) -> datetime | None:
    """Ensure a datetime is timezone-aware (UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _scan_stale(db: Session, threshold: timedelta) -> list[LintIssue]:
    now = datetime.now(UTC)
    cutoff = now - threshold
    rows = (
        db.query(Topic)
        .filter(Topic.status.notin_([TopicStatus.ARCHIVED, TopicStatus.MERGED]))
        .all()
    )
    issues: list[LintIssue] = []
    for topic in rows:
        ts = _as_aware(topic.last_compiled_at)
        if ts is None or ts < cutoff:
            detail = (
                f"last_compiled_at is {ts.isoformat() if ts else 'null'}"
                f" (threshold {cutoff.isoformat()})"
            )
            issues.append(
                LintIssue(
                    slug=topic.slug,
                    issue_type=KBLintIssueType.STALE,
                    detail=detail,
                )
            )
    return issues


def _scan_orphaned(db: Session) -> list[LintIssue]:
    rows = (
        db.query(Topic)
        .filter(Topic.status.notin_([TopicStatus.ARCHIVED, TopicStatus.MERGED]))
        .all()
    )
    issues: list[LintIssue] = []
    for topic in rows:
        refs = list(topic.source_content_ids or [])
        related = list(topic.related_topic_ids or [])
        if not refs and not related:
            issues.append(
                LintIssue(
                    slug=topic.slug,
                    issue_type=KBLintIssueType.ORPHANED,
                    detail="zero source_content_ids and zero related_topic_ids",
                )
            )
    return issues


def _scan_score_anomalies(db: Session) -> list[LintIssue]:
    rows = (
        db.query(Topic)
        .filter(Topic.status.notin_([TopicStatus.ARCHIVED, TopicStatus.MERGED]))
        .all()
    )
    by_category: dict[str, list[Topic]] = {}
    for topic in rows:
        by_category.setdefault(topic.category or "__uncat__", []).append(topic)

    issues: list[LintIssue] = []
    for category, topics in by_category.items():
        if len(topics) < _MIN_CATEGORY_SAMPLE:
            continue
        scores = [float(t.relevance_score or 0.0) for t in topics]
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        stdev = math.sqrt(variance)
        if stdev <= 0:
            continue
        for topic in topics:
            value = float(topic.relevance_score or 0.0)
            z = abs(value - mean) / stdev
            if z > _SIGMA_THRESHOLD:
                issues.append(
                    LintIssue(
                        slug=topic.slug,
                        issue_type=KBLintIssueType.SCORE_ANOMALY,
                        detail=(
                            f"relevance_score={value:.3f} (category={category},"
                            f" mean={mean:.3f}, stdev={stdev:.3f}, z={z:.2f})"
                        ),
                    )
                )
    return issues


@router.get("/lint", response_model=KBLintResponse)
async def lint_knowledge_base() -> KBLintResponse:
    """Read-only scan of KB health. No DB mutations occur."""
    threshold = timedelta(days=_stale_threshold_days())
    with get_db() as db:
        stale = _scan_stale(db, threshold)
        orphaned = _scan_orphaned(db)
        anomalies = _scan_score_anomalies(db)

    return KBLintResponse(
        stale_topics=stale,
        orphaned_topics=orphaned,
        score_anomalies=anomalies,
    )


@router.post("/lint/fix", response_model=KBLintFixResponse)
@audited(operation="kb.lint.fix")
async def apply_knowledge_base_lint_fix(request: Request) -> KBLintFixResponse:
    """Apply auto-corrections to lint issues.

    Currently applies two fix types:
    - ``status:archived`` — archive orphaned topics (zero refs + zero related)
    - ``status:stale`` — mark topics as ``stale`` when their last compile is
      older than threshold AND their current status is ``ACTIVE``.
    """
    threshold = timedelta(days=_stale_threshold_days())
    corrections: list[CorrectionApplied] = []

    with get_db() as db:
        orphaned = _scan_orphaned(db)
        orphan_slugs = {issue.slug for issue in orphaned}
        if orphan_slugs:
            topics = (
                db.query(Topic)
                .filter(Topic.slug.in_(orphan_slugs))
                .filter(Topic.status != TopicStatus.ARCHIVED)
                .all()
            )
            for topic in topics:
                before = str(topic.status)
                topic.status = TopicStatus.ARCHIVED
                corrections.append(
                    CorrectionApplied(
                        slug=topic.slug,
                        fix_type="status:archived",
                        before=before,
                        after=TopicStatus.ARCHIVED.value,
                    )
                )

        stale = _scan_stale(db, threshold)
        stale_slugs = {issue.slug for issue in stale} - orphan_slugs
        if stale_slugs:
            topics = (
                db.query(Topic)
                .filter(Topic.slug.in_(stale_slugs))
                .filter(Topic.status == TopicStatus.ACTIVE)
                .all()
            )
            for topic in topics:
                before = str(topic.status)
                topic.status = TopicStatus.STALE
                corrections.append(
                    CorrectionApplied(
                        slug=topic.slug,
                        fix_type="status:stale",
                        before=before,
                        after=TopicStatus.STALE.value,
                    )
                )

        if corrections:
            db.commit()

    # IR-007: structured audit notes so the audit_log row records zero-diff runs
    # and correction counts (spec knowledge-base §"POST lint/fix when no
    # corrections are needed" expects the audit row to note the zero-diff case).
    request.state.audit_notes = {
        "corrections_applied": len(corrections),
        "zero_diff": len(corrections) == 0,
    }

    return KBLintFixResponse(corrections_applied=corrections)
