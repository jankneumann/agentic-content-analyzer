"""Test-only PostgreSQL database isolation for executable migration evidence.

This module is deliberately local to migration tests.  It is not a production
schema doctor and never resets or drops the session-shared test database.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from tests.helpers.test_db import get_test_database_url, get_worktree_name

_DATABASE_PREFIX = "aca_migration_test_"
_MAX_POSTGRES_IDENTIFIER = 63


@dataclass(frozen=True)
class DisposableMigrationDatabase:
    """Connection state for one uniquely named PostgreSQL test database."""

    name: str
    engine: Engine
    alembic_config: Config


def _disposable_database_name() -> str:
    worktree = get_worktree_name() or Path.cwd().name
    slug = re.sub(r"[^a-z0-9]+", "_", worktree.lower()).strip("_") or "main"
    unique_suffix = uuid.uuid4().hex[:12]
    available_slug_length = (
        _MAX_POSTGRES_IDENTIFIER - len(_DATABASE_PREFIX) - len(unique_suffix) - 1
    )
    return f"{_DATABASE_PREFIX}{slug[:available_slug_length]}_{unique_suffix}"


def _quoted_database_name(engine: Engine, database_name: str) -> str:
    if not re.fullmatch(r"[a-z0-9_]+", database_name):
        raise ValueError(f"unsafe disposable database name: {database_name!r}")
    if not database_name.startswith(_DATABASE_PREFIX):
        raise ValueError(f"refusing non-disposable database name: {database_name!r}")
    return engine.dialect.identifier_preparer.quote_identifier(database_name)


def _alembic_config(database_url: URL) -> Config:
    repo_root = Path(__file__).resolve().parents[2]
    config = Config(str(repo_root / "alembic.ini"))
    config.set_main_option("script_location", str(repo_root / "alembic"))
    # ConfigParser treats percent signs as interpolation markers.  Escaping here
    # preserves credentials containing '%' while Alembic receives the real URL.
    rendered_url = database_url.render_as_string(hide_password=False).replace("%", "%%")
    config.set_main_option("sqlalchemy.url", rendered_url)
    return config


@pytest.fixture
def disposable_migration_database() -> DisposableMigrationDatabase:
    """Create and finally drop one database used only by the requesting test."""

    base_url = make_url(get_test_database_url())
    if base_url.get_backend_name() != "postgresql":
        pytest.fail("source-overrides migration evidence requires PostgreSQL")

    database_name = _disposable_database_name()
    admin_url = base_url.set(database="postgres")
    target_url = base_url.set(database=database_name)
    admin_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    target_engine: Engine | None = None
    created = False

    try:
        quoted_name = _quoted_database_name(admin_engine, database_name)
        try:
            with admin_engine.connect() as connection:
                connection.execute(sa.text(f"CREATE DATABASE {quoted_name}"))
            created = True
        except SQLAlchemyError as exc:
            pytest.fail(
                f"cannot create disposable PostgreSQL migration database: {exc}"
            )

        target_engine = sa.create_engine(target_url, poolclass=NullPool)
        # A new PostgreSQL database already owns an isolated public schema.  Re-
        # creating it makes that boundary explicit and prevents template objects
        # from being mistaken for objects created by this migration run.
        with target_engine.begin() as connection:
            connection.execute(sa.text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(sa.text("CREATE SCHEMA public"))

        yield DisposableMigrationDatabase(
            name=database_name,
            engine=target_engine,
            alembic_config=_alembic_config(target_url),
        )
    finally:
        if target_engine is not None:
            target_engine.dispose()
        if created:
            quoted_name = _quoted_database_name(admin_engine, database_name)
            with admin_engine.connect() as connection:
                connection.execute(
                    sa.text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                    ),
                    {"database_name": database_name},
                )
                connection.execute(sa.text(f"DROP DATABASE {quoted_name}"))
        admin_engine.dispose()


def source_overrides_schema_mismatches(engine: Engine) -> list[str]:
    """Describe unsupported schema drift for migration tests only.

    The shipped migration intentionally guards only on table existence.  This
    verifier lets the regression test prove why a manually created table is not
    thereby supported without adding a production preflight or editing history.
    """

    inspector = sa.inspect(engine)
    if not inspector.has_table("source_overrides", schema="public"):
        return ["missing table: source_overrides"]

    expected_columns = {
        "id",
        "source_key",
        "source_type",
        "config",
        "enabled",
        "version",
        "description",
        "created_at",
        "updated_at",
    }
    columns = {
        str(column["name"]): column
        for column in inspector.get_columns("source_overrides", schema="public")
    }
    mismatches = [
        *(f"missing column: {name}" for name in sorted(expected_columns - columns.keys())),
        *(f"unexpected column: {name}" for name in sorted(columns.keys() - expected_columns)),
    ]

    if "config" in columns and not isinstance(columns["config"]["type"], postgresql.JSONB):
        mismatches.append("column config is not PostgreSQL JSONB")

    expected_nullability = {
        "id": False,
        "source_key": False,
        "source_type": False,
        "config": False,
        "enabled": False,
        "version": False,
        "description": True,
        "created_at": False,
        "updated_at": False,
    }
    for name, expected_nullable in expected_nullability.items():
        if name in columns and columns[name]["nullable"] is not expected_nullable:
            mismatches.append(f"column {name} has wrong nullability")

    if "enabled" in columns and str(columns["enabled"]["default"]).lower() != "true":
        mismatches.append("column enabled has wrong server default")
    if "version" in columns and str(columns["version"]["default"]) != "1":
        mismatches.append("column version has wrong server default")

    primary_key = inspector.get_pk_constraint("source_overrides", schema="public")
    if primary_key.get("constrained_columns") != ["id"]:
        mismatches.append("primary key is not (id)")

    indexes = {
        str(index["name"]): index
        for index in inspector.get_indexes("source_overrides", schema="public")
        if index["name"] is not None
    }
    source_key_index = indexes.get("ix_source_overrides_source_key")
    if source_key_index is None or not source_key_index.get("unique"):
        mismatches.append("missing unique index: ix_source_overrides_source_key")
    elif source_key_index.get("column_names") != ["source_key"]:
        mismatches.append("source-key unique index has wrong columns")

    source_type_index = indexes.get("ix_source_overrides_source_type")
    if source_type_index is None:
        mismatches.append("missing index: ix_source_overrides_source_type")
    elif source_type_index.get("column_names") != ["source_type"]:
        mismatches.append("source-type index has wrong columns")
    elif source_type_index.get("unique"):
        mismatches.append("source-type index is unexpectedly unique")

    return mismatches
