"""Prompt service for loading prompts with database overrides.

This service provides centralized prompt management with:
- Default prompts loaded from YAML configuration
- Database overrides for user customizations
- Support for chat prompts and pipeline step prompts

Usage:
    from src.services.prompt_service import PromptService

    # Without DB (defaults only)
    service = PromptService()
    prompt = service.get_chat_prompt("summary")

    # With DB for overrides
    service = PromptService(db_session)
    prompt = service.get_chat_prompt("summary")  # Returns override if exists
"""

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from src.models.settings import PromptOverride


class PromptService:
    """Load prompts from config with database overrides."""

    def __init__(self, db: Session | None = None):
        """Initialize the prompt service.

        Args:
            db: SQLAlchemy session for accessing overrides. If None, only defaults are used.
        """
        self.db = db
        self._defaults: dict[str, Any] = self._load_defaults()

    def _load_defaults(self) -> dict[str, Any]:
        """Load default prompts from YAML configuration."""
        config_path = Path(__file__).parent.parent / "config" / "prompts.yaml"

        if not config_path.exists():
            raise FileNotFoundError(
                f"Prompts configuration not found: {config_path}. "
                "Ensure src/config/prompts.yaml exists."
            )

        with open(config_path) as f:
            return yaml.safe_load(f) or {}

    def get_chat_prompt(self, artifact_type: str) -> str:
        """Get chat system prompt with DB override.

        Args:
            artifact_type: Type of artifact (summary, digest, script)

        Returns:
            System prompt for the chat assistant
        """
        key = f"chat.{artifact_type}.system"
        return self._get_prompt(key, ["chat", artifact_type, "system"])

    def get_pipeline_prompt(self, step: str, prompt_name: str = "system") -> str:
        """Get pipeline step prompt with DB override.

        Args:
            step: Pipeline step (summarization, digest_creation, etc.)
            prompt_name: Name of the prompt (default: system)

        Returns:
            Prompt for the pipeline step
        """
        key = f"pipeline.{step}.{prompt_name}"
        return self._get_prompt(key, ["pipeline", step, prompt_name])

    def _get_prompt(self, key: str, path: list[str]) -> str:
        """Get a prompt, checking DB override first.

        Args:
            key: Full dot-separated key for DB lookup
            path: List of keys to traverse in defaults dict

        Returns:
            Prompt value (override if exists, otherwise default)
        """
        # Check for DB override
        if self.db:
            override = self.db.query(PromptOverride).filter_by(key=key).first()
            if override:
                return override.value

        # Return default
        return self._get_nested(self._defaults, path, "")

    def _get_nested(self, data: dict[str, Any], path: list[str], default: str) -> str:
        """Get a nested value from a dictionary.

        Args:
            data: Dictionary to traverse
            path: List of keys to follow
            default: Default value if path not found

        Returns:
            Value at path or default
        """
        current = data
        for key in path:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]

        return str(current) if current else default

    def set_override(self, key: str, value: str) -> None:
        """Set a prompt override in database.

        Args:
            key: Full dot-separated key (e.g., "chat.summary.system")
            value: The override prompt value

        Raises:
            ValueError: If no database session is available
        """
        if not self.db:
            raise ValueError("Database session required for setting overrides")

        existing = self.db.query(PromptOverride).filter_by(key=key).first()
        if existing:
            existing.value = value
        else:
            self.db.add(PromptOverride(key=key, value=value))
        self.db.commit()

    def clear_override(self, key: str) -> None:
        """Remove a prompt override, reverting to default.

        Args:
            key: Full dot-separated key to clear
        """
        if self.db:
            self.db.query(PromptOverride).filter_by(key=key).delete()
            self.db.commit()

    def get_override(self, key: str) -> str | None:
        """Get an override value without falling back to default.

        Args:
            key: Full dot-separated key

        Returns:
            Override value if exists, None otherwise
        """
        if not self.db:
            return None

        override = self.db.query(PromptOverride).filter_by(key=key).first()
        return override.value if override else None

    def list_all_prompts(self) -> list[dict[str, Any]]:
        """List all prompts with their defaults and overrides.

        Returns:
            List of prompt info dictionaries with keys:
            - key: Full dot-separated key
            - category: chat or pipeline
            - step: artifact type or pipeline step
            - default: Default value from YAML
            - override: Override value from DB (or None)
            - has_override: Boolean flag
        """
        prompts = []

        # Chat prompts
        chat_config = self._defaults.get("chat", {})
        for artifact_type, prompt_data in chat_config.items():
            if isinstance(prompt_data, dict) and "system" in prompt_data:
                key = f"chat.{artifact_type}.system"
                override = self.get_override(key)
                prompts.append(
                    {
                        "key": key,
                        "category": "chat",
                        "step": artifact_type,
                        "default": prompt_data["system"],
                        "override": override,
                        "has_override": override is not None,
                    }
                )

        # Pipeline prompts
        pipeline_config = self._defaults.get("pipeline", {})
        for step, prompt_data in pipeline_config.items():
            if isinstance(prompt_data, dict) and "system" in prompt_data:
                key = f"pipeline.{step}.system"
                override = self.get_override(key)
                prompts.append(
                    {
                        "key": key,
                        "category": "pipeline",
                        "step": step,
                        "default": prompt_data["system"],
                        "override": override,
                        "has_override": override is not None,
                    }
                )

        return prompts

    @property
    def defaults(self) -> dict[str, Any]:
        """Get the raw defaults dictionary for inspection."""
        return self._defaults.copy()
