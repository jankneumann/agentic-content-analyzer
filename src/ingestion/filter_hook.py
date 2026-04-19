"""Post-persist ingestion filter hook.

Runs after an ingestion adapter finishes persisting Content rows but before
any summarization job would normally pick them up. Because the summarizer
(src/processors/summarizer.py) queries for status in (PENDING, PARSED),
moving filtered items to FILTERED_OUT naturally excludes them without any
change to the summarizer itself.

The hook is intentionally time-bounded (``since`` timestamp) rather than
adapter-specific so it works uniformly for every source. Each ingestion
wrapper captures ``datetime.utcnow()`` before its adapter runs and passes it
here afterward; any Content row ingested after that point with
``filter_decision IS NULL`` is evaluated.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.config.filter_config import FilterConfig, resolve_filter_config
from src.models.content import Content, ContentStatus
from src.services.ingestion_filter import FilterDecision, IngestionFilterService
from src.telemetry.decorators import observe
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FilterStats:
    """Aggregate counts for a single filter-hook invocation."""

    evaluated: int = 0
    kept: int = 0
    skipped: int = 0
    errors: int = 0
    by_tier: dict[str, int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.by_tier is None:
            self.by_tier = {"heuristic": 0, "embedding": 0, "llm": 0}

    def record(self, decision: FilterDecision) -> None:
        self.evaluated += 1
        if decision.decision == "keep":
            self.kept += 1
        else:
            self.skipped += 1
        self.by_tier[decision.tier.value] = self.by_tier.get(decision.tier.value, 0) + 1

    def record_error(self) -> None:
        self.evaluated += 1
        self.errors += 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "evaluated": self.evaluated,
            "kept": self.kept,
            "skipped": self.skipped,
            "errors": self.errors,
            "by_tier": dict(self.by_tier),
        }


@observe(name="ingestion.filter_hook")
def apply_filter_to_recent(
    *,
    since: datetime,
    persona_id: str = "default",
    dry_run: bool = False,
    db: Session | None = None,
) -> FilterStats:
    """Evaluate every unfiltered Content ingested at or after ``since``.

    Safe to call even when filtering is globally disabled — the config is
    consulted on entry and an all-zero FilterStats is returned.
    """
    # Env-var overrides let CLI flags (--no-filter / --filter-dry-run) and
    # tests temporarily flip behavior without mutating persisted config.
    if os.environ.get("ACA_FILTER_ENABLED", "").lower() in ("false", "0", "no"):
        logger.debug("filter_hook: ACA_FILTER_ENABLED=false — skipping")
        return FilterStats()
    if os.environ.get("ACA_FILTER_DRY_RUN", "").lower() in ("true", "1", "yes"):
        dry_run = True

    config = _load_persona_config(persona_id)
    if not config.enabled:
        logger.debug("filter_hook: filtering.enabled=false — skipping")
        return FilterStats()

    own_session = db is None
    if own_session:
        from src.storage.database import get_db

        ctx = get_db()
        db = ctx.__enter__()
    try:
        assert db is not None  # for mypy
        stats = _run(db, config=config, persona_id=persona_id, since=since, dry_run=dry_run)
    finally:
        if own_session:
            ctx.__exit__(None, None, None)
    return stats


def _run(
    db: Session, *, config: FilterConfig, persona_id: str, since: datetime, dry_run: bool
) -> FilterStats:
    stats = FilterStats()
    candidates: list[Content] = (
        db.query(Content)
        .filter(
            and_(
                Content.ingested_at >= since,
                Content.filter_decision.is_(None),
                Content.status.in_([ContentStatus.PENDING, ContentStatus.PARSED]),
            )
        )
        .all()
    )
    if not candidates:
        return stats

    service = IngestionFilterService(db, config=config, persona_id=persona_id)
    for content in candidates:
        try:
            decision = service.filter(content.id, dry_run=dry_run)
            stats.record(decision)
        except Exception as exc:  # defensive — never block ingestion
            stats.record_error()
            logger.exception(
                "filter_hook: evaluation failed",
                extra={"content_id": content.id, "error": type(exc).__name__},
            )
            if config.strict:
                raise

    if not dry_run:
        db.commit()
    logger.info("filter_hook: %s", stats.as_dict())
    return stats


def _load_persona_config(persona_id: str) -> FilterConfig:
    """Load filter config for ``persona_id`` with YAML fallback to defaults."""
    persona = _load_persona_yaml(persona_id)
    return resolve_filter_config(persona=persona)


def _load_persona_yaml(persona_id: str) -> dict[str, Any] | None:
    from pathlib import Path

    import yaml  # type: ignore[import-untyped]

    # settings/personas/<persona_id>.yaml
    root = Path(__file__).resolve().parents[2]
    path = root / "settings" / "personas" / f"{persona_id}.yaml"
    if not path.exists():
        return None
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return data
