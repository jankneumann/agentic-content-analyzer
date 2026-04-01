"""Prompt service for loading prompts with database overrides.

This service provides centralized prompt management with:
- Default prompts loaded from YAML configuration
- Database overrides for user customizations
- Template variable interpolation via render()
- Support for chat prompts and pipeline step prompts

Usage:
    from src.services.prompt_service import PromptService

    # Without DB (defaults only)
    service = PromptService()
    prompt = service.get_chat_prompt("summary")

    # With DB for overrides
    service = PromptService(db_session)
    prompt = service.get_chat_prompt("summary")

    # With template variables
    rendered = service.render("pipeline.podcast_script.length_brief", period="daily")
"""

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from sqlalchemy.orm import Session

from src.models.settings import PromptOverride


class SafeDict(dict):
    """Dict subclass that returns the placeholder unchanged for missing keys.

    Used with str.format_map() to allow partial template rendering —
    unknown variables are left as {variable} in the output instead of
    raising KeyError.
    """

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class PromptService:
    """Load prompts from config with database overrides."""

    _CACHED_DEFAULTS: dict[str, Any] | None = None

    def __init__(self, db: Session | None = None):
        """Initialize the prompt service.

        Args:
            db: SQLAlchemy session for accessing overrides. If None, only defaults are used.
        """
        self.db = db
        self._defaults: dict[str, Any] = self._load_defaults()

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the cached defaults. Useful for testing."""
        cls._CACHED_DEFAULTS = None

    def _load_defaults(self) -> dict[str, Any]:
        """Load default prompts from ConfigRegistry.

        Uses the centralized ConfigRegistry to load from settings/prompts.yaml.
        Falls back to direct YAML file read if registry is not initialized
        (e.g., during early startup or in tests).
        """
        if PromptService._CACHED_DEFAULTS is not None:
            return PromptService._CACHED_DEFAULTS

        try:
            from src.config.config_registry import get_config_registry

            registry = get_config_registry()
            if "prompts" in registry.registered_domains:
                PromptService._CACHED_DEFAULTS = registry.get_raw("prompts")
                return PromptService._CACHED_DEFAULTS
        except (ImportError, ValueError, FileNotFoundError):
            # ImportError: registry module not available (unusual)
            # ValueError: domain not registered (registry not initialized yet)
            # FileNotFoundError: YAML file missing (registry misconfigured)
            pass

        # Fallback: direct YAML read (for tests or early startup before registry init)
        config_path = Path(__file__).parent.parent / "config" / "prompts.yaml"
        settings_path = Path(__file__).resolve().parent.parent.parent / "settings" / "prompts.yaml"

        yaml_path = settings_path if settings_path.exists() else config_path

        if not yaml_path.exists():
            raise FileNotFoundError(
                f"Prompts configuration not found. Checked: {settings_path}, {config_path}"
            )

        with open(yaml_path) as f:
            PromptService._CACHED_DEFAULTS = yaml.safe_load(f) or {}
            return PromptService._CACHED_DEFAULTS

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

    def render(self, key: str, **variables: Any) -> str:
        """Get a prompt and render template variables.

        Uses str.format_map() with SafeDict so that missing variables are
        left as {placeholder} in the output instead of raising KeyError.

        Variable values that contain literal braces (e.g., JSON content)
        are automatically escaped so they don't interfere with format_map().

        Args:
            key: Full dot-separated key (e.g., "pipeline.podcast_script.length_brief")
            **variables: Template variables to substitute

        Returns:
            Rendered prompt string
        """
        path = key.split(".")
        template = self._get_prompt(key, path)
        return self.render_template(template, variables)

    @staticmethod
    def render_template(template: str, variables: dict[str, Any]) -> str:
        """Render a template string with variables safely.

        Applies the same escaping logic as render() to ensure consistency.

        Args:
            template: The template string (e.g. "Hello {name}")
            variables: Dictionary of variables to substitute

        Returns:
            Rendered string with variables substituted
        """
        if not variables:
            return template

        # Escape literal braces in variable values to prevent format_map
        # from treating JSON content like {"key": "value"} as placeholders
        safe_variables = {
            k: str(v).replace("{", "{{").replace("}", "}}") for k, v in variables.items()
        }
        return template.format_map(SafeDict(safe_variables))

    def _get_prompt(self, key: str, path: list[str]) -> str:
        """Get a prompt, checking DB override first.

        If no db session was provided at init time, a short-lived session
        is opened automatically so that DB overrides are always respected
        regardless of how the caller instantiated PromptService.

        Args:
            key: Full dot-separated key for DB lookup
            path: List of keys to traverse in defaults dict

        Returns:
            Prompt value (override if exists, otherwise default)
        """
        # Check for DB override using provided session
        if self.db:
            override = self.db.query(PromptOverride).filter_by(key=key).first()
            if override:
                return str(override.value)
        else:
            # Auto-acquire a short-lived session for override lookup
            auto_override = self._check_override_auto(key)
            if auto_override is not None:
                return auto_override

        # Return default
        return self._get_nested(self._defaults, path, "")

    def _check_override_auto(self, key: str) -> str | None:
        """Check for a DB override using a short-lived session.

        Opens and closes its own session so callers that didn't provide
        a db session still get override support. Returns None if no
        override exists or if the database is unavailable.
        """
        try:
            from src.storage.database import get_db

            with get_db() as db:
                override = db.query(PromptOverride).filter_by(key=key).first()
                if override:
                    return str(override.value)
        except Exception:
            # DB unavailable (e.g., tests without DB, CLI without DB)
            pass
        return None

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

        return str(current) if current is not None else default

    def get_prompt(self, key: str) -> str:
        """Get a prompt value by its full dot-separated key.

        Checks DB override first, then falls back to YAML default.

        Args:
            key: Full dot-separated key (e.g., "pipeline.summarization.system")

        Returns:
            Prompt value (override if exists, otherwise default)
        """
        path = key.split(".")
        return self._get_prompt(key, path)

    def set_override(self, key: str, value: str, description: str | None = None) -> None:
        """Set a prompt override in database.

        Auto-increments version on update.

        Args:
            key: Full dot-separated key (e.g., "chat.summary.system")
            value: The override prompt value
            description: Optional description of the change

        Raises:
            ValueError: If no database session is available or value is empty
        """
        if not self.db:
            raise ValueError("Database session required for setting overrides")

        if not value or not value.strip():
            raise ValueError("Prompt override value cannot be empty")

        existing = self.db.query(PromptOverride).filter_by(key=key).first()
        if existing:
            existing.value = value
            existing.version = (existing.version or 1) + 1
            if description is not None:
                existing.description = description
        else:
            self.db.add(PromptOverride(key=key, value=value, version=1, description=description))
        self.db.commit()

    def clear_override(self, key: str) -> None:
        """Remove a prompt override, reverting to default.

        Args:
            key: Full dot-separated key to clear
        """
        if self.db:
            self.db.query(PromptOverride).filter_by(key=key).delete()
            self.db.commit()

    def get_override(self, key: str) -> PromptOverride | None:
        """Get an override record without falling back to default.

        Args:
            key: Full dot-separated key

        Returns:
            PromptOverride record if exists, None otherwise
        """
        if not self.db:
            return None

        return self.db.query(PromptOverride).filter_by(key=key).first()

    def get_default(self, key: str) -> str:
        """Get the default value from YAML for a key, ignoring DB overrides.

        Args:
            key: Full dot-separated key

        Returns:
            Default value from YAML, or empty string if not found
        """
        path = key.split(".")
        return self._get_nested(self._defaults, path, "")

    def list_all_prompts(self) -> list[dict[str, Any]]:
        """List all prompts with their defaults and overrides.

        Walks the full YAML tree to find all leaf-node prompts, not just
        those with a 'system' key. This captures prompt variants like
        pipeline.podcast_script.length_brief, etc.

        Returns:
            List of prompt info dictionaries with keys:
            - key: Full dot-separated key
            - category: chat or pipeline
            - step: artifact type or pipeline step
            - name: prompt name (e.g., "system", "length_brief")
            - default: Default value from YAML
            - override: Override value from DB (or None)
            - has_override: Boolean flag
            - version: Override version (or None)
            - description: Override description (or None)
        """
        prompts: list[dict[str, Any]] = []

        for category in ("chat", "pipeline"):
            category_config = self._defaults.get(category, {})
            for step, step_data in category_config.items():
                if not isinstance(step_data, dict):
                    continue
                for prompt_name, prompt_value in step_data.items():
                    if isinstance(prompt_value, dict):
                        # Skip nested dicts (shouldn't happen in current schema)
                        continue
                    key = f"{category}.{step}.{prompt_name}"
                    override = self.get_override(key)
                    prompts.append(
                        {
                            "key": key,
                            "category": category,
                            "step": step,
                            "name": prompt_name,
                            "default": str(prompt_value) if prompt_value is not None else "",
                            "override": override.value if override else None,
                            "has_override": override is not None,
                            "version": override.version if override else None,
                            "description": override.description if override else None,
                        }
                    )

        return prompts

    @property
    def defaults(self) -> dict[str, Any]:
        """Get the raw defaults dictionary for inspection."""
        return self._defaults.copy()
