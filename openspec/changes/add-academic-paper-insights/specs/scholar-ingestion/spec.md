# Scholar Ingestion

## ADDED Requirements

### Requirement: Scholar Paper Search via Semantic Scholar

The system SHALL support discovery and ingestion of academic papers using the Semantic Scholar Academic Graph API.

#### Scenario: Successful keyword search and ingestion

- **WHEN** the user runs scholar paper ingestion with a search query
- **THEN** the system queries the Semantic Scholar `/paper/search` endpoint with the provided query
- **AND** requests fields: paperId, externalIds, title, abstract, year, venue, citationCount, influentialCitationCount, fieldsOfStudy, authors, publicationTypes, openAccessPdf, tldr
- **AND** for each result, creates one Content record with `source_type=scholar`
- **AND** uses the Semantic Scholar paper ID as `source_id`
- **AND** formats the paper as structured markdown (title, authors, venue, abstract, TL;DR, references, links)
- **AND** stores academic metadata in `metadata_json` (s2_paper_id, arxiv_id, doi, authors, venue, year, citation_count, fields_of_study, publication_types)
- **AND** returns the count of newly ingested papers

#### Scenario: Single paper lookup by identifier

- **WHEN** the user provides a paper identifier (DOI, arXiv ID, Semantic Scholar ID, or Semantic Scholar URL)
- **THEN** the system resolves the identifier to a Semantic Scholar paper ID
- **AND** fetches complete paper details including references and citations
- **AND** creates one Content record with the full paper information
- **AND** optionally ingests the paper's top references (controlled by `--with-refs` flag)

#### Scenario: Filtering by citation count

- **WHEN** the source configuration specifies `min_citation_count`
- **THEN** the system skips papers with fewer citations than the threshold
- **AND** logs a debug message for each skipped low-citation paper
- **AND** does not count skipped papers in the ingestion count

#### Scenario: Filtering by publication type

- **WHEN** the source configuration specifies `paper_types` (e.g., ["Review"])
- **THEN** the system only ingests papers whose `publicationTypes` intersect the configured types
- **AND** this enables focusing on survey/review papers as exploration seeds

#### Scenario: Filtering by field of study

- **WHEN** the source configuration specifies `fields_of_study` (e.g., ["Computer Science"])
- **THEN** the system only ingests papers whose `fieldsOfStudy` intersect the configured fields

#### Scenario: Filtering by year range

- **WHEN** the source configuration specifies `year_range` (e.g., "2024-" or "2023-2024")
- **THEN** the system passes the year filter to the Semantic Scholar API
- **AND** only returns papers published within the specified range

### Requirement: Scholar Paper Deduplication

The system SHALL prevent duplicate ingestion of academic papers across all source types.

#### Scenario: Duplicate detection by Semantic Scholar ID

- **WHEN** ingesting a paper whose Semantic Scholar paper ID already exists as `source_id` with `source_type=scholar`
- **THEN** the system skips the duplicate without creating a new record
- **AND** logs a debug message indicating the duplicate was skipped

#### Scenario: Cross-source deduplication by DOI

- **WHEN** ingesting a paper whose DOI matches a DOI stored in `metadata_json` of any existing Content record (regardless of source_type)
- **THEN** the system recognizes this as a cross-source duplicate
- **AND** links the new record to the existing one via `canonical_id` if desired, or skips ingestion

#### Scenario: Cross-source deduplication by arXiv ID

- **WHEN** ingesting a paper whose arXiv ID matches an arXiv URL or ID in existing Content records
- **THEN** the system recognizes this as a cross-source duplicate
- **AND** behaves identically to DOI-based cross-source deduplication

### Requirement: Citation Graph Traversal

The system SHALL support exploring a paper's citation graph to discover related work.

#### Scenario: Fetching a paper's references

- **WHEN** the user requests references for a specific paper (via `--with-refs` or explicit command)
- **THEN** the system fetches the paper's references via `/paper/{id}/references`
- **AND** applies the same filtering (citation count, field, type) as search-based ingestion
- **AND** ingests qualifying references as new Content records
- **AND** stores the relationship in metadata_json (`ingestion_mode: "citation_traversal"`, `parent_paper_id`)

#### Scenario: Fetching a paper's citations (papers that cite it)

- **WHEN** the user requests citations for a specific paper
- **THEN** the system fetches citing papers via `/paper/{id}/citations`
- **AND** applies the same filtering and deduplication as search-based ingestion

### Requirement: Reference Extraction from Existing Content

The system SHALL support extracting academic paper references from previously ingested content and queuing them for ingestion.

#### Scenario: Extracting arXiv references from content

- **WHEN** the user runs reference extraction (`aca ingest scholar-refs`)
- **THEN** the system scans `markdown_content` of recent Content records
- **AND** extracts arXiv identifiers matching patterns `arXiv:YYMM.NNNNN` and `arxiv.org/abs/YYMM.NNNNN`
- **AND** batch-resolves them via Semantic Scholar `/paper/batch` endpoint
- **AND** ingests papers not already present in the database
- **AND** tags ingested papers with `ingestion_mode: "reference_extraction"` in metadata_json

#### Scenario: Extracting DOI references from content

- **WHEN** the user runs reference extraction
- **THEN** the system also extracts DOI patterns (`doi.org/10.xxx`, `DOI: 10.xxx`)
- **AND** resolves and ingests them using the same batch workflow

#### Scenario: Filtering reference extraction by date range

- **WHEN** the user specifies `--after` and/or `--before` flags
- **THEN** the system only scans Content records within the specified date range
- **AND** this allows incremental extraction from newly ingested content

### Requirement: Scholar Source Configuration

The system SHALL support YAML-based configuration for recurring scholar paper searches.

#### Scenario: Loading scholar sources from sources.d

- **WHEN** the application loads source configuration
- **THEN** the system reads `sources.d/scholar.yaml`
- **AND** each entry defines: name, query, tags, enabled, max_entries, fields_of_study, paper_types, min_citation_count, year_range, venues

#### Scenario: Scholar sources in daily pipeline

- **WHEN** the daily pipeline runs (`aca pipeline daily`)
- **THEN** scholar sources from `sources.d/scholar.yaml` are included in the ingestion stage
- **AND** they run concurrently with other source types via `asyncio.gather()`

### Requirement: Scholar CLI Commands

The system SHALL provide CLI commands for scholar paper ingestion.

#### Scenario: Search-based ingestion

- **WHEN** the user runs `aca ingest scholar`
- **THEN** the system loads sources from `sources.d/scholar.yaml`
- **AND** executes each enabled source's search query
- **AND** reports per-source ingestion counts

#### Scenario: Single paper ingestion

- **WHEN** the user runs `aca ingest scholar-paper <identifier>`
- **THEN** the system resolves the identifier (DOI, arXiv ID, S2 ID, or URL)
- **AND** ingests the paper with full details
- **AND** optionally ingests references with `--with-refs` flag

#### Scenario: Reference extraction from existing content

- **WHEN** the user runs `aca ingest scholar-refs`
- **THEN** the system scans existing content for paper references
- **AND** batch-resolves and ingests discovered papers
- **AND** supports `--after`, `--before`, `--source`, and `--dry-run` flags

### Requirement: Scholar Web Search Provider

The system SHALL provide a scholar search provider for ad-hoc queries in chat and digest review contexts.

#### Scenario: Ad-hoc scholar search

- **WHEN** a component requests web search with `provider="scholar"`
- **THEN** the system queries Semantic Scholar for matching papers
- **AND** returns results as `WebSearchResult` objects with paper title, S2 URL, and abstract snippet

### Requirement: Semantic Scholar API Rate Limiting

The system SHALL respect Semantic Scholar API rate limits.

#### Scenario: Unauthenticated rate limiting

- **WHEN** no `SEMANTIC_SCHOLAR_API_KEY` is configured
- **THEN** the system limits requests to stay within the ~100 requests per 5 minutes shared pool
- **AND** implements exponential backoff on 429 responses

#### Scenario: Authenticated rate limiting

- **WHEN** `SEMANTIC_SCHOLAR_API_KEY` is configured
- **THEN** the system sends the key via `x-api-key` header
- **AND** respects 1 RPS for search/batch endpoints and 10 RPS for other endpoints
- **AND** implements exponential backoff on 429 responses
