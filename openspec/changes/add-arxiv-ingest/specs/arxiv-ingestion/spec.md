# arXiv Ingestion Specification

## Overview

Ingest academic papers from arXiv.org with full PDF text extraction and version-aware updates.

## ADDED Requirements

### Requirement: arXiv API Search

The system SHALL search arXiv via the Atom API (`export.arxiv.org/api/query`) using category filters, keyword queries, combined category + keyword queries, sort options (`relevance`, `lastUpdatedDate`, `submittedDate`), and pagination via `start` and `max_results` parameters.

#### Scenario: Successful category and keyword search

- **WHEN** the system queries arXiv with categories `["cs.AI"]` and search_query `"transformer"`
- **THEN** it constructs the query string `cat:cs.AI+AND+all:transformer`
- **AND** sends a GET request to `export.arxiv.org/api/query`
- **AND** parses the Atom XML response via feedparser
- **AND** returns a list of `ArxivPaper` objects with metadata

#### Scenario: Empty search results

- **WHEN** the system queries arXiv with a search that returns no results
- **THEN** it returns an empty list without error
- **AND** logs an informational message indicating zero results

#### Scenario: API error during search

- **WHEN** the arXiv API returns a 500 error during search
- **THEN** the system retries with exponential backoff (base 5s, max 60s, 3 retries)
- **AND** if all retries fail, raises an error with the HTTP status code and response body

### Requirement: Single Paper Lookup

The system MUST retrieve a single paper by arXiv ID. It SHALL support standard IDs (`2301.12345`, `2301.12345v3`), legacy IDs (`hep-th/9901001`), and normalize input by stripping `arXiv:` prefix, URL components, and version suffix.

**SSRF prevention**: The client MUST construct all API and PDF URLs from the normalized ID using hardcoded base URLs (`export.arxiv.org`, `arxiv.org/pdf/`). User-provided URLs MUST only be used for ID extraction via `normalize_arxiv_id()`, never passed to HTTP clients.

#### Scenario: Lookup by standard arXiv ID

- **WHEN** a user runs `aca ingest arxiv-paper 2301.12345`
- **THEN** the system fetches paper metadata via arXiv API `id_list` query
- **AND** downloads and parses the PDF
- **AND** creates a Content record with `ingestion_mode="single"`

#### Scenario: Lookup by arXiv URL

- **WHEN** a user provides `https://arxiv.org/abs/2301.12345v3`
- **THEN** `normalize_arxiv_id()` extracts `2301.12345` as the base ID
- **AND** the system constructs the API URL from the extracted ID (not the user-provided URL)

#### Scenario: Invalid arXiv identifier

- **WHEN** a user provides an identifier that does not match any known arXiv ID format
- **THEN** the system raises a validation error with a descriptive message
- **AND** does not make any HTTP requests

### Requirement: PDF Download and Extraction

When `pdf_extraction` is enabled for a source, the system SHALL download the PDF from `https://arxiv.org/pdf/{id}` via streaming HTTP, enforce a max file size (default 50 MB) during streaming, check page count via a lightweight PDF reader BEFORE running full Docling parsing, and parse the PDF to markdown via DoclingParser. On parse failure, the system SHALL fall back to abstract-only content. Temporary PDF files MUST be cleaned up after parsing.

#### Scenario: Successful PDF extraction

- **WHEN** a paper has a 15-page PDF under the size limit
- **THEN** the system downloads the PDF via streaming to a temp file
- **AND** checks page count (15 <= 80 default limit)
- **AND** runs DoclingParser to produce markdown
- **AND** stores the markdown as `markdown_content`
- **AND** sets `parser_used="DoclingParser"` and `metadata_json.pdf_extracted=true`
- **AND** deletes the temp file after parsing

#### Scenario: Large PDF skipped

- **GIVEN** `sources.d/arxiv.yaml` has `max_pdf_pages=80`
- **WHEN** a paper has a 120-page PDF
- **THEN** the system skips PDF extraction for that paper
- **AND** falls back to abstract-only content
- **AND** logs `"Skipped PDF for 2301.12345: 120 pages exceeds limit of 80"`

#### Scenario: PDF exceeds size limit during download

- **WHEN** a PDF download exceeds 50 MB during streaming
- **THEN** the system aborts the download
- **AND** cleans up the partial temp file
- **AND** falls back to abstract-only content

#### Scenario: PDF extraction failure fallback

- **GIVEN** an arXiv paper `2301.99999` has a PDF that DoclingParser cannot parse
- **WHEN** the system attempts PDF extraction
- **THEN** it falls back to abstract-only markdown
- **AND** sets `metadata_json.pdf_extracted=false`
- **AND** sets `parser_used="ArxivAbstractParser"`
- **AND** the Content record is still created successfully

### Requirement: Abstract-Only Fallback

When PDF extraction is disabled or fails, the system SHALL generate structured markdown from Atom metadata including title, authors, abstract, categories, and arXiv link. It SHALL set `parser_used` to `"ArxivAbstractParser"` and `metadata_json.pdf_extracted` to `false`.

#### Scenario: PDF extraction disabled in source config

- **GIVEN** `sources.d/arxiv.yaml` has `pdf_extraction: false` for a source
- **WHEN** the system ingests papers from that source
- **THEN** it creates Content records with abstract-only markdown
- **AND** does not attempt any PDF downloads

#### Scenario: Abstract markdown format

- **WHEN** generating abstract-only content for paper `2301.12345`
- **THEN** the markdown includes the title as h1, authors, published date, categories, arXiv link, and the full abstract text

### Requirement: Version-Aware Updates

The system MUST track and update paper versions using the base arXiv ID (without version suffix) as `source_id` and storing the current version in `metadata_json.arxiv_version`. On re-ingest with a newer version, the system SHALL update content, re-parse PDF, delete existing Summary records, and reset status to PENDING. On same/older version, it SHALL skip (no-op). The original `ingested_at` timestamp MUST be preserved on updates.

#### Scenario: Version update replaces content

- **GIVEN** a Content record exists with `source_type=ARXIV`, `source_id="2301.12345"`, `metadata_json.arxiv_version=1`
- **WHEN** re-ingest discovers version 2 of the same paper
- **THEN** the system downloads the v2 PDF
- **AND** updates `markdown_content` with new PDF text
- **AND** sets `metadata_json.arxiv_version=2`
- **AND** deletes existing Summary records for this Content
- **AND** resets status to PENDING for re-summarization
- **AND** preserves the original `ingested_at` timestamp

#### Scenario: Same version is a no-op

- **GIVEN** a Content record exists with `metadata_json.arxiv_version=2`
- **WHEN** re-ingest encounters version 2 of the same paper
- **THEN** the system skips the paper without modification
- **AND** does not download the PDF

### Requirement: Source Configuration

Source entries in `sources.d/arxiv.yaml` MUST support: `categories` (list of arXiv category codes), `search_query` (optional keyword query), `sort_by` (one of `relevance`, `lastUpdatedDate`, `submittedDate`), `pdf_extraction` (bool, default true), `max_pdf_pages` (int, default 80), and inherited fields from SourceBase (`name`, `tags`, `enabled`, `max_entries`).

#### Scenario: Valid arxiv source configuration

- **GIVEN** `sources.d/arxiv.yaml` contains a source with `categories: ["cs.AI"]` and `search_query: "transformer"`
- **WHEN** the source config is loaded
- **THEN** it creates an `ArxivSource` with the specified fields and default values for unspecified optional fields

#### Scenario: Invalid category code

- **GIVEN** `sources.d/arxiv.yaml` contains a source with `categories: ["invalid.XY"]`
- **WHEN** the source config is loaded
- **THEN** the source is loaded without error (validation is advisory, arXiv API returns empty results for invalid categories)

### Requirement: Rate Limiting

The system SHALL enforce a minimum 3-second delay between arXiv API requests (search, metadata). PDF downloads SHALL use a separate, more permissive rate limiter (1-second delay) since arXiv serves PDFs from CDN with different limits. The system MUST respect `Retry-After` header on 429/503 responses and use exponential backoff on errors (base 5s, max 60s, 3 retries).

#### Scenario: Rate limiting between API requests

- **WHEN** the system sends consecutive arXiv API search requests
- **THEN** it waits at least 3 seconds between each request

#### Scenario: Rate-limited response with Retry-After

- **GIVEN** the system is ingesting papers from arXiv
- **WHEN** it sends a request and receives a 429 response with `Retry-After: 10`
- **THEN** it waits 10 seconds before retrying
- **AND** uses exponential backoff for subsequent failures
- **AND** gives up after 3 retries, logging the failure

### Requirement: Date Handling

All dates parsed from feedparser `published_parsed` and `updated_parsed` fields MUST be converted to timezone-aware datetime with `tzinfo=UTC` before storage.

#### Scenario: Naive feedparser date converted to UTC

- **WHEN** feedparser returns `published_parsed` as a naive time struct
- **THEN** the system converts it to a timezone-aware `datetime` with `tzinfo=datetime.timezone.utc`
- **AND** stores the UTC-aware datetime in the Content record's `published_date` field

### Requirement: Content Model

Each arXiv paper SHALL create a Content record with `source_type = ContentSource.ARXIV`, `source_id` = base arXiv ID, `source_url` = `https://arxiv.org/abs/{id}`, `publication` = `"arXiv [{primary_category}]"`, and `metadata_json` containing: `arxiv_id`, `arxiv_version`, `categories`, `primary_category`, `authors` (list), `abstract`, `doi`, `journal_ref`, `comment`, `updated_date`, `pdf_extracted`, `pdf_pages`, `ingestion_mode`.

#### Scenario: Content record created from arXiv paper

- **WHEN** the system ingests paper `2301.12345` from category `cs.AI`
- **THEN** it creates a Content record with `source_type=ARXIV`
- **AND** `source_id="2301.12345"` (base ID without version)
- **AND** `source_url="https://arxiv.org/abs/2301.12345"`
- **AND** `publication="arXiv [cs.AI]"`
- **AND** `metadata_json` includes all required fields

### Requirement: Cross-Source Deduplication

arXiv full-text is authoritative; Scholar abstracts are a discovery aid. Before creating a new record, the system MUST check for existing content with the same `arxiv_id` in `metadata_json` (GIN-indexed containment query; requires `jsonb` column type). If found as Scholar content, the system SHALL replace the Scholar record's `markdown_content` with full arXiv PDF text, update `parser_used` and `metadata_json.pdf_extracted`, delete stale summaries, and reset status to PENDING. If found as arXiv content, the system SHALL apply the version check. Conversely, when Scholar ingests a paper that already exists as arXiv content, Scholar MUST skip.

#### Scenario: arXiv enriches existing Scholar record

- **GIVEN** a Content record exists with `source_type=SCHOLAR` and `metadata_json.arxiv_id="2301.12345"` containing only an abstract
- **WHEN** `aca ingest arxiv` encounters the same paper
- **THEN** the system detects the existing Scholar record via GIN index query
- **AND** downloads and parses the full PDF
- **AND** replaces the Scholar record's `markdown_content` with full PDF text
- **AND** updates `parser_used` to `"DoclingParser"`
- **AND** sets `metadata_json.pdf_extracted=true`
- **AND** deletes stale Summary records
- **AND** resets status to PENDING for re-summarization

#### Scenario: arXiv enrichment fails PDF extraction

- **GIVEN** a Content record exists with `source_type=SCHOLAR` and `metadata_json.arxiv_id="2301.12345"`
- **WHEN** `aca ingest arxiv` encounters the paper but PDF extraction fails
- **THEN** the system does NOT replace the Scholar record's existing content
- **AND** logs a warning that enrichment was skipped due to PDF failure
- **AND** the Scholar record remains unchanged

#### Scenario: Scholar skips existing arXiv record

- **GIVEN** a Content record exists with `source_type=ARXIV` and `metadata_json.arxiv_id="2301.12345"` with full PDF text
- **WHEN** Scholar ingestion encounters the same paper
- **THEN** Scholar skips creating a duplicate record
- **AND** logs `"Skipped 2301.12345: arXiv full-text record exists"`

### Requirement: CLI Commands

The system SHALL provide:
- `aca ingest arxiv` — run all enabled sources from `sources.d/arxiv.yaml` with options: `--max <n>`, `--days <n>` (client-side date filtering after API fetch), `--force-reprocess`, `--no-pdf`
- `aca ingest arxiv-paper <identifier>` — ingest a single paper with options: `--no-pdf`, `--force-reprocess`, accepting arXiv ID, arXiv URL, or DOI

#### Scenario: Search-based ingestion via CLI

- **GIVEN** `sources.d/arxiv.yaml` has an entry with `categories: ["cs.AI"]` and `search_query: "transformer"`
- **WHEN** `aca ingest arxiv` runs
- **THEN** the system queries arXiv API with `cat:cs.AI AND all:transformer`
- **AND** downloads and parses PDFs for each result
- **AND** creates Content records with `source_type=ARXIV`
- **AND** outputs the count of ingested papers

#### Scenario: CLI with --no-pdf flag

- **WHEN** `aca ingest arxiv --no-pdf` runs
- **THEN** the system ingests papers with abstract-only content
- **AND** does not download any PDFs

#### Scenario: Missing sources.d/arxiv.yaml

- **WHEN** `aca ingest arxiv` runs but `sources.d/arxiv.yaml` does not exist
- **THEN** the system exits with a warning message indicating no arXiv sources are configured

### Requirement: Pipeline Integration

The orchestrator SHALL provide an `ingest_arxiv()` function added to `_run_ingestion()` in the pipeline runner. arXiv ingestion SHALL be gated on presence of `sources.d/arxiv.yaml` and run concurrently with other ingestion sources via `asyncio.gather()`.

#### Scenario: Daily pipeline includes arXiv

- **GIVEN** `sources.d/arxiv.yaml` exists with enabled sources
- **WHEN** `aca pipeline daily` runs the ingestion stage
- **THEN** arXiv ingestion runs concurrently with other sources (RSS, Gmail, etc.)
- **AND** the pipeline continues to summarization even if arXiv ingestion fails

#### Scenario: Pipeline skips arXiv when unconfigured

- **GIVEN** `sources.d/arxiv.yaml` does not exist
- **WHEN** `aca pipeline daily` runs the ingestion stage
- **THEN** arXiv ingestion is skipped without error

### Requirement: Database Migration

The system SHALL create an Alembic migration that:
- Adds `'arxiv'` value to PostgreSQL `contentsource` enum type (ALTER TYPE ADD VALUE is non-transactional — MUST run outside transaction block using `op.execute()` with autocommit or explicit COMMIT/BEGIN)
- ALTERs `contents.metadata_json` column from `json` to `jsonb` type if not already `jsonb` (required for GIN index and `@>` containment queries)
- Creates GIN index on `contents.metadata_json` if not already present (idempotent: `CREATE INDEX IF NOT EXISTS`)
- Checks for Alembic multiple heads and merges if needed

#### Scenario: Migration adds enum value

- **WHEN** the migration runs on a database without the `arxiv` enum value
- **THEN** it adds `'arxiv'` to the `contentsource` enum type
- **AND** the migration runs outside a transaction block

#### Scenario: Migration is idempotent

- **WHEN** the migration runs on a database that already has the `arxiv` enum value and GIN index
- **THEN** it completes without error (uses `IF NOT EXISTS` guards)
