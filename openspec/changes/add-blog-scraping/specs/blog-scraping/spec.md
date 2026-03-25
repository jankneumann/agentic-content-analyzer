# Spec: Blog Page Scraping Ingestion

## Overview

Adds a `blog` source type that discovers and ingests blog posts by scraping blog index/listing pages. Configured via `sources.d/blogs.yaml`, integrated into the daily pipeline.

## Requirements

### Source Configuration

- **SHALL** support a `BlogSource` model with `type: "blog"` and required `url` field
- **SHALL** support optional `link_selector` (CSS selector) for targeted link extraction
- **SHALL** support optional `link_pattern` (regex) for URL filtering
- **SHALL** support `request_delay` (float, default 1.0s) for rate limiting between HTTP requests
- **SHALL** inherit standard fields from `SourceBase`: `name`, `tags`, `enabled`, `max_entries`
- **SHALL** load blog sources from `sources.d/blogs.yaml` via the existing `load_sources_directory()` mechanism

### Link Discovery

- **SHALL** fetch the blog index page via HTTP with the same SSRF protection as `URLExtractor`
- **SHALL** use the configured `link_selector` CSS selector when provided
- **SHALL** fall back to heuristic link discovery when no selector is configured
- **SHALL** resolve relative URLs to absolute using the index page URL as base
- **SHALL** filter discovered links to same-domain or subdomain only
- **SHALL** exclude common non-article paths: `/tag/`, `/category/`, `/author/`, `/page/`, `/about`, `/contact`
- **SHALL** deduplicate discovered URLs before processing
- **SHALL** respect `max_entries` limit on discovered links
- **SHOULD** order links by page position (top = most recent) when no date is available

### Content Extraction

- **SHALL** reuse `HtmlMarkdownConverter` (Trafilatura) for HTML-to-markdown conversion
- **SHALL** extract published date using multiple strategies in order:
  1. Open Graph `article:published_time` meta tag
  2. `<time datetime>` elements
  3. `<meta name="date">` or `<meta name="DC.date">`
  4. JSON-LD `datePublished`
  5. Fallback: ingestion timestamp
- **SHALL** extract title from `<title>`, `<h1>`, or Open Graph `og:title`
- **SHALL** extract author from meta tags or JSON-LD when available
- **SHALL** set `publication` to the source `name` (or domain if unnamed)
- **SHALL** respect `request_delay` between fetching individual post pages

### Content Storage

- **SHALL** store ingested posts as `Content` records with `source_type = ContentSource.BLOG`
- **SHALL** set `source_id` to `"blog:{post_url}"` for unique identification
- **SHALL** set `source_url` to the post URL
- **SHALL** populate `markdown_content` as the primary content field
- **SHALL** store raw HTML in `raw_content` with `raw_format = "html"`
- **SHALL** set `parser_used = "BlogScraper"` and include version
- **SHALL** compute `content_hash` via `generate_markdown_hash()`

### Deduplication

- **SHALL** check `source_type + source_id` unique constraint (primary dedup)
- **SHALL** check `source_url` for URL-based dedup
- **SHALL** check `content_hash` for cross-source dedup
- **SHALL** skip duplicates unless `force_reprocess=True`
- **SHALL** support `after_date` filtering to skip posts older than threshold

### Integration

- **SHALL** provide `ingest_blog()` orchestrator function with lazy imports
- **SHALL** be included in `_run_ingestion()` pipeline runner (runs in parallel)
- **SHALL** provide `aca ingest blog` CLI command with `--max`, `--days`, `--force` options
- **SHALL** return `IngestionResult` with per-source `SourceFetchResult` details

### Error Handling

- **SHALL** log and skip individual post failures without aborting the source
- **SHALL** log and skip source-level failures without aborting other sources
- **SHALL** set `status = FAILED` with `error_message` on individual content extraction failures
- **SHOULD** include the failing URL in error messages for debugging

## Non-Requirements

- **SHALL NOT** execute JavaScript (relies on Trafilatura; Crawl4AI fallback is separate)
- **SHALL NOT** follow pagination beyond the configured index page
- **SHALL NOT** handle authentication-gated content
- **SHALL NOT** extract comments from blog posts
