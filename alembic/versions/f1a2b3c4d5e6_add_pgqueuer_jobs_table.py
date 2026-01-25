"""add_pgqueuer_jobs_table

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
Create Date: 2026-01-25 10:00:00.000000

This migration creates the pgqueuer_jobs table for the PGQueuer
durable task queue system, along with the pgqueuer_enqueue helper
function used by pg_cron for scheduled job insertion.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the pgqueuer_jobs table for durable task queue
    op.create_table(
        "pgqueuer_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("entrypoint", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=True,
        ),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "status", sa.Text(), server_default="queued", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "execute_after",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create composite index for job selection (status + execute_after + priority)
    # This index is critical for the SELECT FOR UPDATE SKIP LOCKED pattern
    op.create_index(
        "idx_pgqueuer_jobs_status",
        "pgqueuer_jobs",
        ["status", "execute_after", sa.text("priority DESC")],
        unique=False,
    )

    # Create index for filtering by entrypoint
    op.create_index(
        "idx_pgqueuer_jobs_entrypoint",
        "pgqueuer_jobs",
        ["entrypoint"],
        unique=False,
    )

    # Create helper function for pg_cron to enqueue jobs
    # This function is used by scheduled cron jobs to insert work into the queue
    op.execute(
        """
        CREATE OR REPLACE FUNCTION pgqueuer_enqueue(
            p_entrypoint TEXT,
            p_payload JSONB DEFAULT '{}'::jsonb,
            p_priority INTEGER DEFAULT 0
        ) RETURNS BIGINT AS $$
        DECLARE
            v_job_id BIGINT;
        BEGIN
            INSERT INTO pgqueuer_jobs (entrypoint, payload, priority, status, created_at, execute_after)
            VALUES (p_entrypoint, p_payload, p_priority, 'queued', NOW(), NOW())
            RETURNING id INTO v_job_id;

            -- Notify workers (PGQueuer listens on this channel)
            PERFORM pg_notify('pgqueuer', p_entrypoint);

            RETURN v_job_id;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    # Drop the helper function
    op.execute("DROP FUNCTION IF EXISTS pgqueuer_enqueue(TEXT, JSONB, INTEGER)")

    # Drop indexes
    op.drop_index("idx_pgqueuer_jobs_entrypoint", table_name="pgqueuer_jobs")
    op.drop_index("idx_pgqueuer_jobs_status", table_name="pgqueuer_jobs")

    # Drop the table
    op.drop_table("pgqueuer_jobs")
