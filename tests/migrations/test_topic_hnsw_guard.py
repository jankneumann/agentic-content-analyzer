"""Regression coverage for fresh topic-table migrations on managed pgvector."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock


def _load_migration() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[2]
    migration_path = repo_root / "alembic/versions/c5f6a7b8d9e0_add_topic_tables.py"
    spec = importlib.util.spec_from_file_location("topic_tables_migration", migration_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hnsw_guard_skips_unconstrained_or_missing_embedding_dimensions() -> None:
    migration = _load_migration()
    connection = Mock()
    connection.execute.return_value.scalar.side_effect = [-1, None]

    assert migration._topics_embedding_is_dimensioned(connection) is False
    assert migration._topics_embedding_is_dimensioned(connection) is False


def test_hnsw_guard_allows_dimensioned_embedding() -> None:
    migration = _load_migration()
    connection = Mock()
    connection.execute.return_value.scalar.return_value = 1539

    assert migration._topics_embedding_is_dimensioned(connection) is True
