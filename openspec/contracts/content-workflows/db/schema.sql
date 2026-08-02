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

-- Terminal workflow outcomes are captured as minimal durable intent in the
-- same transaction as the authoritative operation/action transition. Copied
-- identifiers intentionally have no foreign keys so operation retention cannot
-- cascade-delete or orphan the evidence boundary.
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
        OR (source_kind = 'reconciliation_action' AND event_key =
          'reconciliation-action:' || reconciliation_action_id::text)
        OR (source_kind = 'reconciliation_failure' AND event_key =
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
        OR (status = 'leased' AND attempt_count >= 1
         AND lease_expires_at IS NOT NULL AND delivered_at IS NULL)
        OR (status = 'delivered' AND attempt_count >= 1
         AND lease_expires_at IS NULL AND delivered_at IS NOT NULL
         AND last_error_code IS NULL)
        OR (status IN ('permanent_failure','exhausted') AND attempt_count >= 1
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

CREATE FUNCTION capture_pgqueuer_terminal_event()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    captured_event_id UUID;
BEGIN
    INSERT INTO workflow_terminal_events (
        event_key, source_kind, operation_id, claim_generation,
        terminal_status, occurred_at
    ) VALUES (
        format('operation:%s:claim:%s:status:%s',
               NEW.id, NEW.claim_generation, NEW.status),
        'operation', NEW.id, NEW.claim_generation, NEW.status,
        COALESCE(NEW.completed_at, NOW())
    ) ON CONFLICT (event_key) DO UPDATE
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
FOR EACH ROW WHEN (
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
        'reconciliation_action', NEW.id, NEW.run_id, NEW.content_id, NEW.created_at
    ) ON CONFLICT (event_key) DO UPDATE
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
