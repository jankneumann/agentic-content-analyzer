-- retrieval-adapter-boundary: additive schema changes.
-- Applied by one Alembic revision (task 1.6). Run `alembic heads` first; merge if
-- more than one head exists (GOTCHAS: Alembic multiple heads).

-- Retrieval dataset kind on existing evaluation datasets. Routing datasets keep
-- their current shape; the default preserves every existing row.
ALTER TABLE evaluation_datasets
    ADD COLUMN dataset_kind VARCHAR(20) NOT NULL DEFAULT 'routing';
ALTER TABLE evaluation_datasets
    ADD CONSTRAINT ck_evaluation_datasets_kind
    CHECK (dataset_kind IN ('routing', 'retrieval'));
ALTER TABLE evaluation_datasets ALTER COLUMN strong_model DROP NOT NULL;
ALTER TABLE evaluation_datasets ALTER COLUMN weak_model DROP NOT NULL;

-- Retrieval samples: relevant content ids and provenance of the label.
ALTER TABLE evaluation_samples
    ADD COLUMN relevant_ids JSONB NULL;
ALTER TABLE evaluation_samples
    ADD COLUMN provisional BOOLEAN NOT NULL DEFAULT FALSE;

-- Shadow-read comparisons. One row per shadow read that completed.
CREATE TABLE retrieval_shadow_comparisons (
    id                  BIGSERIAL PRIMARY KEY,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    namespace           VARCHAR(32)  NOT NULL,
    search_mode         VARCHAR(16)  NOT NULL,
    query_hash          VARCHAR(64)  NOT NULL,
    primary_adapter     VARCHAR(32)  NOT NULL,
    secondary_adapter   VARCHAR(32)  NOT NULL,
    primary_top_ids     JSONB        NOT NULL,
    secondary_top_ids   JSONB        NOT NULL,
    overlap_at_10       REAL         NOT NULL,
    rank_correlation    REAL         NULL,
    primary_latency_ms  INTEGER      NOT NULL,
    secondary_latency_ms INTEGER     NOT NULL,
    CONSTRAINT ck_retrieval_shadow_namespace
        CHECK (namespace IN ('content_chunks', 'agent_memories')),
    CONSTRAINT ck_retrieval_shadow_mode
        CHECK (search_mode IN ('bm25', 'vector', 'hybrid'))
);
CREATE INDEX ix_retrieval_shadow_comparisons_created_at
    ON retrieval_shadow_comparisons (created_at);
CREATE INDEX ix_retrieval_shadow_comparisons_query_hash
    ON retrieval_shadow_comparisons (query_hash);

-- Retrieval metric rows reuse evaluation_results:
--   judge_type = 'metric', judge_model = '<adapter>:<mode>', preference = 'n/a',
--   critiques = {"recall_at_5": ..., "recall_at_10": ..., "recall_at_20": ...,
--                "mrr": ..., "p50_ms": ..., "p95_ms": ..., "skipped": N,
--                "overlap_at_10": {"<other adapter>": ...}}
-- judge_type is VARCHAR(10); 'metric' fits. No DDL change to evaluation_results.

-- No change to document_chunks or agent_memories.
