"""Knowledge base compilation service.

Compiles persistent knowledge topics from theme analyses, summaries, and
content items. The service is monolithic by design (D1) — a single class
owns the gather → match → compile → index pipeline.

Concurrency is controlled via PostgreSQL advisory locks (D10): only one
compilation can run at a time. The lock has a stale-recovery timeout
configurable via ``KB_COMPILE_LOCK_TIMEOUT_MINUTES``.

Topic matching is two-phase (D3): exact name match first, then semantic
similarity via cosine distance over topic embeddings. Embeddings are
generated via the existing ``EmbeddingProvider`` infrastructure.

Relationships are stored DB-primary (D2) with optional Graphiti sync —
graph backend failures are logged and ignored.
"""

from __future__ import annotations

import asyncio
import logging
import math
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.models import ModelConfig, ModelStep, get_model_config
from src.config.settings import get_settings
from src.models.theme import (
    ThemeAnalysis,
    ThemeCategory,
    ThemeTrend,
)
from src.models.topic import KBIndex, Topic, TopicNote, TopicNoteType, TopicStatus
from src.services.llm_router import LLMRouter
from src.services.prompt_service import PromptService

logger = logging.getLogger(__name__)


# Stable advisory lock key — derived from a fixed string so all processes
# converge on the same integer. PostgreSQL advisory locks take a bigint;
# we use the high 32 bits of a deterministic hash.
_KB_COMPILE_LOCK_KEY = 0x4B42434F4D504C45  # "KBCOMPLE" packed as ASCII


class KBCompileLockError(Exception):
    """Raised when a compile cannot acquire the advisory lock."""


@dataclass
class TopicCompileResult:
    """Per-topic outcome of a compilation cycle."""

    slug: str
    action: str  # "created" | "updated" | "skipped" | "failed"
    error: str | None = None
    article_version: int | None = None
    token_usage: int | None = None


@dataclass
class CompileSummary:
    """Aggregate result of a KB compile run."""

    started_at: datetime
    finished_at: datetime | None = None
    topics_found: int = 0
    topics_compiled: int = 0
    topics_skipped: int = 0
    topics_failed: int = 0
    merge_candidates: list[tuple[str, str]] = field(default_factory=list)
    per_topic: list[TopicCompileResult] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "topics_found": self.topics_found,
            "topics_compiled": self.topics_compiled,
            "topics_skipped": self.topics_skipped,
            "topics_failed": self.topics_failed,
            "merge_candidates": [{"a": a, "b": b} for a, b in self.merge_candidates],
            "per_topic": [
                {
                    "slug": r.slug,
                    "action": r.action,
                    "error": r.error,
                    "article_version": r.article_version,
                    "token_usage": r.token_usage,
                }
                for r in self.per_topic
            ],
            "error": self.error,
        }


def slugify(text_value: str) -> str:
    """Generate a URL-safe slug from a topic name."""
    cleaned = text_value.lower().strip()
    cleaned = re.sub(r"[^a-z0-9\s-]", "", cleaned)
    cleaned = re.sub(r"[\s_]+", "-", cleaned)
    cleaned = cleaned.strip("-")
    return cleaned or "topic"


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors. Returns 0.0 on length mismatch."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class KnowledgeBaseService:
    """Compile, maintain, and query the knowledge base.

    Args:
        db: SQLAlchemy session.
        model_config: Optional ModelConfig (defaults to global config).
        prompt_service: Optional PromptService (auto-instantiated if not provided).
        llm_router: Optional LLMRouter (auto-instantiated if not provided).
    """

    def __init__(
        self,
        db: Session,
        *,
        model_config: ModelConfig | None = None,
        prompt_service: PromptService | None = None,
        llm_router: LLMRouter | None = None,
    ) -> None:
        self.db = db
        self.model_config = model_config or get_model_config()
        self.prompt_service = prompt_service or PromptService(db)
        self.llm_router = llm_router or LLMRouter(self.model_config)
        self.settings = get_settings()

    # ------------------------------------------------------------------ #
    # Public compilation API
    # ------------------------------------------------------------------ #

    async def compile(self) -> CompileSummary:
        """Run incremental compilation: only new evidence since last run."""
        return await self._run_compile(mode="incremental")

    async def compile_full(self) -> CompileSummary:
        """Recompile ALL active topics regardless of last_compiled_at."""
        return await self._run_compile(mode="full")

    async def compile_topic(self, slug: str) -> CompileSummary:
        """Recompile a single topic by slug."""
        return await self._run_compile(mode="single", target_slug=slug)

    async def _run_compile(
        self,
        *,
        mode: str,
        target_slug: str | None = None,
    ) -> CompileSummary:
        summary = CompileSummary(started_at=datetime.now(UTC))
        run_id = uuid.uuid4().hex[:12]

        if not self._acquire_lock():
            summary.error = "Another KB compilation is already in progress."
            summary.finished_at = datetime.now(UTC)
            raise KBCompileLockError(summary.error)

        logger.info(
            "kb_compile.start run_id=%s mode=%s target=%s",
            run_id,
            mode,
            target_slug or "-",
        )
        start = datetime.now(UTC)

        try:
            # 1. Gather evidence
            evidence = self._gather_evidence(mode=mode, target_slug=target_slug)
            summary.topics_found = len(evidence)

            if not evidence:
                logger.info(
                    "kb_compile.finish run_id=%s status=empty topics_found=0",
                    run_id,
                )
                self._regenerate_indices()
                summary.finished_at = datetime.now(UTC)
                self.db.commit()
                return summary

            # 2. Compile each topic candidate
            for theme_payload in evidence:
                try:
                    result = await self._compile_topic_from_evidence(theme_payload)
                    summary.per_topic.append(result)
                    if result.action == "failed":
                        summary.topics_failed += 1
                    elif result.action == "skipped":
                        summary.topics_skipped += 1
                    else:
                        summary.topics_compiled += 1
                except Exception as exc:
                    logger.exception(
                        "kb_compile.topic_failed run_id=%s name=%s",
                        run_id,
                        theme_payload.get("name", "<unknown>"),
                    )
                    summary.per_topic.append(
                        TopicCompileResult(
                            slug=theme_payload.get("name", "<unknown>"),
                            action="failed",
                            error=str(exc),
                        )
                    )
                    summary.topics_failed += 1

            # 3. Detect merge candidates
            summary.merge_candidates = self._detect_merge_candidates()

            # 4. Detect simple relationships
            self._update_simple_relationships()

            # 5. Regenerate indices
            self._regenerate_indices()

            self.db.commit()
            elapsed = (datetime.now(UTC) - start).total_seconds()
            logger.info(
                "kb_compile.finish run_id=%s status=ok topics_found=%d "
                "compiled=%d skipped=%d failed=%d elapsed_seconds=%.2f",
                run_id,
                summary.topics_found,
                summary.topics_compiled,
                summary.topics_skipped,
                summary.topics_failed,
                elapsed,
            )
        except Exception:
            # Roll back any partially-written state so subsequent queries
            # against this session (e.g., index regeneration) don't fail
            # on a broken transaction. Lock release still happens in finally.
            logger.exception("kb_compile.aborted run_id=%s", run_id)
            try:
                self.db.rollback()
            except Exception:
                logger.debug(
                    "kb_compile: rollback failed during abort",
                    exc_info=True,
                )
            raise
        finally:
            self._release_lock()
            summary.finished_at = datetime.now(UTC)

        return summary

    # ------------------------------------------------------------------ #
    # Concurrency control (D10)
    # ------------------------------------------------------------------ #

    def _acquire_lock(self) -> bool:
        """Try to acquire the KB compile advisory lock.

        Stale lock recovery: if a previously-held lock has been around longer
        than ``kb_compile_lock_timeout_minutes`` (best-effort detection via
        a sentinel row in kb_indices), we forcibly release and re-acquire.
        """
        # Best-effort stale lock detection: check if a sentinel row exists
        # with an old timestamp. We use kb_indices with a special index_type.
        sentinel_type = "_compile_lock_sentinel"
        try:
            existing = self.db.query(KBIndex).filter_by(index_type=sentinel_type).first()
            if existing is not None:
                age = datetime.now(UTC) - _coerce_aware(existing.generated_at)
                threshold = timedelta(minutes=self.settings.kb_compile_lock_timeout_minutes)
                if age > threshold:
                    logger.warning("KB compile: clearing stale lock sentinel (age=%s)", age)
                    # Clear the application-side sentinel; the DB advisory
                    # lock will release automatically on the holder's
                    # session disconnect.
                    self.db.delete(existing)
                    self.db.commit()
        except Exception:
            logger.debug("KB compile: stale lock check skipped", exc_info=True)

        try:
            row = self.db.execute(
                text("SELECT pg_try_advisory_lock(:key)").bindparams(key=_KB_COMPILE_LOCK_KEY)
            ).scalar()
        except Exception:
            # Non-Postgres backend (e.g. SQLite in tests) — fall back to
            # sentinel-row locking only.
            return self._acquire_sentinel_lock()

        if not bool(row):
            return False

        # Write sentinel for stale-recovery
        self._write_sentinel_lock()
        return True

    def _acquire_sentinel_lock(self) -> bool:
        """Fallback lock for backends without advisory locks (tests)."""
        existing = self.db.query(KBIndex).filter_by(index_type="_compile_lock_sentinel").first()
        if existing is not None:
            return False
        self._write_sentinel_lock()
        return True

    def _write_sentinel_lock(self) -> None:
        """Write the lock sentinel row inside a savepoint.

        Using ``begin_nested()`` isolates the sentinel write: if the INSERT
        fails (e.g., a race inserted another sentinel), only the savepoint
        is rolled back, not the outer compile transaction.
        """
        sentinel = KBIndex(
            index_type="_compile_lock_sentinel",
            content="locked",
            generated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        try:
            with self.db.begin_nested():
                self.db.add(sentinel)
                self.db.flush()
        except Exception:
            logger.debug(
                "kb_compile: sentinel write skipped (concurrent insert?)",
                exc_info=True,
            )

    def _release_lock(self) -> None:
        try:
            self.db.execute(
                text("SELECT pg_advisory_unlock(:key)").bindparams(key=_KB_COMPILE_LOCK_KEY)
            )
        except Exception:
            logger.debug("KB compile: pg_advisory_unlock skipped", exc_info=True)

        # Clear sentinel
        try:
            self.db.query(KBIndex).filter_by(index_type="_compile_lock_sentinel").delete()
            self.db.commit()
        except Exception:
            self.db.rollback()

    # ------------------------------------------------------------------ #
    # Evidence gathering
    # ------------------------------------------------------------------ #

    def _gather_evidence(self, *, mode: str, target_slug: str | None) -> list[dict[str, Any]]:
        """Build a list of theme payloads to compile.

        Returns:
            List of dicts with at least: name, category, description,
            content_ids, theme_id, mention_count, relevance_score, trend.
        """
        if mode == "single" and target_slug:
            topic = self.db.query(Topic).filter_by(slug=target_slug).first()
            if not topic:
                return []
            return [self._theme_payload_for_existing_topic(topic)]

        if mode == "full":
            # Recompile every active topic from its accumulated source themes.
            topics = self.db.query(Topic).filter(Topic.status == TopicStatus.ACTIVE).all()
            return [self._theme_payload_for_existing_topic(t) for t in topics]

        # Incremental: gather themes from completed ThemeAnalysis records
        # since the most recent topic compilation.
        latest_compiled = (
            self.db.query(Topic.last_compiled_at)
            .filter(Topic.last_compiled_at.isnot(None))
            .order_by(Topic.last_compiled_at.desc())
            .first()
        )
        cutoff: datetime | None = latest_compiled[0] if latest_compiled else None

        query = self.db.query(ThemeAnalysis).filter(ThemeAnalysis.themes.isnot(None))
        if cutoff is not None:
            query = query.filter(ThemeAnalysis.created_at > cutoff)

        analyses = query.order_by(ThemeAnalysis.created_at.asc()).all()
        return self._flatten_themes(analyses)

    def _flatten_themes(self, analyses: list[ThemeAnalysis]) -> list[dict[str, Any]]:
        """Flatten ThemeAnalysis JSON into per-theme payloads."""
        out: list[dict[str, Any]] = []
        for analysis in analyses:
            themes = analysis.themes or []
            if not isinstance(themes, list):
                continue
            for raw in themes:
                if not isinstance(raw, dict):
                    continue
                out.append(
                    {
                        "name": raw.get("name", ""),
                        "description": raw.get("description", ""),
                        "category": raw.get("category", "other"),
                        "content_ids": raw.get("content_ids", []),
                        "theme_id": analysis.id,
                        "mention_count": raw.get("mention_count", 0),
                        "relevance_score": raw.get("relevance_score", 0.0),
                        "novelty_score": raw.get("novelty_score", 0.0),
                        "trend": raw.get("trend", "one_off"),
                        "key_points": raw.get("key_points", []),
                        "analysis_created_at": analysis.created_at,
                    }
                )
        return out

    def _theme_payload_for_existing_topic(self, topic: Topic) -> dict[str, Any]:
        return {
            "name": topic.name,
            "description": topic.summary or "",
            "category": topic.category,
            "content_ids": list(topic.source_content_ids or []),
            "theme_id": (topic.source_theme_ids or [None])[0],
            "mention_count": topic.mention_count,
            "relevance_score": topic.relevance_score,
            "novelty_score": topic.novelty_score,
            "trend": topic.trend or "one_off",
            "key_points": [],
            "analysis_created_at": topic.last_evidence_at or topic.updated_at,
            "force_existing": topic,
        }

    # ------------------------------------------------------------------ #
    # Topic matching (D3)
    # ------------------------------------------------------------------ #

    async def _match_to_topic(
        self, payload: dict[str, Any]
    ) -> tuple[Topic | None, list[float] | None]:
        """Find an existing topic matching the payload.

        Returns:
            (matched_topic, embedding) — embedding may be None if generation failed.
        """
        # Phase 1: exact name match
        existing = self.db.query(Topic).filter(Topic.name == payload["name"]).first()
        if existing is not None:
            return existing, None

        # Phase 2: semantic match
        embedding: list[float] | None = None
        try:
            embedding = await self._generate_embedding(
                f"{payload['name']}\n{payload.get('description', '')}"
            )
        except Exception as exc:
            logger.warning(
                "KB compile: embedding failed for %s, falling back to exact match: %s",
                payload.get("name"),
                exc,
            )
            return None, None

        if embedding is None:
            return None, None

        # Compare with existing topic embeddings (loaded via raw SQL since
        # embedding column is not mapped on Topic model).
        try:
            rows = self.db.execute(
                text(
                    "SELECT id, slug, embedding::text "
                    "FROM topics WHERE embedding IS NOT NULL "
                    "AND status != 'archived'"
                )
            ).fetchall()
        except Exception:
            rows = []

        threshold = self.settings.kb_match_similarity_threshold
        best_id: int | None = None
        best_score = 0.0
        for row in rows:
            other_emb = _parse_pgvector_text(row[2])
            if not other_emb:
                continue
            score = cosine_similarity(embedding, other_emb)
            if score > best_score:
                best_score = score
                best_id = row[0]

        if best_id is not None and best_score >= threshold:
            return self.db.query(Topic).get(best_id), embedding

        return None, embedding

    async def _generate_embedding(self, text_value: str) -> list[float] | None:
        """Generate an embedding using the configured provider."""
        from src.services.embedding import get_embedding_provider

        provider = get_embedding_provider()
        return await provider.embed(text_value)

    # ------------------------------------------------------------------ #
    # Article compilation
    # ------------------------------------------------------------------ #

    async def _compile_topic_from_evidence(self, payload: dict[str, Any]) -> TopicCompileResult:
        """Compile or recompile a single topic from evidence."""
        forced = payload.get("force_existing")
        embedding: list[float] | None = None

        if isinstance(forced, Topic):
            topic = forced
        else:
            topic, embedding = await self._match_to_topic(payload)

            if topic is None:
                # Create new draft topic
                slug = self._unique_slug(payload["name"])
                topic = Topic(
                    slug=slug,
                    name=payload["name"],
                    category=str(payload["category"]),
                    status=TopicStatus.DRAFT,
                    summary=payload.get("description", "")[:1000],
                    trend=str(payload.get("trend", "one_off")),
                    relevance_score=float(payload.get("relevance_score", 0.0)),
                    novelty_score=float(payload.get("novelty_score", 0.0)),
                    mention_count=int(payload.get("mention_count", 0)),
                    source_content_ids=list(payload.get("content_ids", [])),
                    source_theme_ids=([payload["theme_id"]] if payload.get("theme_id") else []),
                )
                self.db.add(topic)
                self.db.flush()
            else:
                # Merge new evidence into existing topic
                self._merge_evidence(topic, payload)

        # Compile article via LLM (skipped on failure)
        try:
            article_md, token_usage = await self._render_article(topic, payload)
        except Exception as exc:
            logger.warning("KB compile: LLM call failed for %s: %s", topic.slug, exc)
            return TopicCompileResult(
                slug=topic.slug,
                action="failed",
                error=str(exc),
            )

        topic.article_md = article_md
        topic.article_version = (topic.article_version or 0) + 1
        topic.compilation_model = self.model_config.get_model_for_step(ModelStep.KB_COMPILATION)
        topic.compilation_token_usage = token_usage
        topic.last_compiled_at = datetime.now(UTC).replace(tzinfo=None)
        topic.last_evidence_at = payload.get("analysis_created_at") or topic.last_compiled_at
        if topic.status == TopicStatus.DRAFT:
            topic.status = TopicStatus.ACTIVE

        # Persist embedding if we generated one
        if embedding is not None:
            self._persist_topic_embedding(topic.id, embedding)

        return TopicCompileResult(
            slug=topic.slug,
            action="updated",
            article_version=topic.article_version,
            token_usage=token_usage,
        )

    def _merge_evidence(self, topic: Topic, payload: dict[str, Any]) -> None:
        """Merge new evidence (content_ids, theme_id, mention_count) into a topic."""
        existing_content = set(topic.source_content_ids or [])
        existing_content.update(payload.get("content_ids", []))
        topic.source_content_ids = sorted(existing_content)

        if payload.get("theme_id") is not None:
            existing_themes = set(topic.source_theme_ids or [])
            existing_themes.add(payload["theme_id"])
            topic.source_theme_ids = sorted(existing_themes)

        topic.mention_count = max(
            topic.mention_count or 0,
            int(payload.get("mention_count", 0)),
        )
        new_relevance = float(payload.get("relevance_score", 0.0))
        if new_relevance > (topic.relevance_score or 0.0):
            topic.relevance_score = new_relevance

    def _unique_slug(self, name: str) -> str:
        base = slugify(name)
        candidate = base
        suffix = 2
        while self.db.query(Topic).filter_by(slug=candidate).first() is not None:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    async def _render_article(
        self, topic: Topic, payload: dict[str, Any]
    ) -> tuple[str, int | None]:
        """Render a topic article via the LLM."""
        existing_article = topic.article_md or "(none)"

        evidence_lines = [f"- {payload.get('description', '')}"]
        for point in payload.get("key_points") or []:
            if isinstance(point, str):
                evidence_lines.append(f"  - {point}")
        evidence_block = "\n".join(evidence_lines)

        user_prompt = self.prompt_service.render(
            "pipeline.kb_compilation.user_template",
            topic_name=topic.name,
            topic_category=topic.category,
            existing_article=existing_article,
            evidence_block=evidence_block,
        )
        system_prompt = self.prompt_service.get_pipeline_prompt("kb_compilation", "system")
        if not system_prompt:
            system_prompt = "You are a knowledge base curator compiling topic articles."

        model = self.model_config.get_model_for_step(ModelStep.KB_COMPILATION)
        # Defensive per-topic timeout so a stuck upstream can't hold the
        # advisory lock for hours. Budget is proportional to the compile
        # lock timeout: a single topic shouldn't take more than 1/3 of it.
        per_topic_timeout_seconds = max(
            int(self.settings.kb_compile_lock_timeout_minutes * 60 / 3),
            60,
        )
        try:
            response = await asyncio.wait_for(
                self.llm_router.generate(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=2048,
                    temperature=0.3,
                ),
                timeout=per_topic_timeout_seconds,
            )
        except TimeoutError as exc:
            raise RuntimeError(
                f"KB article compilation timed out after "
                f"{per_topic_timeout_seconds}s for topic '{topic.slug}'"
            ) from exc
        token_usage = (response.input_tokens or 0) + (response.output_tokens or 0)
        return response.text.strip(), token_usage or None

    def _persist_topic_embedding(self, topic_id: int, embedding: list[float]) -> None:
        """Write a topic embedding via raw SQL."""
        try:
            vector_literal = "[" + ",".join(f"{v:.6f}" for v in embedding) + "]"
            self.db.execute(
                text(
                    "UPDATE topics SET embedding = CAST(:emb AS vector) WHERE id = :id"
                ).bindparams(emb=vector_literal, id=topic_id)
            )
        except Exception:
            logger.debug(
                "Topic embedding persist skipped (vector unsupported)",
                exc_info=True,
            )

    # ------------------------------------------------------------------ #
    # Relationships and merge detection
    # ------------------------------------------------------------------ #

    def _detect_merge_candidates(self) -> list[tuple[str, str]]:
        """Find topic pairs with article token-Jaccard similarity above threshold.

        Implementation notes:
        - Token sets are computed ONCE per topic (was: re-tokenized per pair).
        - Complexity is still O(N²) in the number of candidates — OK up to
          ~1000 topics; beyond that, switch to locality-sensitive hashing.
        """
        topics = (
            self.db.query(Topic)
            .filter(
                Topic.status.in_([TopicStatus.ACTIVE, TopicStatus.DRAFT]),
                Topic.article_md.isnot(None),
                Topic.article_md != "",
            )
            .all()
        )

        # Pre-tokenize once per topic (major speedup for N > ~50)
        token_sets: list[tuple[str, set[str]]] = []
        for topic in topics:
            tokens = _tokenize(topic.article_md)
            if tokens:
                token_sets.append((topic.slug, tokens))

        candidates: list[tuple[str, str]] = []
        threshold = self.settings.kb_merge_similarity_threshold
        for i in range(len(token_sets)):
            slug_a, tokens_a = token_sets[i]
            for j in range(i + 1, len(token_sets)):
                slug_b, tokens_b = token_sets[j]
                score = _jaccard(tokens_a, tokens_b)
                if score >= threshold:
                    candidates.append((slug_a, slug_b))
        return candidates

    def _update_simple_relationships(self) -> None:
        """Update related_topic_ids based on shared source content."""
        topics = self.db.query(Topic).filter(Topic.status == TopicStatus.ACTIVE).all()
        # Build content_id -> topics mapping
        content_index: dict[int, list[int]] = {}
        for topic in topics:
            for cid in topic.source_content_ids or []:
                content_index.setdefault(cid, []).append(topic.id)

        for topic in topics:
            related: set[int] = set()
            for cid in topic.source_content_ids or []:
                for other_id in content_index.get(cid, []):
                    if other_id != topic.id:
                        related.add(other_id)
            topic.related_topic_ids = sorted(related)

        # Best-effort graph sync (D2)
        for topic in topics:
            try:
                self._sync_to_graph(topic)
            except Exception as exc:
                logger.warning(
                    "KB compile: graph sync failed for %s: %s",
                    topic.slug,
                    exc,
                )

    def _sync_to_graph(self, topic: Topic) -> None:
        """Optionally sync topic relationships to a graph backend.

        Wraps Graphiti access in try/except so missing/failed graph backends
        do not break compilation. DB relationships remain authoritative.
        """
        try:
            from src.storage.graphiti_client import GraphitiClient
        except ImportError:
            return  # Graphiti not installed
        try:
            client = GraphitiClient()
            if not client.is_available():
                return
        except Exception:
            return
        # Real sync intentionally minimal — DB is authoritative
        return

    # ------------------------------------------------------------------ #
    # Index generation (D4)
    # ------------------------------------------------------------------ #

    def generate_indices(self) -> None:
        """Public entrypoint for index regeneration (used outside compile)."""
        self._regenerate_indices()
        self.db.commit()

    def _regenerate_indices(self) -> None:
        """Regenerate master/category/trend/recency indices."""
        topics = self.db.query(Topic).filter(Topic.status == TopicStatus.ACTIVE).all()

        master_md = self._render_master_index(topics)
        self._upsert_index("master", master_md)

        for cat in ThemeCategory:
            category_md = self._render_category_index(topics, cat.value)
            self._upsert_index(f"category_{cat.value}", category_md)

        for trend in ThemeTrend:
            trend_md = self._render_trend_index(topics, trend.value)
            self._upsert_index(f"trend_{trend.value}", trend_md)

        recency_md = self._render_recency_index(topics)
        self._upsert_index("recency", recency_md)

    def _render_master_index(self, topics: list[Topic]) -> str:
        if not topics:
            return "# Knowledge Base — Master Index\n\n_No active topics yet._\n"
        sorted_topics = sorted(topics, key=lambda t: t.relevance_score or 0.0, reverse=True)
        lines = ["# Knowledge Base — Master Index", ""]
        for t in sorted_topics:
            summary = (t.summary or "").splitlines()[0] if t.summary else ""
            lines.append(f"- **{t.name}** ({t.category}, {t.trend or 'unknown'}) — {summary}")
        return "\n".join(lines) + "\n"

    def _render_category_index(self, topics: list[Topic], category: str) -> str:
        filtered = [t for t in topics if t.category == category]
        if not filtered:
            return f"# Category: {category}\n\n_No active topics._\n"
        sorted_topics = sorted(filtered, key=lambda t: t.relevance_score or 0.0, reverse=True)
        lines = [f"# Category: {category}", ""]
        for t in sorted_topics:
            lines.append(f"- **{t.name}** — {t.summary or ''}")
        return "\n".join(lines) + "\n"

    def _render_trend_index(self, topics: list[Topic], trend: str) -> str:
        filtered = [t for t in topics if (t.trend or "") == trend]
        if not filtered:
            return f"# Trend: {trend}\n\n_No active topics._\n"
        sorted_topics = sorted(filtered, key=lambda t: t.mention_count or 0, reverse=True)
        lines = [f"# Trend: {trend}", ""]
        for t in sorted_topics:
            lines.append(f"- **{t.name}** ({t.mention_count} mentions) — {t.summary or ''}")
        return "\n".join(lines) + "\n"

    def _render_recency_index(self, topics: list[Topic]) -> str:
        with_dates = [t for t in topics if t.last_compiled_at is not None]
        if not with_dates:
            return "# Recency Index\n\n_No compiled topics yet._\n"
        epoch = datetime.min.replace(tzinfo=UTC)
        sorted_topics = sorted(
            with_dates,
            key=lambda t: _coerce_aware(t.last_compiled_at) or epoch,
            reverse=True,
        )[:50]
        lines = ["# Recency Index", ""]
        for t in sorted_topics:
            ts = t.last_compiled_at.strftime("%Y-%m-%d") if t.last_compiled_at else ""
            lines.append(f"- **{t.name}** — last compiled {ts}")
        return "\n".join(lines) + "\n"

    def _upsert_index(self, index_type: str, content: str) -> None:
        existing = self.db.query(KBIndex).filter_by(index_type=index_type).first()
        now = datetime.now(UTC).replace(tzinfo=None)
        if existing is not None:
            existing.content = content
            existing.generated_at = now
        else:
            self.db.add(
                KBIndex(
                    index_type=index_type,
                    content=content,
                    generated_at=now,
                )
            )

    # ------------------------------------------------------------------ #
    # Topic note helper
    # ------------------------------------------------------------------ #

    def add_note(
        self,
        topic_slug: str,
        content: str,
        note_type: str = "observation",
        author: str = "system",
    ) -> TopicNote:
        topic = self.db.query(Topic).filter_by(slug=topic_slug).first()
        if topic is None:
            raise ValueError(f"Topic not found: {topic_slug}")

        # Validate note_type against the enum so callers get a clean 422/ValueError
        # instead of an opaque SQLAlchemy IntegrityError at commit time.
        try:
            validated_type = TopicNoteType(note_type)
        except ValueError as exc:
            valid = [t.value for t in TopicNoteType]
            raise ValueError(f"Invalid note_type '{note_type}'. Must be one of: {valid}") from exc

        note = TopicNote(
            topic_id=topic.id,
            note_type=validated_type,
            content=content,
            author=author,
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note


# ---------------------------------------------------------------------- #
# Module-level helpers
# ---------------------------------------------------------------------- #


def _parse_pgvector_text(text_value: str | None) -> list[float]:
    """Parse pgvector text output (e.g. '[0.1, 0.2, ...]') into a Python list."""
    if not text_value:
        return []
    text_value = text_value.strip()
    if text_value.startswith("[") and text_value.endswith("]"):
        text_value = text_value[1:-1]
    out: list[float] = []
    for piece in text_value.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            out.append(float(piece))
        except ValueError:
            return []
    return out


def _tokenize(text_value: str | None) -> set[str]:
    """Tokenize text into a lowercase word set (used for Jaccard similarity)."""
    if not text_value:
        return set()
    return set(re.findall(r"\w+", text_value.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity over pre-tokenized word sets."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


def _article_similarity(a: str | None, b: str | None) -> float:
    """Cheap article similarity using token Jaccard.

    Used for merge candidate detection without LLM cost. Spec says
    "cosine similarity > 0.90 between articles" — Jaccard is a fast
    proxy that biases towards precision. Prefer :func:`_jaccard` with
    pre-tokenized sets for batch operations.
    """
    return _jaccard(_tokenize(a), _tokenize(b))


def _coerce_aware(value: datetime | None) -> datetime:
    """Make a possibly-naive datetime UTC-aware for comparison."""
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
