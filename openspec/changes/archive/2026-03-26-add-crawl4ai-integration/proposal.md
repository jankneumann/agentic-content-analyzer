# Change: Add Crawl4AI Integration for JavaScript-Heavy Content

## Change ID
`add-crawl4ai-integration`

## Status
PROPOSED

## Summary

Activate and productionize the existing Crawl4AI fallback path in `HtmlMarkdownConverter` for JavaScript-heavy content extraction. Adds settings-driven configuration, Docker-based remote server mode, cache management, and health check integration.

## Why

The HTML-to-markdown pipeline uses Trafilatura as the primary extractor, which handles most web content well. However, **JavaScript-heavy pages** (SPAs, dynamic content loaders like `claude.ai/blog`) return empty or incomplete content because Trafilatura doesn't execute JavaScript.

The `HtmlMarkdownConverter` already has Crawl4AI fallback code implemented but **disabled by default** because:
- Crawl4AI is not listed as a dependency in `pyproject.toml`
- Browser dependencies (Chromium via Playwright) require setup
- Docker deployment option needs configuration
- Settings integration is missing — converter uses hardcoded constructor defaults

## Current State

From `add-html-markdown-conversion` (archived):
- `HtmlMarkdownConverter._convert_with_crawl4ai()` is **implemented and API-current** (uses `AsyncWebCrawler`, `BrowserConfig`, `CrawlerRunConfig`, `PruningContentFilter`)
- Two-tier fallback logic exists but is gated by `use_crawl4ai_fallback=False` constructor default
- Quality validation (`validate_markdown_quality()`) triggers fallback when Trafilatura output < 200 chars
- `_check_crawl4ai()` does lazy import detection — returns `False` when package is missing
- RSS and Gmail ingestion services already call `converter.convert()` — no integration wiring needed

## What Changes

### 1. Dependencies
- Add `crawl4ai>=0.7.0` to `pyproject.toml` as **optional dependency group** (`[project.optional-dependencies] crawl4ai`)
- Document `uv pip install -e ".[crawl4ai]"` and `crawl4ai-setup` for local browser install
- Add `crawl4ai-doctor` verification step to setup docs

### 2. Settings Integration
- Add to `Settings` class in `src/config/settings.py`:
  - `crawl4ai_enabled: bool = False` — feature flag
  - `crawl4ai_cache_mode: str = "bypass"` — maps to `CacheMode` enum (bypass/enabled/disabled/read_only/write_only)
  - `crawl4ai_server_url: str | None = None` — remote server URL (e.g., `http://localhost:11235`)
  - `crawl4ai_page_timeout: int = 30000` — page load timeout in ms
  - `crawl4ai_excluded_tags: list[str] = ["nav", "footer", "header"]` — HTML tags to exclude
- Wire settings into `profiles/base.yaml` with `${CRAWL4AI_*}` interpolation

### 3. Converter Updates
- Update `HtmlMarkdownConverter.__init__()` to read from `get_settings()` instead of constructor defaults
- Add remote server mode: when `crawl4ai_server_url` is set, use HTTP REST API (`POST /md`) instead of local browser
- Map `crawl4ai_cache_mode` string setting to `CacheMode` enum
- Add `crawl4ai_excluded_tags` to `CrawlerRunConfig`
- Add configurable page timeout

### 4. Docker Deployment
- Add `crawl4ai` service to `docker-compose.yml` under `test` profile (opt-in)
- Image: `unclecode/crawl4ai:latest`, port 11235, `--shm-size=1g`
- Health check: `curl -f http://localhost:11235/health`
- Add Makefile targets: `crawl4ai-up`, `crawl4ai-down`, `crawl4ai-logs`

### 5. Testing
- Unit tests for settings integration and CacheMode mapping
- Unit tests for remote server mode (mocked HTTP)
- Integration tests with `@pytest.mark.crawl4ai` marker (requires browser or Docker)
- Hoverfly simulation for remote server API responses

### 6. Documentation
- Update `docs/SETUP.md` with Crawl4AI setup section
- Update `docs/ARCHITECTURE.md` with extraction pipeline diagram
- Update `CLAUDE.md` with new settings and gotchas
- Add Makefile target documentation

## Impact

- **Affected specs**: Extends `web-content-extraction` capability
- **Affected code**:
  - `pyproject.toml` — new optional dependency
  - `src/config/settings.py` — 5 new settings fields
  - `src/parsers/html_markdown.py` — settings integration + remote mode
  - `docker-compose.yml` — new service
  - `profiles/base.yaml` — new secret interpolation
  - `Makefile` — new targets
- **Breaking changes**: None — opt-in feature, disabled by default
- **Performance**: Crawl4AI adds 2-5s per page when triggered as fallback; remote mode adds ~100ms network overhead but avoids local browser memory usage

## Related Work

- **`add-html-markdown-conversion`** (archived) — core converter with Trafilatura, already integrated
- **`add-blog-scraping`** (proposed) — will benefit from Crawl4AI for JS-heavy blog index pages; complementary, not blocking
- **`add-kreuzberg-optional-parser`** (proposed) — alternative parser backend, different scope (PDFs/OCR vs web pages)

## Success Criteria

- `HtmlMarkdownConverter` falls back to Crawl4AI when Trafilatura quality is insufficient and `crawl4ai_enabled=True`
- Remote server mode works via Docker service without local browser install
- Cache mode settings correctly map to Crawl4AI `CacheMode` enum
- Existing RSS/Gmail ingestion works unchanged when Crawl4AI is disabled
- All new settings wired through profiles and `.secrets.yaml`
