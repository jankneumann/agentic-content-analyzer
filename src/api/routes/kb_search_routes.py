"""``GET /api/v1/kb/search`` — full-text topic search across the compiled KB.

The handler ranks topics against a simple tokenized score against the
``name``, ``summary``, and ``article_md`` columns. Every returned row has a
non-null ``last_compiled_at`` — per OpenAPI the field is required, so we
fall back to ``updated_at`` or ``created_at`` for topics that have never been
compiled rather than emitting null. Rows with no valid timestamp are filtered
out before the response is serialized.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import verify_admin_key
from src.api.schemas.kb import KBSearchResponse, TopicSearchResult
from src.models.topic import Topic, TopicStatus
from src.storage.database import get_db

router = APIRouter(
    prefix="/api/v1/kb",
    tags=["knowledge-base"],
    dependencies=[Depends(verify_admin_key)],
)


def _extract_excerpt(topic: Topic, needle: str) -> str:
    """Return a short excerpt, preferring the first match location in body text."""
    body = (topic.article_md or topic.summary or "") or ""
    if not body:
        return topic.name or ""
    if not needle:
        return body[:200]
    lower = body.lower()
    pos = lower.find(needle.lower())
    if pos < 0:
        return body[:200]
    start = max(pos - 50, 0)
    end = min(pos + len(needle) + 150, len(body))
    snippet = body[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(body):
        snippet = snippet + "…"
    return snippet


def _score_topic(topic: Topic, needle: str) -> float:
    """Compute a simple match score in [0, 1]. Higher is better."""
    needle_low = needle.lower().strip()
    if not needle_low:
        return 0.0

    score = 0.0
    name = (topic.name or "").lower()
    slug = (topic.slug or "").lower()
    summary = (topic.summary or "").lower()
    article = (topic.article_md or "").lower()

    if needle_low in name:
        score += 0.6
    if needle_low in slug:
        score += 0.2
    if needle_low in summary:
        score += 0.15
    if needle_low in article:
        # Article can dominate due to length — cap its contribution.
        hits = min(article.count(needle_low), 5)
        score += 0.05 * hits

    # Combine with the intrinsic relevance score as a tiebreaker.
    relevance = float(topic.relevance_score or 0.0)
    score += 0.1 * relevance

    if score > 1.0:
        score = 1.0
    return score


def _resolve_last_compiled_at(topic: Topic) -> datetime | None:
    """Return the best available timestamp for ``last_compiled_at``.

    Order: ``last_compiled_at`` → ``updated_at`` → ``created_at``. When none
    exist the row is dropped by the caller (OpenAPI requires non-null).
    """
    for candidate in (topic.last_compiled_at, topic.updated_at, topic.created_at):
        if candidate is not None:
            return candidate  # type: ignore[return-value]
    return None


@router.get("/search", response_model=KBSearchResponse)
async def search_knowledge_base(
    q: str = Query(..., min_length=1, description="Full-text query"),
    limit: int = Query(default=20, ge=1, le=100),
) -> KBSearchResponse:
    """Search compiled KB topics by name/summary/article text."""
    needle = q.strip()
    needle_like = f"%{needle}%"

    with get_db() as db:
        # Narrow the candidate set with a single ILIKE sweep; score + rank in Python.
        candidates: list[Any] = (
            db.query(Topic)
            .filter(
                Topic.status.notin_([TopicStatus.ARCHIVED, TopicStatus.MERGED]),
            )
            .filter(
                (Topic.name.ilike(needle_like))
                | (Topic.slug.ilike(needle_like))
                | (Topic.summary.ilike(needle_like))
                | (Topic.article_md.ilike(needle_like)),
            )
            .all()
        )

    ranked: list[tuple[float, Topic]] = []
    for topic in candidates:
        score = _score_topic(topic, needle)
        if score <= 0.0:
            continue
        ranked.append((score, topic))

    ranked.sort(key=lambda pair: pair[0], reverse=True)
    total = len(ranked)

    results: list[TopicSearchResult] = []
    for score, topic in ranked[:limit]:
        last_compiled = _resolve_last_compiled_at(topic)
        if last_compiled is None:
            # OpenAPI marks last_compiled_at as required — skip malformed rows
            # rather than emit nulls.
            continue
        results.append(
            TopicSearchResult(
                slug=topic.slug,
                title=topic.name,
                score=round(score, 6),
                excerpt=_extract_excerpt(topic, needle),
                last_compiled_at=last_compiled,
            )
        )

    return KBSearchResponse(topics=results, total_count=total)
