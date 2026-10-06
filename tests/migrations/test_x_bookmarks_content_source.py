"""Migration coverage for the additive X bookmarks Content source enum."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.models.content import ContentSource

ROOT = Path(__file__).resolve().parents[2]


def _migration():
    paths = list(ROOT.glob("alembic/versions/*x_bookmarks_content_source*.py"))
    assert len(paths) == 1
    spec = importlib.util.spec_from_file_location("x_bookmarks_content_source", paths[0])
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_x_bookmarks_migration_is_idempotent_add_value() -> None:
    source = inspect.getsource(_migration().upgrade)
    assert "ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'x_bookmarks'" in source


def test_x_bookmarks_enum_downgrade_is_documented_noop() -> None:
    migration = _migration()
    assert migration.downgrade() is None
    assert "no-op" in (migration.downgrade.__doc__ or "").lower()


def test_x_bookmarks_python_enum_matches_contract_ddl() -> None:
    assert ContentSource.X_BOOKMARKS.value == "x_bookmarks"
    schema = (ROOT / "openspec/contracts/content-workflows/db/schema.sql").read_text()
    assert "ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'x_bookmarks';" in schema


def test_x_bookmarks_enum_value_exists_after_upgrade(test_engine: Engine) -> None:
    with test_engine.connect() as connection:
        values = connection.execute(
            text(
                "SELECT enumlabel FROM pg_enum "
                "JOIN pg_type ON pg_type.oid = pg_enum.enumtypid "
                "WHERE pg_type.typname = 'contentsource'"
            )
        ).scalars()
        assert {source.value for source in ContentSource} <= set(values)
