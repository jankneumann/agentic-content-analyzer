# Tasks: Add Crawl4AI Integration

## 1. Dependencies & Setup

- [ ] 1.1 Add `crawl4ai>=0.7.0` to pyproject.toml as optional dependency
  ```toml
  [project.optional-dependencies]
  crawl4ai = ["crawl4ai>=0.7.0"]
  ```
- [ ] 1.2 Document `pip install -e ".[crawl4ai]"` installation
- [ ] 1.3 Document `crawl4ai-setup` command for browser dependencies
- [ ] 1.4 Add verification step using `crawl4ai-doctor`

## 2. Configuration

- [ ] 2.1 Add `crawl4ai_enabled: bool = False` to Settings class
- [ ] 2.2 Add `crawl4ai_cache_mode: str = "bypass"` setting
  - Options: "bypass", "read_only", "write_only", "enabled"
- [ ] 2.3 Add `crawl4ai_cache_dir: str = "data/crawl4ai_cache"` setting
- [ ] 2.4 Update `HtmlMarkdownConverter` to read settings
- [ ] 2.5 Update `CRAWL4AI_AVAILABLE` check to include settings flag

## 3. Docker Deployment

- [ ] 3.1 Add Crawl4AI service to docker-compose.yml
  ```yaml
  crawl4ai:
    image: unclecode/crawl4ai:latest
    ports:
      - "11235:11235"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11235/health"]
      interval: 30s
      timeout: 10s
      retries: 3
  ```
- [ ] 3.2 Add `CRAWL4AI_SERVER_URL` setting for Docker mode
- [ ] 3.3 Update converter to support remote Crawl4AI server
- [ ] 3.4 Add health check endpoint integration
- [ ] 3.5 Document Docker deployment in README or docs

## 4. Converter Updates

- [ ] 4.1 Update `_convert_with_crawl4ai()` to use cache settings
- [ ] 4.2 Add support for remote Crawl4AI server (Docker mode)
- [ ] 4.3 Add timeout configuration for browser operations
- [ ] 4.4 Improve error handling for browser launch failures

## 5. Testing

- [ ] 5.1 Add integration test with JS-heavy page URL
- [ ] 5.2 Add test for fallback triggering from Trafilatura to Crawl4AI
- [ ] 5.3 Add test for cache mode behavior
- [ ] 5.4 Add test for Docker/remote server mode
- [ ] 5.5 Mark tests with `@pytest.mark.crawl4ai` for conditional execution

## 6. Documentation

- [ ] 6.1 Update ARCHITECTURE.md with Crawl4AI integration diagram
- [ ] 6.2 Add Crawl4AI setup section to docs/SETUP.md
- [ ] 6.3 Document when Crawl4AI fallback triggers
- [ ] 6.4 Add troubleshooting section for browser issues
- [ ] 6.5 Update CLAUDE.md with new settings
