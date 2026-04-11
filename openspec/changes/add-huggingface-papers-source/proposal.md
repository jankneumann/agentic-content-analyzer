# Change: Add HuggingFace Papers Ingestion Source

**Change ID**: `add-huggingface-papers-source`
**Status**: Implemented
**Created**: 2026-04-11

## Why

HuggingFace's daily papers page (https://huggingface.co/papers/) is a curated,
community-upvoted listing of recent AI/ML research papers. It surfaces trending
arXiv papers with community engagement signals (upvotes, discussions) that raw
arXiv feeds miss.

Current gaps:
- The existing `arxiv` source ingests papers by category/keyword search, but
  misses community-curated "what's trending today" papers
- No way to capture HuggingFace-specific signals (upvotes, community interest)
- Users must manually check the HuggingFace papers page for daily highlights

By adding HuggingFace Papers:
1. **Community signal**: Capture papers the AI community deems important
2. **Complementary to arXiv**: Trending papers vs. exhaustive category search
3. **Cross-source dedup**: Papers already ingested via arXiv are linked, not duplicated
4. **Consistent experience**: Same CLI/API/pipeline integration as other sources

## What Changes

### New Components
1. **`src/ingestion/huggingface_papers.py`** — Client-service pair for paper discovery and extraction
   - `HuggingFacePapersClient`: Fetches listing page, discovers paper links via arXiv ID regex, extracts metadata (title, authors, abstract) from individual paper pages
   - `HuggingFacePapersContentIngestionService`: Orchestrates ingestion with 3-level deduplication including cross-source arXiv matching
   - `DiscoveredPaper`: Dataclass for discovered paper links with arXiv IDs

2. **`sources.d/huggingface_papers.yaml`** — Source configuration with defaults (30 papers, 1s request delay)

3. **`alembic/versions/b2c3d4e5f6a7_add_huggingface_papers_source.py`** — PostgreSQL enum migration

### Modified Components
1. **`src/models/content.py`** — Add `HUGGINGFACE_PAPERS` to `ContentSource` enum
2. **`src/config/sources.py`** — Add `HuggingFacePapersSource` model, discriminated union, getter method
3. **`src/ingestion/orchestrator.py`** — Add `ingest_huggingface_papers()` orchestrator function
4. **`src/cli/ingest_commands.py`** — Add `aca ingest huggingface-papers` CLI command

## Approaches Considered

### Approach A: RSS/Atom Feed
**Description**: Use HuggingFace's RSS feed if available
**Pros**: Reuses existing RSS infrastructure, structured data
**Cons**: HuggingFace daily papers page has no RSS feed
**Effort**: S (if feed existed)

### Approach B: HTML Scraping with Blog Scraper Pattern (Selected)
**Description**: Two-phase scraping following the established blog scraper pattern
**Pros**: Proven pattern in codebase, handles dynamic page layouts, arXiv ID regex is stable
**Cons**: Fragile if HuggingFace changes HTML structure
**Effort**: M

### Approach C: HuggingFace Hub API
**Description**: Use the `huggingface_hub` Python SDK to query papers programmatically
**Pros**: Structured API, less fragile than scraping
**Cons**: Papers endpoint may not be in the public SDK, adds dependency
**Effort**: M

### Selected Approach: B
The blog scraper pattern is well-established in this codebase and the arXiv ID
regex (`/papers/\d{4}\.\d{4,5}`) provides a stable anchor for link discovery
regardless of HTML layout changes. Cross-source dedup with the existing arXiv
source is a natural fit since both index the same underlying papers.

## Out of Scope
- Full-text PDF extraction (handled by existing arXiv source)
- HuggingFace model/dataset pages
- Comment/discussion ingestion
- Historical paper backfill (only current listing page)
