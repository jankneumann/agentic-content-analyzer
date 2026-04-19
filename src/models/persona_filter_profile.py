"""PersonaFilterProfile — cached persona interest embeddings.

One row per (persona_id, embedding_provider, embedding_model). Invalidated by
the interest_hash — when a persona's `filter_profile.interest_description`
changes, the hash changes and the cache row is re-encoded.

Embeddings are stored as JSONB rather than pgvector to avoid a hard dependency
on the extension. Filtering does not need approximate-nearest-neighbor index
scans — a cosine similarity computation in Python against a small set of
profile vectors is sufficient.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB

from src.models.base import Base


class PersonaFilterProfile(Base):  # type: ignore[valid-type, misc]
    __tablename__ = "persona_filter_profiles"

    persona_id = Column(String(200), primary_key=True)
    embedding_provider = Column(String(100), primary_key=True)
    embedding_model = Column(String(200), primary_key=True)

    interest_hash = Column(String(64), nullable=False)
    embedding = Column(JSONB, nullable=False)

    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return (
            f"<PersonaFilterProfile(persona_id={self.persona_id!r}, "
            f"provider={self.embedding_provider!r}, model={self.embedding_model!r})>"
        )
