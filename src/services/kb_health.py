"""Knowledge base health checks and linting (D9).

Evaluates the KB for staleness, duplicate topics, coverage gaps, and
article quality. Produces a markdown report and, in ``lint_fix`` mode,
flips stale topics to the ``stale`` status.

Thresholds are driven by settings:
- ``kb_stale_threshold_days`` (default: 30)
- ``kb_merge_similarity_threshold`` (default: 0.90)
- ``kb_min_topics_per_category`` (default: 3)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.models.theme import ThemeCategory
from src.models.topic import Topic, TopicStatus
from src.services.knowledge_base import _article_similarity

logger = logging.getLogger(__name__)


class KBHealthService:
    """Run health checks over the compiled knowledge base.

    Args:
        db: SQLAlchemy session.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def lint(self) -> dict[str, Any]:
        """Run all health checks and return findings + markdown report."""
        findings = self._collect_findings()
        report_md = self._build_report(findings)
        return {
            **findings,
            "report_md": report_md,
        }

    def lint_fix(self) -> dict[str, Any]:
        """Run lint and apply auto-fixes (mark stale topics as stale)."""
        findings = self._collect_findings()
        fixed_count = 0
        if findings["stale"]:
            fixed_slugs = set(findings["stale"])
            stale_topics = self.db.query(Topic).filter(Topic.slug.in_(fixed_slugs)).all()
            for topic in stale_topics:
                if topic.status != TopicStatus.STALE:
                    topic.status = TopicStatus.STALE
                    fixed_count += 1
            self.db.commit()

        report_md = self._build_report(findings, fixed_count=fixed_count)
        return {
            **findings,
            "report_md": report_md,
            "fixed_count": fixed_count,
        }

    # ------------------------------------------------------------------ #
    # Internal collectors
    # ------------------------------------------------------------------ #

    def _collect_findings(self) -> dict[str, Any]:
        """Run every check and return a findings dict."""
        active = (
            self.db.query(Topic)
            .filter(Topic.status.in_([TopicStatus.ACTIVE, TopicStatus.DRAFT]))
            .all()
        )

        stale = self._find_stale(active)
        merge_candidates = self._find_merge_candidates(active)
        coverage_gaps = self._find_coverage_gaps(active)
        quality_scores = self._score_topics(active)

        return {
            "stale": stale,
            "merge_candidates": merge_candidates,
            "coverage_gaps": coverage_gaps,
            "quality_scores": quality_scores,
        }

    def _find_stale(self, topics: list[Topic]) -> list[str]:
        """Return slugs of topics with no new evidence in >threshold days."""
        threshold_days = int(self.settings.kb_stale_threshold_days or 30)
        cutoff = datetime.now(UTC) - timedelta(days=threshold_days)
        stale_slugs: list[str] = []
        for topic in topics:
            last = topic.last_evidence_at or topic.last_compiled_at
            if last is None:
                continue
            if _coerce_aware(last) < cutoff:
                stale_slugs.append(topic.slug)
        return sorted(stale_slugs)

    def _find_merge_candidates(self, topics: list[Topic]) -> list[tuple[str, str]]:
        """Return (slug_a, slug_b) pairs with article similarity above threshold."""
        threshold = float(self.settings.kb_merge_similarity_threshold or 0.90)
        usable = [t for t in topics if t.article_md and t.article_md.strip()]
        pairs: list[tuple[str, str]] = []
        for i in range(len(usable)):
            for j in range(i + 1, len(usable)):
                a = usable[i]
                b = usable[j]
                score = _article_similarity(a.article_md, b.article_md)
                if score >= threshold:
                    pairs.append((a.slug, b.slug))
        return pairs

    def _find_coverage_gaps(self, topics: list[Topic]) -> list[str]:
        """Return categories with fewer than ``kb_min_topics_per_category`` topics.

        The count is seeded with every ``ThemeCategory`` enum value so
        genuinely empty categories surface as gaps. It also tolerates
        legacy topics whose ``category`` does not match the current enum
        (e.g., from migrations or manual inserts): such values contribute
        to their own bucket and won't be reported as a gap unless they
        are under the minimum.
        """
        minimum = int(self.settings.kb_min_topics_per_category or 3)
        counts: dict[str, int] = {}
        for cat in ThemeCategory:
            counts[cat.value] = 0
        for topic in topics:
            if topic.status != TopicStatus.ACTIVE:
                continue
            key = topic.category or "uncategorized"
            counts[key] = counts.get(key, 0) + 1
        gaps = [cat for cat, count in counts.items() if count < minimum]
        return sorted(gaps)

    def _score_topics(self, topics: list[Topic]) -> dict[str, float]:
        """Assign a 0-1 quality score to every topic.

        Blend of evidence volume, recency, and completeness:
        - ``evidence``: log-scaled mention_count normalized to [0,1]
        - ``recency``: 1.0 at compile time, decays to 0 over 2*stale_threshold
        - ``completeness``: article length / (50 * max(1, mention_count)),
          clipped to [0,1]

        The final score is the mean of the three components.
        """
        stale_days = int(self.settings.kb_stale_threshold_days or 30)
        horizon = max(2 * stale_days, 1)
        now = datetime.now(UTC)

        scores: dict[str, float] = {}
        for topic in topics:
            mentions = max(int(topic.mention_count or 0), 0)
            # evidence: log-scale mention count — cap at ~10 mentions
            evidence = min(mentions / 10.0, 1.0)

            last = topic.last_evidence_at or topic.last_compiled_at
            if last is None:
                recency = 0.0
            else:
                age_days = (now - _coerce_aware(last)).days
                if age_days <= 0:
                    recency = 1.0
                else:
                    recency = max(0.0, 1.0 - (age_days / horizon))

            article_len = len(topic.article_md or "")
            expected = 50 * max(1, mentions)
            completeness = min(article_len / expected, 1.0) if expected else 0.0

            score = (evidence + recency + completeness) / 3.0
            scores[topic.slug] = round(score, 3)
        return scores

    # ------------------------------------------------------------------ #
    # Report rendering
    # ------------------------------------------------------------------ #

    def _build_report(
        self,
        findings: dict[str, Any],
        *,
        fixed_count: int | None = None,
    ) -> str:
        """Render a markdown report grouped by check type."""
        lines: list[str] = ["# KB Health Report", ""]
        if fixed_count is not None:
            lines.append(f"_Auto-fix applied: {fixed_count} topics marked stale._")
            lines.append("")

        stale = findings.get("stale", [])
        lines.append("## Stale Topics")
        if stale:
            for slug in stale:
                lines.append(
                    f"- `{slug}` — no new evidence in "
                    f">{self.settings.kb_stale_threshold_days} days. "
                    "Recompile or archive."
                )
        else:
            lines.append("_No stale topics._")
        lines.append("")

        merges = findings.get("merge_candidates", [])
        lines.append("## Merge Candidates")
        if merges:
            for a, b in merges:
                lines.append(
                    f"- `{a}` ⇄ `{b}` — article similarity above "
                    f"{self.settings.kb_merge_similarity_threshold}. "
                    "Review and merge manually."
                )
        else:
            lines.append("_No merge candidates._")
        lines.append("")

        gaps = findings.get("coverage_gaps", [])
        lines.append("## Coverage Gaps")
        if gaps:
            for cat in gaps:
                lines.append(
                    f"- `{cat}` — fewer than "
                    f"{self.settings.kb_min_topics_per_category} "
                    "active topics. Consider ingesting more content in "
                    "this area."
                )
        else:
            lines.append("_All categories meet the coverage minimum._")
        lines.append("")

        scores = findings.get("quality_scores", {}) or {}
        lines.append("## Quality Scores")
        if scores:
            worst = sorted(scores.items(), key=lambda kv: kv[1])[:10]
            for slug, score in worst:
                lines.append(f"- `{slug}`: {score:.2f}")
        else:
            lines.append("_No topics to score._")
        lines.append("")

        return "\n".join(lines)


def _coerce_aware(value: datetime) -> datetime:
    """Make a possibly-naive datetime UTC-aware for comparison."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
