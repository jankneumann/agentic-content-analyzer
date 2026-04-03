-- Contract: theme_analyses table schema
-- Must match ThemeAnalysis ORM model in src/models/theme.py

-- Enum type (idempotent creation)
DO $$ BEGIN
    CREATE TYPE analysisstatus AS ENUM ('queued', 'running', 'completed', 'failed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE theme_analyses (
    id SERIAL PRIMARY KEY,

    -- Lifecycle status
    status analysisstatus NOT NULL DEFAULT 'queued',

    -- Time range
    analysis_date TIMESTAMP NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,

    -- Analysis scope
    content_count INTEGER NOT NULL DEFAULT 0,
    content_ids JSON NOT NULL DEFAULT '[]'::json,

    -- Detected themes
    themes JSON NOT NULL DEFAULT '[]'::json,

    -- Summary statistics
    total_themes INTEGER NOT NULL DEFAULT 0,
    emerging_themes_count INTEGER NOT NULL DEFAULT 0,
    top_theme VARCHAR(500),

    -- Metadata
    agent_framework VARCHAR(100) NOT NULL DEFAULT '',
    model_used VARCHAR(100) NOT NULL DEFAULT '',
    model_version VARCHAR(20),
    processing_time_seconds FLOAT,
    token_usage INTEGER,

    -- Insights and errors
    cross_theme_insights JSON,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

-- Indexes
CREATE INDEX ix_theme_analyses_status ON theme_analyses (status);
CREATE INDEX ix_theme_analyses_analysis_date ON theme_analyses (analysis_date);
CREATE INDEX ix_theme_analyses_created_at ON theme_analyses (created_at);
CREATE INDEX ix_theme_analyses_status_created ON theme_analyses (status, created_at);
