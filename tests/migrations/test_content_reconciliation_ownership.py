"""PostgreSQL migration coverage for reconciliation ownership fencing."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import Engine


def _load_migration() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[2]
    migrations = list(repo_root.glob("alembic/versions/*content_reconciliation_ownership*.py"))
    assert len(migrations) == 1, "expected exactly one ownership migration"
    spec = importlib.util.spec_from_file_location("content_reconciliation_ownership", migrations[0])
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_is_additive_on_the_current_head() -> None:
    migration = _load_migration()
    assert migration.down_revision == "7f4a2c9e1b60"


def test_deployed_schema_fences_claims_and_legacy_status_writers(test_engine: Engine) -> None:
    migration = _load_migration()
    inspector = sa.inspect(test_engine)
    queue_columns = {column["name"] for column in inspector.get_columns("pgqueuer_jobs")}
    content_columns = {column["name"] for column in inspector.get_columns("contents")}
    summary_columns = {column["name"] for column in inspector.get_columns("summaries")}
    assert {"claim_generation", "claim_protocol_version"} <= queue_columns
    assert {
        "status_operation_id",
        "status_claim_generation",
        "status_operation_phase",
        "status_owner_version",
    } <= content_columns
    assert {"operation_id", "operation_claim_generation"} <= summary_columns
    assert "content_reconciliation_actions" in inspector.get_table_names()

    with test_engine.connect() as connection, connection.begin() as transaction:
        job_id = connection.execute(
            sa.text(
                """
                INSERT INTO pgqueuer_jobs (entrypoint, payload, status)
                VALUES ('legacy_worker_test', '{}'::jsonb, 'queued')
                RETURNING id
                """
            )
        ).scalar_one()
        connection.execute(
            sa.text("UPDATE pgqueuer_jobs SET status = 'in_progress' WHERE id = :id"),
            {"id": job_id},
        )
        claim = connection.execute(
            sa.text(
                "SELECT claim_generation, claim_protocol_version FROM pgqueuer_jobs WHERE id = :id"
            ),
            {"id": job_id},
        ).one()
        assert claim == (1, 1)

        connection.execute(
            sa.text(
                "UPDATE pgqueuer_jobs SET claim_protocol_version = 2, status = 'failed' "
                "WHERE id = :id"
            ),
            {"id": job_id},
        )
        connection.execute(
            sa.text("UPDATE pgqueuer_jobs SET status = 'queued' WHERE id = :id"),
            {"id": job_id},
        )
        connection.execute(
            sa.text("UPDATE pgqueuer_jobs SET status = 'in_progress' WHERE id = :id"),
            {"id": job_id},
        )
        reclaimed = connection.execute(
            sa.text(
                "SELECT claim_generation, claim_protocol_version FROM pgqueuer_jobs WHERE id = :id"
            ),
            {"id": job_id},
        ).one()
        assert reclaimed == (2, 1)

        content_id = connection.execute(
            sa.text(
                """
                INSERT INTO contents (
                    source_type, source_id, title, markdown_content, content_hash, status,
                    status_operation_id, status_claim_generation,
                    status_operation_phase, status_owner_version
                ) VALUES (
                    'manual', 'ownership-trigger-test', 'Ownership trigger test', '# test',
                    'ownership-trigger-test', 'parsing', 101, 1, 'parsing', 1
                ) RETURNING id
                """
            )
        ).scalar_one()
        connection.execute(
            sa.text(
                "UPDATE contents SET status = 'failed', status_owner_version = 2 WHERE id = :id"
            ),
            {"id": content_id},
        )
        retained = connection.execute(
            sa.text(
                "SELECT status_operation_id, status_claim_generation, "
                "status_operation_phase, status_owner_version FROM contents WHERE id = :id"
            ),
            {"id": content_id},
        ).one()
        assert retained == (101, 1, "parsing", 2)

        connection.execute(
            sa.text("UPDATE contents SET status = 'parsed' WHERE id = :id"),
            {"id": content_id},
        )
        cleared = connection.execute(
            sa.text(
                "SELECT status_operation_id, status_claim_generation, "
                "status_operation_phase, status_owner_version FROM contents WHERE id = :id"
            ),
            {"id": content_id},
        ).one()
        assert cleared == (None, None, None, None)

        invalid_owner = connection.begin_nested()
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(
                sa.text(
                    """
                    INSERT INTO contents (
                        source_type, source_id, title, markdown_content, content_hash, status,
                        status_operation_id, status_claim_generation,
                        status_operation_phase, status_owner_version
                    ) VALUES (
                        'manual', 'invalid-owner-phase', 'Invalid owner phase', '# test',
                        'invalid-owner-phase', 'processing', 102, 1, 'parsing', 1
                    )
                    """
                )
            )
        invalid_owner.rollback()

        summary_id = connection.execute(
            sa.text(
                """
                INSERT INTO summaries (
                    content_id, executive_summary, key_themes, strategic_insights,
                    technical_details, actionable_items, notable_quotes, relevance_scores,
                    agent_framework, model_used, created_at,
                    operation_id, operation_claim_generation
                ) VALUES (
                    :content_id, 'summary', '[]'::json, '[]'::json, '[]'::json,
                    '[]'::json, '[]'::json, '{}'::json, 'test', 'test', NOW(),
                    :operation_id, 2
                ) RETURNING id
                """
            ),
            {"content_id": content_id, "operation_id": job_id},
        ).scalar_one()
        provenance = connection.execute(
            sa.text(
                "SELECT operation_id, operation_claim_generation FROM summaries WHERE id = :id"
            ),
            {"id": summary_id},
        ).one()
        assert provenance == (job_id, 2)

        invalid_summary = connection.begin_nested()
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(
                sa.text("UPDATE summaries SET operation_claim_generation = NULL WHERE id = :id"),
                {"id": summary_id},
            )
        invalid_summary.rollback()

        action_id = connection.execute(
            sa.text(
                """
                INSERT INTO content_reconciliation_actions (
                    run_id, content_id, operation_id, claim_generation,
                    claim_protocol_version, phase, content_status_before,
                    content_status_after, operation_status_before,
                    operation_status_after, retry_count_before, retry_count_after,
                    action, reason
                ) VALUES (
                    '00000000-0000-0000-0000-000000000001',
                    :content_id, :operation_id, 2, 1, 'parsing',
                    'parsing', 'parsed', 'completed', 'completed', 0, 0,
                    'project_parsed', 'extraction_completed'
                ) RETURNING id
                """
            ),
            {"content_id": content_id, "operation_id": job_id},
        ).scalar_one()
        savepoint = connection.begin_nested()
        with pytest.raises(sa.exc.DBAPIError):
            connection.execute(
                sa.text("UPDATE content_reconciliation_actions SET reason = reason WHERE id = :id"),
                {"id": action_id},
            )
        savepoint.rollback()

        migration.op = Operations(MigrationContext.configure(connection))
        migration.downgrade()
        downgraded = sa.inspect(connection)
        assert "content_reconciliation_actions" not in downgraded.get_table_names()
        assert "claim_generation" not in {
            column["name"] for column in downgraded.get_columns("pgqueuer_jobs")
        }
        assert "status_operation_id" not in {
            column["name"] for column in downgraded.get_columns("contents")
        }
        transaction.rollback()
