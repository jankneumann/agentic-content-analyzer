# Tasks: HTML to Markdown Conversion

## Phase 1: Core Implementation (COMPLETE)

### 1. Dependencies & Setup

- [x] 1.1 Add `trafilatura>=2.0.0` to pyproject.toml
- [ ] 1.2 Add `trafilatura[all]` for full features (language detection) - *deferred*
- [ ] 1.3 Add `crawl4ai>=0.7.0` to pyproject.toml (optional dependency) - *Phase 2*
- [ ] 1.4 Run `crawl4ai-setup` to install browser dependencies - *Phase 2*
- [ ] 1.5 Verify installation with `crawl4ai-doctor` - *Phase 2*

### 2. Core Implementation

- [x] 2.1 Create `src/parsers/html_markdown.py` module
- [x] 2.2 Implement `HtmlMarkdownConverter` class (async-native)
  - [x] 2.2.1 `_convert_with_trafilatura()` method (sync, wrapped with to_thread)
  - [x] 2.2.2 `_convert_with_crawl4ai()` async method (implemented, disabled by default)
  - [x] 2.2.3 `convert()` async method with automatic fallback
  - [x] 2.2.4 Support dual input: `url` parameter OR `html` parameter
- [x] 2.3 Implement `validate_markdown_quality()` function
- [x] 2.4 Add configuration options (fallback enable/disable, thresholds)

### 3. Trafilatura Integration

- [x] 3.1 Configure Trafilatura extraction options
  - [x] 3.1.1 `output_format="markdown"`
  - [x] 3.1.2 `include_formatting=True`
  - [x] 3.1.3 `include_links=True`
  - [x] 3.1.4 `include_tables=True`
  - [x] 3.1.5 `favor_precision=True`
  - [x] 3.1.6 `with_metadata=False` (metadata handled separately)
- [x] 3.2 Support both URL fetching (`fetch_url`) and raw HTML (`extract`)
- [ ] 3.3 Add RSS feed URL discovery using `trafilatura.feeds` - *nice-to-have*
- [x] 3.4 Handle extraction failures gracefully

### 4. Crawl4AI Integration (Implemented, Disabled by Default)

- [x] 4.1 Implement async crawler with content filtering
  - [x] 4.1.1 Configure `PruningContentFilter` (threshold=0.45)
  - [x] 4.1.2 Configure `DefaultMarkdownGenerator`
  - [x] 4.1.3 Configure `BrowserConfig` (headless=True)
- [x] 4.2 Use native async (no sync wrapper needed)
- [ ] 4.3 Add cache mode configuration - *Phase 2*
- [x] 4.4 Handle browser launch failures

### 5. Quality Validation

- [x] 5.1 Implement length threshold check (min 200 chars)
- [x] 5.2 Implement structure checks
  - [x] 5.2.1 Heading detection (`#` present)
  - [x] 5.2.2 Paragraph detection (`\n\n` present)
  - [x] 5.2.3 Link detection (`](` present)
- [x] 5.3 Implement code block integrity check (balanced ```)
- [x] 5.4 Return structured validation result

### 7. Gmail Pipeline Integration (Partial)

- [x] 7.1 Update `html_to_markdown()` function in gmail.py to use `HtmlMarkdownConverter`
- [ ] 7.2 Update `GmailContentIngestionService` to use converter directly - *Phase 2*
- [x] 7.3 Preserve plain text emails without conversion (existing behavior)
- [ ] 7.4 Store converted markdown in Content.markdown_content - *Phase 2*
- [ ] 7.5 Add logging for conversion stats - *Phase 2*

### 8. Async Batch Processing

- [x] 8.1 Implement `batch_convert()` async method
- [x] 8.2 Use `asyncio.Semaphore` for concurrency limiting
- [x] 8.3 Use `asyncio.gather()` for parallel execution
- [x] 8.4 Handle individual failures without stopping batch
- [x] 8.5 Return structured results with success/error per item

### 9. Testing (Unit Tests Complete)

- [ ] 9.1 Create HTML fixtures for testing - *Phase 2*
  - [ ] 9.1.1 Simple content HTML (RSS article)
  - [ ] 9.1.2 Complex HTML with tables and code
  - [ ] 9.1.3 Gmail HTML email format
  - [ ] 9.1.4 JS-heavy page URL (for Crawl4AI testing)
- [x] 9.2 Unit tests for `HtmlMarkdownConverter` (6 tests)
- [x] 9.3 Unit tests for `validate_markdown_quality` (6 tests)
- [ ] 9.4 Integration tests with real RSS feed URLs - *Phase 2*
- [ ] 9.5 Integration tests with sample Gmail HTML - *Phase 2*
- [ ] 9.6 Test fallback triggering behavior - *Phase 2*
- [x] 9.7 Test async batch processing (3 tests)

### 11. Documentation

- [x] 11.1 Update CLAUDE.md with new module guidance
- [x] 11.2 Add docstrings to all public functions
- [x] 11.3 Add usage examples to module docstring
- [ ] 11.4 Update ARCHITECTURE.md if needed - *Phase 2*

---

## Phase 2: Full Pipeline Integration (TODO)

### 6. RSS Pipeline Integration

- [ ] 6.1 Update `RSSContentIngestionService` to use `HtmlMarkdownConverter`
- [ ] 6.2 Call converter with `url=article_url` for each feed item
- [ ] 6.3 Store converted markdown in Content.markdown_content
- [ ] 6.4 Add logging for extraction method used and quality stats
- [ ] 6.5 Add metrics for extraction success/fallback rates

### 7. Gmail Pipeline Integration (Complete)

- [ ] 7.2 Update `GmailContentIngestionService` to use converter directly
- [ ] 7.4 Store converted markdown in Content.markdown_content
- [ ] 7.5 Add logging for conversion stats

### 9. Testing (Integration)

- [ ] 9.1 Create HTML fixtures for testing
- [ ] 9.4 Integration tests with real RSS feed URLs
- [ ] 9.5 Integration tests with sample Gmail HTML
- [ ] 9.6 Test fallback triggering behavior

---

## Phase 3: Crawl4AI & Docker (Optional)

### 1. Dependencies

- [ ] 1.3 Add `crawl4ai>=0.7.0` to pyproject.toml
- [ ] 1.4 Run `crawl4ai-setup` to install browser dependencies
- [ ] 1.5 Verify installation with `crawl4ai-doctor`

### 4. Crawl4AI Activation

- [ ] 4.3 Add cache mode configuration

### 10. Docker Setup

- [ ] 10.1 Add Crawl4AI service to docker-compose.yml
- [ ] 10.2 Configure Docker client usage
- [ ] 10.3 Add health check for Crawl4AI service
- [ ] 10.4 Document Docker deployment option

### 11. Documentation

- [ ] 11.4 Update ARCHITECTURE.md with full system design
