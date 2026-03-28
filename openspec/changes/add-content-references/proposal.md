# Proposal: Add Content References & Citation Tracking

## Change ID
`add-content-references`

## Status
Proposed

## Summary

Add a cross-cutting content relationship layer that tracks citations, references, and links between content items — both internal (resolved to DB records) and external (URLs and structured identifiers). Stores relationships in PostgreSQL (source of truth) with one-way projection to Neo4j (graph analysis).

## Motivation

Content in the system doesn't exist in isolation. A Substack blog post cites an arXiv paper. That paper references three other papers. A YouTube video discusses the same paper. A Perplexity search result links to the blog post. Today, these connections are invisible:

- `links_json` extracts URLs but doesn't classify or resolve them
- `canonical_id` handles exact duplicates but not citations
- The knowledge graph extracts entities but has no structural citation edges
- The Scholar proposal stores `parent_paper_id` in metadata_json (ad-hoc, single-hop)

Without a relationship layer, the digest pipeline treats each content item as independent. With it, we can:

1. **Auto-discover content** — Blog references arXiv paper → ingest the paper automatically
2. **Enrich existing records** — Scholar abstract exists → arXiv full text arrives → link them
3. **Power graph analysis** — "What are the most-cited papers across all our sources?"
4. **Improve digest quality** — Theme analysis gains structural citation signals, not just semantic similarity

## Relationship to Other Proposals

This proposal provides **infrastructure** consumed by:

| Proposal | How it uses content-references |
|---|---|
| `add-academic-paper-insights` (Scholar) | Citation graph traversal stores edges here; reference extraction resolves identifiers against this table |
| `add-arxiv-ingest` (arXiv) | arXiv papers linked to Scholar abstracts; blog→paper references resolved |
| Future proposals | Any source that extracts URLs/identifiers can produce references |

## Existing Code (Post-Scholar Implementation)

The Scholar PR (#338) already built reference extraction infrastructure that this proposal must extend rather than duplicate:

| Component | Location | What Exists | What This Proposal Adds |
|---|---|---|---|
| `ReferenceExtractor` class | `src/ingestion/reference_extractor.py` | Regex patterns for arXiv, DOI, S2; `extract_all()`, `extract_from_contents()` methods; Scholar-specific `ingest_extracted_references()` | Chunk anchoring, URL classification, `store_references()` with `content_references` table, context snippets |
| CLI command | `aca ingest scholar-refs` | Extract identifiers → ingest via Scholar service | New `aca manage extract-refs` (source-agnostic, stores to `content_references` table) and `aca manage resolve-refs` (background resolution) |
| Orchestrator function | `src/ingestion/orchestrator.py:ingest_scholar_refs()` | Wraps `ReferenceExtractor` for CLI | Ingestion hooks (auto-extract on any content ingest), reverse resolution |
| Tests | `tests/test_ingestion/test_reference_extractor.py` | Regex extraction tests | Chunk anchoring, store_references, resolution, API route tests |

**Migration strategy**: Refactor existing `ReferenceExtractor` from `src/ingestion/` to `src/services/` (aligns with service layer), extend with chunk anchoring and `content_references` persistence. Preserve existing `extract_all()` and `extract_from_contents()` APIs for backward compatibility. The `aca ingest scholar-refs` command continues to work but delegates to the new system internally.

## Scope

### In Scope
- `content_references` PostgreSQL table with resolution tracking
- `ReferenceType` and `ExternalIdType` enums
- Reference extraction service (regex patterns for arXiv, DOI, S2, internal URLs)
- Background resolution job (queue-based, resolves external_id → target_content_id)
- Auto-ingest trigger (optionally ingest unresolved arXiv/DOI references)
- Neo4j projection (CITES/CITED_BY edges between Episode nodes)
- API endpoints for querying references per content item
- CLI command for manual reference extraction runs

### Out of Scope
- Semantic similarity-based "related content" (that's the knowledge graph's job)
- Full citation graph visualization (frontend — future)
- Citation count aggregation and ranking (future enhancement)
- Automatic backfill of all existing content (opt-in via CLI)

### Future: Click-to-Ingest Citations in Frontend

This proposal lays the groundwork for a frontend capability where unresolved references are rendered as clickable citations in content, summary, and digest views. A user reading a digest could click an arXiv or DOI reference inline and trigger ad-hoc ingestion — the paper would be fetched, parsed, and added to the database on demand. This requires:
- The reference extraction and resolution infrastructure from this proposal (backend ready)
- Frontend rendering of `content_references` with resolution status (resolved → link to internal content, unresolved → "ingest" action button)
- A `POST /api/v1/references/{id}/ingest` endpoint that triggers single-paper ingestion and resolves the reference
- Markdown pipeline integration to annotate citations with reference metadata during rendering

The API endpoint (`REQ-REF-008`) and auto-ingest trigger (`REQ-REF-006`) provide the backend primitives; the frontend UX and markdown annotation are a separate proposal.

## Risks

| Risk | Mitigation |
|---|---|
| Existing code overlap with Scholar PR | Refactor-and-extend strategy; preserve backward-compatible APIs |
| Large reference volume from existing content | Batch processing with queue jobs; backfill is opt-in CLI command |
| Circular references (A cites B, B cites A) | Allowed — these are valid in academia; no infinite loops since extraction is content-driven |
| Auto-ingest creating unbounded content growth | Configurable: `auto_ingest_enabled` setting, `max_auto_ingest_depth=1` (no recursive auto-ingest of auto-ingested content) |
| Neo4j sync lag | Eventual consistency is fine; PG is authoritative; Neo4j sync is fire-and-forget |
| Reference extraction false positives | Structured ID patterns (arXiv/DOI) have very low false positive rates; URL-only references are lower confidence |

## Success Criteria

1. When a blog post is ingested, arXiv/DOI references are automatically extracted and stored as `content_references` rows
2. Background job resolves references: matches to existing DB content or marks as unresolved
3. When an arXiv paper is later ingested, previously-unresolved references to it are automatically resolved
4. Neo4j contains CITES edges between Episode nodes that mirror resolved PostgreSQL references
5. API returns reference data: "this blog post cites these 3 papers"
6. `aca manage extract-refs` backfills references for existing content
