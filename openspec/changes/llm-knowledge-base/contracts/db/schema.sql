-- Knowledge Base Database Schema
-- Topics and TopicNotes tables

-- TopicStatus enum
DO $$ BEGIN
    CREATE TYPE topicstatus AS ENUM ('draft', 'active', 'stale', 'archived', 'merged');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- TopicCategory table (hierarchical taxonomy)
CREATE TABLE IF NOT EXISTS topic_categories (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(200) NOT NULL,
    name VARCHAR(500) NOT NULL,
    description TEXT,
    parent_id INTEGER REFERENCES topic_categories(id) ON DELETE SET NULL,
    icon VARCHAR(50),
    color VARCHAR(20),
    display_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_topic_categories_slug UNIQUE (slug)
);

CREATE INDEX IF NOT EXISTS ix_topic_categories_parent ON topic_categories (parent_id);

-- Seed default categories from ThemeCategory enum
INSERT INTO topic_categories (slug, name, description, display_order) VALUES
    ('ml-ai', 'ML/AI', 'LLMs, agents, RAG, fine-tuning', 1),
    ('devops-infra', 'DevOps & Infrastructure', 'Cloud, containers, orchestration', 2),
    ('data-engineering', 'Data Engineering', 'Pipelines, lakes, processing', 3),
    ('business-strategy', 'Business Strategy', 'Adoption, ROI, governance', 4),
    ('tools-products', 'Tools & Products', 'New releases, updates', 5),
    ('research-academia', 'Research & Academia', 'Papers, breakthroughs', 6),
    ('security', 'Security', 'Security, privacy, compliance', 7),
    ('other', 'Other', 'Miscellaneous', 8)
ON CONFLICT (slug) DO NOTHING;

-- Topics table
CREATE TABLE IF NOT EXISTS topics (
    id SERIAL PRIMARY KEY,
    slug VARCHAR(200) NOT NULL,
    name VARCHAR(500) NOT NULL,
    category_id INTEGER NOT NULL REFERENCES topic_categories(id) ON DELETE RESTRICT,
    status topicstatus NOT NULL DEFAULT 'draft',

    -- LLM-compiled article content
    summary TEXT,
    article_md TEXT,
    article_version INTEGER NOT NULL DEFAULT 1,

    -- Trend & scoring (promoted from ThemeData)
    trend themeTrend,
    relevance_score FLOAT,
    strategic_relevance FLOAT,
    tactical_relevance FLOAT,
    novelty_score FLOAT,
    cross_functional_impact FLOAT,
    mention_count INTEGER NOT NULL DEFAULT 0,

    -- Evidence links
    source_content_ids JSON DEFAULT '[]',
    source_summary_ids JSON DEFAULT '[]',
    source_theme_ids JSON DEFAULT '[]',
    key_points JSON DEFAULT '[]',

    -- Relationships
    related_topic_ids JSON DEFAULT '[]',
    parent_topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    merged_into_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,

    -- Compilation metadata
    first_evidence_at TIMESTAMP WITH TIME ZONE,
    last_evidence_at TIMESTAMP WITH TIME ZONE,
    last_compiled_at TIMESTAMP WITH TIME ZONE,
    compilation_model VARCHAR(100),
    compilation_token_usage INTEGER,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT uq_topics_slug UNIQUE (slug)
);

-- Indexes
CREATE INDEX IF NOT EXISTS ix_topics_slug ON topics (slug);
CREATE INDEX IF NOT EXISTS ix_topics_category_id ON topics (category_id);
CREATE INDEX IF NOT EXISTS ix_topics_status ON topics (status);
CREATE INDEX IF NOT EXISTS ix_topics_trend ON topics (trend);
CREATE INDEX IF NOT EXISTS ix_topics_relevance ON topics (relevance_score DESC);
CREATE INDEX IF NOT EXISTS ix_topics_last_compiled ON topics (last_compiled_at);
CREATE INDEX IF NOT EXISTS ix_topics_category_trend ON topics (category_id, trend);
CREATE INDEX IF NOT EXISTS ix_topics_parent ON topics (parent_topic_id);

-- TopicNotes table
CREATE TABLE IF NOT EXISTS topic_notes (
    id SERIAL PRIMARY KEY,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    note_type VARCHAR(50) NOT NULL DEFAULT 'observation',
    content TEXT NOT NULL,
    author VARCHAR(100) NOT NULL DEFAULT 'system',
    filed_back BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS ix_topic_notes_topic_id ON topic_notes (topic_id);
CREATE INDEX IF NOT EXISTS ix_topic_notes_created_at ON topic_notes (created_at);
CREATE INDEX IF NOT EXISTS ix_topic_notes_filed_back ON topic_notes (filed_back) WHERE filed_back = FALSE;
