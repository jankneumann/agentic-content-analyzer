## ADDED Requirements

### Requirement: Blog stages emit classified correlated evidence

Each configured source and discovered article SHALL emit correlated outcomes for discovery, fetch, extraction, filtering, deduplication, parsing, and persistence stages. Batch continuation SHALL preserve detailed exception evidence in Langfuse and bounded stage/error codes in PostgreSQL.

#### Scenario: [BLOG-001] Extraction fallback succeeds

- **WHEN** the preferred extractor fails and an allowed fallback succeeds
- **THEN** the article outcome records the failed stage and fallback decision
- **AND** the final item outcome is succeeded or partial according to content-quality policy

#### Scenario: [BLOG-002] Persistence fails after extraction

- **WHEN** an article is fetched and extracted but persistence fails
- **THEN** the item and source failed counts include it
- **AND** the active persistence span captures the exception
- **AND** PostgreSQL stores only the bounded persistence diagnostic and correlation IDs

#### Scenario: [BLOG-003] Source discovery fails

- **WHEN** index discovery fails for one configured blog source
- **THEN** that source outcome is retryable or permanent failure
- **AND** other configured sources continue independently
