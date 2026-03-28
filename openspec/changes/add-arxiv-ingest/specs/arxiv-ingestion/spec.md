# arXiv Ingestion Specification

## Overview

Ingest academic papers from arXiv.org with full PDF text extraction and version-aware updates.

## Requirements

### REQ-ARXIV-001: arXiv API Search

The system must search arXiv via the Atom API (`export.arxiv.org/api/query`) using:
- Category filters (e.g., `cs.AI`, `cs.CL`, `cs.LG`)
- Keyword queries (arXiv query syntax: `all:`, `ti:`, `abs:`)
- Combined category + keyword queries
- Sort options: `relevance`, `lastUpdatedDate`, `submittedDate`
- Pagination via `start` and `max_results` parameters

### REQ-ARXIV-002: Single Paper Lookup

The system must retrieve a single paper by arXiv ID using:
- Standard IDs: `2301.12345` or `2301.12345v3`
- Legacy IDs: `hep-th/9901001`
- ID normalization: strip `arXiv:` prefix, URL prefix, version suffix

### REQ-ARXIV-003: PDF Download and Extraction

When `pdf_extraction` is enabled for a source:
- Download PDF from `https://arxiv.org/pdf/{id}` via streaming HTTP
- Enforce max file size (default 50 MB) and max page count (default 80 pages)
- Parse PDF to markdown via DoclingParser
- On parse failure, fall back to abstract-only content with metadata header
- Clean up temporary PDF files after parsing

### REQ-ARXIV-004: Abstract-Only Fallback

When PDF extraction is disabled or fails:
- Generate structured markdown from Atom metadata
- Include: title, authors, abstract, categories, arXiv link
- Mark `parser_used` as `"ArxivAbstractParser"` and `metadata_json.pdf_extracted` as `false`

### REQ-ARXIV-005: Version-Aware Updates

The system must track and update paper versions:
- Use base arXiv ID (without version suffix) as `source_id`
- Store current version number in `metadata_json.arxiv_version`
- On re-ingest, compare versions:
  - Newer version: update content, re-parse PDF, reset status to PENDING
  - Same/older version: skip (no-op)
- Preserve original `ingested_at` timestamp on updates

### REQ-ARXIV-006: Source Configuration

Source entries in `sources.d/arxiv.yaml` must support:
- `categories: list[str]` — arXiv category codes
- `search_query: str | None` — keyword query string
- `sort_by: str` — one of `relevance`, `lastUpdatedDate`, `submittedDate`
- `pdf_extraction: bool` — enable/disable PDF download (default: true)
- `max_pdf_pages: int` — skip PDFs exceeding this page count (default: 80)
- Inherited fields from SourceBase: `name`, `tags`, `enabled`, `max_entries`

### REQ-ARXIV-007: Rate Limiting

- Minimum 3-second delay between arXiv API requests
- Respect `Retry-After` header on 429/503 responses
- Exponential backoff on errors: base 5s, max 60s, 3 retries
- PDF downloads share the same rate limiter as API queries

### REQ-ARXIV-008: Content Model

Each arXiv paper creates a Content record with:
- `source_type = ContentSource.ARXIV`
- `source_id` = base arXiv ID (e.g., `2301.12345`)
- `source_url` = `https://arxiv.org/abs/{id}`
- `publication` = `"arXiv [{primary_category}]"`
- `metadata_json` containing: `arxiv_id`, `arxiv_version`, `categories`, `primary_category`, `authors` (list), `abstract`, `doi`, `journal_ref`, `comment`, `updated_date`, `pdf_extracted`, `pdf_pages`, `ingestion_mode`

### REQ-ARXIV-009: Cross-Source Deduplication

- Before creating a new record, check for existing content with the same `arxiv_id` in `metadata_json` (GIN-indexed containment query)
- If an arXiv paper already exists as a Scholar source record, skip ingestion (Scholar record takes precedence for metadata; arXiv can enrich with full text in future)
- If an arXiv paper exists as an arXiv source, apply version check per REQ-ARXIV-005

### REQ-ARXIV-010: CLI Commands

- `aca ingest arxiv` — run all enabled sources from `sources.d/arxiv.yaml`
  - Options: `--max <n>`, `--days <n>`, `--force-reprocess`, `--no-pdf`
- `aca ingest arxiv-paper <identifier>` — ingest a single paper
  - Options: `--no-pdf`, `--force-reprocess`
  - Accepts: arXiv ID, arXiv URL, DOI

### REQ-ARXIV-011: Pipeline Integration

- `ingest_arxiv()` orchestrator function added to `_run_ingestion()` in pipeline runner
- Gated on presence of `sources.d/arxiv.yaml`
- Runs concurrently with other ingestion sources via `asyncio.gather()`

### REQ-ARXIV-012: Database Migration

- Add `'arxiv'` value to PostgreSQL `contentsource` enum type
- Create GIN index on `metadata_json` if not already present (idempotent with Scholar migration)

## Scenarios

### Scenario: Search-based ingestion
```
GIVEN sources.d/arxiv.yaml has an entry with categories ["cs.AI"] and search_query "transformer"
WHEN aca ingest arxiv runs
THEN the system queries arXiv API with cat:cs.AI AND all:transformer
AND downloads and parses PDFs for each result
AND creates Content records with source_type=ARXIV
AND stores full markdown text from PDF extraction
```

### Scenario: Version update
```
GIVEN a Content record exists with source_type=ARXIV, source_id="2301.12345", metadata_json.arxiv_version=1
WHEN re-ingest discovers version 2 of the same paper
THEN the system downloads the v2 PDF
AND updates markdown_content with new PDF text
AND sets metadata_json.arxiv_version=2
AND resets status to PENDING for re-summarization
AND preserves the original ingested_at timestamp
```

### Scenario: PDF extraction failure fallback
```
GIVEN an arXiv paper "2301.99999" has a PDF that DoclingParser cannot parse
WHEN the system attempts PDF extraction
THEN it falls back to abstract-only markdown
AND sets metadata_json.pdf_extracted=false
AND sets parser_used="ArxivAbstractParser"
AND the Content record is still created successfully
```

### Scenario: Cross-source deduplication with Scholar
```
GIVEN a Content record exists with source_type=SCHOLAR and metadata_json.arxiv_id="2301.12345"
WHEN aca ingest arxiv encounters the same paper
THEN the system detects the existing Scholar record via GIN index query
AND skips creating a duplicate arXiv record
AND logs "Skipped 2301.12345: exists as Scholar source"
```

### Scenario: Single paper lookup
```
GIVEN a user runs aca ingest arxiv-paper 2301.12345
THEN the system fetches paper metadata via arXiv API id_list query
AND downloads and parses the PDF
AND creates a Content record with ingestion_mode="single"
```

### Scenario: Rate limiting
```
GIVEN the system is ingesting papers from arXiv
WHEN it sends a request and receives a 429 response with Retry-After: 10
THEN it waits 10 seconds before retrying
AND uses exponential backoff for subsequent failures
AND gives up after 3 retries, logging the failure
```

### Scenario: Large PDF skipped
```
GIVEN sources.d/arxiv.yaml has max_pdf_pages=80
WHEN a paper has a 120-page PDF
THEN the system skips PDF extraction for that paper
AND falls back to abstract-only content
AND logs "Skipped PDF for 2301.12345: 120 pages exceeds limit of 80"
```
