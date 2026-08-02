"""PostgreSQL migration coverage for private Obsidian ingest state."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import Engine

from src.models.obsidian_ingest import OBSIDIAN_ERROR_CODES


def _load_migration() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[2]
    migrations = list(repo_root.glob("alembic/versions/*obsidian_ingest_state*.py"))
    assert len(migrations) == 1, "expected exactly one Obsidian ingest-state migration"
    spec = importlib.util.spec_from_file_location("obsidian_ingest_state", migrations[0])
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_is_additive_on_the_current_head() -> None:
    migration = _load_migration()
    assert migration.revision == "a6c3e8f1d204"
    assert migration.down_revision == "91c7d2e4f8a6"


def test_model_migration_and_canonical_schema_share_bounded_error_codes(
    test_engine: Engine,
) -> None:
    inspector = sa.inspect(test_engine)
    for table in ("obsidian_ingest_state", "obsidian_ingest_events"):
        constraint = next(
            check
            for check in inspector.get_check_constraints(table)
            if check["name"] == f"ck_{table}_error_code"
        )
        assert set(re.findall(r"'([a-z_]+)'", constraint["sqltext"])) == set(OBSIDIAN_ERROR_CODES)

    schema = (
        Path(__file__).resolve().parents[2] / "openspec/contracts/content-workflows/db/schema.sql"
    ).read_text()
    for code in OBSIDIAN_ERROR_CODES:
        assert schema.count(f"'{code}'") >= 2
    assert {
        "normalization_collision",
        "scan_entry_limit",
        "file_unavailable",
    } <= OBSIDIAN_ERROR_CODES


def test_deployed_schema_is_digest_only_bounded_and_indexed(test_engine: Engine) -> None:
    inspector = sa.inspect(test_engine)
    assert {"obsidian_ingest_state", "obsidian_ingest_events"} <= set(inspector.get_table_names())

    state_columns = {
        column["name"]: column for column in inspector.get_columns("obsidian_ingest_state")
    }
    event_columns = {
        column["name"]: column for column in inspector.get_columns("obsidian_ingest_events")
    }
    assert set(state_columns) == {
        "id",
        "configured_source_digest",
        "relative_path_digest",
        "current_file_hash",
        "observed_mtime_ns",
        "observed_size",
        "status",
        "claim_token",
        "lease_expires_at",
        "operation_id",
        "content_id",
        "error_code",
        "attempt_count",
        "missing_since",
        "first_seen_at",
        "updated_at",
    }
    assert set(event_columns) == {
        "id",
        "state_id",
        "configured_source_digest",
        "relative_path_digest",
        "file_hash",
        "status",
        "claim_token",
        "lease_expires_at",
        "operation_id",
        "content_id",
        "error_code",
        "attempt_count",
        "created_at",
        "updated_at",
        "completed_at",
    }
    assert all(
        "CHAR(64)" in str(columns[name]["type"])
        for columns, names in (
            (
                state_columns,
                ("configured_source_digest", "relative_path_digest", "current_file_hash"),
            ),
            (event_columns, ("configured_source_digest", "relative_path_digest", "file_hash")),
        )
        for name in names
    )
    for column_name in (*state_columns, *event_columns):
        lowered = column_name.lower()
        assert "url" not in lowered
        assert "body" not in lowered
        assert "frontmatter" not in lowered
        assert "message" not in lowered
        assert lowered not in {"path", "relative_path", "vault_path"}

    state_uniques = {
        constraint["name"]: constraint
        for constraint in inspector.get_unique_constraints("obsidian_ingest_state")
    }
    event_uniques = {
        constraint["name"]: constraint
        for constraint in inspector.get_unique_constraints("obsidian_ingest_events")
    }
    assert state_uniques["uq_obsidian_ingest_state_source_path"]["column_names"] == [
        "configured_source_digest",
        "relative_path_digest",
    ]
    assert event_uniques["uq_obsidian_ingest_events_file_version"]["column_names"] == [
        "configured_source_digest",
        "relative_path_digest",
        "file_hash",
    ]

    state_fks = {fk["name"]: fk for fk in inspector.get_foreign_keys("obsidian_ingest_state")}
    event_fks = {fk["name"]: fk for fk in inspector.get_foreign_keys("obsidian_ingest_events")}
    assert state_fks["fk_obsidian_ingest_state_operation"]["referred_table"] == "pgqueuer_jobs"
    assert state_fks["fk_obsidian_ingest_state_content"]["referred_table"] == "contents"
    assert event_fks["fk_obsidian_ingest_events_state"]["referred_table"] == "obsidian_ingest_state"
    assert event_fks["fk_obsidian_ingest_events_operation"]["referred_table"] == "pgqueuer_jobs"
    assert event_fks["fk_obsidian_ingest_events_content"]["referred_table"] == "contents"
    assert all(fk["options"]["ondelete"] == "SET NULL" for fk in state_fks.values())
    assert event_fks["fk_obsidian_ingest_events_state"]["options"]["ondelete"] == "RESTRICT"
    assert all(
        event_fks[name]["options"]["ondelete"] == "SET NULL"
        for name in ("fk_obsidian_ingest_events_operation", "fk_obsidian_ingest_events_content")
    )

    check_names = {
        check["name"]
        for table in ("obsidian_ingest_state", "obsidian_ingest_events")
        for check in inspector.get_check_constraints(table)
    }
    assert {
        "ck_obsidian_ingest_state_digests",
        "ck_obsidian_ingest_state_status",
        "ck_obsidian_ingest_state_error_code",
        "ck_obsidian_ingest_state_attempt_count",
        "ck_obsidian_ingest_state_shape",
        "ck_obsidian_ingest_events_digests",
        "ck_obsidian_ingest_events_status",
        "ck_obsidian_ingest_events_error_code",
        "ck_obsidian_ingest_events_attempt_count",
        "ck_obsidian_ingest_events_shape",
    } <= check_names

    indexes = {
        index["name"]
        for table in ("obsidian_ingest_state", "obsidian_ingest_events")
        for index in inspector.get_indexes(table)
    }
    assert {
        "ix_obsidian_ingest_state_claim_expiry",
        "ix_obsidian_ingest_state_status_updated",
        "ix_obsidian_ingest_events_claim_expiry",
        "ix_obsidian_ingest_events_state_created",
    } <= indexes

    with test_engine.connect() as connection:
        triggers = {
            row.name
            for row in connection.execute(
                sa.text(
                    """
                    SELECT tgname AS name
                    FROM pg_trigger
                    WHERE NOT tgisinternal
                      AND tgrelid = 'obsidian_ingest_events'::regclass
                    """
                )
            )
        }
    assert "obsidian_ingest_events_identity_immutable" in triggers


def test_migration_downgrade_removes_only_obsidian_state(test_engine: Engine) -> None:
    migration = _load_migration()
    with test_engine.connect() as connection:
        transaction = connection.begin()
        migration.op = Operations(MigrationContext.configure(connection))
        migration.downgrade()
        inspector = sa.inspect(connection)
        assert "obsidian_ingest_state" not in inspector.get_table_names()
        assert "obsidian_ingest_events" not in inspector.get_table_names()
        assert "contents" in inspector.get_table_names()
        assert "pgqueuer_jobs" in inspector.get_table_names()
        transaction.rollback()
