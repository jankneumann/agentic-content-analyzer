-- Contract: inert Gemini batch-execution persistence.
-- The Alembic revision is authoritative executable DDL; this file documents
-- the intended PostgreSQL shape reviewed with the OpenSpec change.

CREATE TABLE batch_jobs (
    id                varchar(36) PRIMARY KEY,
    provider          varchar(20)  NOT NULL CHECK (provider = 'google_ai'),
    provider_job_name text,
    model_id          varchar(64)  NOT NULL,
    model_step        varchar(40)  NOT NULL,
    state             varchar(24)  NOT NULL CHECK (
        state IN ('submitting', 'pending', 'running', 'succeeded',
                  'failed', 'cancelled', 'expired')
    ),
    request_count     integer      NOT NULL DEFAULT 0,
    submitted_at      timestamptz,
    completed_at      timestamptz,
    error             text,
    created_at        timestamptz  NOT NULL DEFAULT now(),
    updated_at        timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX ix_batch_jobs_open ON batch_jobs (state)
    WHERE state IN ('submitting', 'pending', 'running');
CREATE UNIQUE INDEX uq_batch_jobs_provider_job_name
    ON batch_jobs (provider_job_name)
    WHERE provider_job_name IS NOT NULL;

CREATE TABLE batch_requests (
    id                varchar(36) PRIMARY KEY,
    request_key       varchar(128) NOT NULL UNIQUE,
    batch_job_id      varchar(36) REFERENCES batch_jobs(id) ON DELETE SET NULL,
    model_step        varchar(40)  NOT NULL,
    model_id          varchar(64)  NOT NULL,
    content_id        bigint REFERENCES contents(id) ON DELETE SET NULL,
    request_payload   jsonb        NOT NULL,
    status            varchar(20)  NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'claimed', 'submitted', 'succeeded',
                   'fallback', 'failed')
    ),
    result_text       text,
    error             text,
    fallback_attempts integer      NOT NULL DEFAULT 0 CHECK (fallback_attempts >= 0),
    created_at        timestamptz  NOT NULL DEFAULT now(),
    updated_at        timestamptz  NOT NULL DEFAULT now(),
    completed_at      timestamptz
);
CREATE INDEX ix_batch_requests_pending
    ON batch_requests (model_step, model_id, created_at)
    WHERE status = 'pending';
CREATE INDEX ix_batch_requests_job ON batch_requests (batch_job_id);
CREATE UNIQUE INDEX uq_batch_requests_active_target
    ON batch_requests (model_step, content_id)
    WHERE content_id IS NOT NULL
      AND status IN ('pending', 'claimed', 'submitted', 'fallback');
