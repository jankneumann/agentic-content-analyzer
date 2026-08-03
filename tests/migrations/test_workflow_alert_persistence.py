"""PostgreSQL migration coverage for durable workflow alert intent."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from uuid import UUID

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import Engine


@pytest.fixture(scope="module", autouse=True)
def _purge_module_rows(test_engine: Engine):
    """Remove the rows this module commits.

    These tests exercise real trigger and constraint behavior, so they must
    commit rather than roll back. Without this, the committed `contents` rows
    stay visible to every later test in the session and silently change the
    result of any query-shaped assertion that counts or orders content.
    """

    yield
    # Child rows first. One test in this module downgrades the migration, so the
    # alert tables may legitimately be gone by teardown; skipping a missing table
    # is correct, while failing on it would turn cleanup into a phantom error.
    # Child rows first. `content_reconciliation_actions` is append-only in
    # production and enforces that with a trigger, so teardown suspends the
    # trigger for its own statement — leaving the rows would pin the `contents`
    # rows they reference, and those leftovers stay visible to every later test
    # in the session, silently changing any assertion that counts or orders
    # content in a period.
    #
    # Each statement runs in its own transaction because one test in this module
    # downgrades the migration: a table that is legitimately gone by teardown
    # must not abort the rest of the cleanup.
    statements = (
        "DELETE FROM workflow_alert_deliveries",
        "DELETE FROM workflow_terminal_events",
        "ALTER TABLE content_reconciliation_actions "
        "DISABLE TRIGGER content_reconciliation_actions_append_only",
        "DELETE FROM content_reconciliation_actions",
        "ALTER TABLE content_reconciliation_actions "
        "ENABLE TRIGGER content_reconciliation_actions_append_only",
        "DELETE FROM contents WHERE source_id LIKE 'workflow-alert-%'",
        "DELETE FROM pgqueuer_jobs",
    )
    for statement in statements:
        try:
            with test_engine.begin() as connection:
                connection.execute(sa.text(statement))
        except (sa.exc.ProgrammingError, sa.exc.InternalError):
            continue


def _load_migration() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[2]
    migrations = list(repo_root.glob("alembic/versions/*workflow_alert_persistence*.py"))
    assert len(migrations) == 1, "expected exactly one workflow alert persistence migration"
    spec = importlib.util.spec_from_file_location("workflow_alert_persistence", migrations[0])
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _insert_job(connection: sa.Connection, *, status: str = "queued") -> int:
    return connection.execute(
        sa.text(
            """
            INSERT INTO pgqueuer_jobs (entrypoint, payload, status)
            VALUES ('ingestion.execute', '{}'::jsonb, :status)
            RETURNING id
            """
        ),
        {"status": status},
    ).scalar_one()


def _insert_content(connection: sa.Connection, suffix: str) -> int:
    return connection.execute(
        sa.text(
            """
            INSERT INTO contents (
                source_type, source_id, title, markdown_content, content_hash, status
            ) VALUES (
                'manual', :source_id, 'Alert persistence', '# test', :content_hash, 'failed'
            )
            RETURNING id
            """
        ),
        {"source_id": f"workflow-alert-{suffix}", "content_hash": f"workflow-alert-{suffix}"},
    ).scalar_one()


def _insert_reconciliation_action(
    connection: sa.Connection,
    *,
    run_id: str,
    content_id: int,
    operation_id: int,
) -> int:
    return connection.execute(
        sa.text(
            """
            INSERT INTO content_reconciliation_actions (
                run_id, content_id, operation_id, claim_generation,
                claim_protocol_version, phase, content_status_before,
                content_status_after, operation_status_before,
                operation_status_after, retry_count_before, retry_count_after,
                action, reason
            ) VALUES (
                :run_id, :content_id, :operation_id, 1, 2, 'parsing',
                'failed', 'pending', 'failed', 'queued', 0, 1,
                'retry_operation', 'failed_operation'
            )
            RETURNING id
            """
        ),
        {"run_id": run_id, "content_id": content_id, "operation_id": operation_id},
    ).scalar_one()


def test_migration_is_additive_on_the_current_head() -> None:
    migration = _load_migration()
    assert migration.down_revision == "8a5c3e7f9b21"


def test_deployed_schema_has_closed_tables_indexes_and_trigger_identity(
    test_engine: Engine,
) -> None:
    inspector = sa.inspect(test_engine)
    assert {"workflow_terminal_events", "workflow_alert_deliveries"} <= set(
        inspector.get_table_names()
    )

    event_columns = {column["name"] for column in inspector.get_columns("workflow_terminal_events")}
    assert {
        "id",
        "event_key",
        "source_kind",
        "operation_id",
        "claim_generation",
        "terminal_status",
        "reconciliation_action_id",
        "reconciliation_run_id",
        "reconciliation_content_id",
        "classification_status",
        "envelope",
        "telemetry_emitted_at",
        "occurred_at",
        "created_at",
    } == event_columns
    assert inspector.get_foreign_keys("workflow_terminal_events") == []

    delivery_fks = inspector.get_foreign_keys("workflow_alert_deliveries")
    assert len(delivery_fks) == 1
    assert delivery_fks[0]["referred_table"] == "workflow_terminal_events"
    assert delivery_fks[0]["options"]["ondelete"] == "RESTRICT"

    with test_engine.connect() as connection:
        indexes = {
            row.name: row.indexdef
            for row in connection.execute(
                sa.text(
                    """
                    SELECT indexname AS name, indexdef
                    FROM pg_indexes
                    WHERE schemaname = current_schema()
                      AND tablename IN ('workflow_terminal_events', 'workflow_alert_deliveries')
                    """
                )
            )
        }
        pending = indexes["ix_workflow_alert_deliveries_pending_due"]
        assert "(next_attempt_at, id)" in pending
        assert "status" in pending and "pending" in pending and "leased" not in pending
        leased = indexes["ix_workflow_alert_deliveries_lease_expiry"]
        assert "(lease_expires_at, id)" in leased
        assert "status" in leased and "leased" in leased and "pending" not in leased
        assert "ix_workflow_terminal_events_classification_due" in indexes
        assert "ix_workflow_terminal_events_retention" in indexes
        assert "ix_workflow_alert_deliveries_retention" in indexes

        triggers = {
            row.name: row.definition
            for row in connection.execute(
                sa.text(
                    """
                    SELECT tgname AS name, pg_get_triggerdef(oid) AS definition
                    FROM pg_trigger
                    WHERE NOT tgisinternal
                      AND tgrelid IN (
                          'pgqueuer_jobs'::regclass,
                          'content_reconciliation_actions'::regclass
                      )
                    """
                )
            )
        }
    assert "pgqueuer_jobs_capture_terminal_event" in triggers
    assert "AFTER UPDATE OF status" in triggers["pgqueuer_jobs_capture_terminal_event"]
    assert "content_reconciliation_actions_capture_terminal_event" in triggers
    assert "AFTER INSERT" in triggers["content_reconciliation_actions_capture_terminal_event"]


def test_operation_trigger_is_literal_attempt_aware_and_idempotent(test_engine: Engine) -> None:
    with test_engine.begin() as connection:
        queued_id = _insert_job(connection)
        connection.execute(
            sa.text(
                "UPDATE pgqueuer_jobs SET status = 'cancelled', completed_at = NOW() WHERE id = :id"
            ),
            {"id": queued_id},
        )
        queued_event = connection.execute(
            sa.text(
                """
                SELECT event_key, operation_id, claim_generation, terminal_status
                FROM workflow_terminal_events WHERE operation_id = :id
                """
            ),
            {"id": queued_id},
        ).one()
        assert queued_event == (
            f"operation:{queued_id}:claim:0:status:cancelled",
            queued_id,
            0,
            "cancelled",
        )

        connection.execute(
            sa.text("UPDATE pgqueuer_jobs SET status = status WHERE id = :id"),
            {"id": queued_id},
        )
        assert (
            connection.execute(
                sa.text("SELECT COUNT(*) FROM workflow_terminal_events WHERE operation_id = :id"),
                {"id": queued_id},
            ).scalar_one()
            == 1
        )

        claimed_id = _insert_job(connection)
        connection.execute(
            sa.text("UPDATE pgqueuer_jobs SET status = 'in_progress' WHERE id = :id"),
            {"id": claimed_id},
        )
        connection.execute(
            sa.text(
                "UPDATE pgqueuer_jobs SET status = 'failed', completed_at = NOW() "
                "WHERE id = :id AND claim_generation = 1"
            ),
            {"id": claimed_id},
        )
        connection.execute(
            sa.text("UPDATE pgqueuer_jobs SET status = 'queued' WHERE id = :id"),
            {"id": claimed_id},
        )
        connection.execute(
            sa.text("UPDATE pgqueuer_jobs SET status = 'in_progress' WHERE id = :id"),
            {"id": claimed_id},
        )
        stale = connection.execute(
            sa.text(
                "UPDATE pgqueuer_jobs SET status = 'failed' WHERE id = :id AND claim_generation = 1"
            ),
            {"id": claimed_id},
        )
        assert stale.rowcount == 0
        connection.execute(
            sa.text(
                "UPDATE pgqueuer_jobs SET status = 'failed', completed_at = NOW() "
                "WHERE id = :id AND claim_generation = 2"
            ),
            {"id": claimed_id},
        )
        keys = (
            connection.execute(
                sa.text(
                    "SELECT event_key FROM workflow_terminal_events "
                    "WHERE operation_id = :id ORDER BY claim_generation"
                ),
                {"id": claimed_id},
            )
            .scalars()
            .all()
        )
        assert keys == [
            f"operation:{claimed_id}:claim:1:status:failed",
            f"operation:{claimed_id}:claim:2:status:failed",
        ]


def test_reconciliation_trigger_is_atomic_and_uses_immutable_action_identity(
    test_engine: Engine,
) -> None:
    with test_engine.begin() as connection:
        operation_id = _insert_job(connection, status="failed")
        content_id = _insert_content(connection, "committed")
        action_id = _insert_reconciliation_action(
            connection,
            run_id="00000000-0000-0000-0000-000000000031",
            content_id=content_id,
            operation_id=operation_id,
        )
        event = connection.execute(
            sa.text(
                """
                SELECT event_key, source_kind, reconciliation_action_id,
                       reconciliation_run_id, reconciliation_content_id
                FROM workflow_terminal_events
                WHERE reconciliation_action_id = :action_id
                """
            ),
            {"action_id": action_id},
        ).one()
        assert event == (
            f"reconciliation-action:{action_id}",
            "reconciliation_action",
            action_id,
            UUID("00000000-0000-0000-0000-000000000031"),
            content_id,
        )

        rolled_back_content = _insert_content(connection, "rolled-back")
        savepoint = connection.begin_nested()
        rolled_back_action = _insert_reconciliation_action(
            connection,
            run_id="00000000-0000-0000-0000-000000000032",
            content_id=rolled_back_content,
            operation_id=operation_id,
        )
        savepoint.rollback()
        assert (
            connection.execute(
                sa.text(
                    "SELECT COUNT(*) FROM workflow_terminal_events "
                    "WHERE reconciliation_action_id = :action_id"
                ),
                {"action_id": rolled_back_action},
            ).scalar_one()
            == 0
        )


def test_terminal_event_keys_follow_the_closed_source_specific_grammar(test_engine: Engine) -> None:
    with test_engine.begin() as connection:
        invalid = connection.begin_nested()
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(
                sa.text(
                    """
                    INSERT INTO workflow_terminal_events (
                        event_key, source_kind, operation_id, claim_generation,
                        terminal_status, occurred_at
                    ) VALUES (
                        'operation:1:claim:0:status:queued', 'operation', 1, 0,
                        'completed', NOW()
                    )
                    """
                )
            )
        invalid.rollback()

        connection.execute(
            sa.text(
                """
                INSERT INTO workflow_terminal_events (
                    event_key, source_kind, reconciliation_run_id,
                    reconciliation_content_id, occurred_at
                ) VALUES (
                    'reconciliation-failure:00000000-0000-4000-8000-000000000041:content:7:reason:apply_failed',
                    'reconciliation_failure',
                    '00000000-0000-4000-8000-000000000041', 7, NOW()
                )
                """
            )
        )

        mismatch_cases = [
            (
                """
                INSERT INTO workflow_terminal_events (
                    event_key, source_kind, operation_id, claim_generation,
                    terminal_status, occurred_at
                ) VALUES (
                    'operation:2:claim:0:status:failed', 'operation', 1, 0,
                    'failed', NOW()
                )
                """,
                "operation identity",
            ),
            (
                """
                INSERT INTO workflow_terminal_events (
                    event_key, source_kind, reconciliation_action_id,
                    reconciliation_run_id, reconciliation_content_id, occurred_at
                ) VALUES (
                    'reconciliation-action:8', 'reconciliation_action', 7,
                    '00000000-0000-4000-8000-000000000041', 7, NOW()
                )
                """,
                "action identity",
            ),
            (
                """
                INSERT INTO workflow_terminal_events (
                    event_key, source_kind, reconciliation_run_id,
                    reconciliation_content_id, occurred_at
                ) VALUES (
                    'reconciliation-failure:00000000-0000-4000-8000-000000000041:content:8:reason:apply_failed',
                    'reconciliation_failure',
                    '00000000-0000-4000-8000-000000000041', 7, NOW()
                )
                """,
                "failure identity",
            ),
        ]
        for statement, _case in mismatch_cases:
            mismatch = connection.begin_nested()
            with pytest.raises(sa.exc.IntegrityError):
                connection.execute(sa.text(statement))
            mismatch.rollback()


def test_reconciliation_trigger_rejects_event_key_collision_with_different_identity(
    test_engine: Engine,
) -> None:
    with test_engine.begin() as connection:
        operation_id = _insert_job(connection, status="failed")
        content_id = _insert_content(connection, "collision-target")
        other_content_id = _insert_content(connection, "collision-existing")
        action_id = connection.execute(
            sa.text("SELECT nextval('content_reconciliation_actions_id_seq')")
        ).scalar_one()
        connection.execute(
            sa.text(
                """
                INSERT INTO workflow_terminal_events (
                    event_key, source_kind, reconciliation_action_id,
                    reconciliation_run_id, reconciliation_content_id, occurred_at
                ) VALUES (
                    :event_key, 'reconciliation_action', :action_id,
                    '00000000-0000-4000-8000-000000000051', :content_id, NOW()
                )
                """
            ),
            {
                "event_key": f"reconciliation-action:{action_id}",
                "action_id": action_id,
                "content_id": other_content_id,
            },
        )

        collision = connection.begin_nested()
        with pytest.raises(sa.exc.DBAPIError, match="identity collision"):
            connection.execute(
                sa.text(
                    """
                    INSERT INTO content_reconciliation_actions (
                        id, run_id, content_id, operation_id, claim_generation,
                        claim_protocol_version, phase, content_status_before,
                        content_status_after, operation_status_before,
                        operation_status_after, retry_count_before, retry_count_after,
                        action, reason
                    ) VALUES (
                        :action_id, '00000000-0000-4000-8000-000000000052',
                        :content_id, :operation_id, 1, 2, 'parsing',
                        'failed', 'pending', 'failed', 'queued', 0, 1,
                        'retry_operation', 'failed_operation'
                    )
                    """
                ),
                {
                    "action_id": action_id,
                    "content_id": content_id,
                    "operation_id": operation_id,
                },
            )
        collision.rollback()
        assert (
            connection.execute(
                sa.text(
                    "SELECT COUNT(*) FROM content_reconciliation_actions WHERE id = :action_id"
                ),
                {"action_id": action_id},
            ).scalar_one()
            == 0
        )


def test_terminal_source_identity_is_immutable_but_retention_delete_is_explicit(
    test_engine: Engine,
) -> None:
    with test_engine.begin() as connection:
        operation_id = _insert_job(connection)
        connection.execute(
            sa.text(
                "UPDATE pgqueuer_jobs SET status = 'completed', completed_at = NOW() WHERE id = :id"
            ),
            {"id": operation_id},
        )
        event_id = connection.execute(
            sa.text("SELECT id FROM workflow_terminal_events WHERE operation_id = :id"),
            {"id": operation_id},
        ).scalar_one()

        connection.execute(
            sa.text(
                "UPDATE workflow_terminal_events SET classification_status = 'telemetry_only' "
                "WHERE id = :id"
            ),
            {"id": event_id},
        )
        immutable = connection.begin_nested()
        with pytest.raises(sa.exc.DBAPIError, match="source identity is immutable"):
            connection.execute(
                sa.text(
                    "UPDATE workflow_terminal_events SET operation_id = operation_id + 1 "
                    "WHERE id = :id"
                ),
                {"id": event_id},
            )
        immutable.rollback()

        assert (
            connection.execute(
                sa.text("DELETE FROM workflow_terminal_events WHERE id = :id RETURNING id"),
                {"id": event_id},
            ).scalar_one()
            == event_id
        )


def test_delivery_state_constraint_matches_closed_runtime_contract(test_engine: Engine) -> None:
    with test_engine.begin() as connection:
        operation_id = _insert_job(connection)
        connection.execute(
            sa.text("UPDATE pgqueuer_jobs SET status = 'failed' WHERE id = :id"),
            {"id": operation_id},
        )
        event_id = connection.execute(
            sa.text("SELECT id FROM workflow_terminal_events WHERE operation_id = :id"),
            {"id": operation_id},
        ).scalar_one()

        valid_states = [
            ("pending", 0, None, None, None),
            ("leased", 1, "1 minute", None, "timeout"),
            ("delivered", 1, None, "now", None),
            ("permanent_failure", 1, None, None, "http_400"),
            ("exhausted", 1, None, None, "retry_exhausted"),
        ]
        for sequence, (status, attempt_count, lease, delivered, error_code) in enumerate(
            valid_states, start=1
        ):
            connection.execute(
                sa.text(
                    """
                    INSERT INTO workflow_alert_deliveries (
                        event_id, sink_name, status, attempt_count,
                        lease_expires_at, delivered_at, last_error_code
                    ) VALUES (
                        :event_id, :sink_name, :status, :attempt_count,
                        CASE WHEN :lease IS NULL THEN NULL ELSE NOW() + CAST(:lease AS interval) END,
                        CASE WHEN :delivered IS NULL THEN NULL ELSE NOW() END,
                        :error_code
                    )
                    """
                ),
                {
                    "event_id": event_id,
                    "sink_name": f"sink_{sequence}",
                    "status": status,
                    "attempt_count": attempt_count,
                    "lease": lease,
                    "delivered": delivered,
                    "error_code": error_code,
                },
            )

        invalid_states = [
            ("pending", 0, "1 minute", None, None),
            ("leased", 0, "1 minute", None, None),
            ("leased", 1, None, None, None),
            ("delivered", 1, None, None, None),
            ("delivered", 1, None, "now", "stale_error"),
            ("permanent_failure", 1, None, None, None),
            ("exhausted", 0, None, None, "retry_exhausted"),
        ]
        for sequence, (status, attempt_count, lease, delivered, error_code) in enumerate(
            invalid_states, start=1
        ):
            invalid = connection.begin_nested()
            with pytest.raises(sa.exc.IntegrityError):
                connection.execute(
                    sa.text(
                        """
                        INSERT INTO workflow_alert_deliveries (
                            event_id, sink_name, status, attempt_count,
                            lease_expires_at, delivered_at, last_error_code
                        ) VALUES (
                            :event_id, :sink_name, :status, :attempt_count,
                            CASE WHEN :lease IS NULL THEN NULL ELSE NOW() + CAST(:lease AS interval) END,
                            CASE WHEN :delivered IS NULL THEN NULL ELSE NOW() END,
                            :error_code
                        )
                        """
                    ),
                    {
                        "event_id": event_id,
                        "sink_name": f"invalid_{sequence}",
                        "status": status,
                        "attempt_count": attempt_count,
                        "lease": lease,
                        "delivered": delivered,
                        "error_code": error_code,
                    },
                )
            invalid.rollback()


def test_event_survives_operation_cleanup_and_delivery_uniqueness_is_bounded(
    test_engine: Engine,
) -> None:
    with test_engine.begin() as connection:
        operation_id = _insert_job(connection)
        connection.execute(
            sa.text(
                "UPDATE pgqueuer_jobs SET status = 'completed', completed_at = NOW() WHERE id = :id"
            ),
            {"id": operation_id},
        )
        event_id = connection.execute(
            sa.text("SELECT id FROM workflow_terminal_events WHERE operation_id = :id"),
            {"id": operation_id},
        ).scalar_one()

        connection.execute(
            sa.text(
                """
                INSERT INTO workflow_alert_deliveries (event_id, sink_name)
                VALUES (:event_id, 'webhook')
                """
            ),
            {"event_id": event_id},
        )
        duplicate = connection.begin_nested()
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(
                sa.text(
                    """
                    INSERT INTO workflow_alert_deliveries (event_id, sink_name)
                    VALUES (:event_id, 'webhook')
                    """
                ),
                {"event_id": event_id},
            )
        duplicate.rollback()

        connection.execute(
            sa.text("DELETE FROM pgqueuer_jobs WHERE id = :id"),
            {"id": operation_id},
        )
        assert (
            connection.execute(
                sa.text("SELECT event_key FROM workflow_terminal_events WHERE id = :id"),
                {"id": event_id},
            ).scalar_one()
            == f"operation:{operation_id}:claim:0:status:completed"
        )


def test_pending_and_expired_lease_queries_use_separate_bounded_indexes(
    test_engine: Engine,
) -> None:
    with test_engine.connect() as connection:
        connection.execute(sa.text("SET LOCAL enable_seqscan = off"))
        pending_plan = "\n".join(
            row[0]
            for row in connection.execute(
                sa.text(
                    """
                    EXPLAIN (COSTS OFF)
                    SELECT id
                    FROM workflow_alert_deliveries
                    WHERE status = 'pending'
                      AND next_attempt_at <= NOW()
                    ORDER BY next_attempt_at, id
                    LIMIT 50
                    """
                )
            )
        )
        leased_plan = "\n".join(
            row[0]
            for row in connection.execute(
                sa.text(
                    """
                    EXPLAIN (COSTS OFF)
                    SELECT id
                    FROM workflow_alert_deliveries
                    WHERE status = 'leased'
                      AND lease_expires_at <= NOW()
                    ORDER BY lease_expires_at, id
                    LIMIT 50
                    """
                )
            )
        )
    assert "ix_workflow_alert_deliveries_pending_due" in pending_plan
    assert "ix_workflow_alert_deliveries_lease_expiry" in leased_plan


def test_migration_downgrade_removes_only_workflow_alert_objects(test_engine: Engine) -> None:
    migration = _load_migration()
    with test_engine.connect() as connection:
        transaction = connection.begin()
        migration.op = Operations(MigrationContext.configure(connection))
        migration.downgrade()
        inspector = sa.inspect(connection)
        assert "workflow_terminal_events" not in inspector.get_table_names()
        assert "workflow_alert_deliveries" not in inspector.get_table_names()
        assert "pgqueuer_jobs" in inspector.get_table_names()
        assert "content_reconciliation_actions" in inspector.get_table_names()
        transaction.rollback()
