-- agent-runtime-correctness: database contract delta.
-- Applied through two Alembic migrations (tasks 4.2 and 5.6); this file is the reviewable
-- statement of intent, not a script to run directly.

-- D10: link an approval request to its approval.wait operation (pgqueuer_jobs.id).
ALTER TABLE approval_requests
    ADD COLUMN IF NOT EXISTS operation_id BIGINT NULL
        REFERENCES pgqueuer_jobs (id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_approval_requests_operation
    ON approval_requests (operation_id);

-- D7: align the memory embedding column with the configured embedding model.
-- :dims is interpolated at migration time from AGENT_MEMORY_EMBEDDING_DIMENSIONS
-- (default 384), following the migration-time interpolation pattern in docs/GOTCHAS.md.
-- Existing 1536-dim vectors cannot be cast, so they are nulled; the migration logs the count.
DROP INDEX IF EXISTS ix_agent_memories_embedding;
UPDATE agent_memories SET embedding = NULL WHERE embedding IS NOT NULL;
ALTER TABLE agent_memories
    ALTER COLUMN embedding TYPE vector(:dims) USING NULL;
CREATE INDEX IF NOT EXISTS ix_agent_memories_embedding
    ON agent_memories USING hnsw (embedding vector_cosine_ops);
COMMENT ON COLUMN agent_memories.embedding IS 'dimensions=:dims';

-- D3: no schema change. wait_on lives in pgqueuer_jobs.payload (JSONB) and the wake path
-- updates execute_after on the existing (status, execute_after, priority DESC) index.
