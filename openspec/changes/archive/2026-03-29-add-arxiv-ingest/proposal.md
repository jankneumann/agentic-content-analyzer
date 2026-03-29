# Proposal: Add arXiv Paper Ingestion

## Change ID
`add-arxiv-ingest`

## Status
Proposed

## Summary

Add a dedicated arXiv ingestion source that searches the arXiv API, downloads open-access PDFs, extracts full paper text via the existing Docling parser, and tracks paper versions so newer revisions automatically replace older ones.

## Why

The existing `add-academic-paper-insights` proposal (Semantic Scholar) provides excellent **metadata and discovery** — search, citation graphs, filtering by venue/citations. However, it stores only abstracts and TL;DRs, not the full paper content.

arXiv is the primary open-access preprint server for AI/ML research. A dedicated arXiv ingest adds two capabilities that Semantic Scholar cannot provide:

1. **Full-text extraction** — arXiv PDFs are freely downloadable. Running them through Docling gives the summarization pipeline the entire paper (methods, results, equations, tables), not just a 200-word abstract. This produces dramatically better summaries for the digest.

2. **Version-aware updates** — arXiv has explicit versioning (e.g., `2301.12345v1` → `v2`). Using the base arXiv ID as `source_id` means newer versions naturally replace older content, keeping digests current with the latest revision.

## What Changes

- New `ContentSource.ARXIV` enum value and Alembic migration (jsonb column, GIN index)
- New `ArxivClient` HTTP client for arXiv Atom API search and PDF download
- New `ArxivContentIngestionService` with full-text PDF extraction via Docling and version-aware updates
- New `ArxivSource` config model and `sources.d/arxiv.yaml` configuration
- Orchestrator `ingest_arxiv()` function and pipeline integration
- CLI commands: `aca ingest arxiv`, `aca ingest arxiv-paper <id>`
- MCP tools: `ingest_arxiv`, `ingest_arxiv_paper`
- Frontend source type registration for arXiv
- Cross-source deduplication with Semantic Scholar via GIN-indexed `metadata_json.arxiv_id`

## Relationship to `add-academic-paper-insights`

This proposal is **complementary**, not competing:

| Capability | Semantic Scholar | arXiv Ingest |
|---|---|---|
| Paper discovery (keyword search) | Yes (S2 API) | Yes (arXiv API) |
| Citation graph traversal | Yes | No |
| Abstract + TL;DR | Yes | Yes |
| **Full PDF text extraction** | No | **Yes** |
| **Version tracking & replacement** | No | **Yes** |
| Category-based new submissions | No | **Yes** (cs.AI, cs.LG, etc.) |
| Cross-source dedup | Via DOI/arXiv ID | Via arXiv ID |

The two features share deduplication infrastructure (GIN-indexed `metadata_json` with `arxiv_id`) and can cross-reference: Scholar can discover papers → arXiv ingest fetches the full text.

## Scope

### In Scope
- arXiv API client (Atom feed search for categories and keywords)
- PDF download and full-text extraction via existing Docling parser
- Version-aware deduplication (base arXiv ID as `source_id`, version in metadata)
- `ARXIV` content source type and Alembic migration
- Source configuration via `sources.d/arxiv.yaml` (categories, search queries)
- CLI commands: `aca ingest arxiv`, `aca ingest arxiv-paper <id>`
- Orchestrator and pipeline integration
- Frontend source type registration

### Out of Scope
- Citation graph traversal (covered by Semantic Scholar proposal)
- LaTeX source parsing (PDF extraction is sufficient)
- arXiv bulk data access (requires institutional agreement)
- Reference extraction and citation tracking (covered by `add-content-references` proposal)
- Scholar ↔ arXiv supplementary linking (covered by `add-content-references` proposal)

## Risks

| Risk | Mitigation |
|---|---|
| arXiv API rate limiting (unclear formal limits) | Polite delay (3s between requests), respect `Retry-After` headers |
| Large PDFs (100+ pages) causing slow parsing | Configurable page limit, timeout per paper, skip on failure |
| Docling struggles with math-heavy papers | Graceful degradation: store abstract-only if PDF parsing fails |
| arXiv API returns Atom XML (not JSON) | Use `feedparser` (already a dependency) for Atom parsing |
| Overlap with Semantic Scholar arXiv ID lookup | Shared dedup via `metadata_json.arxiv_id` GIN index |

## Impact

### New Specs
- `arxiv-ingestion` — new capability spec for arXiv paper ingestion, PDF extraction, version tracking, and cross-source deduplication

### Affected Existing Specs
- `content-ingestion` — arXiv adds a new ingestion source type; no modifications to existing spec required (additive only)
- `source-configuration` — new `ArxivSource` config model added to source type union
- `cli-interface` — new `aca ingest arxiv` and `aca ingest arxiv-paper` commands
- `pipeline` — `ingest_arxiv()` added to daily pipeline ingestion stage

## Success Criteria

1. `aca ingest arxiv` fetches papers from configured categories and stores full-text markdown
2. Version updates replace older content (v2 overwrites v1 for same arXiv ID)
3. Papers appear in digest pipeline with rich full-text summaries
4. Cross-source deduplication works between arXiv and Scholar sources
5. Rate limiting prevents API abuse
