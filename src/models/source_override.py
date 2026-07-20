"""Source override model for database-backed ingestion source configuration.

Stores ingestion source definitions as validated JSON, merged on top of the
``sources.d/*.yaml`` defaults by :func:`src.config.sources.load_sources_config`.

Each row is keyed by a natural ``source_key`` of the form ``<type>:<locator>``
(see ``src.config.sources._source_key``) so that a database override lines up
with its YAML twin: a row with the same key overrides the YAML source, and a
row with ``enabled=False`` shadows (suppresses) it.

Precedence: env (n/a for sources) > DB override > YAML default.
"""

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.types import JSON

from src.models.base import Base


class SourceOverride(Base):
    """Database override for a single ingestion source.

    Mirrors the :class:`~src.models.settings_override.SettingsOverride` pattern,
    but stores a structured source definition (``config``) rather than a scalar,
    plus an ``enabled`` flag so a YAML source can be disabled without deleting it.
    """

    __tablename__ = "source_overrides"

    id = Column(Integer, primary_key=True)
    # Natural key "<type>:<locator>", e.g. "blog:https://www.normaltech.ai/"
    source_key = Column(String(512), unique=True, nullable=False, index=True)
    source_type = Column(String(64), nullable=False, index=True)
    # Full source definition, validated against the Source discriminated union.
    config = Column(JSON, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
    description = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return (
            f"<SourceOverride(source_key={self.source_key!r}, "
            f"enabled={self.enabled}, version={self.version})>"
        )
