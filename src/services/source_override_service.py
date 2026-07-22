"""Service for managing database-backed ingestion source overrides.

Mirrors :class:`~src.services.settings_service.SettingsService` but stores a
structured, validated source definition rather than a scalar value. Each
override is keyed by the natural key ``<type>:<locator>`` (see
:func:`src.config.sources.source_key`) so that database rows line up with their
YAML twins for the merge in :func:`src.config.sources.load_sources_config`.

Usage:
    from src.services.source_override_service import SourceOverrideService

    service = SourceOverrideService(db)
    service.upsert({"type": "blog", "url": "https://www.normaltech.ai/"})
"""

from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from src.config.sources import Source, source_key
from src.models.source_override import SourceOverride

# Validates a raw source dict against the discriminated Source union — the same
# schema the YAML loader enforces. Built once at import time.
_SOURCE_ADAPTER: TypeAdapter[Any] = TypeAdapter(Source)


class SourceOverrideError(ValueError):
    """Raised when a source override config fails validation."""


class SourceOverrideService:
    """Manage ingestion source overrides in the database."""

    def __init__(self, db: Session):
        """Args: db - SQLAlchemy session (required for all operations)."""
        self.db = db

    # --- Validation -------------------------------------------------------

    @staticmethod
    def validate_config(config: dict[str, Any]) -> dict[str, Any]:
        """Validate a raw source dict against the Source union.

        Returns the normalized dict (with model defaults applied, ``origin``
        stripped so it is derived at merge time).

        Raises:
            SourceOverrideError: If the config is not a valid source.
        """
        if not isinstance(config, dict) or not config.get("type"):
            raise SourceOverrideError("source config must be an object with a 'type' field")
        try:
            model = _SOURCE_ADAPTER.validate_python(config)
        except ValidationError as e:
            raise SourceOverrideError(f"invalid source config: {e}") from e
        data = model.model_dump()
        data.pop("origin", None)
        return data

    # --- Reads ------------------------------------------------------------

    def get(self, key: str) -> SourceOverride | None:
        """Return the override row for a natural key, or None."""
        return self.db.query(SourceOverride).filter_by(source_key=key).first()

    def list_overrides(self, source_type: str | None = None) -> list[dict[str, Any]]:
        """List override rows, optionally filtered by source type.

        Returns dicts with key, type, config, enabled, version, description.
        """
        query = self.db.query(SourceOverride)
        if source_type:
            query = query.filter(SourceOverride.source_type == source_type)
        query = query.order_by(SourceOverride.source_key)
        return [
            {
                "source_key": o.source_key,
                "source_type": o.source_type,
                "config": o.config,
                "enabled": o.enabled,
                "version": o.version,
                "description": o.description,
            }
            for o in query.all()
        ]

    def list_for_merge(self) -> list[dict[str, Any]]:
        """Return all overrides (enabled and disabled) for the loader merge.

        Disabled rows are included so they can shadow their YAML twin.
        """
        return [
            {"source_key": o.source_key, "config": o.config, "enabled": o.enabled}
            for o in self.db.query(SourceOverride).all()
        ]

    # --- Writes -----------------------------------------------------------

    def upsert(
        self,
        config: dict[str, Any],
        *,
        enabled: bool | None = None,
        description: str | None = None,
    ) -> SourceOverride:
        """Create or update a source override (union-if-new / update-if-existing).

        The config is validated against the Source union and the natural key is
        derived from it. On update, ``version`` is incremented.

        Raises:
            SourceOverrideError: If the config is invalid.
        """
        validated = self.validate_config(config)
        try:
            key = source_key(validated)
        except ValueError as e:
            # Valid per the Source union but missing a locator (e.g. readwise with
            # no name, arxiv with only categories). Surface as a 4xx, not a 500.
            raise SourceOverrideError(
                f"cannot derive a source key for this {validated.get('type')!r} source: {e}. "
                "Provide a locator (url/id/query/name) for it."
            ) from e
        stype = validated["type"]

        existing = self.get(key)
        if existing:
            existing.config = validated
            existing.source_type = stype
            existing.version = (existing.version or 1) + 1
            if enabled is not None:
                existing.enabled = enabled
            if description is not None:
                existing.description = description
            self.db.commit()
            self.db.refresh(existing)
            return existing

        row = SourceOverride(
            source_key=key,
            source_type=stype,
            config=validated,
            enabled=True if enabled is None else enabled,
            version=1,
            description=description,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def set_enabled(
        self,
        key: str,
        enabled: bool,
        *,
        fallback_config: dict[str, Any] | None = None,
    ) -> SourceOverride:
        """Enable or disable a source by key.

        If no override row exists yet (e.g. disabling a YAML-defined source),
        ``fallback_config`` MUST be supplied so a self-describing shadow row can
        be created. The fallback is the resolved source's own definition.

        Raises:
            SourceOverrideError: If the row is absent and no fallback is given.
        """
        existing = self.get(key)
        if existing:
            existing.enabled = enabled
            existing.version = (existing.version or 1) + 1
            self.db.commit()
            self.db.refresh(existing)
            return existing

        if fallback_config is None:
            raise SourceOverrideError(
                f"no source override for key {key!r} and no fallback config to create one"
            )
        return self.upsert(fallback_config, enabled=enabled)

    def delete(self, key: str) -> bool:
        """Delete an override row by key. Returns True if a row was removed."""
        count = self.db.query(SourceOverride).filter_by(source_key=key).delete()
        self.db.commit()
        return count > 0
