-- Contract: database schema additions for ingestion filtering
-- Two Alembic migrations are needed because ALTER TYPE ADD VALUE cannot share
-- a transaction with other DDL.

-- ============================================================
-- Migration A (standalone): extend ContentStatus enum
-- ============================================================
ALTER TYPE content_status ADD VALUE 'FILTERED_OUT';

-- ============================================================
-- Migration B (transactional): contents columns + indexes
-- ============================================================
ALTER TABLE contents
    ADD COLUMN filter_score     double precision   NULL,
    ADD COLUMN filter_decision  varchar(20)        NULL,
    ADD COLUMN filter_tier      varchar(20)        NULL,
    ADD COLUMN filter_reason    text               NULL,
    ADD COLUMN priority_bucket  varchar(20)        NULL,
    ADD COLUMN filtered_at      timestamptz        NULL;

CREATE INDEX ix_contents_status_filter_score
    ON contents (status, filter_score DESC);

CREATE INDEX ix_contents_filter_decision_ingested
    ON contents (filter_decision, ingested_at DESC);

-- ============================================================
-- Migration C: persona profile cache and feedback events
-- ============================================================
CREATE TABLE persona_filter_profiles (
    persona_id          text         NOT NULL,
    embedding_provider  text         NOT NULL,
    embedding_model     text         NOT NULL,
    interest_hash       text         NOT NULL,
    -- dimension intentionally unconstrained — follows existing document_chunks.embedding convention
    embedding           vector       NOT NULL,
    updated_at          timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (persona_id, embedding_provider, embedding_model)
);

CREATE TABLE filter_feedback_events (
    id                 bigserial     PRIMARY KEY,
    content_id         bigint        NOT NULL REFERENCES contents (id) ON DELETE CASCADE,
    persona_id         text          NOT NULL,
    original_score     double precision NOT NULL,
    original_decision  varchar(20)   NOT NULL,
    reviewer_decision  varchar(20)   NOT NULL,
    reviewed_at        timestamptz   NOT NULL DEFAULT now(),
    metadata           jsonb         NULL
);

CREATE INDEX ix_filter_feedback_events_content
    ON filter_feedback_events (content_id);
CREATE INDEX ix_filter_feedback_events_persona_reviewed
    ON filter_feedback_events (persona_id, reviewed_at DESC);
