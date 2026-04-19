"""Persona interest-vector cache.

Encoding the persona's interest description on every filter call would dominate
latency, so we cache one vector per (persona_id, embedding_provider,
embedding_model) tuple in `persona_filter_profiles`. Invalidation is by the
SHA-256 hash of the interest description.

Cosine similarity is computed in Python against the cached vector — we don't
need ANN index scans for a small number of personas.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from src.models.persona_filter_profile import PersonaFilterProfile


@dataclass(frozen=True)
class CachedProfile:
    persona_id: str
    embedding_provider: str
    embedding_model: str
    interest_hash: str
    embedding: list[float]


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity clamped to [-1, 1]. Returns 0.0 for zero vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    sim = dot / (math.sqrt(na) * math.sqrt(nb))
    if sim > 1.0:
        return 1.0
    if sim < -1.0:
        return -1.0
    return sim


class PersonaProfileCache:
    """Upserts/reads persona interest embeddings backed by Postgres."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get(
        self, *, persona_id: str, embedding_provider: str, embedding_model: str
    ) -> CachedProfile | None:
        row = self._db.get(
            PersonaFilterProfile,
            (persona_id, embedding_provider, embedding_model),
        )
        if row is None:
            return None
        return CachedProfile(
            persona_id=row.persona_id,
            embedding_provider=row.embedding_provider,
            embedding_model=row.embedding_model,
            interest_hash=row.interest_hash,
            embedding=list(row.embedding or []),
        )

    def needs_refresh(self, cached: CachedProfile | None, interest_description: str) -> bool:
        if cached is None:
            return True
        return cached.interest_hash != _hash(interest_description)

    def upsert(
        self,
        *,
        persona_id: str,
        embedding_provider: str,
        embedding_model: str,
        interest_description: str,
        embedding: list[float],
    ) -> CachedProfile:
        digest = _hash(interest_description)
        row = self._db.get(
            PersonaFilterProfile,
            (persona_id, embedding_provider, embedding_model),
        )
        if row is None:
            row = PersonaFilterProfile(
                persona_id=persona_id,
                embedding_provider=embedding_provider,
                embedding_model=embedding_model,
                interest_hash=digest,
                embedding=list(embedding),
                updated_at=datetime.now(UTC).replace(tzinfo=None),
            )
            self._db.add(row)
        else:
            row.interest_hash = digest
            row.embedding = list(embedding)
            row.updated_at = datetime.now(UTC).replace(tzinfo=None)
        self._db.flush()
        return CachedProfile(
            persona_id=persona_id,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            interest_hash=digest,
            embedding=list(embedding),
        )
