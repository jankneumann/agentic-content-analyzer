"""Unit tests for SettingsService CRUD operations."""

import pytest
from sqlalchemy.orm import Session, sessionmaker

from src.models.base import Base
from src.models.settings_override import SettingsOverride
from src.services.settings_service import SettingsService
from tests.helpers.test_db import create_test_engine, get_test_database_url

TEST_DATABASE_URL = get_test_database_url()


@pytest.fixture(scope="module")
def engine():
    """Create test database engine for settings service tests."""
    eng = create_test_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def db(engine) -> Session:
    """Create a session with transaction rollback."""
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


class TestSettingsServiceGet:
    """Tests for SettingsService.get()."""

    def test_get_existing_key(self, db):
        service = SettingsService(db)
        service.set("model.summarization", "claude-haiku-4-5")
        assert service.get("model.summarization") == "claude-haiku-4-5"

    def test_get_nonexistent_key_returns_none(self, db):
        service = SettingsService(db)
        assert service.get("model.nonexistent") is None

    def test_get_without_db_session(self):
        """Without DB session, get falls back to auto-session (returns None if DB unavailable)."""
        service = SettingsService()
        # In test env without real DB, this should return None (not raise)
        result = service.get("model.summarization")
        assert result is None


class TestSettingsServiceSet:
    """Tests for SettingsService.set()."""

    def test_set_creates_new_override(self, db):
        service = SettingsService(db)
        service.set("model.summarization", "claude-haiku-4-5")

        override = db.query(SettingsOverride).filter_by(key="model.summarization").first()
        assert override is not None
        assert override.value == "claude-haiku-4-5"
        assert override.version == 1

    def test_set_updates_existing_increments_version(self, db):
        service = SettingsService(db)
        service.set("model.summarization", "claude-haiku-4-5")
        service.set("model.summarization", "claude-sonnet-4-5")

        override = db.query(SettingsOverride).filter_by(key="model.summarization").first()
        assert override.value == "claude-sonnet-4-5"
        assert override.version == 2

    def test_set_with_description(self, db):
        service = SettingsService(db)
        service.set("model.summarization", "claude-haiku-4-5", description="Cost reduction")

        override = db.query(SettingsOverride).filter_by(key="model.summarization").first()
        assert override.description == "Cost reduction"

    def test_set_updates_description(self, db):
        service = SettingsService(db)
        service.set("model.summarization", "claude-haiku-4-5", description="v1")
        service.set("model.summarization", "claude-sonnet-4-5", description="v2")

        override = db.query(SettingsOverride).filter_by(key="model.summarization").first()
        assert override.description == "v2"

    def test_set_empty_value_raises(self, db):
        service = SettingsService(db)
        with pytest.raises(ValueError, match="cannot be empty"):
            service.set("model.summarization", "")

    def test_set_whitespace_value_raises(self, db):
        service = SettingsService(db)
        with pytest.raises(ValueError, match="cannot be empty"):
            service.set("model.summarization", "   ")

    def test_set_without_db_session_raises(self):
        service = SettingsService()
        with pytest.raises(ValueError, match="Database session required"):
            service.set("model.summarization", "claude-haiku-4-5")


class TestSettingsServiceDelete:
    """Tests for SettingsService.delete()."""

    def test_delete_existing_key(self, db):
        service = SettingsService(db)
        service.set("model.summarization", "claude-haiku-4-5")
        assert service.delete("model.summarization") is True
        assert service.get("model.summarization") is None

    def test_delete_nonexistent_key_returns_false(self, db):
        service = SettingsService(db)
        assert service.delete("model.nonexistent") is False

    def test_delete_without_db_session_raises(self):
        service = SettingsService()
        with pytest.raises(ValueError, match="Database session required"):
            service.delete("model.summarization")


class TestSettingsServiceListByPrefix:
    """Tests for SettingsService.list_by_prefix()."""

    def test_list_all(self, db):
        service = SettingsService(db)
        service.set("model.summarization", "claude-haiku-4-5")
        service.set("voice.provider", "openai")
        results = service.list_by_prefix()
        assert len(results) == 2

    def test_list_by_prefix_filters(self, db):
        service = SettingsService(db)
        service.set("model.summarization", "claude-haiku-4-5")
        service.set("model.theme_analysis", "claude-sonnet-4-5")
        service.set("voice.provider", "openai")

        model_results = service.list_by_prefix("model")
        assert len(model_results) == 2
        assert all(r["key"].startswith("model.") for r in model_results)

    def test_list_empty_prefix_returns_all(self, db):
        service = SettingsService(db)
        service.set("model.summarization", "claude-haiku-4-5")
        results = service.list_by_prefix("")
        assert len(results) >= 1

    def test_list_nonexistent_prefix_returns_empty(self, db):
        service = SettingsService(db)
        results = service.list_by_prefix("nonexistent")
        assert results == []

    def test_list_without_db_session_raises(self):
        service = SettingsService()
        with pytest.raises(ValueError, match="Database session required"):
            service.list_by_prefix()

    def test_list_results_sorted_by_key(self, db):
        service = SettingsService(db)
        service.set("model.z_step", "val-z")
        service.set("model.a_step", "val-a")
        results = service.list_by_prefix("model")
        keys = [r["key"] for r in results]
        assert keys == sorted(keys)


class TestSettingsServiceGetOverride:
    """Tests for SettingsService.get_override()."""

    def test_get_override_returns_record(self, db):
        service = SettingsService(db)
        service.set("model.summarization", "claude-haiku-4-5")
        override = service.get_override("model.summarization")
        assert override is not None
        assert isinstance(override, SettingsOverride)
        assert override.key == "model.summarization"

    def test_get_override_nonexistent_returns_none(self, db):
        service = SettingsService(db)
        assert service.get_override("model.nonexistent") is None

    def test_get_override_without_db_returns_none(self):
        service = SettingsService()
        assert service.get_override("model.summarization") is None
