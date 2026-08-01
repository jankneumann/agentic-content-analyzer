-- Contract delta for canonical content provenance and queue-backed operations.
-- Implementation must translate this contract into an idempotent Alembic migration.

-- Each generated resource is durably owned by at most one queue operation.
-- Nullable ownership preserves legacy writers while allowing a worker to recover
-- a committed resource if its operation projection was not attached before a crash.
ALTER TABLE theme_analyses ADD COLUMN operation_id BIGINT;
ALTER TABLE digests ADD COLUMN operation_id BIGINT;
ALTER TABLE podcast_scripts ADD COLUMN operation_id BIGINT;
ALTER TABLE podcasts ADD COLUMN operation_id BIGINT;
ALTER TABLE audio_digests ADD COLUMN operation_id BIGINT;

CREATE UNIQUE INDEX ix_theme_analyses_operation_id ON theme_analyses (operation_id);
CREATE UNIQUE INDEX ix_digests_operation_id ON digests (operation_id);
CREATE UNIQUE INDEX ix_podcast_scripts_operation_id ON podcast_scripts (operation_id);
CREATE UNIQUE INDEX ix_podcasts_operation_id ON podcasts (operation_id);
CREATE UNIQUE INDEX ix_audio_digests_operation_id ON audio_digests (operation_id);

-- Theme analysis preserves the exact resolved content and Summary pairs rather
-- than re-querying a period and silently broadening the selection.
ALTER TABLE theme_analyses
    ADD COLUMN summary_ids JSONB,
    ADD COLUMN selection_fingerprint VARCHAR(64),
    ADD COLUMN selection_policy JSONB;

COMMENT ON COLUMN theme_analyses.summary_ids IS
    'Ordered persisted Summary IDs paired with content_ids';
COMMENT ON COLUMN theme_analyses.selection_fingerprint IS
    'SHA-256 fingerprint of selection schema, normalized policy, content IDs, and summary IDs';
COMMENT ON COLUMN theme_analyses.selection_policy IS
    'Normalized workflow SelectionPolicy including schema version and date basis';

UPDATE theme_analyses
SET summary_ids = COALESCE(summary_ids, '[]'::jsonb),
    selection_policy = COALESCE(
        selection_policy,
        jsonb_build_object(
            'schema_version', 0,
            'provenance', 'legacy-v0',
            'date_basis', 'published_date',
            'start_inclusive', true,
            'end_exclusive', false
        )
    )
WHERE summary_ids IS NULL OR selection_policy IS NULL;

-- The Alembic migration computes selection_fingerprint from the preserved
-- content_ids, empty legacy summary_ids, and legacy policy using the same
-- canonical JSON serialization as ContentSetResolver.

ALTER TABLE theme_analyses
    ALTER COLUMN summary_ids SET DEFAULT '[]'::jsonb,
    ALTER COLUMN summary_ids SET NOT NULL,
    ALTER COLUMN selection_policy SET DEFAULT
        '{"date_basis":"published_date","end_exclusive":false,"provenance":"legacy-v0","schema_version":0,"start_inclusive":true}'::jsonb,
    ALTER COLUMN selection_policy SET NOT NULL;

CREATE INDEX ix_theme_analyses_selection_fingerprint
    ON theme_analyses (selection_fingerprint);

ALTER TABLE digests
    ADD COLUMN source_summary_ids JSONB,
    ADD COLUMN selection_fingerprint VARCHAR(64),
    ADD COLUMN selection_policy JSONB;

COMMENT ON COLUMN digests.source_summary_ids IS
    'Ordered persisted Summary IDs paired with source_content_ids';
COMMENT ON COLUMN digests.selection_fingerprint IS
    'SHA-256 fingerprint of selection schema, normalized policy, content IDs, and summary IDs';
COMMENT ON COLUMN digests.selection_policy IS
    'Normalized workflow SelectionPolicy including schema version and date basis';

CREATE INDEX ix_digests_selection_fingerprint
    ON digests (selection_fingerprint);

-- Backfill legacy records before the columns become non-null. The exact digest
-- function is implemented in the Alembic migration so Python and SQL use the
-- same canonical JSON serialization.
UPDATE digests
SET source_summary_ids = COALESCE(source_summary_ids, '[]'::jsonb),
    selection_policy = COALESCE(
        selection_policy,
        jsonb_build_object(
            'schema_version', 0,
            'provenance', 'legacy-v0',
            'date_basis', 'published_date',
            'start_inclusive', true,
            'end_exclusive', false
        )
    )
WHERE source_summary_ids IS NULL OR selection_policy IS NULL;

ALTER TABLE digests
    ALTER COLUMN source_summary_ids SET NOT NULL,
    ALTER COLUMN selection_policy SET NOT NULL;

-- Use additive columns during the rolling deployment. A later cleanup
-- migration removes the newsletter-named columns after old workers drain.
ALTER TABLE podcast_scripts
    ADD COLUMN source_content_ids_available JSONB,
    ADD COLUMN source_content_ids_cited JSONB,
    ADD COLUMN selection_fingerprint VARCHAR(64);

UPDATE podcast_scripts
SET source_content_ids_available = COALESCE(
        source_content_ids_available,
        newsletter_ids_available,
        '[]'::jsonb
    ),
    source_content_ids_cited = COALESCE(
        source_content_ids_cited,
        '[]'::jsonb
    )
WHERE source_content_ids_available IS NULL OR source_content_ids_cited IS NULL;

ALTER TABLE podcast_scripts
    ALTER COLUMN source_content_ids_available SET NOT NULL,
    ALTER COLUMN source_content_ids_cited SET NOT NULL;

CREATE INDEX ix_podcast_scripts_selection_fingerprint
    ON podcast_scripts (selection_fingerprint);

-- pgqueuer_jobs already has payload JSONB, parent_job_id, idempotency_key,
-- error, retry_count, and lifecycle timestamps. Operation payload schema v2
-- is an application contract and intentionally requires no second table.
COMMENT ON COLUMN pgqueuer_jobs.payload IS
    'Versioned operation payload: schema_version, operation_type, input, progress, message, cancel_requested, resource, result';

-- Reconciliation ownership is additive so legacy workers continue to claim and
-- transition records while protocol-aware workers can fence stale attempts.
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
        (status_operation_id IS NULL AND status_claim_generation IS NULL
         AND status_operation_phase IS NULL AND status_owner_version IS NULL)
        OR
        (status_operation_id IS NOT NULL AND status_operation_id > 0
         AND status_claim_generation IS NOT NULL AND status_claim_generation > 0
         AND status_operation_phase IS NOT NULL
         AND status_owner_version IS NOT NULL AND status_owner_version > 0
         AND ((status_operation_phase = 'parsing' AND status IN ('parsing', 'failed'))
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

CREATE TABLE content_reconciliation_actions (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL,
    content_id BIGINT NOT NULL CHECK (content_id > 0),
    operation_id BIGINT NOT NULL CHECK (operation_id > 0),
    claim_generation BIGINT NOT NULL CHECK (claim_generation > 0),
    claim_protocol_version SMALLINT NOT NULL CHECK (claim_protocol_version >= 1),
    phase VARCHAR(16) NOT NULL CHECK (phase IN ('parsing', 'processing')),
    content_status_before VARCHAR(32) NOT NULL,
    content_status_after VARCHAR(32) NOT NULL,
    operation_status_before VARCHAR(32) NOT NULL,
    operation_status_after VARCHAR(32) NOT NULL,
    retry_count_before INTEGER NOT NULL CHECK (retry_count_before >= 0),
    retry_count_after INTEGER NOT NULL CHECK (retry_count_after >= 0),
    action VARCHAR(40) NOT NULL CHECK (action IN (
        'retry_operation','project_completed','project_parsed','restore_parsed',
        'restore_pending','cancel_restore_parsed','cancel_restore_pending'
    )),
    reason VARCHAR(40) NOT NULL CHECK (reason IN (
        'summary_exists','extraction_completed','cancellation_requested',
        'stale_operation','failed_operation','summarization_cancelled','extraction_cancelled'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_content_reconciliation_actions_run_content UNIQUE (run_id, content_id),
    CHECK (content_status_before IN
        ('pending','parsing','parsed','processing','completed','failed','filtered_out')),
    CHECK (content_status_after IN
        ('pending','parsing','parsed','processing','completed','failed','filtered_out')),
    CHECK (operation_status_before IN
        ('queued','in_progress','completed','failed','cancelled')),
    CHECK (operation_status_after IN
        ('queued','in_progress','completed','failed','cancelled'))
);

CREATE INDEX ix_content_reconciliation_actions_run
    ON content_reconciliation_actions (run_id, id);
CREATE INDEX ix_content_reconciliation_actions_content_created
    ON content_reconciliation_actions (content_id, created_at DESC);

-- The append-only action trigger rejects both UPDATE and DELETE. Queue claim
-- generation advances on every queued-to-in-progress claim; every requeue
-- resets protocol to 1 so an old worker cannot inherit protocol-aware authority.
-- A Content status transition clears an unchanged ownership token, preserving
-- compatibility for writers that do not yet advance status_owner_version.

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
FOR EACH ROW WHEN (OLD.status = 'queued' AND NEW.status = 'in_progress')
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
FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM 'queued' AND NEW.status = 'queued')
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
