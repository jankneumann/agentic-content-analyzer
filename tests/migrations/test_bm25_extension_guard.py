"""Regression coverage for optional pg_search installation on managed Postgres."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, Mock

import sqlalchemy as sa


def _load_migration() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[2]
    migration_path = repo_root / "alembic/versions/e7f8a9b0c1d2_fix_bm25_index_key_field.py"
    spec = importlib.util.spec_from_file_location("bm25_key_field_migration", migration_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pg_search_guard_reuses_installed_extension() -> None:
    migration = _load_migration()
    connection = MagicMock()
    connection.execute.return_value.scalar.return_value = 1

    assert migration._ensure_pg_search_installed(connection) is True
    connection.begin_nested.assert_not_called()


def test_pg_search_guard_skips_provider_denial() -> None:
    migration = _load_migration()
    connection = MagicMock()
    missing = Mock()
    missing.scalar.return_value = None
    denial = sa.exc.ProgrammingError("CREATE EXTENSION pg_search", {}, Exception("denied"))
    connection.execute.side_effect = [missing, denial]

    assert migration._ensure_pg_search_installed(connection) is False
    connection.begin_nested.assert_called_once_with()


def test_pg_search_guard_accepts_successful_install() -> None:
    migration = _load_migration()
    connection = MagicMock()
    missing = Mock()
    missing.scalar.return_value = None
    installed = Mock()
    connection.execute.side_effect = [missing, installed]

    assert migration._ensure_pg_search_installed(connection) is True
    connection.begin_nested.assert_called_once_with()
