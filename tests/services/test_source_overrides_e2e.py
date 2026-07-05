"""End-to-end acceptance for database source overrides through load_sources_config().

Exercises the full backend path on SQLite (no Postgres): a DB override row is
merged into the real sources.d/ YAML config. Covers the acceptance example
(adding https://www.normaltech.ai/ as a blog) and the disable-shadow behavior.

NOTE: lives under tests/services (the `services-stack` CI shard), not
tests/config, on purpose. In the `rest` shard these tests reordered a
pre-existing test-isolation bug (a shared FastAPI router object emptied by
another DB-backed test) into the path of tests/regression's route-inventory
assertion. Keep source-override tests out of the `rest` shard.
"""

from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.config.sources import load_sources_config, source_key
from src.models.base import Base
from src.models.source_override import SourceOverride


@pytest.fixture
def sqlite_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[SourceOverride.__table__])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@contextmanager
def _patched_get_db(monkeypatch, session):
    @contextmanager
    def fake_get_db():
        yield session

    # load_sources_config()'s merge imports get_db from src.storage.database lazily.
    import src.storage.database as database

    monkeypatch.setattr(database, "get_db", fake_get_db)
    yield


def _add_override(session, config, enabled=True):
    session.add(
        SourceOverride(
            source_key=source_key(config),
            source_type=config["type"],
            config=config,
            enabled=enabled,
            version=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    session.commit()


def test_db_blog_override_is_picked_up_by_load_sources_config(sqlite_session, monkeypatch):
    """Adding normaltech.ai as a DB blog makes it appear in the resolved blog sources."""
    _add_override(
        sqlite_session,
        {"type": "blog", "url": "https://www.normaltech.ai/", "name": "Normal Tech"},
    )
    with _patched_get_db(monkeypatch, sqlite_session):
        config = load_sources_config()

    blogs = config.get_blog_sources()
    by_url = {b.url: b for b in blogs}
    assert "https://www.normaltech.ai/" in by_url
    assert by_url["https://www.normaltech.ai/"].origin == "db"


def test_disabled_override_excludes_a_yaml_blog(sqlite_session, monkeypatch):
    """A disabled DB shadow over a real YAML blog removes it from active ingestion."""
    # Pick a real YAML blog to shadow.
    yaml_config = load_sources_config()
    yaml_blogs = yaml_config.get_blog_sources()
    assert yaml_blogs, "expected at least one YAML blog in sources.d/blogs.yaml"
    target = yaml_blogs[0]
    target_url = target.url

    _add_override(
        sqlite_session,
        {"type": "blog", "url": target_url},
        enabled=False,
    )
    with _patched_get_db(monkeypatch, sqlite_session):
        merged = load_sources_config()

    active_urls = {b.url for b in merged.get_blog_sources()}
    assert target_url not in active_urls
    # ...but the source remains visible (disabled) so it can be re-enabled.
    all_urls = {getattr(s, "url", None) for s in merged.sources}
    assert target_url in all_urls
