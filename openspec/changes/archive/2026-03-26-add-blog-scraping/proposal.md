# Proposal: Blog Page Scraping Ingestion

## Change ID
`add-blog-scraping`

## Status
PROPOSED

## Summary

Add a new ingestion source type (`blog`) that discovers and ingests blog posts by scraping blog index/listing pages. Many blogs (e.g., https://claude.ai/blog) no longer offer RSS feeds but link to new posts directly from their main page. This feature reads the index page, extracts post links, follows them to extract full content, and ingests them as Content records with deduplication and date filtering.

## Motivation

- **Gap in coverage**: A growing number of high-quality AI/ML blogs have dropped RSS feeds entirely. The only way to follow them is to visit the page.
- **Examples**: Anthropic's blog (claude.ai/blog), many company engineering blogs, research lab announcements.
- **User request**: Configurable in `sources.d/` like other sources, integrated into the daily pipeline.

## Scope

### In Scope
- New `BlogSource` model in `src/config/sources.py` with `type: "blog"`
- New `sources.d/blogs.yaml` configuration file
- New `BlogScrapingClient` that fetches an index page, extracts post links via CSS selectors or heuristics
- New `BlogContentIngestionService` following the existing client-service pattern
- Orchestrator function `ingest_blog()` in `src/ingestion/orchestrator.py`
- CLI command `aca ingest blog`
- Pipeline runner integration (included in `_run_ingestion()`)
- Deduplication by source URL (reuse existing `source_url` check + content hash)
- Date filtering via `published_date` extraction from article pages
- `ContentSource.BLOG` enum value (or reuse `WEBPAGE` with metadata distinction)

### Out of Scope
- JavaScript-rendered blog pages (Crawl4AI fallback exists but is separate)
- Automatic blog discovery (user configures URLs)
- Comment extraction
- Pagination beyond a single index page (future enhancement)
- Authentication-gated blogs

## Dependencies
- Existing: `HtmlMarkdownConverter` (Trafilatura), `URLExtractor`, `extract_links()`, `html_to_text()`
- Existing: `sources.d/` configuration system, `SourcesConfig` loader
- Optional: Crawl4AI fallback for JS-heavy sites (already implemented, disabled by default)

## Risks
- **Link extraction heuristics**: Blog index pages vary widely in structure. CSS selector configuration per source mitigates this.
- **Rate limiting**: Fetching multiple pages per blog source. Configurable delay and max_entries cap.
- **Content quality**: Some index pages may link to non-article pages (about, contact). Filtering by URL pattern and content quality validation.

## Success Criteria
- `aca ingest blog` successfully discovers and ingests posts from configured blog URLs
- Posts from `claude.ai/blog` are ingested with correct titles, dates, and markdown content
- Duplicates are skipped on re-run
- Integrated into `aca pipeline daily` alongside other sources
- No regressions in existing ingestion sources
