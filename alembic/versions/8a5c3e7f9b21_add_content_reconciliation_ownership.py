"""Add fenced content ownership and reconciliation audit storage.

Revision ID: 8a5c3e7f9b21
Revises: 7f4a2c9e1b60
Create Date: 2026-08-01 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "8a5c3e7f9b21"
down_revision: str | None = "7f4a2c9e1b60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE pgqueuer_jobs
          ADD COLUMN claim_generation BIGINT NOT NULL DEFAULT 0,
          ADD COLUMN claim_protocol_version SMALLINT NOT NULL DEFAULT 1,
          ADD CONSTRAINT ck_pgqueuer_jobs_claim_generation_nonnegative
            CHECK (claim_generation >= 0),
          ADD CONSTRAINT ck_pgqueuer_jobs_claim_protocol_positive
            CHECK (claim_protocol_version >= 1);

        ALTER TABLE contents
          ADD COLUMN status_operation_id BIGINT,
          ADD COLUMN status_claim_generation BIGINT,
          ADD COLUMN status_operation_phase VARCHAR(16),
          ADD COLUMN status_owner_version BIGINT,
          ADD CONSTRAINT ck_contents_status_owner_complete CHECK (
            (status_operation_id IS NULL
             AND status_claim_generation IS NULL
             AND status_operation_phase IS NULL
             AND status_owner_version IS NULL)
            OR
            (status_operation_id IS NOT NULL AND status_operation_id > 0
             AND status_claim_generation IS NOT NULL AND status_claim_generation > 0
             AND status_operation_phase IS NOT NULL
             AND status_owner_version IS NOT NULL AND status_owner_version > 0
             AND ((status_operation_phase = 'parsing'
                   AND status IN ('parsing', 'failed'))
                  OR (status_operation_phase = 'processing'
                      AND status IN ('processing', 'failed'))))
          );

        ALTER TABLE summaries
          ADD COLUMN operation_id BIGINT,
          ADD COLUMN operation_claim_generation BIGINT,
          ADD CONSTRAINT ck_summaries_operation_owner_complete CHECK (
            (operation_id IS NULL AND operation_claim_generation IS NULL)
            OR (operation_id IS NOT NULL AND operation_id > 0
                AND operation_claim_generation IS NOT NULL
                AND operation_claim_generation > 0)
          );
        """
    )
    op.execute(
        """
        CREATE TABLE content_reconciliation_actions (
          id BIGSERIAL PRIMARY KEY,
          run_id UUID NOT NULL,
          content_id BIGINT NOT NULL
            CONSTRAINT ck_content_reconciliation_content_id CHECK (content_id > 0),
          operation_id BIGINT NOT NULL
            CONSTRAINT ck_content_reconciliation_operation_id CHECK (operation_id > 0),
          claim_generation BIGINT NOT NULL
            CONSTRAINT ck_content_reconciliation_claim_generation CHECK (claim_generation > 0),
          claim_protocol_version SMALLINT NOT NULL
            CONSTRAINT ck_content_reconciliation_claim_protocol
              CHECK (claim_protocol_version >= 1),
          phase VARCHAR(16) NOT NULL
            CONSTRAINT ck_content_reconciliation_phase
              CHECK (phase IN ('parsing', 'processing')),
          content_status_before VARCHAR(32) NOT NULL,
          content_status_after VARCHAR(32) NOT NULL,
          operation_status_before VARCHAR(32) NOT NULL,
          operation_status_after VARCHAR(32) NOT NULL,
          retry_count_before INTEGER NOT NULL
            CONSTRAINT ck_content_reconciliation_retry_before CHECK (retry_count_before >= 0),
          retry_count_after INTEGER NOT NULL
            CONSTRAINT ck_content_reconciliation_retry_after CHECK (retry_count_after >= 0),
          action VARCHAR(40) NOT NULL,
          reason VARCHAR(40) NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT uq_content_reconciliation_actions_run_content UNIQUE (run_id, content_id),
          CONSTRAINT ck_content_reconciliation_content_status_before CHECK (
            content_status_before IN
              ('pending','parsing','parsed','processing','completed','failed','filtered_out')
          ),
          CONSTRAINT ck_content_reconciliation_content_status_after CHECK (
            content_status_after IN
              ('pending','parsing','parsed','processing','completed','failed','filtered_out')
          ),
          CONSTRAINT ck_content_reconciliation_operation_status_before CHECK (
            operation_status_before IN ('queued','in_progress','completed','failed','cancelled')
          ),
          CONSTRAINT ck_content_reconciliation_operation_status_after CHECK (
            operation_status_after IN ('queued','in_progress','completed','failed','cancelled')
          ),
          CONSTRAINT ck_content_reconciliation_action CHECK (action IN (
            'retry_operation','project_completed','project_parsed','restore_parsed',
            'restore_pending','cancel_restore_parsed','cancel_restore_pending'
          )),
          CONSTRAINT ck_content_reconciliation_reason CHECK (reason IN (
            'summary_exists','extraction_completed','cancellation_requested',
            'stale_operation','failed_operation','summarization_cancelled',
            'extraction_cancelled'
          ))
        );

        CREATE INDEX ix_content_reconciliation_actions_run
          ON content_reconciliation_actions (run_id, id);
        CREATE INDEX ix_content_reconciliation_actions_content_created
          ON content_reconciliation_actions (content_id, created_at DESC);
        """
    )
    op.execute(
        """
        CREATE FUNCTION deny_content_reconciliation_action_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'content_reconciliation_actions is append-only';
        END;
        $$;
        CREATE TRIGGER content_reconciliation_actions_append_only
        BEFORE UPDATE OR DELETE ON content_reconciliation_actions
        FOR EACH ROW EXECUTE FUNCTION deny_content_reconciliation_action_mutation();

        CREATE FUNCTION advance_pgqueuer_claim_generation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          NEW.claim_generation := OLD.claim_generation + 1;
          RETURN NEW;
        END;
        $$;
        CREATE TRIGGER pgqueuer_jobs_advance_claim_generation
        BEFORE UPDATE OF status ON pgqueuer_jobs
        FOR EACH ROW
        WHEN (OLD.status = 'queued' AND NEW.status = 'in_progress')
        EXECUTE FUNCTION advance_pgqueuer_claim_generation();

        CREATE FUNCTION reset_pgqueuer_claim_protocol()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          NEW.claim_protocol_version := 1;
          RETURN NEW;
        END;
        $$;
        CREATE TRIGGER pgqueuer_jobs_reset_claim_protocol
        BEFORE UPDATE OF status ON pgqueuer_jobs
        FOR EACH ROW
        WHEN (OLD.status IS DISTINCT FROM 'queued' AND NEW.status = 'queued')
        EXECUTE FUNCTION reset_pgqueuer_claim_protocol();

        CREATE FUNCTION clear_unchanged_content_status_owner()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.status IS DISTINCT FROM OLD.status
             AND NEW.status_owner_version IS NOT DISTINCT FROM OLD.status_owner_version THEN
            NEW.status_operation_id := NULL;
            NEW.status_claim_generation := NULL;
            NEW.status_operation_phase := NULL;
            NEW.status_owner_version := NULL;
          END IF;
          RETURN NEW;
        END;
        $$;
        CREATE TRIGGER contents_clear_unchanged_status_owner
        BEFORE UPDATE OF status ON contents
        FOR EACH ROW EXECUTE FUNCTION clear_unchanged_content_status_owner();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS contents_clear_unchanged_status_owner ON contents;
        DROP FUNCTION IF EXISTS clear_unchanged_content_status_owner();
        DROP TRIGGER IF EXISTS pgqueuer_jobs_reset_claim_protocol ON pgqueuer_jobs;
        DROP FUNCTION IF EXISTS reset_pgqueuer_claim_protocol();
        DROP TRIGGER IF EXISTS pgqueuer_jobs_advance_claim_generation ON pgqueuer_jobs;
        DROP FUNCTION IF EXISTS advance_pgqueuer_claim_generation();
        DROP TRIGGER IF EXISTS content_reconciliation_actions_append_only
          ON content_reconciliation_actions;
        DROP FUNCTION IF EXISTS deny_content_reconciliation_action_mutation();
        DROP TABLE content_reconciliation_actions;

        ALTER TABLE summaries
          DROP CONSTRAINT ck_summaries_operation_owner_complete,
          DROP COLUMN operation_claim_generation,
          DROP COLUMN operation_id;
        ALTER TABLE contents
          DROP CONSTRAINT ck_contents_status_owner_complete,
          DROP COLUMN status_owner_version,
          DROP COLUMN status_operation_phase,
          DROP COLUMN status_claim_generation,
          DROP COLUMN status_operation_id;
        ALTER TABLE pgqueuer_jobs
          DROP CONSTRAINT ck_pgqueuer_jobs_claim_protocol_positive,
          DROP CONSTRAINT ck_pgqueuer_jobs_claim_generation_nonnegative,
          DROP COLUMN claim_protocol_version,
          DROP COLUMN claim_generation;
        """
    )
