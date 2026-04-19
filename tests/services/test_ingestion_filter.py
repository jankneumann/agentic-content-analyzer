"""Unit tests for IngestionFilterService.

Covers each tier in isolation with in-memory stubs so the tests don't need a
real database, embedding provider, or LLM. The service reads and writes the
Content row via a lightweight fake Session.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest

from src.config.filter_config import BorderlineBand, FilterConfig
from src.models.content import Content, ContentStatus
from src.services.ingestion_filter import (
    FilterDecision,
    FilterTier,
    IngestionFilterService,
    _parse_llm_response,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeSession:
    """Minimal Session stub supporting get/add/flush for the two models we touch."""

    def __init__(self, rows: dict[tuple[type, Any], Any] | None = None) -> None:
        self._rows: dict[tuple[type, Any], Any] = rows or {}
        self.flushed: int = 0

    def get(self, model: type, pk: Any) -> Any | None:
        return self._rows.get((model, pk))

    def add(self, row: Any) -> None:
        if hasattr(row, "persona_id"):
            key = (
                type(row),
                (row.persona_id, row.embedding_provider, row.embedding_model),
            )
            self._rows[key] = row

    def flush(self) -> None:
        self.flushed += 1


class _FakeEmbeddingProvider:
    def __init__(self, name: str = "fake", vector: list[float] | None = None) -> None:
        self._name = name
        self._model = f"{name}-model"
        self._vector = vector or [1.0, 0.0, 0.0]

    @property
    def name(self) -> str:
        return self._name

    @property
    def dimensions(self) -> int:
        return len(self._vector)

    async def embed(self, text: str, *, is_query: bool = False) -> list[float]:
        return list(self._vector)

    async def embed_batch(
        self, texts: list[str], *, is_query: bool = False
    ) -> list[list[float]]:
        return [list(self._vector) for _ in texts]


@dataclass
class _FakeLLM:
    responses: list[str] = field(default_factory=list)
    calls: list[dict[str, str]] = field(default_factory=list)

    def classify(self, *, interest_description: str, title: str, excerpt: str) -> str:
        self.calls.append(
            {"interest_description": interest_description, "title": title, "excerpt": excerpt}
        )
        if not self.responses:
            return '{"decision": "keep", "score": 0.5, "reason": "stub"}'
        return self.responses.pop(0)


def _make_content(**overrides: Any) -> Content:
    content = Content()
    content.id = overrides.get("id", 1)
    content.title = overrides.get("title", "Retrieval-Augmented Generation in production")
    content.markdown_content = overrides.get(
        "markdown_content",
        " ".join(["word"] * 200),
    )
    content.status = overrides.get("status", ContentStatus.PENDING)
    return content


def _make_config(**overrides: Any) -> FilterConfig:
    defaults = {
        "enabled": True,
        "strict": False,
        "min_word_count": 10,
        "allowed_languages": ("en",),
        "borderline_band": BorderlineBand(low=0.45, high=0.65),
        "priority_high_threshold": 0.65,
        "priority_low_threshold": 0.45,
        "excerpt_chars": 200,
        "interest_description": "AI agents and production ML",
    }
    defaults.update(overrides)
    return FilterConfig(**defaults)


# ---------------------------------------------------------------------------
# Dataclass / parser tests
# ---------------------------------------------------------------------------


def test_filter_decision_log_attrs_shape() -> None:
    d = FilterDecision(
        decision="keep", score=0.72, tier=FilterTier.EMBEDDING, reason="r", priority_bucket="high"
    )
    attrs = d.as_log_attrs()
    assert attrs["decision"] == "keep"
    assert attrs["tier"] == "embedding"
    assert attrs["score"] == pytest.approx(0.72)


def test_parse_llm_response_strips_code_fence() -> None:
    raw = '```json\n{"decision": "skip", "score": 0.2, "reason": "noise"}\n```'
    parsed = _parse_llm_response(raw)
    assert parsed["decision"] == "skip"
    assert parsed["score"] == pytest.approx(0.2)


def test_parse_llm_response_recovers_on_bad_json() -> None:
    parsed = _parse_llm_response("not json at all")
    assert parsed["decision"] == "keep"
    assert parsed["reason"] == "llm.parse_failed"


# ---------------------------------------------------------------------------
# Tier 1 — heuristic
# ---------------------------------------------------------------------------


def test_heuristic_must_exclude_short_circuits() -> None:
    cfg = _make_config(must_exclude=("press release",))
    svc = IngestionFilterService(
        _FakeSession(), config=cfg, persona_id="p",
        embedding_provider=_FakeEmbeddingProvider(), llm_client=_FakeLLM(),
    )
    content = _make_content(title="Acme Q4 press release: big news")
    decision = svc._evaluate(content)
    assert decision.decision == "skip"
    assert decision.tier is FilterTier.HEURISTIC
    assert "must_exclude" in decision.reason


def test_heuristic_must_include_short_circuits_to_keep_high() -> None:
    cfg = _make_config(must_include=("retrieval-augmented generation",))
    svc = IngestionFilterService(
        _FakeSession(), config=cfg, persona_id="p",
        embedding_provider=_FakeEmbeddingProvider(), llm_client=_FakeLLM(),
    )
    content = _make_content(markdown_content="Deep dive into retrieval-augmented generation at scale. " * 20)
    decision = svc._evaluate(content)
    assert decision.decision == "keep"
    assert decision.priority_bucket == "high"
    assert decision.tier is FilterTier.HEURISTIC


def test_heuristic_min_word_count_skip() -> None:
    cfg = _make_config(min_word_count=50)
    svc = IngestionFilterService(
        _FakeSession(), config=cfg, persona_id="p",
        embedding_provider=_FakeEmbeddingProvider(), llm_client=_FakeLLM(),
    )
    content = _make_content(markdown_content="too short")
    decision = svc._evaluate(content)
    assert decision.decision == "skip"
    assert decision.tier is FilterTier.HEURISTIC
    assert "min_word_count" in decision.reason


# ---------------------------------------------------------------------------
# Tier 2 — embedding
# ---------------------------------------------------------------------------


def test_embedding_tier_keep_above_high_threshold() -> None:
    # Profile and doc vectors are identical -> cosine=1.0 -> score=1.0.
    cfg = _make_config()
    provider = _FakeEmbeddingProvider(vector=[1.0, 0.0, 0.0])
    svc = IngestionFilterService(
        _FakeSession(), config=cfg, persona_id="p",
        embedding_provider=provider, llm_client=_FakeLLM(),
    )
    content = _make_content()
    decision = svc._evaluate(content)
    assert decision.decision == "keep"
    assert decision.tier is FilterTier.EMBEDDING
    assert decision.priority_bucket == "high"


def test_embedding_tier_skip_below_low_threshold() -> None:
    # Opposite vectors -> cosine=-1 -> normalized score=0.0.
    cfg = _make_config()
    svc = IngestionFilterService(
        _FakeSession(), config=cfg, persona_id="p",
        embedding_provider=_OpposedProvider(), llm_client=_FakeLLM(),
    )
    content = _make_content()
    decision = svc._evaluate(content)
    assert decision.decision == "skip"
    assert decision.tier is FilterTier.EMBEDDING
    assert decision.priority_bucket is None


def test_embedding_borderline_triggers_llm_tier() -> None:
    cfg = _make_config()
    llm = _FakeLLM(responses=['{"decision": "keep", "score": 0.58, "reason": "edge"}'])
    svc = IngestionFilterService(
        _FakeSession(), config=cfg, persona_id="p",
        embedding_provider=_BorderlineProvider(), llm_client=llm,
    )
    content = _make_content()
    decision = svc._evaluate(content)
    assert decision.tier is FilterTier.LLM
    assert decision.decision == "keep"
    assert len(llm.calls) == 1


def test_embedding_borderline_with_tier3_disabled_keeps_low() -> None:
    cfg = _make_config(llm_enabled=False)
    svc = IngestionFilterService(
        _FakeSession(), config=cfg, persona_id="p",
        embedding_provider=_BorderlineProvider(), llm_client=_FakeLLM(),
    )
    decision = svc._evaluate(_make_content())
    assert decision.tier is FilterTier.EMBEDDING
    assert decision.priority_bucket == "low"


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


def test_embedding_failure_falls_open_when_not_strict() -> None:
    cfg = _make_config()
    svc = IngestionFilterService(
        _FakeSession(), config=cfg, persona_id="p",
        embedding_provider=_RaisingProvider(), llm_client=_FakeLLM(),
    )
    decision = svc._evaluate(_make_content())
    assert decision.decision == "keep"
    assert "embedding.error" in decision.reason


def test_embedding_failure_raises_when_strict() -> None:
    cfg = _make_config(strict=True)
    svc = IngestionFilterService(
        _FakeSession(), config=cfg, persona_id="p",
        embedding_provider=_RaisingProvider(), llm_client=_FakeLLM(),
    )
    with pytest.raises(RuntimeError):
        svc._evaluate(_make_content())


# ---------------------------------------------------------------------------
# Support fixtures
# ---------------------------------------------------------------------------


class _OpposedProvider(_FakeEmbeddingProvider):
    def __init__(self) -> None:
        super().__init__(vector=[1.0, 0.0, 0.0])

    async def embed(self, text: str, *, is_query: bool = False) -> list[float]:
        # First call is profile encode (returns [1,0,0]); subsequent doc
        # encodes return opposite.
        self._calls = getattr(self, "_calls", 0) + 1
        if self._calls == 1:
            return [1.0, 0.0, 0.0]
        return [-1.0, 0.0, 0.0]


class _BorderlineProvider(_FakeEmbeddingProvider):
    def __init__(self) -> None:
        super().__init__(vector=[1.0, 0.0, 0.0])

    async def embed(self, text: str, *, is_query: bool = False) -> list[float]:
        self._calls = getattr(self, "_calls", 0) + 1
        if self._calls == 1:
            return [1.0, 0.0, 0.0]
        # angle ~70deg -> cosine ~0.34 -> score ~0.67 -- wait, we need borderline.
        # Use cosine 0.1 so (1+0.1)/2 = 0.55 which is in the band.
        return [0.1, 0.995, 0.0]


class _RaisingProvider(_FakeEmbeddingProvider):
    async def embed(self, text: str, *, is_query: bool = False) -> list[float]:
        raise RuntimeError("embedding boom")
