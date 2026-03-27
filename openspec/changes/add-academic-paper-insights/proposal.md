## Why

The newsletter aggregator ingests content from newsletters, RSS feeds, YouTube, podcasts, and social media — but academic research papers are a critical blind spot. Many ingested articles reference arXiv papers, conference proceedings, and survey papers that provide deeper context. Currently, users must manually track down these references. Adding academic paper discovery as a first-class source type enables:

1. **Survey paper seeding** — Overview/survey papers act as curated entry points to entire research areas, making it easy to explore new topics
2. **Reference follow-up** — Papers cited in existing ingested content can be automatically discovered and queued for ingestion
3. **Citation graph exploration** — Semantic Scholar's citation graph enables discovering influential papers and tracking research lineage
4. **Academic-grade search** — Structured metadata (authors, venues, citation counts, abstracts) enables more precise content filtering than general web search

This fills the gap between informal AI coverage (newsletters, social media) and primary research sources, giving technical leaders a complete picture of the AI/Data landscape.

## What Changes

- Add a `SemanticScholarClient` that wraps the Semantic Scholar Academic Graph API for paper search, paper details, citation/reference traversal, and bulk lookup
- Add an `AcademicPaperIngestionService` following the existing Client-Service ingestion pattern, with support for search-based discovery, single-paper lookup (by DOI/arXiv ID/S2 paper ID), and citation graph traversal
- Add `academic` as a new source type in the sources.d configuration system and `ACADEMIC` to the `ContentSource` enum
- Add `sources.d/academic.yaml` for configuring recurring academic searches (topics, venues, recency filters)
- Add an `AcademicWebSearchProvider` for ad-hoc academic search (used in chat, digest review context)
- Add a reference extraction utility that scans existing ingested content for arXiv IDs, DOIs, and paper titles, and queues them for academic paper ingestion
- Add CLI commands: `aca ingest academic` (search-based), `aca ingest academic-paper <id>` (single paper by DOI/arXiv/S2 ID)
- Extend the pipeline runner to include academic sources in the daily pipeline
- Store academic-specific metadata (authors, venue, year, citation count, fields of study, arXiv ID, DOI, S2 paper ID, paper type) in metadata_json

## Capabilities

### New Capabilities
- `academic-paper-ingestion`: Academic paper discovery and ingestion via Semantic Scholar API, including search-based discovery, single-paper lookup, citation graph traversal, and reference extraction from existing content

### Modified Capabilities
- `content-ingestion`: Add `ACADEMIC` source type to the ingestion pipeline
- `source-configuration`: Add `academic` source type to sources.d configuration with academic-specific fields (venues, fields_of_study, min_citation_count, paper_type filter)
- `content-model`: Add `ACADEMIC` to ContentSource enum

## Impact

- **Backend**: New ingestion service (~400 LOC), Semantic Scholar client (~250 LOC), reference extractor (~150 LOC), CLI commands (~80 LOC), web search provider (~80 LOC)
- **Frontend**: No changes required (academic content appears as standard Content records in existing UI)
- **Dependencies**: None — Semantic Scholar API uses standard HTTP (httpx, already in deps). No API key required for basic access (1000 req/5min unauthenticated; optional API key for higher limits)
- **Database**: One Alembic migration to add `ACADEMIC` to ContentSource enum
- **Cost**: Free (Semantic Scholar API is free and open). Optional API key available for higher rate limits
- **Risk**: Low — follows established ingestion patterns exactly, no schema changes beyond enum addition
