# Spec: HuggingFace Papers Ingestion

**Capability**: `huggingface-papers-ingestion`
**Status**: Implemented
**Depends on**: `content-ingestion`

## Scenarios

### Enum & Configuration

#### hf-papers.1 — ContentSource enum includes HUGGINGFACE_PAPERS
**Given** the ContentSource enum in `src/models/content.py`
**When** a developer references `ContentSource.HUGGINGFACE_PAPERS`
**Then** the value is `"huggingface_papers"`
**And** an Alembic migration exists to add the value to the PostgreSQL enum type

#### hf-papers.2 — Source config loads from YAML
**Given** a `sources.d/huggingface_papers.yaml` file with enabled sources
**When** `load_sources_config()` is called
**Then** `get_huggingface_papers_sources()` returns `HuggingFacePapersSource` instances
**And** each source has `type`, `url`, `name`, `tags`, `request_delay` fields
**And** disabled sources are excluded from the result

### Link Discovery

#### hf-papers.3 — Paper links discovered from listing page
**Given** HTML containing links matching `/papers/<arxiv_id>` pattern
**When** `discover_paper_links()` is called with the HTML
**Then** each link is returned as a `DiscoveredPaper` with `arxiv_id` and `url`
**And** the arXiv ID is extracted from the URL path (e.g., `2401.12345`)

#### hf-papers.4 — Version suffixes stripped for deduplication
**Given** links to `/papers/2401.12345v2` and `/papers/2401.12345`
**When** `discover_paper_links()` processes both links
**Then** only one `DiscoveredPaper` is returned (version stripped for dedup)

#### hf-papers.5 — Max papers limit respected
**Given** a listing page with 50+ paper links
**When** `discover_paper_links(max_papers=30)` is called
**Then** at most 30 papers are returned

#### hf-papers.6 — Non-paper links ignored
**Given** HTML containing links to `/about`, `/models`, `/datasets`
**When** `discover_paper_links()` is called
**Then** only links matching the `/papers/<arxiv_id>` pattern are returned

### Content Extraction

#### hf-papers.7 — Paper metadata extracted from page
**Given** a HuggingFace paper page with title, authors, and abstract
**When** `extract_paper_content()` fetches and parses the page
**Then** a `ContentData` is returned with structured markdown
**And** `source_type` is `HUGGINGFACE_PAPERS`
**And** `source_id` is `hf-paper:<arxiv_id>`
**And** `metadata_json` contains `arxiv_id`, `hf_url`, `arxiv_url`, `pdf_url`

#### hf-papers.8 — Insufficient content returns None
**Given** a paper page with less than 50 characters of extractable content
**When** `extract_paper_content()` processes the page
**Then** `None` is returned

### Deduplication

#### hf-papers.9 — Duplicate HF paper skipped
**Given** a paper with `source_id=hf-paper:2401.12345` already in the database
**When** the same paper is discovered again
**Then** the paper is skipped (not re-ingested)
**And** `force_reprocess=True` overrides this and updates the existing record

#### hf-papers.10 — Cross-source arXiv dedup links canonical
**Given** a paper `2401.12345` already ingested via the arXiv source
**When** the same paper appears on HuggingFace daily papers
**Then** the HF version is stored with `canonical_id` pointing to the arXiv record
**And** the HF record status is set to `COMPLETED`

### CLI & Orchestrator

#### hf-papers.11 — Orchestrator function delegates to service
**Given** the `ingest_huggingface_papers()` function is called
**When** it executes
**Then** it lazy-imports `HuggingFacePapersContentIngestionService`
**And** returns the count of items ingested as an integer

#### hf-papers.12 — CLI command invokes ingestion
**Given** a user runs `aca ingest huggingface-papers`
**When** the backend API is available
**Then** ingestion is dispatched via the API with SSE progress
**And** falls back to direct mode if the API is unreachable

#### hf-papers.13 — CLI options pass through correctly
**Given** a user runs `aca ingest huggingface-papers --max 50 --force --days 3`
**When** the command executes in direct mode
**Then** `max_papers=50`, `force_reprocess=True`, and `after_date` is 3 days ago
