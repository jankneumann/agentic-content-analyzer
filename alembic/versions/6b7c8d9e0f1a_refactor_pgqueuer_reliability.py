"""refactor_pgqueuer_reliability

Revision ID: 6b7c8d9e0f1a
Revises: 1a4ad3270eb7
Create Date: 2026-02-14 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "6b7c8d9e0f1a"
down_revision: Union[str, None] = "1a4ad3270eb7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "pgqueuer_jobs" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("pgqueuer_jobs")}

    if "parent_job_id" not in columns:
        op.add_column("pgqueuer_jobs", sa.Column("parent_job_id", sa.BigInteger(), nullable=True))
        op.create_foreign_key(
            "fk_pgqueuer_jobs_parent_job_id",
            "pgqueuer_jobs",
            "pgqueuer_jobs",
            ["parent_job_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if "heartbeat_at" not in columns:
        op.add_column("pgqueuer_jobs", sa.Column("heartbeat_at", sa.DateTime(timezone=True)))

    if "idempotency_key" not in columns:
        op.add_column("pgqueuer_jobs", sa.Column("idempotency_key", sa.Text(), nullable=True))

    op.execute(
        """
        UPDATE pgqueuer_jobs
        SET heartbeat_at = COALESCE(heartbeat_at, started_at, completed_at, created_at)
        WHERE heartbeat_at IS NULL
        """
    )

    op.execute(
        """
        UPDATE pgqueuer_jobs
        SET idempotency_key = entrypoint || ':content_id:' || (payload->>'content_id')
        WHERE idempotency_key IS NULL
          AND entrypoint IN ('summarize_content', 'extract_url_content')
          AND payload ? 'content_id'
        """
    )

    # Existing deployments can contain duplicate active jobs before the
    # dedupe index is introduced. Keep the earliest row and mark the rest as
    # failed so the unique partial index can be created safely.
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY entrypoint, idempotency_key
                       ORDER BY created_at ASC, id ASC
                   ) AS rn
            FROM pgqueuer_jobs
            WHERE status IN ('queued', 'in_progress')
              AND idempotency_key IS NOT NULL
        )
        UPDATE pgqueuer_jobs j
        SET status = 'failed',
            error = COALESCE(j.error, 'Deduplicated during migration'),
            completed_at = COALESCE(j.completed_at, NOW()),
            heartbeat_at = COALESCE(j.heartbeat_at, NOW())
        FROM ranked r
        WHERE j.id = r.id
          AND r.rn > 1
        """
    )

    indexes = {idx["name"] for idx in inspector.get_indexes("pgqueuer_jobs")}
    if "idx_pgqueuer_jobs_parent_job_id" not in indexes:
        op.create_index("idx_pgqueuer_jobs_parent_job_id", "pgqueuer_jobs", ["parent_job_id"])
    if "idx_pgqueuer_jobs_heartbeat" not in indexes:
        op.create_index("idx_pgqueuer_jobs_heartbeat", "pgqueuer_jobs", ["status", "heartbeat_at"])
    if "uq_pgqueuer_jobs_active_dedupe" not in indexes:
        op.create_index(
            "uq_pgqueuer_jobs_active_dedupe",
            "pgqueuer_jobs",
            ["entrypoint", "idempotency_key"],
            unique=True,
            postgresql_where=sa.text(
                "status IN ('queued', 'in_progress') AND idempotency_key IS NOT NULL"
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "pgqueuer_jobs" not in inspector.get_table_names():
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("pgqueuer_jobs")}
    fks = {fk["name"] for fk in inspector.get_foreign_keys("pgqueuer_jobs")}
    columns = {col["name"] for col in inspector.get_columns("pgqueuer_jobs")}

    if "uq_pgqueuer_jobs_active_dedupe" in indexes:
        op.drop_index("uq_pgqueuer_jobs_active_dedupe", table_name="pgqueuer_jobs")
    if "idx_pgqueuer_jobs_heartbeat" in indexes:
        op.drop_index("idx_pgqueuer_jobs_heartbeat", table_name="pgqueuer_jobs")
    if "idx_pgqueuer_jobs_parent_job_id" in indexes:
        op.drop_index("idx_pgqueuer_jobs_parent_job_id", table_name="pgqueuer_jobs")

    if "fk_pgqueuer_jobs_parent_job_id" in fks:
        op.drop_constraint("fk_pgqueuer_jobs_parent_job_id", "pgqueuer_jobs", type_="foreignkey")

    if "idempotency_key" in columns:
        op.drop_column("pgqueuer_jobs", "idempotency_key")
    if "heartbeat_at" in columns:
        op.drop_column("pgqueuer_jobs", "heartbeat_at")
    if "parent_job_id" in columns:
        op.drop_column("pgqueuer_jobs", "parent_job_id")
