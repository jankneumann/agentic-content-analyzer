# Design: Add HuggingFace Papers Ingestion Source

**Change ID**: `add-huggingface-papers-source`

## Architecture Overview

```
sources.d/huggingface_papers.yaml
         │
         ▼
┌─────────────────────────┐
│   SourcesConfig         │──▶ HuggingFacePapersSource (Pydantic)
│   (discriminated union) │
└─────────────────────────┘
         │
         ▼
┌─────────────────────────┐    ┌──────────────────────────┐
│   Orchestrator          │───▶│ HFPapersIngestionService │
│   ingest_hf_papers()    │    └──────────────────────────┘
└─────────────────────────┘              │
         │                               ▼
         │               ┌──────────────────────────┐
         │               │   HFPapersClient          │
         │               │   1. fetch listing page    │
         │               │   2. discover paper links  │
         │               │   3. extract paper content  │
         │               └──────────────────────────┘
         │                               │
         ▼                               ▼
┌─────────────────────────┐    ┌──────────────────────────┐
│   CLI Command           │    │   Content DB (3-level     │
│   aca ingest hf-papers  │    │   dedup + arXiv cross-ref)│
└─────────────────────────┘    └──────────────────────────┘
```

## Key Design Decisions

### D1: arXiv ID as Source Identifier
**Decision**: Use arXiv ID (extracted from URL path) as the `source_id`, formatted as `hf-paper:{arxiv_id}`.
**Rationale**: arXiv IDs are globally unique, stable identifiers for papers. Using them enables deterministic deduplication across runs and cross-source linking with the existing arXiv ingestion source.
**Trade-off**: Papers without arXiv IDs (rare on HuggingFace) won't be discoverable; this is acceptable since >99% of HuggingFace daily papers are arXiv preprints.

### D2: Cross-Source Dedup with ARXIV
**Decision**: Level 2 dedup checks if the same arXiv paper already exists with `source_type=ARXIV`. If found, the HuggingFace version is linked as a canonical duplicate.
**Rationale**: Avoids duplicate summarization while preserving the HuggingFace metadata (upvotes, community signal). The arXiv version with full PDF text is the canonical record.
**Trade-off**: Depends on arXiv source_id format convention (`arxiv_id` base ID); tightly coupled but justified by shared identity.

### D3: Structured Markdown Output
**Decision**: Build markdown from extracted metadata (title, authors, abstract, links) rather than using Trafilatura on the full page.
**Rationale**: HuggingFace paper pages contain navigation, sidebars, and community UI that pollute Trafilatura output. Structured extraction produces cleaner markdown for downstream summarization.
**Trade-off**: More parsing code but higher quality output.

### D4: Version-Stripping for Dedup
**Decision**: Strip arXiv version suffixes (`2401.12345v2` → `2401.12345`) when deduplicating.
**Rationale**: Different versions of the same paper should be treated as the same work. The listing page may link to any version.
**Trade-off**: Loses version-specific tracking; acceptable since we want the latest content.

## Module Structure

```
src/ingestion/huggingface_papers.py    # Client + Service (single module)
sources.d/huggingface_papers.yaml      # Default source configuration
alembic/versions/b2c3d4e5f6a7_...py   # PG enum migration
```

No new directories created — follows the flat ingestion module convention.

## Integration with Existing Sources

- **arXiv source**: Cross-dedup via `source_type=ARXIV` + matching `source_id`
- **Pipeline**: Papers enter as `PARSED` status, flow through standard summarize → digest pipeline
- **Search indexing**: `index_content()` called on new records for hybrid BM25+vector search
- **Content references**: `metadata_json.arxiv_id` enables reference resolution

## Performance Considerations

| Operation | Expected Latency | Notes |
|-----------|-----------------|-------|
| Fetch listing page | 500ms–2s | Single HTTP request |
| Per-paper extraction | 300ms–1s | + request_delay (1s default) |
| 30 papers total | ~60s | Dominated by rate-limiting delay |
| DB persistence | <100ms | Batch within single transaction |

## Security
- No authentication required (public page)
- Rate limiting via configurable `request_delay` (default 1s)
- User-Agent header identifies the client (`ACA-HFPapers/1.0`)
