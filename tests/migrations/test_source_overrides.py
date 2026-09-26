"""Executable PostgreSQL evidence for the shipped source-overrides migration."""

from __future__ import annotations

import json
from datetime import datetime

import sqlalchemy as sa
from alembic.script import ScriptDirectory
from sqlalchemy.dialects import postgresql

from alembic import command
from tests.migrations.postgres_migration_fixture import (
    DisposableMigrationDatabase,
    source_overrides_schema_mismatches,
)

PREDECESSOR_REVISION = "b8f8b5ededed"
SOURCE_OVERRIDES_REVISION = "c3d4e5f6a7b8"


def _current_revision(database: DisposableMigrationDatabase) -> str:
    with database.engine.connect() as connection:
        revision = connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    return str(revision)


def _source_override_snapshot(
    database: DisposableMigrationDatabase,
) -> dict[str, object]:
    with database.engine.connect() as connection:
        row = (
            connection.execute(
                sa.text(
                    "SELECT id, source_key, source_type, config, enabled, version, description "
                    "FROM source_overrides WHERE source_key = :source_key"
                ),
                {"source_key": "rss:https://example.com/feed.xml"},
            )
            .mappings()
            .one()
        )
        sentinel = connection.execute(
            sa.text("SELECT payload FROM migration_evidence_sentinel WHERE id = 1")
        ).scalar_one()
        table_oid = connection.execute(
            sa.text("SELECT 'public.source_overrides'::regclass::oid")
        ).scalar_one()
        indexes = connection.execute(
            sa.text(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE schemaname = 'public' AND tablename = 'source_overrides' "
                "ORDER BY indexname"
            )
        ).all()
    return {
        "row": dict(row),
        "sentinel": sentinel,
        "table_oid": table_oid,
        "indexes": indexes,
    }


def test_source_overrides_migration_builds_supported_schema_without_touching_sentinel(
    disposable_migration_database: DisposableMigrationDatabase,
) -> None:
    database = disposable_migration_database
    script = ScriptDirectory.from_config(database.alembic_config)
    heads = script.get_heads()

    assert len(heads) == 1
    head = heads[0]
    source_revision = script.get_revision(SOURCE_OVERRIDES_REVISION)
    assert source_revision is not None
    assert source_revision.down_revision == PREDECESSOR_REVISION
    assert SOURCE_OVERRIDES_REVISION in {
        revision.revision for revision in script.iterate_revisions(head, "base")
    }

    command.upgrade(database.alembic_config, PREDECESSOR_REVISION)
    assert _current_revision(database) == PREDECESSOR_REVISION

    with database.engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE migration_evidence_sentinel "
                "(id integer PRIMARY KEY, payload text NOT NULL)"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO migration_evidence_sentinel (id, payload) VALUES (1, 'preserve me')"
            )
        )

    command.upgrade(database.alembic_config, SOURCE_OVERRIDES_REVISION)
    assert _current_revision(database) == SOURCE_OVERRIDES_REVISION
    command.upgrade(database.alembic_config, "head")
    assert _current_revision(database) == head

    inspector = sa.inspect(database.engine)
    columns = {column["name"]: column for column in inspector.get_columns("source_overrides")}
    assert set(columns) == {
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
    assert isinstance(columns["id"]["type"], sa.Integer)
    assert isinstance(columns["source_key"]["type"], sa.String)
    assert columns["source_key"]["type"].length == 512
    assert isinstance(columns["source_type"]["type"], sa.String)
    assert columns["source_type"]["type"].length == 64
    assert isinstance(columns["config"]["type"], postgresql.JSONB)
    assert isinstance(columns["enabled"]["type"], sa.Boolean)
    assert isinstance(columns["version"]["type"], sa.Integer)
    assert isinstance(columns["description"]["type"], sa.Text)
    assert isinstance(columns["created_at"]["type"], sa.DateTime)
    assert isinstance(columns["updated_at"]["type"], sa.DateTime)
    assert {name: column["nullable"] for name, column in columns.items()} == {
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
    assert str(columns["enabled"]["default"]).lower() == "true"
    assert str(columns["version"]["default"]) == "1"

    primary_key = inspector.get_pk_constraint("source_overrides")
    assert primary_key["constrained_columns"] == ["id"]
    indexes = {index["name"]: index for index in inspector.get_indexes("source_overrides")}
    assert indexes["ix_source_overrides_source_key"]["column_names"] == ["source_key"]
    assert indexes["ix_source_overrides_source_key"]["unique"] is True
    assert indexes["ix_source_overrides_source_type"]["column_names"] == ["source_type"]
    assert indexes["ix_source_overrides_source_type"]["unique"] is False
    assert source_overrides_schema_mismatches(database.engine) == []

    source_config = {
        "type": "rss",
        "url": "https://example.com/feed.xml",
        "tags": ["migration", "evidence"],
        "options": {"include_images": True},
    }
    timestamp = datetime(2026, 9, 21, 12, 0, 0)
    with database.engine.begin() as connection:
        inserted = (
            connection.execute(
                sa.text(
                    "INSERT INTO source_overrides "
                    "(source_key, source_type, config, created_at, updated_at) "
                    "VALUES (:source_key, :source_type, CAST(:config AS jsonb), :created_at, :updated_at) "
                    "RETURNING enabled, version, description"
                ),
                {
                    "source_key": "rss:https://example.com/feed.xml",
                    "source_type": "rss",
                    "config": json.dumps(source_config),
                    "created_at": timestamp,
                    "updated_at": timestamp,
                },
            )
            .mappings()
            .one()
        )

    assert dict(inserted) == {"enabled": True, "version": 1, "description": None}
    before_repeat = _source_override_snapshot(database)
    assert before_repeat["row"]["config"] == source_config  # type: ignore[index]
    assert before_repeat["sentinel"] == "preserve me"

    command.upgrade(database.alembic_config, "head")

    assert _current_revision(database) == head
    assert _source_override_snapshot(database) == before_repeat


def test_existing_table_guard_does_not_establish_schema_compatibility(
    disposable_migration_database: DisposableMigrationDatabase,
) -> None:
    database = disposable_migration_database
    command.upgrade(database.alembic_config, PREDECESSOR_REVISION)
    with database.engine.begin() as connection:
        connection.execute(
            sa.text("CREATE TABLE source_overrides (id integer PRIMARY KEY, legacy_value text)")
        )

    # The shipped migration intentionally returns when the table already exists.
    command.upgrade(database.alembic_config, SOURCE_OVERRIDES_REVISION)

    assert _current_revision(database) == SOURCE_OVERRIDES_REVISION
    mismatches = source_overrides_schema_mismatches(database.engine)
    assert "missing column: source_key" in mismatches
    assert "missing column: config" in mismatches
    assert "missing unique index: ix_source_overrides_source_key" in mismatches
    assert "unexpected column: legacy_value" in mismatches
