"""IngestionFilterService — post-persist, three-tier filter.

Runs after an ingestion adapter has persisted a `Content` row but before any
summarization job is enqueued. Evaluates the item through up to three tiers —
heuristic, embedding, LLM — short-circuiting on a deterministic decision.

This service is distinct from `src/services/content_filter.py`, which is the
pre-persist adapter-side keyword/LLM filter. The two are complementary:

- `ContentRelevanceFilter` (pre-persist): cheap keyword/LLM pass per adapter
  against a per-source `topics` list. Drops obvious noise before it reaches
  the DB.
- `IngestionFilterService` (post-persist): persona-aware three-tier scoring,
  produces `filter_score` / `priority_bucket` / `filter_decision`, persists
  to the `Content` row, and moves skipped items to `status=FILTERED_OUT`.
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Awaitable, Literal, TypeVar

from sqlalchemy.orm import Session

from src.config.filter_config import FilterConfig
from src.models.content import Content, ContentStatus
from src.services.persona_profile_cache import CachedProfile, PersonaProfileCache, cosine
from src.utils.logging import get_logger

logger = get_logger(__name__)

_T = TypeVar("_T")


def _resolve_embedding_model_id(provider: Any) -> str:
    """Best-effort stable identifier for an embedding provider+model pair.

    The EmbeddingProvider Protocol doesn't mandate a model field, so we try
    a few reasonable attribute names and fall back to the provider's name.
    The resulting string is only used as a cache-partition key, not as an
    API identifier, so "good enough to disambiguate" is sufficient.
    """
    for attr in ("model", "model_name", "_model"):
        value = getattr(provider, attr, None)
        if value:
            return str(value)
    return str(getattr(provider, "name", "unknown"))


def _run_sync(coro: Awaitable[_T]) -> _T:
    """Execute an awaitable synchronously, regardless of whether a loop runs.

    asyncio.run() raises when called from an already-running loop (FastAPI,
    Jupyter, etc). We detect that case and run the awaitable in a dedicated
    thread with a fresh loop so the filter can be called from either sync or
    async contexts.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)  # type: ignore[arg-type]

    result: dict[str, _T] = {}
    error: dict[str, BaseException] = {}

    def _runner() -> None:
        loop = asyncio.new_event_loop()
        try:
            result["v"] = loop.run_until_complete(coro)  # type: ignore[arg-type]
        except BaseException as exc:  # noqa: BLE001
            error["e"] = exc
        finally:
            loop.close()

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    if "e" in error:
        raise error["e"]
    return result["v"]


class FilterTier(StrEnum):
    HEURISTIC = "heuristic"
    EMBEDDING = "embedding"
    LLM = "llm"


Decision = Literal["keep", "skip"]
Bucket = Literal["high", "normal", "low"]


class _Borderline:
    """Sentinel type for the embedding-to-LLM escalation path.

    Emitted from _tier_embedding when the similarity score lands in the
    configured borderline band. Callers check ``isinstance(result, _Borderline)``
    which narrows the union type cleanly — much nicer than relying on an
    ambiguous reason="borderline" string on a FilterDecision.
    """

    __slots__ = ()


_BORDERLINE_SENTINEL = _Borderline()


@dataclass(frozen=True)
class FilterDecision:
    decision: Decision
    score: float  # [0.0, 1.0]
    tier: FilterTier
    reason: str
    priority_bucket: Bucket | None

    def as_log_attrs(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "tier": self.tier.value,
            "score": self.score,
            "reason": self.reason,
            "priority_bucket": self.priority_bucket,
        }


class IngestionFilterService:
    """Three-tier filter: heuristic -> embedding -> LLM.

    Construction is cheap; instances are typically built per-call from the
    orchestrator hook. Pass an ``embedding_provider`` and ``llm_client`` only
    in tests — production code loads them lazily from the standard factories.
    """

    def __init__(
        self,
        db: Session,
        *,
        config: FilterConfig,
        persona_id: str,
        embedding_provider: Any | None = None,
        llm_client: Any | None = None,
    ) -> None:
        self._db = db
        self._config = config
        self._persona_id = persona_id
        self._embedding_provider = embedding_provider
        self._llm_client = llm_client
        self._cache = PersonaProfileCache(db)
        # Tracked across tier 2 so tier 3 (and the fail-open fallback) can
        # report the embedding score even though the sentinel carries no score.
        self._last_embedding_score: float = 0.0

    # --- public entry point -------------------------------------------------

    def filter(self, content_id: int, *, dry_run: bool = False) -> FilterDecision:
        """Evaluate the content row with id ``content_id``.

        When dry_run is True, the decision is returned but no columns are
        written and the status is never transitioned to FILTERED_OUT.
        """
        content = self._db.get(Content, content_id)
        if content is None:
            raise ValueError(f"Content id={content_id} not found")

        decision = self._evaluate(content)

        if not dry_run:
            self._persist(content, decision)
        return decision

    # --- tier evaluation ----------------------------------------------------

    def _evaluate(self, content: Content) -> FilterDecision:
        cfg = self._config

        # Tier 1 — heuristic. Always runs.
        heuristic = self._tier_heuristic(content)
        if heuristic is not None:
            return heuristic

        # Tier 2 — embedding (only if we have an interest description).
        if cfg.interest_description:
            try:
                embedding_result = self._tier_embedding(content)
            except Exception as exc:  # fail-open per design.failure_modes
                if cfg.strict:
                    raise
                logger.warning(
                    "embedding tier failed, falling back to keep",
                    extra={"content_id": content.id, "error": type(exc).__name__},
                )
                return FilterDecision(
                    decision="keep",
                    score=0.0,
                    tier=FilterTier.EMBEDDING,
                    reason=f"embedding.error:{type(exc).__name__}",
                    priority_bucket="low",
                )
            if not isinstance(embedding_result, _Borderline):
                return embedding_result

            # Tier 3 — LLM. Runs only when embedding landed in borderline band.
            embedding_score = self._last_embedding_score
            if not cfg.llm_enabled:
                return FilterDecision(
                    decision="keep",
                    score=embedding_score,
                    tier=FilterTier.EMBEDDING,
                    reason="embedding.borderline.tier3_disabled",
                    priority_bucket="low",
                )
            try:
                return self._tier_llm(content, embedding_score=embedding_score)
            except Exception as exc:  # fail-open
                if cfg.strict:
                    raise
                logger.warning(
                    "llm tier failed, falling back to keep",
                    extra={"content_id": content.id, "error": type(exc).__name__},
                )
                return FilterDecision(
                    decision="keep",
                    score=embedding_score,
                    tier=FilterTier.LLM,
                    reason=f"llm.error:{type(exc).__name__}",
                    priority_bucket="low",
                )

        # No interest description and no tier-1 verdict -> keep at normal.
        return FilterDecision(
            decision="keep",
            score=0.5,
            tier=FilterTier.HEURISTIC,
            reason="heuristic.default_keep",
            priority_bucket="normal",
        )

    def _tier_heuristic(self, content: Content) -> FilterDecision | None:
        cfg = self._config
        title = (content.title or "").lower()
        body = (content.markdown_content or "")[: cfg.excerpt_chars].lower()
        haystack = f"{title}\n{body}"

        for token in cfg.must_exclude:
            if token and token.lower() in haystack:
                return FilterDecision(
                    decision="skip",
                    score=0.0,
                    tier=FilterTier.HEURISTIC,
                    reason=f"heuristic.must_exclude:{token.lower()}",
                    priority_bucket=None,
                )

        for token in cfg.must_include:
            if token and token.lower() in haystack:
                return FilterDecision(
                    decision="keep",
                    score=1.0,
                    tier=FilterTier.HEURISTIC,
                    reason=f"heuristic.must_include:{token.lower()}",
                    priority_bucket="high",
                )

        word_count = len(re.findall(r"\w+", content.markdown_content or ""))
        if word_count < cfg.min_word_count:
            return FilterDecision(
                decision="skip",
                score=0.0,
                tier=FilterTier.HEURISTIC,
                reason=f"heuristic.min_word_count:{word_count}<{cfg.min_word_count}",
                priority_bucket=None,
            )

        return None

    def _tier_embedding(self, content: Content) -> FilterDecision | _Borderline:
        cfg = self._config
        provider = self._load_embedding_provider()
        persona_vec = self._get_or_compute_profile_vector(provider)

        excerpt = self._build_excerpt(content)
        doc_vec = _run_sync(provider.embed(excerpt, is_query=False))

        similarity = cosine(persona_vec, list(doc_vec))
        # Normalize cosine [-1, 1] into [0, 1] for downstream score math.
        score = (similarity + 1.0) / 2.0
        self._last_embedding_score = score

        band = cfg.borderline_band
        classified = band.classify(score)
        if classified == "below":
            return FilterDecision(
                decision="skip",
                score=score,
                tier=FilterTier.EMBEDDING,
                reason=f"embedding.similarity:{score:.3f}<{band.low:.2f}",
                priority_bucket=None,
            )
        if classified == "above":
            return FilterDecision(
                decision="keep",
                score=score,
                tier=FilterTier.EMBEDDING,
                reason=f"embedding.similarity:{score:.3f}",
                priority_bucket=cfg.priority_bucket(score),
            )
        # borderline -> explicit sentinel, caller dispatches to tier 3
        return _BORDERLINE_SENTINEL

    def _tier_llm(self, content: Content, *, embedding_score: float) -> FilterDecision:
        cfg = self._config
        client = self._load_llm_client()
        title = content.title or ""
        excerpt = (content.markdown_content or "")[: cfg.excerpt_chars]

        raw = client.classify(
            interest_description=cfg.interest_description or "",
            title=title,
            excerpt=excerpt,
        )
        parsed = _parse_llm_response(raw)
        decision: Decision = "keep" if parsed.get("decision") == "keep" else "skip"
        score = float(parsed.get("score", embedding_score))
        score = max(0.0, min(1.0, score))
        reason = str(parsed.get("reason") or f"llm.score:{score:.2f}")

        return FilterDecision(
            decision=decision,
            score=score,
            tier=FilterTier.LLM,
            reason=reason,
            priority_bucket=cfg.priority_bucket(score) if decision == "keep" else None,
        )

    # --- helpers ------------------------------------------------------------

    def _build_excerpt(self, content: Content) -> str:
        title = (content.title or "").strip()
        body = (content.markdown_content or "").strip()[: self._config.excerpt_chars]
        return f"{title}\n{body}".strip()

    def _load_embedding_provider(self) -> Any:
        if self._embedding_provider is not None:
            return self._embedding_provider
        from src.services.embedding import get_embedding_provider  # lazy

        provider = get_embedding_provider()
        self._embedding_provider = provider
        return provider

    def _load_llm_client(self) -> Any:
        if self._llm_client is not None:
            return self._llm_client
        self._llm_client = _DefaultLLMClient()
        return self._llm_client

    def _get_or_compute_profile_vector(self, provider: Any) -> list[float]:
        cfg = self._config
        cached: CachedProfile | None = self._cache.get(
            persona_id=self._persona_id,
            embedding_provider=provider.name,
            embedding_model=_resolve_embedding_model_id(provider),
        )
        interest = cfg.interest_description or ""
        if not self._cache.needs_refresh(cached, interest):
            assert cached is not None
            return cached.embedding

        vec = _run_sync(provider.embed(interest, is_query=False))
        refreshed = self._cache.upsert(
            persona_id=self._persona_id,
            embedding_provider=provider.name,
            embedding_model=_resolve_embedding_model_id(provider),
            interest_description=interest,
            embedding=list(vec),
        )
        return refreshed.embedding

    def _persist(self, content: Content, decision: FilterDecision) -> None:
        content.filter_score = decision.score
        content.filter_decision = decision.decision
        content.filter_tier = decision.tier.value
        content.filter_reason = decision.reason
        content.priority_bucket = decision.priority_bucket
        content.filtered_at = datetime.now(UTC).replace(tzinfo=None)
        if decision.decision == "skip":
            content.status = ContentStatus.FILTERED_OUT
        self._db.flush()


# ---------------------------------------------------------------------------
# LLM client adapter
# ---------------------------------------------------------------------------


class _DefaultLLMClient:
    """Routes the filter prompt through the existing LLMRouter + PromptService."""

    def classify(self, *, interest_description: str, title: str, excerpt: str) -> str:
        from src.config.models import ModelStep, get_model_config
        from src.services.llm_router import LLMRouter
        from src.services.prompt_service import PromptService

        model_cfg = get_model_config()
        model = model_cfg.get_model_for_step(ModelStep.CONTENT_FILTERING)
        prompts = PromptService()
        system_prompt = prompts.get_pipeline_prompt("ingestion_filter", "system")
        user_prompt = prompts.render(
            "pipeline.ingestion_filter.user_template",
            interest_description=interest_description,
            title=title,
            excerpt=excerpt or "(no content)",
        )
        router = LLMRouter(model_cfg)
        response = router.generate_sync(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=200,
            temperature=0.0,
        )
        return response.text


def _parse_llm_response(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]).strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {"decision": "keep", "score": 0.5, "reason": "llm.parse_failed"}
