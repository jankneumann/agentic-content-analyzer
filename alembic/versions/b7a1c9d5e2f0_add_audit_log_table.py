"""Add audit_log table + pg_cron retention job.

Revision ID: b7a1c9d5e2f0
Revises: 1455833d558b
Create Date: 2026-04-24

Implements the ``audit_log`` schema defined at
``openspec/changes/cloud-db-source-of-truth/contracts/db/schema.sql`` and
registers a pg_cron retention job that deletes rows older than
``AUDIT_LOG_RETENTION_DAYS`` (default 90) — interpolated at MIGRATION TIME
per design decision D4a (Railway managed Postgres restricts custom GUCs, so
we cannot read retention via ``current_setting('app.audit_retention_days')``).

The pg_cron extension is optional — environments without it (e.g. local dev,
test databases) skip the schedule step with a warning.
"""

from __future__ import annotations

import logging
import os

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7a1c9d5e2f0"
down_revision: str | None = "1455833d558b"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


_CRON_JOB_NAME = "audit-log-retention"
_DEFAULT_RETENTION_DAYS = 90


logger = logging.getLogger(__name__)


def _pg_cron_available(conn) -> bool:
    """Return True when the pg_cron extension is installed in the target DB."""
    result = conn.execute(sa.text("SELECT 1 FROM pg_extension WHERE extname = 'pg_cron'")).scalar()
    return bool(result)


def upgrade() -> None:
    """Create audit_log + indexes, and register the pg_cron retention job.

    Table + indexes mirror contracts/db/schema.sql. Retention interval is
    interpolated at migration time from AUDIT_LOG_RETENTION_DAYS — the
    resulting pg_cron command contains the literal number of days, NOT a
    call to ``current_setting()``. See D4a.
    """
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=True),
        sa.Column("admin_key_fp", sa.Text(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("body_size", sa.Integer(), nullable=True),
        sa.Column("client_ip", postgresql.INET(), nullable=True),
        sa.Column(
            "notes",
            postgresql.JSONB(),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.CheckConstraint(
            "timestamp >= '2026-01-01'::timestamptz",
            name="audit_log_timestamp_check",
        ),
    )

    op.create_index(
        "idx_audit_log_timestamp",
        "audit_log",
        [sa.text("timestamp DESC")],
    )
    op.create_index(
        "idx_audit_log_operation",
        "audit_log",
        ["operation"],
        postgresql_where=sa.text("operation IS NOT NULL"),
    )
    op.create_index(
        "idx_audit_log_path_timestamp",
        "audit_log",
        ["path", sa.text("timestamp DESC")],
    )
    op.create_index(
        "idx_audit_log_admin_key_fp",
        "audit_log",
        ["admin_key_fp", sa.text("timestamp DESC")],
        postgresql_where=sa.text("admin_key_fp IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # pg_cron retention job (D4a — interpolated at migration time, NOT
    # read via current_setting() GUC).
    # ------------------------------------------------------------------
    retention_days = int(os.environ.get("AUDIT_LOG_RETENTION_DAYS", str(_DEFAULT_RETENTION_DAYS)))
    if retention_days < 1:
        retention_days = _DEFAULT_RETENTION_DAYS

    conn = op.get_bind()
    if _pg_cron_available(conn):
        # Unschedule any existing job so re-running migrations stays idempotent.
        op.execute(
            sa.text(
                f"""
                DO $$
                BEGIN
                    PERFORM cron.unschedule('{_CRON_JOB_NAME}');
                EXCEPTION WHEN OTHERS THEN
                    NULL;
                END $$;
                """
            )
        )
        # _CRON_JOB_NAME is a module-private constant; retention_days is a
        # sanitized non-negative integer. No user input is interpolated.
        cron_sql = f"SELECT cron.schedule('{_CRON_JOB_NAME}', '0 4 * * *', $$DELETE FROM audit_log WHERE timestamp < now() - INTERVAL '{retention_days} days'$$)"  # noqa: S608
        op.execute(sa.text(cron_sql))
    else:
        logger.warning(
            "pg_cron extension not installed — skipping audit-log-retention job. "
            "Retention must be applied externally (cron, scheduled task, or a "
            "follow-up migration once pg_cron is available)."
        )


def downgrade() -> None:
    """Remove the audit_log table + pg_cron job."""
    conn = op.get_bind()
    if _pg_cron_available(conn):
        op.execute(
            sa.text(
                f"""
                DO $$
                BEGIN
                    PERFORM cron.unschedule('{_CRON_JOB_NAME}');
                EXCEPTION WHEN OTHERS THEN
                    NULL;
                END $$;
                """
            )
        )
    op.drop_index("idx_audit_log_admin_key_fp", table_name="audit_log")
    op.drop_index("idx_audit_log_path_timestamp", table_name="audit_log")
    op.drop_index("idx_audit_log_operation", table_name="audit_log")
    op.drop_index("idx_audit_log_timestamp", table_name="audit_log")
    op.drop_table("audit_log")
