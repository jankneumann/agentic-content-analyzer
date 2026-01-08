"""Settings data models for user configurations."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from src.models.newsletter import Base


class PromptOverride(Base):
    """User customization for prompts.

    Stores overrides for default prompts defined in config/prompts.yaml.
    Keys follow the pattern: category.step.prompt_type
    Examples: "chat.summary.system", "pipeline.summarization.system"
    """

    __tablename__ = "prompt_overrides"

    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<PromptOverride(key={self.key!r})>"
