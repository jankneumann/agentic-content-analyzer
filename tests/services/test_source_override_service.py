"""Unit tests for SourceOverrideService CRUD + validation.

Covers spec scenarios under "Database Source Overrides" and the disable-shadow
behavior of "Source Resolution Precedence and Merge" (design decisions D4, D5).
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.models.base import Base
from src.models.source_override import SourceOverride
from src.services.source_override_service import SourceOverrideError, SourceOverrideService


@pytest.fixture(scope="module")
def engine():
    """In-memory-style SQLite engine on a temp file (parallel-safe, no Postgres)."""
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng, tables=[SourceOverride.__table__])
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


BLOG = {"type": "blog", "url": "https://www.normaltech.ai/", "name": "Normal Tech"}


class TestValidation:
    def test_rejects_non_dict(self, db):
        with pytest.raises(SourceOverrideError):
            SourceOverrideService(db).validate_config("nope")  # type: ignore[arg-type]

    def test_rejects_missing_type(self, db):
        with pytest.raises(SourceOverrideError):
            SourceOverrideService(db).validate_config({"url": "https://x.com"})

    def test_rejects_blog_without_url(self, db):
        with pytest.raises(SourceOverrideError):
            SourceOverrideService(db).validate_config({"type": "blog", "name": "x"})

    def test_strips_origin_from_validated(self, db):
        out = SourceOverrideService(db).validate_config({**BLOG, "origin": "db"})
        assert "origin" not in out


class TestUpsert:
    def test_insert_new_row(self, db):
        svc = SourceOverrideService(db)
        row = svc.upsert(BLOG)
        assert row.source_key == "blog:https://www.normaltech.ai/"
        assert row.source_type == "blog"
        assert row.version == 1
        assert row.enabled is True
        assert row.config["url"] == "https://www.normaltech.ai/"

    def test_update_existing_bumps_version(self, db):
        svc = SourceOverrideService(db)
        svc.upsert(BLOG)
        row = svc.upsert({**BLOG, "max_entries": 42})
        assert row.version == 2
        assert row.config["max_entries"] == 42
        # still a single row
        assert len(svc.list_overrides()) == 1

    def test_invalid_config_raises(self, db):
        with pytest.raises(SourceOverrideError):
            SourceOverrideService(db).upsert({"type": "blog"})

    def test_valid_but_unkeyable_source_raises_service_error(self, db):
        # readwise passes the Source union but has no locator field; upsert must
        # surface a SourceOverrideError (-> HTTP 400), not a bare ValueError (500).
        with pytest.raises(SourceOverrideError):
            SourceOverrideService(db).upsert({"type": "readwise"})


class TestListAndGet:
    def test_list_filters_by_type(self, db):
        svc = SourceOverrideService(db)
        svc.upsert(BLOG)
        svc.upsert({"type": "rss", "url": "https://r.com/feed"})
        assert len(svc.list_overrides()) == 2
        assert len(svc.list_overrides(source_type="blog")) == 1

    def test_get_returns_row(self, db):
        svc = SourceOverrideService(db)
        svc.upsert(BLOG)
        assert svc.get("blog:https://www.normaltech.ai/") is not None
        assert svc.get("blog:missing") is None

    def test_list_for_merge_includes_disabled(self, db):
        svc = SourceOverrideService(db)
        svc.upsert(BLOG)
        svc.set_enabled("blog:https://www.normaltech.ai/", False)
        merge = svc.list_for_merge()
        assert len(merge) == 1
        assert merge[0]["enabled"] is False


class TestEnableDisableDelete:
    def test_set_enabled_flips_existing(self, db):
        svc = SourceOverrideService(db)
        svc.upsert(BLOG)
        row = svc.set_enabled("blog:https://www.normaltech.ai/", False)
        assert row.enabled is False
        assert row.version == 2

    def test_disable_yaml_source_with_fallback_creates_shadow(self, db):
        svc = SourceOverrideService(db)
        # No row exists yet; disabling a YAML source supplies its config as fallback.
        row = svc.set_enabled(
            "blog:https://www.together.ai/blog",
            False,
            fallback_config={"type": "blog", "url": "https://www.together.ai/blog"},
        )
        assert row.enabled is False
        assert row.source_key == "blog:https://www.together.ai/blog"

    def test_set_enabled_without_row_or_fallback_raises(self, db):
        with pytest.raises(SourceOverrideError):
            SourceOverrideService(db).set_enabled("blog:missing", False)

    def test_delete_removes_row(self, db):
        svc = SourceOverrideService(db)
        svc.upsert(BLOG)
        assert svc.delete("blog:https://www.normaltech.ai/") is True
        assert svc.delete("blog:https://www.normaltech.ai/") is False
