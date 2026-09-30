"""Executable PostgreSQL evidence for the content-reference expansion-state migration."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from alembic.script import ScriptDirectory
from sqlalchemy.exc import IntegrityError

from alembic import command
from tests.migrations.postgres_migration_fixture import DisposableMigrationDatabase

PREDECESSOR_REVISION = "e4b7c1a9d2f6"
EXPANSION_STATE_REVISION = "f5c8d2b0e3a7"
EXPANSION_COLUMNS = {"expansion_state", "expansion_attempts", "expansion_attempted_at"}


def _content(connection: sa.Connection, source_type: str, source_id: str) -> int:
    return connection.execute(
        sa.text(
            "INSERT INTO contents "
            "(source_type, source_id, title, markdown_content, content_hash, status) "
            "VALUES (:source_type, :source_id, 'Migration evidence', '# test', :source_id, "
            "'completed') RETURNING id"
        ),
        {"source_type": source_type, "source_id": source_id},
    ).scalar_one()


def _reference(connection: sa.Connection, content_id: int, **values: str | None) -> int:
    return connection.execute(
        sa.text(
            "INSERT INTO content_references "
            "(source_content_id, reference_type, external_url, external_id, external_id_type, "
            "resolution_status) "
            "VALUES (:content_id, 'cites', :external_url, :external_id, :external_id_type, "
            "'unresolved') RETURNING id"
        ),
        {
            "content_id": content_id,
            "external_url": values.get("external_url"),
            "external_id": values.get("external_id"),
            "external_id_type": values.get("external_id_type"),
        },
    ).scalar_one()


def _states(database: DisposableMigrationDatabase) -> dict[int, tuple[str | None, int]]:
    with database.engine.connect() as connection:
        rows = connection.execute(
            sa.text("SELECT id, expansion_state, expansion_attempts FROM content_references")
        ).all()
    return {row.id: (row.expansion_state, row.expansion_attempts) for row in rows}


def test_expansion_state_migration_backfills_bookmark_references_and_downgrades(
    disposable_migration_database: DisposableMigrationDatabase,
) -> None:
    database = disposable_migration_database
    script = ScriptDirectory.from_config(database.alembic_config)
    revision = script.get_revision(EXPANSION_STATE_REVISION)
    assert revision is not None
    assert revision.down_revision == PREDECESSOR_REVISION
    (head,) = script.get_heads()
    assert EXPANSION_STATE_REVISION in {
        rev.revision for rev in script.iterate_revisions(head, "base")
    }

    command.upgrade(database.alembic_config, PREDECESSOR_REVISION)
    with database.engine.begin() as connection:
        bookmark = _content(connection, "x_bookmarks", "xpost:1")
        newsletter = _content(connection, "rss", "rss:issue-1")
        bookmark_url = _reference(connection, bookmark, external_url="https://example.com/a")
        bookmark_id_only = _reference(
            connection, bookmark, external_id="2401.00001", external_id_type="arxiv"
        )
        newsletter_url = _reference(connection, newsletter, external_url="https://example.com/a")

    command.upgrade(database.alembic_config, EXPANSION_STATE_REVISION)

    assert _states(database) == {
        bookmark_url: ("pending", 0),
        # No link to submit: not an expansion candidate.
        bookmark_id_only: (None, 0),
        newsletter_url: (None, 0),
    }
    inspector = sa.inspect(database.engine)
    columns = {column["name"]: column for column in inspector.get_columns("content_references")}
    assert set(columns) >= EXPANSION_COLUMNS
    assert columns["expansion_state"]["nullable"] is True
    assert columns["expansion_state"]["type"].length == 16
    assert isinstance(columns["expansion_attempts"]["type"], sa.SmallInteger)
    assert columns["expansion_attempts"]["nullable"] is False
    assert isinstance(columns["expansion_attempted_at"]["type"], sa.DateTime)
    assert columns["expansion_attempted_at"]["type"].timezone is True
    indexes = {index["name"]: index for index in inspector.get_indexes("content_references")}
    retry_index = indexes["ix_content_refs_expansion_retry"]
    assert retry_index["column_names"] == ["created_at"]
    predicate = retry_index["dialect_options"]["postgresql_where"]
    assert "pending" in predicate and "failed" in predicate

    for invalid in (
        "UPDATE content_references SET expansion_state = 'queued'",
        "UPDATE content_references SET expansion_attempts = -1",
        "UPDATE content_references SET expansion_attempts = 101",
    ):
        with pytest.raises(IntegrityError), database.engine.begin() as connection:
            connection.execute(sa.text(invalid))

    command.downgrade(database.alembic_config, PREDECESSOR_REVISION)

    inspector = sa.inspect(database.engine)
    remaining = {column["name"] for column in inspector.get_columns("content_references")}
    assert not EXPANSION_COLUMNS & remaining
    index_names = {index["name"] for index in inspector.get_indexes("content_references")}
    assert "ix_content_refs_expansion_retry" not in index_names
    with database.engine.connect() as connection:
        kept = connection.execute(sa.text("SELECT count(*) FROM content_references")).scalar_one()
    assert kept == 3

    # The upgrade is repeatable after a downgrade.
    command.upgrade(database.alembic_config, EXPANSION_STATE_REVISION)
    assert _states(database)[bookmark_url] == ("pending", 0)
