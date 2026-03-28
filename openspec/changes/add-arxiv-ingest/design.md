## Architecture

Follows the existing Client-Service ingestion pattern:

```
ArxivClient (HTTP client, Atom XML parsing, PDF download)
    ↓
ArxivContentIngestionService (business logic + persistence)
    ↓
orchestrator.ingest_arxiv() (lazy-loaded entry point)
    ↓
CLI: aca ingest arxiv / aca ingest arxiv-paper <id>
Pipeline: pipeline runner daily stage
```

## arXiv API Integration

**Base URL:** `http://export.arxiv.org/api/query`

**Endpoints used:**

| Endpoint | Purpose |
|----------|---------|
| `GET /api/query?search_query=...` | Keyword + category search |
| `GET /api/query?id_list=...` | Single paper lookup by arXiv ID |
| `GET /pdf/{id}` | PDF download |
| `GET /abs/{id}` | Abstract page (fallback metadata) |

**Query syntax:**
- Category filter: `cat:cs.AI`
- Keyword: `all:transformer+attention`
- Combined: `cat:cs.AI+AND+all:transformer`
- Date sort: `sortBy=submittedDate&sortOrder=descending`
- Pagination: `start=0&max_results=50`

**Response format:** Atom XML (parsed via `feedparser`)

**Rate limiting:**
- arXiv asks for a 3-second delay between requests (no formal rate limit)
- Implemented as `time.sleep(3)` between API calls (sync client)
- PDF downloads use a separate, more permissive rate limiter (1s delay) — arXiv serves PDFs from CDN
- Respect `Retry-After` header on 429/503 responses
- Exponential backoff on errors (base 5s, max 60s, 3 retries)

## Source Configuration

**New file:** `sources.d/arxiv.yaml`

```yaml
version: 1
defaults:
  type: arxiv
  enabled: true
  max_entries: 20
  sort_by: submittedDate
  pdf_extraction: true
  max_pdf_pages: 80

sources:
  - name: "AI Research"
    categories: ["cs.AI"]
    search_query: "artificial intelligence"
    tags: [ai, research]

  - name: "LLM & NLP Papers"
    categories: ["cs.CL", "cs.LG"]
    search_query: "large language model"
    tags: [llm, nlp]

  - name: "AI Agents"
    categories: ["cs.AI", "cs.MA"]
    search_query: "autonomous agent"
    tags: [agents]
```

**ArxivSource model** (in `src/config/sources.py`):

```python
class ArxivSource(SourceBase):
    type: Literal["arxiv"] = "arxiv"
    categories: list[str] = []                    # e.g., ["cs.AI", "cs.LG"]
    search_query: str | None = None               # Keyword search (arXiv query syntax)
    sort_by: Literal["relevance", "lastUpdatedDate", "submittedDate"] = "submittedDate"
    pdf_extraction: bool = True                   # Download and parse PDF
    max_pdf_pages: int = 80                       # Skip PDFs exceeding this
```

## Content Model Mapping

arXiv papers map to existing Content fields:

| Content Field | arXiv Paper Source |
|--------------|-------------------|
| `source_type` | `ContentSource.ARXIV` |
| `source_id` | Base arXiv ID without version (e.g., `2301.12345`) |
| `source_url` | `https://arxiv.org/abs/{id}` |
| `title` | Paper title |
| `author` | First author + "et al." (full list in metadata) |
| `publication` | `"arXiv"` + primary category (e.g., `"arXiv [cs.AI]"`) |
| `published_date` | Original submission date |
| `markdown_content` | Full PDF text (via Docling) or abstract-only fallback |
| `raw_content` | Abstract XML from Atom feed (not PDF binary) |
| `raw_format` | `"xml"` |
| `parser_used` | `"DoclingParser"` or `"ArxivAbstractParser"` |
| `content_hash` | SHA-256 of normalized markdown |
| `metadata_json` | See below |

**metadata_json structure:**
```json
{
  "arxiv_id": "2301.12345",
  "arxiv_version": 3,
  "arxiv_url": "https://arxiv.org/abs/2301.12345v3",
  "pdf_url": "https://arxiv.org/pdf/2301.12345v3",
  "categories": ["cs.AI", "cs.LG"],
  "primary_category": "cs.AI",
  "authors": [
    {"name": "Jane Smith", "affiliation": null},
    {"name": "John Doe", "affiliation": "MIT"}
  ],
  "abstract": "We present a novel approach to...",
  "doi": "10.48550/arXiv.2301.12345",
  "journal_ref": null,
  "comment": "Accepted at NeurIPS 2024, 15 pages",
  "updated_date": "2024-06-15T00:00:00Z",
  "pdf_extracted": true,
  "pdf_pages": 15,
  "ingestion_mode": "search"
}
```

## Version-Aware Update Strategy

arXiv papers go through revisions (v1 → v2 → v3). The update strategy:

1. **source_id = base arXiv ID** (e.g., `2301.12345`, no version suffix)
2. On re-ingest, query existing content by `(source_type=ARXIV, source_id=base_id)`
3. Compare `metadata_json.arxiv_version` with incoming version
4. If incoming version is newer:
   - Re-download and parse the updated PDF
   - Update `markdown_content`, `content_hash`, `metadata_json`
   - Delete or mark stale any existing Summary records for this Content
   - Reset status to `PENDING` so summarization re-runs
   - Preserve the original `ingested_at` timestamp
5. If same or older version: skip (no-op)

This leverages the existing `(source_type, source_id)` unique constraint for upsert behavior.

## PDF Extraction Pipeline

```
arXiv API response (Atom XML)
    ↓ feedparser
Paper metadata (title, abstract, authors, categories, PDF URL)
    ↓
PDF download (httpx, streaming, temp file)
    ↓
Page count check (lightweight PDF reader, skip if > max_pdf_pages)
    ↓
DoclingParser.parse(pdf_path)
    ↓ success?
    ├── Yes → Full markdown content + tables
    └── No  → Fallback: abstract-only markdown with metadata header
    ↓
ContentData (unified format)
    ↓
Content record (database)
```

**PDF download constraints:**
- Max file size: 50 MB (configurable)
- Streaming download to temp file (no full-memory load)
- Timeout: 60 seconds per PDF
- Temp files cleaned up after parsing

**Fallback when PDF extraction fails:**
```markdown
# {title}

**Authors:** {authors}
**Published:** {date} | **Categories:** {categories}
**arXiv:** [{arxiv_id}]({url})

## Abstract

{abstract}

---
*Full text extraction failed. Abstract only.*
```

## Cross-Source Deduplication

arXiv full-text is the primary value; Scholar abstracts are a discovery aid. The dedup policy is **arXiv-first**:

Uses the GIN index on `metadata_json` (requires `jsonb` column — migration MUST ALTER from `json` to `jsonb` if needed):

1. Before ingesting an arXiv paper, check if it already exists:
   - Primary: `SELECT ... WHERE source_type='arxiv' AND source_id='{base_id}'`
   - Cross-source: `SELECT ... WHERE metadata_json @> '{"arxiv_id": "{base_id}"}'::jsonb`
2. If found as Scholar content with same arXiv ID → **replace** the Scholar record's `markdown_content` with full PDF text, update `parser_used`, set `metadata_json.pdf_extracted=true`, reset status to PENDING for re-summarization
3. If found as arXiv content → version check and update if newer
4. If not found → create new Content record

Conversely, when Scholar ingests a paper that already exists as arXiv content (with full text), Scholar MUST skip creating a duplicate — the arXiv full-text record is authoritative for content.

## Design Decisions

### Why a separate source type (not reusing SCHOLAR)?

1. **Different content depth** — Scholar stores abstracts; arXiv stores full PDF text
2. **Different discovery mechanism** — Scholar uses keyword search + citations; arXiv uses category browsing + new submissions
3. **Independent operation** — arXiv requires no API key and works without Scholar
4. **Version tracking** — arXiv versioning is unique and needs dedicated logic

### Why feedparser for Atom XML?

- Already a project dependency (used by RSS ingestion)
- Handles Atom and RSS transparently
- **Important**: feedparser dates are naive — all `published_parsed` and `updated_parsed` values MUST be converted to UTC-aware datetime (per CLAUDE.md gotcha)

### Why synchronous client (not async)?

- The pipeline runner wraps orchestrator functions with `asyncio.to_thread(func)` where func is `Callable[[], int]` (synchronous)
- All existing ingestion clients (RSS, Gmail, etc.) are synchronous using `httpx.Client`
- Rate limiting uses `time.sleep(3)`, not `asyncio.sleep(3)`
- Keeping the client sync avoids event loop conflicts and matches existing patterns

### SSRF Prevention

ArxivClient MUST construct all API and PDF URLs from the normalized arXiv ID using hardcoded base URLs (`export.arxiv.org`, `arxiv.org/pdf/`). User-provided URLs (from CLI or MCP) are used ONLY for ID extraction via `normalize_arxiv_id()`, never passed directly to HTTP clients.

### Why not arXiv bulk access?

- Requires institutional agreement and S3-based data access
- Overkill for targeted category/keyword monitoring
- The API is sufficient for our use case (tens of papers per day, not millions)
