-- Railway PostgreSQL Extension Initialization
-- This script runs automatically on first database initialization

-- Enable pgvector for vector similarity search (AI embeddings)
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable pg_search for full-text search with BM25 ranking (ParadeDB)
CREATE EXTENSION IF NOT EXISTS pg_search;

-- Enable pgmq for lightweight message queue
CREATE EXTENSION IF NOT EXISTS pgmq;

-- Enable pg_cron for job scheduling
-- Note: pg_cron must be loaded via shared_preload_libraries first
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Grant pg_cron permissions to the postgres user
GRANT USAGE ON SCHEMA cron TO postgres;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Railway PostgreSQL extensions initialized successfully:';
    RAISE NOTICE '  - pgvector: Vector similarity search';
    RAISE NOTICE '  - pg_search: Full-text search (ParadeDB)';
    RAISE NOTICE '  - pgmq: Message queue';
    RAISE NOTICE '  - pg_cron: Job scheduling';
END $$;

-- Set up automated backup jobs (pg_cron → MinIO)
\i /docker-entrypoint-initdb.d/init-backup-job.sql
