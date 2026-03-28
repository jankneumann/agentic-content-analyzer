## 1. Content Model & Database Migration

- [ ] 1.1 Add `SCHOLAR = "scholar"` to `ContentSource` enum in `src/models/content.py`
- [ ] 1.2 Create Alembic migration to add `scholar` value to PostgreSQL `contentsource` enum type (`ALTER TYPE contentsource ADD VALUE IF NOT EXISTS 'scholar'`)
- [ ] 1.3 In the same migration, add GIN index on `metadata_json` for cross-source dedup: `CREATE INDEX CONCURRENTLY ix_content_metadata_json_gin ON content USING GIN (metadata_json jsonb_path_ops)`
- [ ] 1.4 Run migration and verify enum and index are available in database

## 2. Semantic Scholar Client

- [ ] 2.1 Create `src/ingestion/semantic_scholar_client.py` with `SemanticScholarClient` class
- [ ] 2.2 Implement `search_papers(query, fields_of_study, year_range, paper_types, limit, offset)` using `GET /paper/search`
- [ ] 2.3 Implement `get_paper(paper_id)` using `GET /paper/{paperId}` with full field set
- [ ] 2.4 Implement `get_paper_references(paper_id, limit)` using `GET /paper/{paperId}/references`
- [ ] 2.5 Implement `get_paper_citations(paper_id, limit)` using `GET /paper/{paperId}/citations`
- [ ] 2.6 Implement `batch_get_papers(paper_ids)` using `POST /paper/batch` (up to 500 IDs per request)
- [ ] 2.7 Implement `resolve_identifier(identifier)` to normalize DOI/arXiv/S2ID/URL to a paper ID format the API accepts
- [ ] 2.8 Add proactive rate limiting using `asyncio.Semaphore(1)` with configurable inter-request delay (3s unauth, 1s/0.1s auth) and reactive exponential backoff on 429 responses (base 2s/1s, max 60s/30s, 3 retries)
- [ ] 2.8a Add error handling: 404 → log warning + skip, invalid ID → raise ValueError, 5xx/timeout → retry 3x then skip, batch partial failure → ingest resolved + log unresolved
- [ ] 2.9 Add optional API key support via `x-api-key` header (from `SEMANTIC_SCHOLAR_API_KEY` setting)
- [ ] 2.10 Add Pydantic response models: `S2Paper`, `S2Author`, `S2SearchResult`
- [ ] 2.11 Write unit tests for client with mocked HTTP responses

## 3. Source Configuration

- [ ] 3.1 Add `ScholarSource` model to `src/config/sources.py` with fields: query, fields_of_study, paper_types, min_citation_count, year_range, venues
- [ ] 3.2 Add `ScholarSource` to the `Source` discriminated union type
- [ ] 3.3 Add `get_scholar_sources()` method to `SourcesConfig`
- [ ] 3.4 Create `sources.d/scholar.yaml` with initial source entries (AI surveys, LLM research, AI agents)
- [ ] 3.5 Add `SEMANTIC_SCHOLAR_API_KEY` to Settings in `src/config/settings.py` (optional, default empty)
- [ ] 3.6 Wire `${SEMANTIC_SCHOLAR_API_KEY:-}` in `profiles/base.yaml`
- [ ] 3.7 Write unit tests for scholar source loading and validation

## 4. Scholar Content Ingestion Service

- [ ] 4.1 Create `src/ingestion/scholar.py` with `ScholarContentIngestionService` class
- [ ] 4.2 Implement `_format_paper_markdown(paper: S2Paper) -> str` to generate structured markdown content
- [ ] 4.3 Implement `_build_metadata(paper: S2Paper, ingestion_mode: str) -> dict` for metadata_json
- [ ] 4.4 Implement `_paper_to_content_data(paper: S2Paper, ingestion_mode: str) -> ContentData` mapper
- [ ] 4.5 Implement `_apply_filters(papers, min_citations, paper_types, fields_of_study) -> list` for post-search filtering
- [ ] 4.6 Implement `_check_cross_source_duplicate(paper: S2Paper, db) -> bool` using GIN-indexed `metadata_json @> '{"doi": "..."}'::jsonb` containment queries for DOI and arXiv ID
- [ ] 4.7 Implement `ingest_from_search(query, source_config, force_reprocess) -> ScholarSearchResult` — main search-based ingestion
- [ ] 4.8 Implement `ingest_paper(identifier, with_refs, force_reprocess) -> ScholarPaperResult` — single paper lookup
- [ ] 4.9 Implement `ingest_from_citations(paper_id, direction, source_config) -> ScholarSearchResult` — citation graph traversal
- [ ] 4.10 Create `ScholarSearchResult` and `ScholarPaperResult` result dataclasses
- [ ] 4.11 Write unit tests for ingestion service with mocked client and database

## 5. Reference Extraction

- [ ] 5.1 Create `src/ingestion/reference_extractor.py` with `ReferenceExtractor` class
- [ ] 5.2 Implement arXiv ID regex extraction from markdown content (`arXiv:YYMM.NNNNN`, `arxiv.org/abs/...`)
- [ ] 5.3 Implement DOI regex extraction from markdown content (`doi.org/10.xxx`, `DOI: 10.xxx`)
- [ ] 5.4 Implement Semantic Scholar URL extraction (`semanticscholar.org/paper/...`)
- [ ] 5.5 Implement `extract_references(content_records, after, before, source_types) -> list[str]` returning unique identifiers
- [ ] 5.6 Implement `ingest_extracted_references(identifiers, dry_run) -> ReferenceExtractionResult` using batch API
- [ ] 5.7 Write unit tests for regex patterns and extraction logic

## 6. Orchestrator & Pipeline Integration

- [ ] 6.1 Add `ingest_scholar()` function to `src/ingestion/orchestrator.py` (lazy-loaded service)
- [ ] 6.2 Add `ingest_scholar_paper(identifier, with_refs)` function to orchestrator
- [ ] 6.3 Add `ingest_scholar_refs(after, before, source_types, dry_run)` function to orchestrator
- [ ] 6.4 Add scholar sources to `_run_ingestion()` in `src/pipeline/runner.py` (load from `sources.d/scholar.yaml`, run concurrently)
- [ ] 6.5 Gate scholar pipeline on presence of `sources.d/scholar.yaml` (no API key required for basic access)

## 7. CLI Commands

- [ ] 7.1 Add `aca ingest scholar` command to `src/cli/ingest_commands.py` — loads sources.d/scholar.yaml and runs all enabled sources
- [ ] 7.2 Add `aca ingest scholar-paper <identifier>` command with `--with-refs` flag
- [ ] 7.3 Add `aca ingest scholar-refs` command with `--after`, `--before`, `--source`, `--dry-run` flags
- [ ] 7.4 Write CLI integration tests

## 8. Web Search Provider

- [ ] 8.1 Add `ScholarWebSearchProvider` class to `src/services/web_search.py`
- [ ] 8.2 Implement `search()` mapping S2 results to `WebSearchResult` (title, S2 URL, abstract snippet)
- [ ] 8.3 Implement `format_results()` with academic formatting (venue, year, citation count)
- [ ] 8.4 Register `"scholar"` in `get_web_search_provider()` factory (opt-in only — not valid as default `WEB_SEARCH_PROVIDER`)
- [ ] 8.5 Add validation in Settings to reject `web_search_provider="scholar"` with clear error message
- [ ] 8.6 Write unit tests for the scholar web search provider

## 9. Source Routes & API

- [ ] 9.1 Update `src/api/source_routes.py` to include scholar sources in `SourcesOverview`
- [ ] 9.2 Ensure scholar Content records are returned by existing content list/search endpoints
- [ ] 9.3 Verify no API changes needed (scholar papers are standard Content records)

## 10. Frontend Source Type Registration

- [ ] 10.1 Add `scholar` entry to `sourceConfig` in `web/src/routes/contents.tsx` with label "Scholar" and GraduationCap icon from lucide-react
- [ ] 10.2 Add matching `scholar` entry to `web/src/routes/ingest.tsx` source configuration

## 11. Documentation & Configuration

- [ ] 11.1 Update CLAUDE.md with scholar ingestion commands and configuration
- [ ] 11.2 Add scholar source examples to sources.d documentation
- [ ] 11.3 Add `SEMANTIC_SCHOLAR_API_KEY` to environment configuration docs
