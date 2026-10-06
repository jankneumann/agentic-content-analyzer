## MODIFIED Requirements

### Requirement: Research Specialist Tool — `search_content`

The `search_content` tool SHALL behave as specified in the scenarios below, and SHALL surface search completeness to the specialist so it cannot present a truncated or degraded page as the whole corpus.

#### Scenario: search_content signature and behavior

```python
async def search_content(query: str, limit: int = 10, source_types: list[str] | None = None) -> str
```

The `search_content` tool SHALL:
- Use the existing `HybridSearchService` instance (already wired as a dependency via `search_service`)
- Call the hybrid search method which combines BM25 full-text search and pgvector cosine similarity via Reciprocal Rank Fusion
- Pass `source_types` filter when provided to restrict results to specific content sources
- Return results formatted with title, source, date, relevance score, and a content snippet (first 200 characters of matched text)
- Append a completeness line derived from `SearchResponse.meta` and `total`

#### Scenario: search_content result format

The return string SHALL be formatted as:
```
Found <N> of <total> results for "<query>" (<completeness>):

1. [<score>] <title> (<source_type>, <date>)
   <snippet...>

2. [<score>] <title> (<source_type>, <date>)
   <snippet...>
```

When `meta.omissions` is non-empty, the header SHALL be followed by one line per omission reason, for example `Note: reranking failed; scores are RRF only`.

When no results are found, return `"No content found matching: <query>"`.
