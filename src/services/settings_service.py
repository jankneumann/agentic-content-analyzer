"""Settings service for managing application settings overrides.

This service provides centralized settings management with:
- Database-persisted overrides for user customizations
- Key namespace filtering (e.g., list all model.* settings)
- Version tracking for audit trail
- Auto-session fallback when no DB session provided

Precedence: env var > DB override > code default
(Env var checking is the caller's responsibility.)

Usage:
    from src.services.settings_service import SettingsService

    # With DB session
    service = SettingsService(db_session)
    service.set("model.summarization", "claude-haiku-4-5")
    value = service.get("model.summarization")

    # Without DB (auto-acquires short-lived session)
    service = SettingsService()
    value = service.get("voice.provider")
"""

from typing import Any

from sqlalchemy.orm import Session

from src.models.settings_override import SettingsOverride


class SettingsService:
    """Manage settings overrides in the database."""

    def __init__(self, db: Session | None = None):
        """Initialize the settings service.

        Args:
            db: SQLAlchemy session for accessing overrides.
                If None, auto-acquires short-lived sessions for reads.
        """
        self.db = db

    def get(self, key: str) -> str | None:
        """Get a settings override value.

        Args:
            key: Dot-separated settings key (e.g., "model.summarization")

        Returns:
            Override value if exists, None otherwise
        """
        if self.db:
            override = self.db.query(SettingsOverride).filter_by(key=key).first()
            if override:
                return str(override.value)
            return None

        # Auto-acquire session for read
        return self._check_override_auto(key)

    def set(self, key: str, value: str, description: str | None = None) -> None:
        """Set a settings override.

        Auto-increments version on update.

        Args:
            key: Dot-separated settings key
            value: The override value
            description: Optional description of the change

        Raises:
            ValueError: If no database session is available or value is empty
        """
        if not self.db:
            raise ValueError("Database session required for setting overrides")

        if not value or not value.strip():
            raise ValueError("Settings override value cannot be empty")

        existing = self.db.query(SettingsOverride).filter_by(key=key).first()
        if existing:
            existing.value = value
            existing.version = (existing.version or 1) + 1
            if description is not None:
                existing.description = description
        else:
            self.db.add(SettingsOverride(key=key, value=value, version=1, description=description))
        self.db.commit()

    def delete(self, key: str) -> bool:
        """Delete a settings override.

        Args:
            key: Dot-separated settings key

        Returns:
            True if an override was deleted, False if key didn't exist
        """
        if not self.db:
            raise ValueError("Database session required for deleting overrides")

        count = self.db.query(SettingsOverride).filter_by(key=key).delete()
        self.db.commit()
        return count > 0

    def list_by_prefix(self, prefix: str = "") -> list[dict[str, Any]]:
        """List settings overrides, optionally filtered by key prefix.

        Args:
            prefix: Key prefix to filter (e.g., "model" returns all model.* keys).
                    Empty string returns all overrides.

        Returns:
            List of override dictionaries with key, value, version, description
        """
        if not self.db:
            raise ValueError("Database session required for listing overrides")

        query = self.db.query(SettingsOverride)
        if prefix:
            query = query.filter(SettingsOverride.key.like(f"{prefix}.%"))
        query = query.order_by(SettingsOverride.key)

        return [
            {
                "key": override.key,
                "value": override.value,
                "version": override.version,
                "description": override.description,
            }
            for override in query.all()
        ]

    def get_override(self, key: str) -> SettingsOverride | None:
        """Get the full override record.

        Args:
            key: Dot-separated settings key

        Returns:
            SettingsOverride record if exists, None otherwise
        """
        if not self.db:
            return None
        return self.db.query(SettingsOverride).filter_by(key=key).first()

    def _check_override_auto(self, key: str) -> str | None:
        """Check for a DB override using a short-lived session.

        Opens and closes its own session so callers that didn't provide
        a db session still get override support. Returns None if no
        override exists or if the database is unavailable.
        """
        try:
            from src.storage.database import get_db

            with get_db() as db:
                override = db.query(SettingsOverride).filter_by(key=key).first()
                if override:
                    return str(override.value)
        except Exception:
            pass
        return None
