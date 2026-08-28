-- Contract DDL only. Implement through Alembic and queue bootstrap compatibility.

ALTER TABLE pgqueuer_jobs
    ADD COLUMN IF NOT EXISTS root_job_id BIGINT NULL REFERENCES pgqueuer_jobs(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS submission_traceparent VARCHAR(512) NULL,
    ADD COLUMN IF NOT EXISTS submission_tracestate VARCHAR(512) NULL,
    ADD COLUMN IF NOT EXISTS trace_id CHAR(32) NULL,
    ADD COLUMN IF NOT EXISTS submission_span_id CHAR(16) NULL,
    ADD CONSTRAINT ck_pgqueuer_jobs_trace_id
        CHECK (trace_id IS NULL OR trace_id ~ '^[0-9a-f]{32}$'),
    ADD CONSTRAINT ck_pgqueuer_jobs_submission_span_id
        CHECK (submission_span_id IS NULL OR submission_span_id ~ '^[0-9a-f]{16}$');

CREATE INDEX IF NOT EXISTS idx_pgqueuer_jobs_root_job_id
    ON pgqueuer_jobs(root_job_id);
CREATE INDEX IF NOT EXISTS idx_pgqueuer_jobs_trace_id
    ON pgqueuer_jobs(trace_id)
    WHERE trace_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS operation_observation_attempts (
    operation_id BIGINT NOT NULL REFERENCES pgqueuer_jobs(id) ON DELETE CASCADE,
    claim_generation INTEGER NOT NULL,
    attempt_number INTEGER NOT NULL,
    trace_id CHAR(32) NOT NULL,
    root_span_id CHAR(16) NOT NULL,
    langfuse_observation_id VARCHAR(64) NULL,
    service_name VARCHAR(100) NOT NULL,
    service_instance_id VARCHAR(128) NOT NULL,
    environment VARCHAR(32) NOT NULL,
    release_revision VARCHAR(64) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NULL,
    terminal_stage VARCHAR(32) NULL,
    outcome VARCHAR(32) NULL,
    retryable BOOLEAN NULL,
    telemetry_delivery_state VARCHAR(16) NOT NULL DEFAULT 'pending',
    diagnostic_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
    diagnostics_omitted INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (operation_id, claim_generation),
    CONSTRAINT ck_operation_attempt_claim_generation CHECK (claim_generation >= 0),
    CONSTRAINT ck_operation_attempt_number CHECK (attempt_number >= 0),
    CONSTRAINT ck_operation_attempt_trace_id CHECK (trace_id ~ '^[0-9a-f]{32}$'),
    CONSTRAINT ck_operation_attempt_root_span_id CHECK (root_span_id ~ '^[0-9a-f]{16}$'),
    CONSTRAINT ck_operation_attempt_completed_after_started
        CHECK (completed_at IS NULL OR completed_at >= started_at),
    CONSTRAINT ck_operation_attempt_outcome CHECK (
        outcome IS NULL OR outcome IN (
            'succeeded', 'partial', 'skipped_policy', 'skipped_duplicate',
            'filtered', 'retryable_failure', 'permanent_failure', 'cancelled'
        )
    ),
    CONSTRAINT ck_operation_attempt_stage CHECK (
        terminal_stage IS NULL OR terminal_stage IN (
            'submit', 'queue_wait', 'claim', 'fetch', 'discover', 'metadata',
            'transcript', 'extract', 'parse', 'filter', 'deduplicate', 'model',
            'fallback', 'persist', 'index', 'graph', 'deliver', 'backup',
            'restore', 'alert', 'cleanup', 'flush'
        )
    ),
    CONSTRAINT ck_operation_attempt_delivery CHECK (
        telemetry_delivery_state IN ('pending', 'delivered', 'degraded', 'dropped', 'disabled')
    ),
    CONSTRAINT ck_operation_attempt_diagnostics_array CHECK (
        jsonb_typeof(diagnostic_codes) = 'array'
        AND jsonb_array_length(diagnostic_codes) <= 20
    ),
    CONSTRAINT ck_operation_attempt_diagnostics_omitted CHECK (diagnostics_omitted >= 0)
);

CREATE INDEX IF NOT EXISTS idx_operation_attempts_trace_id
    ON operation_observation_attempts(trace_id);
CREATE INDEX IF NOT EXISTS idx_operation_attempts_failure_completed
    ON operation_observation_attempts(completed_at)
    WHERE outcome IN ('partial', 'retryable_failure', 'permanent_failure');
