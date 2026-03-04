# Content Ingestion: Perplexity Search

## MODIFIED Requirements

### Requirement: Content Source Types

The system SHALL recognize `perplexity` as a valid content source type for web content discovered via Perplexity Sonar API search.

#### Scenario: Perplexity content stored with correct source type

- **WHEN** content is ingested via Perplexity search
- **THEN** the Content record has `source_type = "perplexity"`
- **AND** the `content_source` PostgreSQL enum includes the `perplexity` value
- **AND** the content appears in search results when filtering by `source_type=perplexity`

### Requirement: Pipeline Ingestion Sources

The system SHALL include web search sources (Perplexity, Grok) in daily and weekly pipelines via `sources.d/websearch.yaml` configuration.

#### Scenario: Web search sources included in daily pipeline

- **WHEN** the daily pipeline runs ingestion
- **AND** `sources.d/websearch.yaml` contains enabled entries with configured provider API keys
- **THEN** each websearch source runs concurrently with Gmail, RSS, YouTube, Podcast, and Substack ingestion
- **AND** total ingestion time is bounded by the slowest source (not sum)

#### Scenario: Web search sources skipped when not configured

- **WHEN** the daily pipeline runs ingestion
- **AND** `sources.d/websearch.yaml` does not exist, has no enabled entries, or no provider API keys are configured
- **THEN** web search ingestion is silently skipped
- **AND** other sources are unaffected
