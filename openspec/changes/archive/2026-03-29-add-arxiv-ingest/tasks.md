## Dependencies

```
Section 1 (DB migration) ─── no deps, run first
Section 2 (arXiv client) ─── no deps, parallel with 1, 3
Section 3 (source config) ── no deps, parallel with 1, 2
Section 4 (ingestion svc) ── depends on 1, 2, 3
Section 5 (orchestrator)  ── depends on 4
Section 6 (CLI)           ── depends on 5
Section 7 (MCP tools)     ── depends on 5
Section 8 (frontend)      ── no deps, parallel with all
Section 9 (docs)          ── depends on all
```

**Max parallel width: 4** (sections 1, 2, 3, 8 in wave 1; section 4 in wave 2; sections 5 in wave 3; sections 6, 7 in wave 4; section 9 in wave 5)

## 1. Content Model & Database Migration

- [x] 1.1 Add `ARXIV = "arxiv"` to `ContentSource` enum in `src/models/content.py`
- [x] 1.2 Create Alembic migration: ALTER TYPE `contentsource` ADD VALUE IF NOT EXISTS `'arxiv'` — **non-transactional** (must run outside transaction block per PG constraint; use `op.execute()` with autocommit or explicit COMMIT/BEGIN)
- [x] 1.3 In the same migration, ALTER `contents.metadata_json` from `json` to `jsonb` if not already `jsonb`: `ALTER TABLE contents ALTER COLUMN metadata_json TYPE jsonb USING metadata_json::jsonb`
- [x] 1.4 Add GIN index: `CREATE INDEX IF NOT EXISTS ix_content_metadata_json_gin ON contents USING GIN (metadata_json jsonb_path_ops)` — check for Alembic multiple heads and merge if needed
- [x] 1.5 Run migration and verify enum, column type, and index are available in database

## 2. arXiv Client (parallel with 1, 3)

- [x] 2.1 Create `src/ingestion/arxiv_client.py` with `ArxivClient` class using `httpx.Client` (synchronous, matching existing ingestion client pattern)
- [x] 2.2 Implement `search_papers(query, categories, sort_by, max_results, start)` — builds arXiv query string, calls `export.arxiv.org/api/query`, parses Atom XML response via `feedparser`
- [x] 2.3 Implement `get_paper(arxiv_id)` — single paper lookup via `id_list` parameter
- [x] 2.4 Implement `download_pdf(arxiv_id, dest_path)` — streaming PDF download to temp file with size limit enforcement (default 50 MB)
- [x] 2.5 Implement `normalize_arxiv_id(identifier)` — strips `arXiv:` prefix, URL components, version suffix; validates format; supports legacy IDs. **SSRF prevention**: only extract ID, never pass user URLs to HTTP client
- [x] 2.6 Add rate limiting: `time.sleep(3)` between API requests (sync), separate 1s delay for PDF downloads; respect `Retry-After` header on 429/503, exponential backoff (base 5s, max 60s, 3 retries)
- [x] 2.7 Ensure all feedparser dates are converted to UTC-aware datetime with `tzinfo=UTC` (CLAUDE.md gotcha: feedparser dates are naive)
- [x] 2.8 Add Pydantic response models: `ArxivPaper` (id, title, abstract, authors, categories, primary_category, published, updated, pdf_url, doi, journal_ref, comment, version)
- [x] 2.9 Write unit tests for client with mocked HTTP responses (search, single paper, PDF download, rate limiting, error handling, DOI normalization)

## 3. Source Configuration (parallel with 1, 2)

- [x] 3.1 Add `ArxivSource` model to `src/config/sources.py` with fields: `categories`, `search_query`, `sort_by`, `pdf_extraction`, `max_pdf_pages`
- [x] 3.2 Add `ArxivSource` to the `Source` discriminated union type
- [x] 3.3 Add `get_arxiv_sources()` method to `SourcesConfig`
- [x] 3.4 Create example `sources.d/arxiv.yaml.example` with sample entries (AI research, LLM papers, AI agents)
- [x] 3.5 Write unit tests for arxiv source loading and validation

## 4. arXiv Content Ingestion Service (depends on 1, 2, 3)

- [x] 4.1 Create `src/ingestion/arxiv.py` with `ArxivContentIngestionService` class
- [x] 4.2 Implement `_extract_pdf_content(arxiv_id, pdf_url, max_pages) -> tuple[str | None, str | None]` — downloads PDF via streaming with 50MB size cap, checks page count via lightweight PDF reader BEFORE full Docling parse, returns `(markdown, parser_used)`. Falls back to `(None, None)` on failure.
- [x] 4.3 Implement `_format_abstract_markdown(paper: ArxivPaper) -> str` — generates structured markdown from metadata when PDF extraction is disabled or fails
- [x] 4.4 Implement `_build_metadata(paper: ArxivPaper, ingestion_mode: str, pdf_extracted: bool, pdf_pages: int | None) -> dict` for metadata_json
- [x] 4.5 Implement `_paper_to_content_data(paper: ArxivPaper, markdown: str, parser_used: str, metadata: dict) -> ContentData` mapper
- [x] 4.6 Implement `_check_version_update(arxiv_id: str, incoming_version: int, db) -> Content | None` — returns existing record if version is older; None if no update needed. On update, delete stale Summary records and reset status to PENDING.
- [x] 4.7 Implement `_check_cross_source_duplicate(arxiv_id: str, db) -> Content | None` — GIN-indexed `metadata_json @> '{"arxiv_id": "..."}'::jsonb` containment query. If Scholar record found, **enrich** it with arXiv full text (replace markdown_content, update parser_used, delete stale summaries, reset to PENDING). If PDF extraction fails, do NOT replace the Scholar record — log warning and leave unchanged. If arXiv record found, apply version check.
- [x] 4.8 Implement `ingest_from_search(source_config: ArxivSource, force_reprocess: bool) -> ArxivIngestionResult` — main search-based ingestion with PDF extraction
- [x] 4.9 Implement `ingest_paper(identifier: str, pdf_extraction: bool, force_reprocess: bool) -> ArxivPaperResult` — single paper lookup and ingest
- [x] 4.10 Implement `ingest_content(sources: list[ArxivSource] | None, after_date, force_reprocess) -> IngestionResult` — loads config, iterates sources, delegates to `ingest_from_search`
- [x] 4.11 Create `ArxivIngestionResult` and `ArxivPaperResult` result dataclasses
- [x] 4.12 Write unit tests for ingestion service with mocked client and database

## 5. Orchestrator & Pipeline Integration (depends on 4)

- [x] 5.1 Add `ingest_arxiv(categories, max_results, after_date, force_reprocess, no_pdf) -> int` function to `src/ingestion/orchestrator.py` (lazy-loaded service)
- [x] 5.2 Add `ingest_arxiv_paper(identifier, pdf_extraction, force_reprocess) -> ArxivPaperResult` function to orchestrator
- [x] 5.3 Add arxiv ingestion to `_run_ingestion()` in `src/pipeline/runner.py` — load from `sources.d/arxiv.yaml`, run concurrently via `asyncio.gather()`
- [x] 5.4 Gate arxiv pipeline on presence of `sources.d/arxiv.yaml` (no API key required)

## 6. CLI Commands (depends on 5)

- [x] 6.1 Add `aca ingest arxiv` command to `src/cli/ingest_commands.py` — loads `sources.d/arxiv.yaml` and runs all enabled sources
  - Options: `--max/-m`, `--days/-d`, `--force-reprocess`, `--no-pdf`
- [x] 6.2 Add `aca ingest arxiv-paper <identifier>` command
  - Options: `--no-pdf`, `--force-reprocess`
  - Accepts: arXiv ID, arXiv URL, DOI
- [x] 6.3 Write CLI integration tests

## 7. MCP Tools (depends on 5)

- [x] 7.1 Add `ingest_arxiv(max, days, force_reprocess, no_pdf)` tool to `src/mcp_server.py` — mirrors `aca ingest arxiv` CLI
- [x] 7.2 Add `ingest_arxiv_paper(identifier, no_pdf, force_reprocess)` tool — mirrors `aca ingest arxiv-paper` CLI
- [x] 7.3 Write MCP tool tests

## 8. Frontend Source Type Registration (no deps, parallel with all)

- [x] 8.1 Add `arxiv` entry to `sourceConfig` in `web/src/routes/contents.tsx` with label "arXiv" and `FileText` icon from lucide-react
- [x] 8.2 Add matching `arxiv` entry to `web/src/routes/ingest.tsx` source configuration

## 9. Documentation (depends on all)

- [x] 9.1 Update CLAUDE.md with arxiv ingestion commands, MCP tools, and configuration
- [x] 9.2 Add arxiv source examples to sources.d documentation
- [x] 9.3 Document version-aware update behavior and cross-source deduplication
