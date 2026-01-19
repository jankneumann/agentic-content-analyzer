# Tasks: HTML to Markdown Conversion

## 1. Dependencies & Setup

- [ ] 1.1 Add `trafilatura>=2.0.0` to requirements.txt
- [ ] 1.2 Add `trafilatura[all]` for full features (language detection)
- [ ] 1.3 Add `crawl4ai>=0.7.0` to requirements.txt (optional dependency)
- [ ] 1.4 Run `crawl4ai-setup` to install browser dependencies
- [ ] 1.5 Verify installation with `crawl4ai-doctor`

## 2. Core Implementation

- [ ] 2.1 Create `src/parsers/html_markdown.py` module
- [ ] 2.2 Implement `HtmlMarkdownConverter` class (async-native)
  - [ ] 2.2.1 `_convert_with_trafilatura()` method (sync, wrapped with to_thread)
  - [ ] 2.2.2 `_convert_with_crawl4ai()` async method
  - [ ] 2.2.3 `convert()` async method with automatic fallback
  - [ ] 2.2.4 Support dual input: `url` parameter OR `html` parameter
- [ ] 2.3 Implement `validate_markdown_quality()` function
- [ ] 2.4 Add configuration options (fallback enable/disable, thresholds)

## 3. Trafilatura Integration

- [ ] 3.1 Configure Trafilatura extraction options
  - [ ] 3.1.1 `output_format="markdown"`
  - [ ] 3.1.2 `include_formatting=True`
  - [ ] 3.1.3 `include_links=True`
  - [ ] 3.1.4 `include_tables=True`
  - [ ] 3.1.5 `favor_precision=True`
  - [ ] 3.1.6 `with_metadata=True`
- [ ] 3.2 Support both URL fetching (`fetch_url`) and raw HTML (`extract`)
- [ ] 3.3 Add RSS feed URL discovery using `trafilatura.feeds`
- [ ] 3.4 Handle extraction failures gracefully

## 4. Crawl4AI Integration

- [ ] 4.1 Implement async crawler with content filtering
  - [ ] 4.1.1 Configure `PruningContentFilter` (threshold=0.45)
  - [ ] 4.1.2 Configure `DefaultMarkdownGenerator`
  - [ ] 4.1.3 Configure `BrowserConfig` (headless=True)
- [ ] 4.2 Use native async (no sync wrapper needed)
- [ ] 4.3 Add cache mode configuration
- [ ] 4.4 Handle browser launch failures

## 5. Quality Validation

- [ ] 5.1 Implement length threshold check (min 200 chars)
- [ ] 5.2 Implement structure checks
  - [ ] 5.2.1 Heading detection (`#` present)
  - [ ] 5.2.2 Paragraph detection (`\n\n` present)
  - [ ] 5.2.3 Link detection (`](` present)
- [ ] 5.3 Implement code block integrity check (balanced ```)
- [ ] 5.4 Return structured validation result

## 6. RSS Pipeline Integration

- [ ] 6.1 Update `RSSContentIngestionService` to use `HtmlMarkdownConverter`
- [ ] 6.2 Call converter with `url=article_url` for each feed item
- [ ] 6.3 Store converted markdown in Content.markdown_content
- [ ] 6.4 Add logging for extraction method used and quality stats
- [ ] 6.5 Add metrics for extraction success/fallback rates

## 7. Gmail Pipeline Integration

- [ ] 7.1 Update `GmailContentIngestionService` to use `HtmlMarkdownConverter`
- [ ] 7.2 Call converter with `html=email_body` for HTML emails
- [ ] 7.3 Preserve plain text emails without conversion
- [ ] 7.4 Store converted markdown in Content.markdown_content
- [ ] 7.5 Add logging for conversion stats

## 8. Async Batch Processing

- [ ] 8.1 Implement `batch_convert()` async method
- [ ] 8.2 Use `asyncio.Semaphore` for concurrency limiting
- [ ] 8.3 Use `asyncio.gather()` for parallel execution
- [ ] 8.4 Handle individual failures without stopping batch
- [ ] 8.5 Return structured results with success/error per item

## 9. Testing

- [ ] 9.1 Create HTML fixtures for testing
  - [ ] 9.1.1 Simple content HTML (RSS article)
  - [ ] 9.1.2 Complex HTML with tables and code
  - [ ] 9.1.3 Gmail HTML email format
  - [ ] 9.1.4 JS-heavy page URL (for Crawl4AI testing)
- [ ] 9.2 Unit tests for `HtmlMarkdownConverter`
- [ ] 9.3 Unit tests for `validate_markdown_quality`
- [ ] 9.4 Integration tests with real RSS feed URLs
- [ ] 9.5 Integration tests with sample Gmail HTML
- [ ] 9.6 Test fallback triggering behavior
- [ ] 9.7 Test async batch processing

## 10. Docker Setup (Optional)

- [ ] 10.1 Add Crawl4AI service to docker-compose.yml
- [ ] 10.2 Configure Docker client usage
- [ ] 10.3 Add health check for Crawl4AI service
- [ ] 10.4 Document Docker deployment option

## 11. Documentation

- [ ] 11.1 Update CLAUDE.md with new module guidance
- [ ] 11.2 Add docstrings to all public functions
- [ ] 11.3 Add usage examples to module docstring
- [ ] 11.4 Update ARCHITECTURE.md if needed
