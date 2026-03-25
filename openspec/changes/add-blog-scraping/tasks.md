# Tasks: Blog Page Scraping Ingestion

## Task Graph

```
T1 (source model) ──┐
T2 (enum + migration)┤
                     ├── T4 (blog scraper module) ── T5 (orchestrator) ── T6 (pipeline) ── T8 (integration test)
T3 (sources.d yaml) ─┘                                    │
                                                           T7 (CLI command)
```

## Tasks

### T1: Add BlogSource to Source Configuration
**Files**: `src/config/sources.py`
**Effort**: Small
**Dependencies**: None

- Add `BlogSource(SourceBase)` with fields: `url`, `link_selector`, `link_pattern`, `request_delay`
- Add `BlogSource` to `Source` discriminated union
- Add `get_blog_sources()` method to `SourcesConfig`
- Add `request_delay` to `SourceDefaults` (blog-specific default)

### T2: Add BLOG Enum Value and Migration
**Files**: `src/models/content.py`, `alembic/versions/xxx_add_blog_enum.py`
**Effort**: Small
**Dependencies**: None

- Add `BLOG = "blog"` to `ContentSource` enum
- Create Alembic migration: `ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'blog'`
- Update module docstring to include BLOG source

### T3: Create Blog Source Configuration File
**Files**: `sources.d/blogs.yaml`
**Effort**: Small
**Dependencies**: None

- Create `sources.d/blogs.yaml` with defaults section (`type: blog`)
- Add initial sources: Anthropic research blog, Claude blog
- Include examples with `link_selector` and without (heuristic mode)

### T4: Implement Blog Scraping Client and Service
**Files**: `src/ingestion/blog_scraper.py`, `tests/test_ingestion/test_blog_scraper.py`
**Effort**: Large
**Dependencies**: T1, T2

Core implementation:

**BlogScrapingClient:**
- `fetch_index_page(url)` — HTTP fetch with SSRF protection, returns HTML
- `discover_post_links(html, base_url, link_selector, link_pattern)` — Extract and filter post URLs
- `extract_post_content(url)` — Fetch article, extract markdown via Trafilatura
- `extract_published_date(html)` — Multi-strategy date extraction (OG, time tag, JSON-LD, meta)
- Rate limiting between requests (`request_delay`)

**BlogContentIngestionService:**
- `ingest_content(sources, max_entries_per_source, after_date, force_reprocess)` → `IngestionResult`
- Source resolution from parameter or `sources.d/blogs.yaml`
- 3-level deduplication (source_id, source_url, content_hash)
- Per-source result tracking via `SourceFetchResult`

**Tests:**
- Unit tests for link discovery with various HTML structures
- Unit tests for date extraction strategies
- Unit tests for URL filtering (same-domain, non-article exclusion)
- Unit tests for deduplication logic
- Mock HTTP responses (no real network calls)

### T5: Add Orchestrator Function
**Files**: `src/ingestion/orchestrator.py`
**Effort**: Small
**Dependencies**: T4

- Add `ingest_blog()` function following existing pattern (lazy import, parameter forwarding)
- Support `on_result` callback for CLI rich output

### T6: Integrate into Pipeline Runner
**Files**: `src/pipeline/runner.py`
**Effort**: Small
**Dependencies**: T5

- Import `ingest_blog` in `_run_ingestion()`
- Add `("blog", ingest_blog)` to the `sources` list
- Blog runs in parallel with other ingestion sources

### T7: Add CLI Command
**Files**: `src/cli/ingest_commands.py`
**Effort**: Small
**Dependencies**: T5

- Add `blog` subcommand to `aca ingest`
- Options: `--max`, `--days`, `--force`, `--direct`
- Follow existing CLI command pattern (API path + direct path)

### T8: Integration Test
**Files**: `tests/test_ingestion/test_blog_scraper_integration.py`
**Effort**: Medium
**Dependencies**: T4, T5, T6, T7

- Test full flow: config loading → link discovery → content extraction → DB persistence
- Test deduplication on second run
- Test date filtering
- Test pipeline integration (blog source appears in ingestion results)
- Use mock HTTP responses via `respx` or `responses` library

## Verification

- [ ] `aca ingest blog` runs successfully against configured sources
- [ ] Posts from Anthropic blog are ingested with titles, dates, and markdown
- [ ] Re-running skips already-ingested posts (deduplication works)
- [ ] `aca pipeline daily` includes blog sources
- [ ] `pytest tests/test_ingestion/test_blog_scraper.py` passes
- [ ] No regressions: `pytest tests/` passes
- [ ] Alembic migration applies cleanly: `alembic upgrade head`
