# Change: Add Two-Tier HTML to Markdown Conversion for Web Content

## Why

When ingesting HTML content from web sources (RSS feeds, Gmail), formatting is lost during conversion to markdown. This degrades the quality of downstream LLM processing (summarization, theme analysis) because:
- Document structure (headings, lists, tables) is flattened or lost
- Code blocks lack language hints for proper rendering
- Links and references may be stripped or malformed
- Semantic formatting (bold, italic, blockquotes) disappears

The current pipeline processes ~100 content items weekly from multiple sources. A robust, self-hosted HTML-to-markdown solution will significantly improve extraction quality for LLM consumption.

## What Changes

### Two-Tier Conversion Architecture
- **Primary (Trafilatura)**: Lightweight, pure Python library for fast extraction (~50ms/page)
  - Academic-quality extraction with built-in RSS/ATOM feed discovery
  - Handles most web content without external services
  - No JavaScript rendering (limitation)

- **Fallback (Crawl4AI)**: Full-featured headless browser extraction (~2-5s/page)
  - JavaScript rendering via headless Chromium
  - "Fit Markdown" automatically removes boilerplate
  - Docker-ready for self-hosted deployment
  - Used when Trafilatura output is too short or likely incomplete

### Quality Validation
- Automatic length threshold checking (min 200 chars)
- Structure validation (headings, paragraphs, links)
- Code block integrity verification
- Fallback triggering when primary extraction fails quality checks

### Integration Points
- New `HtmlMarkdownConverter` class in ingestion pipeline
- **RSS ingestion**: Process feed article URLs through converter
- **Gmail ingestion**: Convert HTML email bodies to clean markdown
- Native async implementation leveraging existing pipeline async patterns
- Configurable fallback behavior (enable/disable Crawl4AI)
- Batch processing support with async concurrent execution

## Impact

- **Affected specs**: Creates new `web-content-extraction` capability
- **Affected code**:
  - `src/ingestion/substack.py` - RSS feed processing (RSSContentIngestionService)
  - `src/ingestion/gmail.py` - Gmail HTML extraction (GmailContentIngestionService)
  - New module: `src/parsers/html_markdown.py`
- **Dependencies added**:
  - `trafilatura>=2.0.0` - Primary extraction
  - `crawl4ai>=0.7.0` - Fallback extraction (optional)
- **Breaking changes**: None - additive feature
- **Performance**: Trafilatura adds ~50ms per article; Crawl4AI fallback adds 2-5s when triggered
