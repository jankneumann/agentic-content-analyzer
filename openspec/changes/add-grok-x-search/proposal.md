# Change: Add Grok API X News Search Ingestion

## Why

X (Twitter) is a primary source for real-time AI news, announcements, and discussions from researchers, companies, and thought leaders. Our current content sources (Gmail newsletters, RSS feeds, YouTube) miss this valuable signal. The xAI Grok API provides an `x_search` tool that enables AI-powered search of X posts with semantic understanding, making it ideal for discovering AI-relevant content without manual curation.

## What Changes

- **New Content Source**: Add `XPOST` (or `X_POST`) to the `ContentSource` enum for X/Twitter posts
- **Grok API Client**: Create `GrokXClient` using the official `xai-sdk` Python package with `x_search` tool calling
- **Ingestion Service**: Create `GrokXContentIngestionService` following the Client-Service pattern
- **Configurable Search**: Support custom prompts for AI news discovery (e.g., "Find AI research announcements, model releases, and technical insights")
- **Structured Output**: Store X posts as Content records with:
  - `markdown_content`: Formatted post content with author, timestamp, engagement metrics
  - `metadata_json`: Post metadata (likes, retweets, author info, media URLs)
  - `raw_content`: Original API response for re-processing
- **Summary Integration**: X posts flow through existing summarization pipeline for inclusion in digests

## Impact

- **Affected code**:
  - `src/models/content.py`: Add `ContentSource.XPOST` enum value
  - `src/ingestion/`: New `xsearch.py` module with client and service
  - `src/config/settings.py`: Add `XAI_API_KEY` and search configuration
  - `alembic/`: Migration to add new enum value to database
- **New dependencies**: `xai-sdk>=1.3.1`
- **Cost**: xAI charges $5 per 1000 successful tool calls for x_search
- **No breaking changes**: Additive feature, existing functionality unchanged
