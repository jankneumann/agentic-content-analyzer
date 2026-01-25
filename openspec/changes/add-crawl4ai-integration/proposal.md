# Change: Add Crawl4AI Integration for JavaScript-Heavy Content

## Why

The HTML-to-markdown pipeline (implemented in `add-html-markdown-conversion`) uses Trafilatura as the primary extractor, which handles most web content well. However, **JavaScript-heavy pages** (SPAs, dynamic content loaders) return empty or incomplete content because Trafilatura doesn't execute JavaScript.

The `HtmlMarkdownConverter` already has Crawl4AI fallback code implemented but **disabled by default** because:
- Crawl4AI is not installed as a dependency
- Browser dependencies (Chromium) require setup
- Docker deployment option needs configuration

This change activates the existing Crawl4AI fallback path for JS-heavy content extraction.

## Current State

From `add-html-markdown-conversion`:
- `HtmlMarkdownConverter._convert_with_crawl4ai()` is implemented
- Fallback logic exists but is gated by `CRAWL4AI_AVAILABLE = False`
- Quality validation triggers fallback when Trafilatura output is insufficient

## What Changes

### Dependencies
- Add `crawl4ai>=0.7.0` to pyproject.toml as optional dependency
- Document browser setup via `crawl4ai-setup`
- Add verification via `crawl4ai-doctor`

### Configuration
- Add `CRAWL4AI_CACHE_MODE` setting for persistent caching
- Add `CRAWL4AI_ENABLED` feature flag (default: False until setup complete)

### Docker Deployment
- Add Crawl4AI service to docker-compose.yml
- Configure health checks for browser availability
- Document self-hosted deployment option

### Documentation
- Update ARCHITECTURE.md with Crawl4AI integration details
- Add setup guide for browser dependencies

## Impact

- **Affected specs**: Extends `web-content-extraction` capability
- **Affected code**:
  - `pyproject.toml` - New optional dependency
  - `src/config/settings.py` - New configuration options
  - `docker-compose.yml` - New service
  - `docs/ARCHITECTURE.md` - Updated documentation
- **Breaking changes**: None - opt-in feature
- **Performance**: Crawl4AI adds 2-5s per page when triggered as fallback

## Related Work

- **`add-html-markdown-conversion`** (complete) - Core converter implementation with Trafilatura
