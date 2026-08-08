"""Add durable workflow terminal event and alert delivery persistence.

Revision ID: 91c7d2e4f8a6
Revises: 8a5c3e7f9b21
Create Date: 2026-08-02 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "91c7d2e4f8a6"
down_revision: str | None = "8a5c3e7f9b21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE workflow_terminal_events (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          event_key VARCHAR(160) NOT NULL UNIQUE,
          source_kind VARCHAR(40) NOT NULL,
          operation_id BIGINT,
          claim_generation BIGINT,
          terminal_status VARCHAR(20),
          reconciliation_action_id BIGINT,
          reconciliation_run_id UUID,
          reconciliation_content_id BIGINT,
          classification_status VARCHAR(20) NOT NULL DEFAULT 'pending',
          envelope JSONB,
          telemetry_emitted_at TIMESTAMPTZ,
          occurred_at TIMESTAMPTZ NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT ck_workflow_terminal_events_source_kind CHECK (
            source_kind IN ('operation','reconciliation_action','reconciliation_failure')
          ),
          CONSTRAINT ck_workflow_terminal_events_event_identity CHECK (
            (source_kind = 'operation' AND event_key =
              'operation:' || operation_id::text || ':claim:' ||
              claim_generation::text || ':status:' || terminal_status)
            OR
            (source_kind = 'reconciliation_action' AND event_key =
              'reconciliation-action:' || reconciliation_action_id::text)
            OR
            (source_kind = 'reconciliation_failure' AND event_key =
              'reconciliation-failure:' || reconciliation_run_id::text || ':content:' ||
              reconciliation_content_id::text || ':reason:apply_failed'
             AND event_key ~
              '^reconciliation-failure:[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}:content:[1-9][0-9]*:reason:apply_failed$')
          ),
          CONSTRAINT ck_workflow_terminal_events_terminal_status CHECK (
            terminal_status IS NULL OR terminal_status IN ('completed','failed','cancelled')
          ),
          CONSTRAINT ck_workflow_terminal_events_classification_status CHECK (
            classification_status IN ('pending','ready','telemetry_only','rejected')
          ),
          CONSTRAINT ck_workflow_terminal_events_operation_id CHECK (
            operation_id IS NULL OR operation_id > 0
          ),
          CONSTRAINT ck_workflow_terminal_events_claim_generation CHECK (
            claim_generation IS NULL OR claim_generation >= 0
          ),
          CONSTRAINT ck_workflow_terminal_events_reconciliation_action_id CHECK (
            reconciliation_action_id IS NULL OR reconciliation_action_id > 0
          ),
          CONSTRAINT ck_workflow_terminal_events_reconciliation_content_id CHECK (
            reconciliation_content_id IS NULL OR reconciliation_content_id > 0
          ),
          CONSTRAINT ck_workflow_terminal_events_envelope_object CHECK (
            envelope IS NULL OR jsonb_typeof(envelope) = 'object'
          ),
          CONSTRAINT ck_workflow_terminal_events_source_shape CHECK (
            (source_kind = 'operation'
             AND operation_id IS NOT NULL
             AND claim_generation IS NOT NULL
             AND terminal_status IS NOT NULL
             AND reconciliation_action_id IS NULL
             AND reconciliation_run_id IS NULL
             AND reconciliation_content_id IS NULL)
            OR
            (source_kind = 'reconciliation_action'
             AND operation_id IS NULL
             AND claim_generation IS NULL
             AND terminal_status IS NULL
             AND reconciliation_action_id IS NOT NULL
             AND reconciliation_run_id IS NOT NULL
             AND reconciliation_content_id IS NOT NULL)
            OR
            (source_kind = 'reconciliation_failure'
             AND operation_id IS NULL
             AND claim_generation IS NULL
             AND terminal_status IS NULL
             AND reconciliation_action_id IS NULL
             AND reconciliation_run_id IS NOT NULL
             AND reconciliation_content_id IS NOT NULL)
          )
        );

        CREATE TABLE workflow_alert_deliveries (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          event_id UUID NOT NULL,
          sink_name VARCHAR(64) NOT NULL,
          status VARCHAR(20) NOT NULL DEFAULT 'pending',
          attempt_count INTEGER NOT NULL DEFAULT 0,
          next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          lease_expires_at TIMESTAMPTZ,
          delivered_at TIMESTAMPTZ,
          last_error_code VARCHAR(80),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT fk_workflow_alert_deliveries_event
            FOREIGN KEY (event_id) REFERENCES workflow_terminal_events(id) ON DELETE RESTRICT,
          CONSTRAINT uq_workflow_alert_deliveries_event_sink UNIQUE (event_id, sink_name),
          CONSTRAINT ck_workflow_alert_deliveries_sink_name CHECK (
            sink_name ~ '^[a-z][a-z0-9_-]{0,63}$'
          ),
          CONSTRAINT ck_workflow_alert_deliveries_status CHECK (
            status IN ('pending','leased','delivered','permanent_failure','exhausted')
          ),
          CONSTRAINT ck_workflow_alert_deliveries_attempt_count CHECK (attempt_count >= 0),
          CONSTRAINT ck_workflow_alert_deliveries_last_error_code CHECK (
            last_error_code IS NULL OR last_error_code ~ '^[a-z][a-z0-9_.-]{0,79}$'
          ),
          CONSTRAINT ck_workflow_alert_deliveries_state CHECK (
            (status = 'pending'
             AND lease_expires_at IS NULL AND delivered_at IS NULL)
            OR
            (status = 'leased' AND attempt_count >= 1
             AND lease_expires_at IS NOT NULL AND delivered_at IS NULL)
            OR
            (status = 'delivered' AND attempt_count >= 1
             AND lease_expires_at IS NULL AND delivered_at IS NOT NULL
             AND last_error_code IS NULL)
            OR
            (status IN ('permanent_failure','exhausted') AND attempt_count >= 1
             AND lease_expires_at IS NULL AND delivered_at IS NULL
             AND last_error_code IS NOT NULL)
          )
        );

        CREATE INDEX ix_workflow_terminal_events_classification_due
          ON workflow_terminal_events (created_at, id)
          WHERE classification_status = 'pending';
        CREATE INDEX ix_workflow_terminal_events_retention
          ON workflow_terminal_events (created_at, id)
          WHERE classification_status IN ('ready','telemetry_only','rejected');
        CREATE INDEX ix_workflow_alert_deliveries_pending_due
          ON workflow_alert_deliveries (next_attempt_at, id)
          WHERE status = 'pending';
        CREATE INDEX ix_workflow_alert_deliveries_lease_expiry
          ON workflow_alert_deliveries (lease_expires_at, id)
          WHERE status = 'leased';
        CREATE INDEX ix_workflow_alert_deliveries_retention
          ON workflow_alert_deliveries (updated_at, id)
          WHERE status IN ('delivered','permanent_failure','exhausted');
        """
    )
    op.execute(
        """
        CREATE FUNCTION capture_pgqueuer_terminal_event()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          terminal_event_key TEXT;
          captured_event_id UUID;
        BEGIN
          terminal_event_key := format(
            'operation:%s:claim:%s:status:%s',
            NEW.id,
            NEW.claim_generation,
            NEW.status
          );
          INSERT INTO workflow_terminal_events (
            event_key, source_kind, operation_id, claim_generation,
            terminal_status, occurred_at
          ) VALUES (
            terminal_event_key,
            'operation',
            NEW.id,
            NEW.claim_generation,
            NEW.status,
            COALESCE(NEW.completed_at, NOW())
          )
          ON CONFLICT (event_key) DO UPDATE
          SET event_key = EXCLUDED.event_key
          WHERE workflow_terminal_events.source_kind = EXCLUDED.source_kind
            AND workflow_terminal_events.operation_id = EXCLUDED.operation_id
            AND workflow_terminal_events.claim_generation = EXCLUDED.claim_generation
            AND workflow_terminal_events.terminal_status = EXCLUDED.terminal_status
          RETURNING id INTO captured_event_id;
          IF captured_event_id IS NULL THEN
            RAISE EXCEPTION 'workflow terminal event identity collision'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$;
        CREATE TRIGGER pgqueuer_jobs_capture_terminal_event
        AFTER UPDATE OF status ON pgqueuer_jobs
        FOR EACH ROW
        WHEN (
          OLD.status IS DISTINCT FROM NEW.status
          AND NEW.status IN ('completed','failed','cancelled')
        )
        EXECUTE FUNCTION capture_pgqueuer_terminal_event();

        CREATE FUNCTION capture_content_reconciliation_terminal_event()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
          captured_event_id UUID;
        BEGIN
          INSERT INTO workflow_terminal_events (
            event_key, source_kind, reconciliation_action_id,
            reconciliation_run_id, reconciliation_content_id, occurred_at
          ) VALUES (
            format('reconciliation-action:%s', NEW.id),
            'reconciliation_action',
            NEW.id,
            NEW.run_id,
            NEW.content_id,
            NEW.created_at
          )
          ON CONFLICT (event_key) DO UPDATE
          SET event_key = EXCLUDED.event_key
          WHERE workflow_terminal_events.source_kind = EXCLUDED.source_kind
            AND workflow_terminal_events.reconciliation_action_id =
                EXCLUDED.reconciliation_action_id
            AND workflow_terminal_events.reconciliation_run_id =
                EXCLUDED.reconciliation_run_id
            AND workflow_terminal_events.reconciliation_content_id =
                EXCLUDED.reconciliation_content_id
          RETURNING id INTO captured_event_id;
          IF captured_event_id IS NULL THEN
            RAISE EXCEPTION 'workflow terminal event identity collision'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$;
        CREATE TRIGGER content_reconciliation_actions_capture_terminal_event
        AFTER INSERT ON content_reconciliation_actions
        FOR EACH ROW EXECUTE FUNCTION capture_content_reconciliation_terminal_event();

        CREATE FUNCTION deny_workflow_terminal_event_identity_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF ROW(
            NEW.id, NEW.event_key, NEW.source_kind, NEW.operation_id,
            NEW.claim_generation, NEW.terminal_status, NEW.reconciliation_action_id,
            NEW.reconciliation_run_id, NEW.reconciliation_content_id,
            NEW.occurred_at, NEW.created_at
          ) IS DISTINCT FROM ROW(
            OLD.id, OLD.event_key, OLD.source_kind, OLD.operation_id,
            OLD.claim_generation, OLD.terminal_status, OLD.reconciliation_action_id,
            OLD.reconciliation_run_id, OLD.reconciliation_content_id,
            OLD.occurred_at, OLD.created_at
          ) THEN
            RAISE EXCEPTION 'workflow_terminal_events source identity is immutable'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$;
        CREATE TRIGGER workflow_terminal_events_source_identity_immutable
        BEFORE UPDATE ON workflow_terminal_events
        FOR EACH ROW EXECUTE FUNCTION deny_workflow_terminal_event_identity_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS content_reconciliation_actions_capture_terminal_event
          ON content_reconciliation_actions;
        DROP FUNCTION IF EXISTS capture_content_reconciliation_terminal_event();
        DROP TRIGGER IF EXISTS pgqueuer_jobs_capture_terminal_event ON pgqueuer_jobs;
        DROP FUNCTION IF EXISTS capture_pgqueuer_terminal_event();
        DROP TRIGGER IF EXISTS workflow_terminal_events_source_identity_immutable
          ON workflow_terminal_events;
        DROP FUNCTION IF EXISTS deny_workflow_terminal_event_identity_mutation();
        DROP TABLE workflow_alert_deliveries;
        DROP TABLE workflow_terminal_events;
        """
    )
