-- Planning contract only; Alembic remains the executable migration authority.
CREATE TABLE workflow_terminal_events (
    id UUID PRIMARY KEY,
    event_key VARCHAR(160) NOT NULL UNIQUE,
    source_kind VARCHAR(40) NOT NULL,
    operation_id BIGINT NULL,
    claim_generation INTEGER NULL,
    terminal_status VARCHAR(20) NULL,
    reconciliation_action_id BIGINT NULL,
    reconciliation_run_id UUID NULL,
    reconciliation_content_id BIGINT NULL,
    classification_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    envelope JSONB NULL,
    telemetry_emitted_at TIMESTAMPTZ NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (source_kind IN ('operation','reconciliation_action','reconciliation_failure')),
    CHECK (classification_status IN ('pending','ready','telemetry_only','rejected')),
    CHECK (claim_generation IS NULL OR claim_generation > 0)
);

CREATE TABLE workflow_alert_deliveries (
    id UUID PRIMARY KEY,
    event_id UUID NOT NULL REFERENCES workflow_terminal_events(id) ON DELETE RESTRICT,
    sink_name VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lease_expires_at TIMESTAMPTZ NULL,
    delivered_at TIMESTAMPTZ NULL,
    last_error_code VARCHAR(80) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (event_id, sink_name),
    CHECK (status IN ('pending','leased','delivered','permanent_failure','exhausted')),
    CHECK (attempt_count >= 0)
);

CREATE INDEX ix_workflow_alert_deliveries_due
ON workflow_alert_deliveries (next_attempt_at, id)
WHERE status IN ('pending','leased');
