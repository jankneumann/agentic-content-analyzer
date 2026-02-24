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

The system SHALL include Perplexity search as a parallel ingestion source in daily and weekly pipelines.

#### Scenario: Perplexity included in daily pipeline

- **WHEN** the daily pipeline runs ingestion
- **AND** `PERPLEXITY_API_KEY` is configured
- **THEN** Perplexity search runs concurrently with Gmail, RSS, YouTube, Podcast, Substack, and X search
- **AND** total ingestion time is the slowest source (not sum)

#### Scenario: Perplexity skipped when not configured

- **WHEN** the daily pipeline runs ingestion
- **AND** `PERPLEXITY_API_KEY` is not configured
- **THEN** Perplexity search is silently skipped
- **AND** other sources are unaffected
