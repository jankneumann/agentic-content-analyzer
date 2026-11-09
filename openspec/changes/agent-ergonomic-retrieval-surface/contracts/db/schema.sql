-- agent-ergonomic-retrieval-surface: database contract delta (one Alembic migration, task 4.2).
-- VARCHAR, not a PG enum, per the agent-tables convention: InsightMaturity StrEnum is the
-- source of truth and new values need no ALTER TYPE.

ALTER TABLE agent_insights
    ADD COLUMN IF NOT EXISTS maturity VARCHAR NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS superseded_by UUID NULL
        REFERENCES agent_insights (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS ix_agent_insights_maturity
    ON agent_insights (maturity);
CREATE INDEX IF NOT EXISTS ix_agent_insights_created_id
    ON agent_insights (created_at DESC, id DESC);   -- keyset paging

-- Downgrade drops the two indexes and columns. Existing rows become 'active' by default.
-- No change to agent_memories: the insight pointer uses the existing tags JSONB
-- (tag 'insight:<uuid>') and memory_type = 'insight'.
