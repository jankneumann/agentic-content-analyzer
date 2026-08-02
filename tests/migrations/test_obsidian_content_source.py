"""Migration coverage for the additive Obsidian Content source enum."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _migration():
    root = Path(__file__).resolve().parents[2]
    paths = list(root.glob("alembic/versions/*obsidian_content_source*.py"))
    assert len(paths) == 1
    spec = importlib.util.spec_from_file_location("obsidian_content_source", paths[0])
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _generation_migration():
    root = Path(__file__).resolve().parents[2]
    paths = list(root.glob("alembic/versions/*obsidian_observation_generation*.py"))
    assert len(paths) == 1
    spec = importlib.util.spec_from_file_location("obsidian_observation_generation", paths[0])
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_obsidian_content_source_is_additive_after_state_migration(test_engine: Engine) -> None:
    migration = _migration()
    generation = _generation_migration()
    assert generation.down_revision == "a6c3e8f1d204"
    assert migration.down_revision == generation.revision
    with test_engine.connect() as connection:
        columns = connection.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='obsidian_ingest_state'"
            )
        ).scalars()
        assert "observation_generation" in set(columns)
        values = connection.execute(
            text(
                "SELECT enumlabel FROM pg_enum "
                "JOIN pg_type ON pg_type.oid = pg_enum.enumtypid "
                "WHERE pg_type.typname = 'contentsource'"
            )
        ).scalars()
        assert "obsidian" in set(values)


def test_obsidian_enum_downgrade_is_documented_noop() -> None:
    migration = _migration()
    assert migration.downgrade() is None
    assert "no-op" in (migration.downgrade.__doc__ or "").lower()
