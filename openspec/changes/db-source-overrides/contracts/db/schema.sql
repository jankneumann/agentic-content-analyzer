-- Contract: source_overrides table for database-backed ingestion source overrides.
-- Mirrors the idempotent creation pattern used by settings_overrides.

CREATE TABLE IF NOT EXISTS source_overrides (
    id          SERIAL PRIMARY KEY,
    source_key  VARCHAR(512) NOT NULL,          -- natural key: "<type>:<locator>"
    source_type VARCHAR(64)  NOT NULL,          -- e.g. blog, rss, youtube_playlist
    config      JSONB        NOT NULL,          -- full validated source definition
    enabled     BOOLEAN      NOT NULL DEFAULT TRUE,
    version     INTEGER      NOT NULL DEFAULT 1,
    description TEXT,
    created_at  TIMESTAMP    NOT NULL,
    updated_at  TIMESTAMP    NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_source_overrides_source_key
    ON source_overrides (source_key);

CREATE INDEX IF NOT EXISTS ix_source_overrides_source_type
    ON source_overrides (source_type);
