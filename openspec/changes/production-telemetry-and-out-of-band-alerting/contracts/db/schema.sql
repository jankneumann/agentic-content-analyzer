-- Planning contract only; Alembic remains the executable migration authority.
CREATE TABLE workflow_terminal_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_key VARCHAR(160) NOT NULL UNIQUE,
    source_kind VARCHAR(40) NOT NULL,
    operation_id BIGINT NULL,
    claim_generation BIGINT NULL,
    terminal_status VARCHAR(20) NULL,
    reconciliation_action_id BIGINT NULL,
    reconciliation_run_id UUID NULL,
    reconciliation_content_id BIGINT NULL,
    classification_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    envelope JSONB NULL,
    telemetry_emitted_at TIMESTAMPTZ NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_workflow_terminal_events_source_kind CHECK (
        source_kind IN ('operation','reconciliation_action','reconciliation_failure')
    ),
    CONSTRAINT ck_workflow_terminal_events_event_key CHECK (
        (source_kind = 'operation' AND event_key ~
          '^operation:[1-9][0-9]*:claim:[0-9]+:status:(completed|failed|cancelled)$')
        OR (source_kind = 'reconciliation_action' AND event_key ~
          '^reconciliation-action:[1-9][0-9]*$')
        OR (source_kind = 'reconciliation_failure' AND event_key ~
          '^reconciliation-failure:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:content:[1-9][0-9]*:reason:apply_failed$')
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
        (source_kind = 'operation' AND operation_id IS NOT NULL
         AND claim_generation IS NOT NULL AND terminal_status IS NOT NULL
         AND reconciliation_action_id IS NULL AND reconciliation_run_id IS NULL
         AND reconciliation_content_id IS NULL)
        OR (source_kind = 'reconciliation_action' AND operation_id IS NULL
         AND claim_generation IS NULL AND terminal_status IS NULL
         AND reconciliation_action_id IS NOT NULL AND reconciliation_run_id IS NOT NULL
         AND reconciliation_content_id IS NOT NULL)
        OR (source_kind = 'reconciliation_failure' AND operation_id IS NULL
         AND claim_generation IS NULL AND terminal_status IS NULL
         AND reconciliation_action_id IS NULL AND reconciliation_run_id IS NOT NULL
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
    lease_expires_at TIMESTAMPTZ NULL,
    delivered_at TIMESTAMPTZ NULL,
    last_error_code VARCHAR(80) NULL,
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
    )
);

CREATE INDEX ix_workflow_terminal_events_classification_due
ON workflow_terminal_events (created_at, id)
WHERE classification_status = 'pending';

CREATE INDEX ix_workflow_terminal_events_retention
ON workflow_terminal_events (created_at, id)
WHERE classification_status IN ('ready','telemetry_only','rejected');

CREATE INDEX ix_workflow_alert_deliveries_due
ON workflow_alert_deliveries (next_attempt_at, id)
WHERE status IN ('pending','leased');

CREATE INDEX ix_workflow_alert_deliveries_retention
ON workflow_alert_deliveries (updated_at, id)
WHERE status IN ('delivered','permanent_failure','exhausted');
