-- Contract: Gemini batch execution persistence (Approach A).
-- Authoritative DDL for the Alembic migration in task 0.1.1. The migration MUST
-- use a generated revision id (alembic revision -m ...), never a hand-crafted one.

-- A submitted (or pending-submission) Gemini batch job.
CREATE TABLE batch_jobs (
    id                uuid PRIMARY KEY,
    provider          varchar(20)  NOT NULL,          -- 'google_ai'
    provider_job_name text,                            -- e.g. batches/123...; NULL until submitted
    model_id          varchar(64)  NOT NULL,           -- logical id, e.g. gemini-3.1-flash-lite
    model_step        varchar(40)  NOT NULL,
    state             varchar(24)  NOT NULL,           -- pending|running|succeeded|failed|expired|cancelled
    request_count     integer      NOT NULL DEFAULT 0,
    submitted_at      timestamptz,
    completed_at      timestamptz,
    error             text,
    created_at        timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX ix_batch_jobs_open ON batch_jobs (state)
    WHERE state IN ('pending', 'running');

-- One deferred LLM request, keyed to the row it reconciles back to.
CREATE TABLE batch_requests (
    id                uuid PRIMARY KEY,
    request_key       varchar(64)  NOT NULL,           -- stable key echoed in the JSONL line
    batch_job_id      uuid REFERENCES batch_jobs(id),  -- NULL until flushed into a job
    model_step        varchar(40)  NOT NULL,
    model_id          varchar(64)  NOT NULL,
    target_table      varchar(40)  NOT NULL,           -- 'contents'
    target_id         uuid         NOT NULL,           -- row to reconcile back to
    request_payload   jsonb        NOT NULL,           -- serialized GenerateContentRequest
    status            varchar(20)  NOT NULL,           -- pending|submitted|succeeded|failed|fallback
    result_text       text,
    error             text,
    created_at        timestamptz  NOT NULL DEFAULT now(),
    completed_at      timestamptz
);
-- Flush worker scans pending requests by (step, model); partial index keeps it cheap.
CREATE INDEX ix_batch_requests_pending ON batch_requests (model_step, model_id, created_at)
    WHERE status = 'pending';
CREATE INDEX ix_batch_requests_job ON batch_requests (batch_job_id);
-- Reconciler looks up a request by the key returned in batch results.
CREATE UNIQUE INDEX uq_batch_requests_key ON batch_requests (request_key);

-- Phase 3 only: new ContentStatus enum value for output-blocking steps.
-- Implemented as ALTER TYPE ... ADD VALUE (Top-10 gotcha #2), shown here for the contract.
-- ALTER TYPE contentstatus ADD VALUE IF NOT EXISTS 'PENDING_BATCH';
