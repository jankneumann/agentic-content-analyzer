-- Contract DDL only. Implement through Alembic and queue bootstrap compatibility.

ALTER TABLE pgqueuer_jobs
    ADD COLUMN IF NOT EXISTS root_job_id BIGINT NULL REFERENCES pgqueuer_jobs(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS submission_context JSONB NULL,
    ADD COLUMN IF NOT EXISTS submission_traceparent VARCHAR(512) NULL,
    ADD COLUMN IF NOT EXISTS submission_tracestate VARCHAR(512) NULL,
    ADD COLUMN IF NOT EXISTS trace_id CHAR(32) NULL,
    ADD COLUMN IF NOT EXISTS submission_span_id CHAR(16) NULL,
    ADD CONSTRAINT ck_pgqueuer_jobs_submission_context
        CHECK (submission_context IS NULL OR (
            jsonb_typeof(submission_context) = 'object'
            AND submission_context @> '{"schema_version": 1}'::jsonb
            AND submission_context ?& ARRAY[
                'schema_version', 'operation_id', 'root_operation_id',
                'parent_operation_id', 'traceparent', 'tracestate', 'trace_id',
                'span_id', 'claim_generation', 'attempt_number', 'entrypoint',
                'service_name', 'service_instance_id', 'environment',
                'release_revision', 'stage', 'resource_kind', 'resource_key'
            ]
            AND (submission_context - ARRAY[
                'schema_version', 'operation_id', 'root_operation_id',
                'parent_operation_id', 'traceparent', 'tracestate', 'trace_id',
                'span_id', 'claim_generation', 'attempt_number', 'entrypoint',
                'service_name', 'service_instance_id', 'environment',
                'release_revision', 'stage', 'resource_kind', 'resource_key'
            ]::text[]) = '{}'::jsonb
            AND octet_length(submission_context::text) <= 4096
        )),
    ADD CONSTRAINT ck_pgqueuer_jobs_trace_id
        CHECK (trace_id IS NULL OR trace_id ~ '^[0-9a-f]{32}$'),
    ADD CONSTRAINT ck_pgqueuer_jobs_submission_span_id
        CHECK (submission_span_id IS NULL OR submission_span_id ~ '^[0-9a-f]{16}$'),
    ADD CONSTRAINT ck_pgqueuer_jobs_context_identity
        CHECK (submission_context IS NULL OR (
            id = (submission_context->>'operation_id')::BIGINT
            AND root_job_id = (submission_context->>'root_operation_id')::BIGINT
            AND submission_traceparent = submission_context->>'traceparent'
            AND submission_tracestate IS NOT DISTINCT FROM submission_context->>'tracestate'
            AND trace_id = submission_context->>'trace_id'
            AND submission_span_id = submission_context->>'span_id'
        ));

CREATE INDEX IF NOT EXISTS idx_pgqueuer_jobs_root_job_id
    ON pgqueuer_jobs(root_job_id);
CREATE INDEX IF NOT EXISTS idx_pgqueuer_jobs_trace_id
    ON pgqueuer_jobs(trace_id)
    WHERE trace_id IS NOT NULL;

CREATE DOMAIN operation_diagnostic_code AS VARCHAR(100)
    CHECK (VALUE ~ '^[a-z][a-z0-9_.-]{0,99}$');

CREATE TABLE IF NOT EXISTS operation_observation_attempts (
    operation_id BIGINT NOT NULL REFERENCES pgqueuer_jobs(id) ON DELETE CASCADE,
    claim_generation BIGINT NOT NULL,
    attempt_number BIGINT NOT NULL,
    trace_id CHAR(32) NOT NULL,
    root_span_id CHAR(16) NULL,
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
    diagnostic_codes operation_diagnostic_code[] NOT NULL DEFAULT ARRAY[]::operation_diagnostic_code[],
    diagnostics_omitted INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (operation_id, claim_generation),
    CONSTRAINT ck_operation_attempt_claim_generation CHECK (claim_generation >= 0),
    CONSTRAINT ck_operation_attempt_number CHECK (attempt_number = claim_generation + 1),
    CONSTRAINT ck_operation_attempt_trace_id CHECK (trace_id ~ '^[0-9a-f]{32}$'),
    CONSTRAINT ck_operation_attempt_root_span_id
        CHECK (root_span_id IS NULL OR root_span_id ~ '^[0-9a-f]{16}$'),
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
        cardinality(diagnostic_codes) <= 20
        AND octet_length(array_to_string(diagnostic_codes, ',')) <= 2048
    ),
    CONSTRAINT ck_operation_attempt_diagnostics_omitted CHECK (diagnostics_omitted >= 0)
);

CREATE INDEX IF NOT EXISTS idx_operation_attempts_trace_id
    ON operation_observation_attempts(trace_id);
CREATE INDEX IF NOT EXISTS idx_operation_attempts_failure_completed
    ON operation_observation_attempts(completed_at)
    WHERE outcome IN ('partial', 'retryable_failure', 'permanent_failure');


-- Cross-process health is bounded, durable status evidence, not workflow state.
CREATE TABLE IF NOT EXISTS telemetry_process_health (
    environment VARCHAR(32) NOT NULL,
    service_name VARCHAR(100) NOT NULL,
    service_instance_id VARCHAR(128) NOT NULL,
    release_revision VARCHAR(64) NOT NULL,
    required_observability BOOLEAN NOT NULL,
    initialized BOOLEAN NOT NULL,
    status VARCHAR(16) NOT NULL,
    export_target VARCHAR(32) NOT NULL,
    last_heartbeat_at TIMESTAMPTZ NOT NULL,
    last_success_at TIMESTAMPTZ NULL,
    last_error_at TIMESTAMPTZ NULL,
    last_error_code VARCHAR(100) NULL,
    buffered_count BIGINT NOT NULL DEFAULT 0,
    buffer_capacity BIGINT NOT NULL,
    dropped_count BIGINT NOT NULL DEFAULT 0,
    last_flush_at TIMESTAMPTZ NULL,
    last_flush_succeeded BOOLEAN NULL,
    PRIMARY KEY (environment, service_name, service_instance_id),
    CONSTRAINT ck_telemetry_process_lifecycle
        CHECK (lifecycle_kind IN ('long_running', 'short_lived')),
    CONSTRAINT ck_telemetry_process_expiry
        CHECK (expires_at > last_heartbeat_at
               AND expires_at <= last_heartbeat_at + INTERVAL '7 days'),
    CONSTRAINT ck_telemetry_process_status
        CHECK (status IN ('healthy', 'degraded', 'disabled', 'stale')),
    CONSTRAINT ck_telemetry_process_export_target
        CHECK (export_target IN ('local_langfuse', 'remote_langfuse', 'other_otlp', 'none')),
    CONSTRAINT ck_telemetry_process_last_error_code
        CHECK (last_error_code IS NULL OR last_error_code ~ '^[a-z][a-z0-9_.-]{0,99}$'),
    CONSTRAINT ck_telemetry_process_counts
        CHECK (buffered_count >= 0 AND buffer_capacity > 0
               AND buffered_count <= buffer_capacity AND dropped_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_telemetry_process_health_expiry
    ON telemetry_process_health(environment, expires_at, last_heartbeat_at DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_process_health_freshness
    ON telemetry_process_health(environment, last_heartbeat_at DESC, service_name, service_instance_id);
-- Writers set expires_at to last_heartbeat_at + 24h for long_running rows and +7d
-- for short_lived final-flush rows. Cleanup removes expired rows only; the API
-- returns the newest 1000 nonexpired rows and reports processes_omitted without
-- deleting current rows.

ALTER TABLE audit_log
    ADD COLUMN IF NOT EXISTS trace_id CHAR(32) NULL,
    ADD COLUMN IF NOT EXISTS request_span_id CHAR(16) NULL,
    ADD COLUMN IF NOT EXISTS submitted_operation_id BIGINT NULL
        REFERENCES pgqueuer_jobs(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS service_name VARCHAR(100) NULL,
    ADD COLUMN IF NOT EXISTS release_revision VARCHAR(64) NULL,
    ADD CONSTRAINT ck_audit_log_trace_id
        CHECK (trace_id IS NULL OR trace_id ~ '^[0-9a-f]{32}$'),
    ADD CONSTRAINT ck_audit_log_request_span_id
        CHECK (request_span_id IS NULL OR request_span_id ~ '^[0-9a-f]{16}$');

CREATE INDEX IF NOT EXISTS idx_audit_log_trace_id
    ON audit_log(trace_id) WHERE trace_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_audit_log_submitted_operation_id
    ON audit_log(submitted_operation_id) WHERE submitted_operation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_audit_log_trace_operation
    ON audit_log(trace_id, submitted_operation_id)
    WHERE trace_id IS NOT NULL OR submitted_operation_id IS NOT NULL;

ALTER TABLE workflow_terminal_events
    ADD COLUMN IF NOT EXISTS trace_id CHAR(32) NULL,
    ADD CONSTRAINT ck_workflow_terminal_events_trace_id
        CHECK (trace_id IS NULL OR trace_id ~ '^[0-9a-f]{32}$');

-- Ownership remains inactive until a separate cutover selects one shared authority.
CREATE TABLE IF NOT EXISTS environment_ownership (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    authority_fingerprint CHAR(64) NOT NULL
        CHECK (authority_fingerprint ~ '^[0-9a-f]{64}$'),
    active_environment VARCHAR(32) NOT NULL,
    epoch BIGINT NOT NULL CHECK (epoch >= 0),
    updated_at TIMESTAMPTZ NOT NULL,
    updated_by VARCHAR(128) NOT NULL
);
