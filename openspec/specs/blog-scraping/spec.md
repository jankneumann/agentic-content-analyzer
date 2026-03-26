# blog-scraping Specification

## Purpose
TBD - created by archiving change add-blog-scraping. Update Purpose after archive.
## Requirements
### Requirement: Blog Source Configuration

The system SHALL support a `BlogSource` configuration model for blog page scraping.

- **SHALL** support `type: "blog"` with required `url` field
- **SHALL** support optional `link_selector` (CSS selector) for targeted link extraction
- **SHALL** support optional `link_pattern` (regex) for URL filtering
- **SHALL** support `request_delay` (float, default 1.0s) for rate limiting
- **SHALL** inherit standard fields from `SourceBase`: `name`, `tags`, `enabled`, `max_entries`
- **SHALL** load blog sources from `sources.d/blogs.yaml` via `load_sources_directory()`

#### Scenario: Blog source with CSS selector
- **GIVEN** a `sources.d/blogs.yaml` with a source entry containing `link_selector: "a[href*='/blog/']"`
- **WHEN** `load_sources_config()` is called
- **THEN** the returned `SourcesConfig` contains a `BlogSource` with `link_selector` set
- **AND** `get_blog_sources()` returns the enabled blog sources

#### Scenario: Blog source with defaults only
- **GIVEN** a `sources.d/blogs.yaml` with a source entry containing only `url` and `name`
- **WHEN** `load_sources_config()` is called
- **THEN** `request_delay` defaults to 1.0
- **AND** `link_selector` is None (heuristic mode)

### Requirement: Blog Index Page Link Discovery

The system SHALL discover blog post links from index pages using CSS selectors or heuristics.

- **SHALL** fetch the blog index page via HTTP with SSRF protection
- **SHALL** use the configured `link_selector` CSS selector when provided
- **SHALL** fall back to heuristic link discovery when no selector is configured
- **SHALL** resolve relative URLs to absolute using the index page URL as base
- **SHALL** filter discovered links to same-domain or subdomain only
- **SHALL** exclude common non-article paths: `/tag/`, `/category/`, `/author/`, `/page/`, `/about`, `/contact`
- **SHALL** deduplicate discovered URLs before processing
- **SHALL** respect `max_entries` limit on discovered links

#### Scenario: CSS selector link discovery
- **GIVEN** a blog index page HTML containing `<article><a href="/blog/post-1">Post 1</a></article>`
- **AND** `link_selector` is `"article a[href]"`
- **WHEN** `discover_post_links()` is called
- **THEN** the returned list contains the absolute URL for `/blog/post-1`
- **AND** the title_hint is "Post 1"

#### Scenario: Heuristic link discovery
- **GIVEN** a blog index page HTML with no `link_selector` configured
- **WHEN** `discover_post_links()` is called
- **THEN** links are extracted using the fallback selector priority list
- **AND** non-article paths (`/tag/`, `/about`) are excluded

#### Scenario: Cross-domain links filtered
- **GIVEN** a blog index page containing links to external domains
- **WHEN** `discover_post_links()` is called
- **THEN** only same-domain or subdomain links are returned

### Requirement: Blog Post Content Extraction

The system SHALL extract structured content from individual blog post pages.

- **SHALL** reuse `HtmlMarkdownConverter` (Trafilatura) for HTML-to-markdown conversion
- **SHALL** extract published date using strategies: OG meta, `<time>`, meta name, JSON-LD, fallback
- **SHALL** extract title from `<title>`, `<h1>`, or Open Graph `og:title`
- **SHALL** extract author from meta tags or JSON-LD when available
- **SHALL** set `publication` to the source `name` (or domain if unnamed)
- **SHALL** respect `request_delay` between fetching individual post pages

#### Scenario: Date extraction from Open Graph
- **GIVEN** a blog post HTML containing `<meta property="article:published_time" content="2026-03-20T12:00:00Z">`
- **WHEN** `extract_published_date()` is called
- **THEN** the returned datetime is 2026-03-20 12:00:00 UTC

#### Scenario: Date extraction fallback to JSON-LD
- **GIVEN** a blog post HTML with no OG meta or `<time>` element
- **AND** JSON-LD containing `"datePublished": "2026-03-20"`
- **WHEN** `extract_published_date()` is called
- **THEN** the JSON-LD date is used

#### Scenario: Content extraction produces markdown
- **GIVEN** a blog post URL pointing to a valid HTML page
- **WHEN** `extract_post_content()` is called
- **THEN** `markdown_content` is populated via Trafilatura
- **AND** `raw_content` contains the original HTML
- **AND** `content_hash` is computed via `generate_markdown_hash()`

### Requirement: Blog Content Storage

The system SHALL store blog posts as Content records with source_type BLOG.

- **SHALL** set `source_type = ContentSource.BLOG`
- **SHALL** set `source_id` to `"blog:{post_url}"`
- **SHALL** set `source_url` to the post URL
- **SHALL** populate `markdown_content` as the primary content field
- **SHALL** store raw HTML in `raw_content` with `raw_format = "html"`
- **SHALL** set `parser_used = "BlogScraper"`
- **SHALL** compute `content_hash` via `generate_markdown_hash()`

#### Scenario: Blog post stored as Content record
- **GIVEN** a successfully extracted blog post from "https://www.anthropic.com/research/example"
- **WHEN** the post is persisted to the database
- **THEN** `source_type` is `ContentSource.BLOG`
- **AND** `source_id` is `"blog:https://www.anthropic.com/research/example"`
- **AND** `parser_used` is `"BlogScraper"`

### Requirement: Blog Content Deduplication

The system SHALL deduplicate blog posts using three levels of checking.

- **SHALL** check `source_type + source_id` unique constraint (primary dedup)
- **SHALL** check `source_url` for URL-based dedup
- **SHALL** check `content_hash` for cross-source dedup
- **SHALL** skip duplicates unless `force_reprocess=True`
- **SHALL** support `after_date` filtering to skip posts older than threshold

#### Scenario: Duplicate post skipped on re-run
- **GIVEN** a blog post already ingested with `source_id = "blog:https://example.com/post-1"`
- **WHEN** `ingest_content()` is called again
- **THEN** the duplicate is skipped
- **AND** `items_ingested` does not increment

#### Scenario: Force reprocess overrides dedup
- **GIVEN** a blog post already ingested
- **WHEN** `ingest_content(force_reprocess=True)` is called
- **THEN** the post is re-extracted and updated

### Requirement: Pipeline and CLI Integration

The system SHALL integrate blog ingestion into the daily pipeline and CLI.

- **SHALL** provide `ingest_blog()` orchestrator function with lazy imports
- **SHALL** be included in `_run_ingestion_stage_async()` pipeline runner
- **SHALL** provide `aca ingest blog` CLI command with `--max`, `--days`, `--force` options
- **SHALL** return `IngestionResult` with per-source `SourceFetchResult` details

#### Scenario: Blog included in daily pipeline
- **GIVEN** blog sources are configured in `sources.d/blogs.yaml`
- **WHEN** `aca pipeline daily` is executed
- **THEN** blog ingestion runs in parallel with other sources
- **AND** blog results are included in the pipeline summary

#### Scenario: CLI direct mode fallback
- **GIVEN** the API server is not running
- **WHEN** `aca ingest blog --direct` is executed
- **THEN** the orchestrator is called directly
- **AND** results are displayed to the user

### Requirement: Graceful Error Handling

The system SHALL handle failures gracefully without aborting entire ingestion.

- **SHALL** log and skip individual post failures without aborting the source
- **SHALL** log and skip source-level failures without aborting other sources
- **SHALL** set `status = FAILED` with `error_message` on extraction failures

#### Scenario: Single post failure does not abort source
- **GIVEN** a blog source with 5 discovered links where link 3 returns HTTP 404
- **WHEN** `ingest_content()` processes the source
- **THEN** links 1, 2, 4, 5 are ingested successfully
- **AND** link 3 is logged as failed
- **AND** `SourceFetchResult.items_fetched` is 4

### Requirement: BLOG Enum Value

The system SHALL add `BLOG` to the `ContentSource` PostgreSQL enum via migration.

- **SHALL** add `BLOG = "blog"` to `ContentSource` Python enum
- **SHALL** create Alembic migration: `ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'blog'`

#### Scenario: Migration applies cleanly
- **GIVEN** a database at the current head migration
- **WHEN** `alembic upgrade head` is run after adding the migration
- **THEN** the `contentsource` enum includes `'blog'`
- **AND** Content records can be created with `source_type = 'blog'`
