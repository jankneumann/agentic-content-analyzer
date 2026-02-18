"""Settings override model for user-configurable settings."""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from src.models.base import Base


class SettingsOverride(Base):
    """User customization for application settings.

    Stores overrides for default settings (model selection, voice config, etc.).
    Keys follow dot-separated namespaces: domain.name
    Examples: "model.summarization", "voice.provider", "voice.speed"

    Precedence: env var > DB override > code default
    """

    __tablename__ = "settings_overrides"

    id = Column(Integer, primary_key=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
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
        return f"<SettingsOverride(key={self.key!r}, version={self.version})>"
