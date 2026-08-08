"""Unit tests for SourceOverrideService CRUD + validation.

Covers spec scenarios under "Database Source Overrides" and the disable-shadow
behavior of "Source Resolution Precedence and Merge" (design decisions D4, D5).
"""

import importlib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config.sources import ObsidianVaultSource
from src.models.base import Base
from src.models.source_override import SourceOverride
from src.services.source_override_service import (
    SourceOverrideError,
    SourceOverrideService,
    public_source_key,
)


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
OBSIDIAN = {
    "type": "obsidian_vault",
    "vault_id": "personal",
    "vault_path": "/srv/obsidian/private-vault",
    "ingest_folder": "Clips/Inbox",
}


def test_obsidian_model_public_key_never_falls_back_to_natural_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "configured-source-key-secret-for-tests"
    settings_module = importlib.import_module("src.config.settings")
    monkeypatch.setattr(
        settings_module,
        "get_settings",
        lambda: type(
            "TestSettings",
            (),
            {"get_configured_source_key_secret": staticmethod(lambda: secret)},
        )(),
    )
    source = ObsidianVaultSource(
        vault_id="private-vault-id",
        vault_path="/srv/obsidian/private",
    )

    projected = public_source_key(source)

    assert projected.startswith("src_")
    assert "private-vault-id" not in projected


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

    def test_singleton_source_uses_stable_default_key(self, db):
        row = SourceOverrideService(db).upsert({"type": "readwise"})

        assert row.source_key == "readwise:default"

    def test_obsidian_private_config_round_trips_under_stable_vault_identity(self, db):
        service = SourceOverrideService(db)

        row = service.upsert(OBSIDIAN)
        merged = service.list_for_merge()

        assert row.source_key == "obsidian_vault:personal"
        assert row.config["vault_path"] == "/srv/obsidian/private-vault"
        assert row.config["ingest_folder"] == "Clips/Inbox"
        assert merged == [
            {
                "source_key": "obsidian_vault:personal",
                "config": row.config,
                "enabled": True,
            }
        ]


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

    def test_obsidian_public_lookup_requires_opaque_key_but_upsert_stays_natural(
        self,
        db,
        monkeypatch: pytest.MonkeyPatch,
    ):
        secret = "configured-source-key-secret-for-tests"
        settings_module = importlib.import_module("src.config.settings")
        monkeypatch.setattr(
            settings_module,
            "get_settings",
            lambda: type(
                "TestSettings",
                (),
                {"get_configured_source_key_secret": staticmethod(lambda: secret)},
            )(),
        )
        svc = SourceOverrideService(db)
        inserted = svc.upsert(OBSIDIAN)
        updated = svc.upsert({**OBSIDIAN, "max_files": 25})
        opaque_key = public_source_key(updated)

        with pytest.raises(SourceOverrideError, match="opaque source key"):
            svc.get("obsidian_vault:personal")

        assert updated.id == inserted.id
        assert updated.version == 2
        assert svc.get(opaque_key).id == inserted.id
        assert svc.list_for_merge()[0]["source_key"] == "obsidian_vault:personal"

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
        assert svc.delete("blog:https://www.normaltech.ai/") == "blog:https://www.normaltech.ai/"
        assert svc.delete("blog:https://www.normaltech.ai/") is None

    def test_delete_obsidian_returns_only_projected_public_key(
        self,
        db,
        monkeypatch: pytest.MonkeyPatch,
    ):
        secret = "configured-source-key-secret-for-tests"
        settings_module = importlib.import_module("src.config.settings")
        monkeypatch.setattr(
            settings_module,
            "get_settings",
            lambda: type(
                "TestSettings",
                (),
                {"get_configured_source_key_secret": staticmethod(lambda: secret)},
            )(),
        )
        svc = SourceOverrideService(db)
        row = svc.upsert(OBSIDIAN)
        opaque_key = public_source_key(row)

        assert svc.delete(opaque_key) == opaque_key
        assert "personal" not in opaque_key
