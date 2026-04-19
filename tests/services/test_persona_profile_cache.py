"""Unit tests for PersonaProfileCache (in-memory fake session).

We don't use a real DB here — the cache operates against a SQLAlchemy Session,
and a minimal stub keyed by primary-key tuple is enough to exercise the
lookup / upsert / invalidation logic.
"""

from __future__ import annotations

from typing import Any

from src.models.persona_filter_profile import PersonaFilterProfile
from src.services.persona_profile_cache import PersonaProfileCache, cosine


class _FakeSession:
    def __init__(self) -> None:
        self._rows: dict[tuple[type, Any], Any] = {}

    def get(self, model: type, pk: Any) -> Any | None:
        return self._rows.get((model, pk))

    def add(self, row: Any) -> None:
        key = (
            type(row),
            (row.persona_id, row.embedding_provider, row.embedding_model),
        )
        self._rows[key] = row

    def flush(self) -> None:
        return None


def test_cache_miss_needs_refresh() -> None:
    cache = PersonaProfileCache(_FakeSession())
    assert cache.needs_refresh(None, "interest") is True


def test_cache_hit_with_same_hash_does_not_need_refresh() -> None:
    session = _FakeSession()
    cache = PersonaProfileCache(session)
    cached = cache.upsert(
        persona_id="p1",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        interest_description="ai agents",
        embedding=[0.1, 0.2, 0.3],
    )
    assert cache.needs_refresh(cached, "ai agents") is False


def test_cache_hit_with_different_description_requires_refresh() -> None:
    session = _FakeSession()
    cache = PersonaProfileCache(session)
    cached = cache.upsert(
        persona_id="p1",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        interest_description="ai agents",
        embedding=[0.1, 0.2, 0.3],
    )
    assert cache.needs_refresh(cached, "quantum computing") is True


def test_upsert_updates_existing_row_in_place() -> None:
    session = _FakeSession()
    cache = PersonaProfileCache(session)
    a = cache.upsert(
        persona_id="p1",
        embedding_provider="openai",
        embedding_model="m",
        interest_description="d1",
        embedding=[1.0],
    )
    b = cache.upsert(
        persona_id="p1",
        embedding_provider="openai",
        embedding_model="m",
        interest_description="d2",
        embedding=[0.5],
    )
    assert a.interest_hash != b.interest_hash
    # One row in the fake session — upsert didn't create a duplicate.
    matching = [
        v for (cls, _pk), v in session._rows.items() if cls is PersonaFilterProfile
    ]
    assert len(matching) == 1


def test_cosine_parallel_is_one() -> None:
    assert cosine([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_antiparallel_is_minus_one() -> None:
    assert cosine([1.0, 0.0], [-1.0, 0.0]) == -1.0


def test_cosine_orthogonal_is_zero() -> None:
    assert cosine([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_zero_vector_returns_zero_not_nan() -> None:
    assert cosine([0.0, 0.0], [1.0, 0.0]) == 0.0
