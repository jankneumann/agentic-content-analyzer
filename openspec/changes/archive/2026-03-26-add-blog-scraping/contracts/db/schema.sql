-- Blog Scraping Ingestion: Database Contract
-- This file defines the DB changes required for the blog source type.
-- Used as the source of truth for Alembic migration generation.

-- 1. Add 'blog' value to the contentsource PostgreSQL enum
-- Note: ALTER TYPE ... ADD VALUE cannot run inside a transaction in PG < 12.
-- Alembic migration must use op.execute() outside of transaction block.
ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'blog';

-- 2. No new tables required.
-- Blog content is stored in the existing `content` table using:
--   source_type = 'blog'
--   source_id   = 'blog:{post_url}'
--   source_url  = '{post_url}'
--   parser_used = 'BlogScraper'
--   raw_format  = 'html'

-- 3. Test fixture seed data
-- INSERT INTO content (
--     source_type, source_id, source_url, title, author, publication,
--     published_date, markdown_content, raw_content, raw_format,
--     parser_used, content_hash, status
-- ) VALUES (
--     'blog',
--     'blog:https://www.anthropic.com/research/example-post',
--     'https://www.anthropic.com/research/example-post',
--     'Example Blog Post',
--     'Anthropic Research',
--     'Anthropic Blog',
--     '2026-03-20T12:00:00Z',
--     '# Example Post\n\nThis is test content.',
--     '<h1>Example Post</h1><p>This is test content.</p>',
--     'html',
--     'BlogScraper',
--     'abc123deadbeef',
--     'pending'
-- );
