## Architecture

Follows the existing Client-Service ingestion pattern:

```
SemanticScholarClient (HTTP client, no DB)
    ↓
ScholarContentIngestionService (business logic + persistence)
    ↓
orchestrator.ingest_scholar() (lazy-loaded entry point)
    ↓
CLI: aca ingest scholar / aca ingest scholar-paper <id>
Pipeline: pipeline runner daily stage
```

## Semantic Scholar API Integration

**Base URL:** `https://api.semanticscholar.org/graph/v1`

**Endpoints used:**

| Endpoint | Purpose |
|----------|---------|
| `GET /paper/search` | Keyword search with relevance ranking |
| `GET /paper/{paperId}` | Single paper details (by S2 ID, DOI, ArXiv, CorpusId) |
| `GET /paper/{paperId}/citations` | Papers that cite this paper |
| `GET /paper/{paperId}/references` | Papers this paper cites |
| `POST /paper/batch` | Bulk paper details lookup |

**Paper ID formats supported:** `S2PaperId`, `DOI:10.xxx`, `ArXiv:2301.xxxxx`, `CorpusId:nnn`, `PMID:nnn`

**Authentication:**
- Unauthenticated: ~100 requests per 5 minutes (shared pool)
- Authenticated: 1 RPS for search/batch, 10 RPS for detail endpoints
- API key via `x-api-key` header
- Settings: `SEMANTIC_SCHOLAR_API_KEY` (optional)

**Fields requested per paper:**
`paperId,externalIds,title,abstract,year,venue,publicationVenue,citationCount,influentialCitationCount,fieldsOfStudy,authors,publicationTypes,openAccessPdf,tldr`

## Source Configuration

**New file:** `sources.d/scholar.yaml`

```yaml
version: 1
defaults:
  type: scholar
  enabled: true
  max_entries: 20
  min_citation_count: 0
  paper_types: []                    # Empty = all types
  fields_of_study: []               # Empty = all fields

sources:
  - name: "AI Survey Papers"
    query: "artificial intelligence survey"
    paper_types: ["Review"]
    fields_of_study: ["Computer Science"]
    min_citation_count: 10
    year_range: "2024-"
    tags: [ai, survey]

  - name: "LLM Research"
    query: "large language model"
    fields_of_study: ["Computer Science"]
    year_range: "2024-"
    max_entries: 30
    tags: [llm, research]

  - name: "AI Agents Research"
    query: "autonomous AI agents"
    fields_of_study: ["Computer Science"]
    year_range: "2024-"
    tags: [agents, research]
```

**ScholarSource model** (in `src/config/sources.py`):

```python
class ScholarSource(SourceBase):
    type: Literal["scholar"] = "scholar"
    query: str                                    # Search query
    fields_of_study: list[str] = []              # e.g., ["Computer Science"]
    paper_types: list[str] = []                  # e.g., ["Review", "JournalArticle"]
    min_citation_count: int = 0                  # Filter low-impact papers
    year_range: str = ""                         # e.g., "2024-" or "2023-2024"
    venues: list[str] = []                       # e.g., ["NeurIPS", "ICML"]
```

## Content Model Mapping

Academic papers map to existing Content fields:

| Content Field | Scholar Paper Source |
|--------------|---------------------|
| `source_type` | `ContentSource.SCHOLAR` |
| `source_id` | Semantic Scholar paper ID (stable, unique) |
| `source_url` | `semanticscholar.org/paper/{id}` or open access PDF URL |
| `title` | Paper title |
| `author` | First author (+ "et al." if multiple) |
| `publication` | Venue name (e.g., "NeurIPS 2024") |
| `published_date` | Publication year (as date) |
| `markdown_content` | Formatted paper summary (see below) |
| `content_hash` | SHA-256 of normalized markdown |
| `metadata_json` | Academic-specific metadata (see below) |

**Markdown content format:**

```markdown
# {title}

**Authors:** {author1}, {author2}, ...
**Venue:** {venue} ({year})
**Citations:** {citation_count} ({influential_citation_count} influential)
**Fields:** {fields_of_study}

## Abstract

{abstract}

## TL;DR

{tldr.text}  <!-- Semantic Scholar's auto-generated TL;DR -->

## Key References

- {reference_1_title} ({reference_1_year}) — {reference_1_citation_count} citations
- ...

## Links

- [Semantic Scholar](https://www.semanticscholar.org/paper/{paperId})
- [arXiv](https://arxiv.org/abs/{arxivId})  <!-- if available -->
- [PDF](https://arxiv.org/pdf/{arxivId})  <!-- if open access -->
- [DOI](https://doi.org/{doi})  <!-- if available -->
```

**metadata_json structure:**

```json
{
  "s2_paper_id": "abc123",
  "arxiv_id": "2301.12345",
  "doi": "10.1234/conf.2024.123",
  "corpus_id": 123456789,
  "authors": [{"name": "...", "authorId": "..."}],
  "venue": "NeurIPS",
  "year": 2024,
  "citation_count": 150,
  "influential_citation_count": 25,
  "fields_of_study": ["Computer Science"],
  "publication_types": ["Conference", "Review"],
  "open_access_pdf_url": "https://arxiv.org/pdf/2301.12345",
  "tldr": "This paper surveys...",
  "search_query": "AI survey papers",
  "ingestion_mode": "search"
}
```

## Deduplication Strategy

1. **Primary:** Source ID match (`source_type=SCHOLAR` + `source_id=S2PaperId`)
2. **Secondary:** Cross-source DOI/arXiv lookup — check metadata_json for matching DOI or arXiv ID across all source types (a paper ingested via Perplexity search might already exist)
3. **Tertiary:** Content hash (normalized markdown)

## Reference Extraction

A utility to scan existing Content records for academic paper references:

**Patterns detected:**
- arXiv IDs: `arXiv:2301.12345`, `arxiv.org/abs/2301.12345`
- DOIs: `doi.org/10.xxxx/...`, `DOI: 10.xxxx/...`
- Semantic Scholar URLs: `semanticscholar.org/paper/...`

**Workflow:**
1. Query Content records (optionally filtered by date/source)
2. Regex-extract arXiv IDs, DOIs, and S2 URLs from markdown_content
3. Batch-resolve via Semantic Scholar `/paper/batch` endpoint
4. Filter already-ingested papers
5. Ingest new papers with `ingestion_mode: "reference_extraction"` in metadata

**CLI:** `aca ingest scholar-refs` — scan recent content and ingest referenced papers

## Ad-hoc Web Search Provider

For use in chat, podcast generation, and digest review contexts:

```python
class ScholarWebSearchProvider:
    """Semantic Scholar search for ad-hoc academic queries."""
    name = "scholar"

    def search(self, query, max_results=5) -> list[WebSearchResult]:
        # Uses /paper/search endpoint
        # Returns WebSearchResult with paper title, S2 URL, abstract snippet

    def format_results(self, results) -> str:
        # Formats as "Paper Title (Venue Year, N citations): abstract snippet..."
```

Registered in `get_web_search_provider()` factory.

## Rate Limiting

- Use httpx with retry logic (exponential backoff)
- Respect 100 req/5min unauthenticated limit
- Optional `SEMANTIC_SCHOLAR_API_KEY` for higher limits (1-10 RPS)
- Batch endpoint for reference extraction (up to 500 papers per request)
- Add `semantic_scholar_api_key` to Settings and base.yaml profile wiring
