-- Contract delta for canonical content provenance and queue-backed operations.
-- Implementation must translate this contract into an idempotent Alembic migration.

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
