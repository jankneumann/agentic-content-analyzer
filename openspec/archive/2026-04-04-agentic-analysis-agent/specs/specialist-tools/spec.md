# Specialist Tool Contracts Specification

**Capability**: `agentic-analysis` (delta)
**Scope**: Tool functions available to specialist agents within their reasoning loops

## Overview

Defines the contracts for each tool function that specialist agents can invoke during their LLM-driven reasoning loops via `LLMRouter.generate_with_tools()`. Each tool is a standalone async function that wraps an existing service or performs a bounded operation. All tools follow a uniform error-handling convention: exceptions are caught internally and returned as descriptive error strings so the LLM can reason about failures without the tool loop aborting.

## Tool Conventions

#### spec-tools.1 -- Error handling convention

All specialist tools SHALL catch exceptions internally and return a string describing the error. No tool SHALL allow an exception to propagate to the LLM tool-calling loop.

The error return format SHALL be: `"Error: <tool_name> failed: <exception message>"`.

This ensures the LLM receives actionable feedback and can decide whether to retry, try an alternative tool, or return partial results (per agentic-analysis.25).

#### spec-tools.2 -- Return type convention

All tools SHALL return `str`. Structured data (lists, dicts) SHALL be serialized to a human-readable string format suitable for LLM consumption (not raw JSON unless the data is inherently tabular).

#### spec-tools.3 -- Async convention

All tools SHALL be `async def` functions. Tools that wrap synchronous services SHALL use `asyncio.to_thread()` for blocking I/O to avoid starving the event loop.

## Research Specialist Tools

### search_web

#### spec-tools.4 -- search_web signature and behavior

```python
async def search_web(query: str, max_results: int = 5) -> str
```

The `search_web` tool SHALL:
- Use the `WebSearchProvider` protocol via `get_web_search_provider()` factory (from `src/services/web_search.py`)
- Pass `query` and `max_results` to the provider's search method
- The active provider is determined by the `WEB_SEARCH_PROVIDER` setting (default: `tavily`; alternatives: `perplexity`, `grok`)
- Return results formatted as a numbered list with title, URL, and snippet for each result
- If no results are found, return `"No results found for: <query>"`

#### spec-tools.5 -- search_web result format

The return string SHALL be formatted as:
```
Web search results for "<query>":

1. <title>
   URL: <url>
   <snippet text>

2. <title>
   URL: <url>
   <snippet text>
```

### fetch_url

#### spec-tools.6 -- fetch_url signature and behavior

```python
async def fetch_url(url: str) -> str
```

The `fetch_url` tool SHALL:
- Use `httpx.AsyncClient` with `follow_redirects=True` and a 30-second timeout
- Convert the HTML response body to plain text using the existing `html_to_text` utility
- Truncate the resulting text to 5000 characters maximum
- Append `"\n\n[Truncated — original was N characters]"` when truncation occurs
- Return the extracted text content

#### spec-tools.7 -- fetch_url error cases

The tool SHALL handle the following error cases:
- `httpx.TimeoutException`: return `"Error: fetch_url failed: Request timed out after 30 seconds"`
- `httpx.HTTPStatusError` (4xx/5xx): return `"Error: fetch_url failed: HTTP <status_code> for <url>"`
- Non-HTML content types (e.g., PDF, image): return the first 5000 characters of the raw response body with a note `"[Non-HTML content: <content-type>]"`
- Connection errors: return `"Error: fetch_url failed: Could not connect to <host>"`

### search_content

#### spec-tools.8 -- search_content signature and behavior

```python
async def search_content(query: str, limit: int = 10, source_types: list[str] | None = None) -> str
```

The `search_content` tool SHALL:
- Use the existing `HybridSearchService` instance (already wired as a dependency via `search_service`)
- Call the hybrid search method which combines BM25 full-text search and pgvector cosine similarity via Reciprocal Rank Fusion
- Pass `source_types` filter when provided to restrict results to specific content sources
- Return results formatted with title, source, date, relevance score, and a content snippet (first 200 characters of matched text)

#### spec-tools.9 -- search_content result format

The return string SHALL be formatted as:
```
Found <N> results for "<query>":

1. [<score>] <title> (<source_type>, <date>)
   <snippet...>

2. [<score>] <title> (<source_type>, <date>)
   <snippet...>
```

When no results are found, return `"No content found matching: <query>"`.

### query_knowledge_graph

#### spec-tools.10 -- query_knowledge_graph signature and behavior

```python
async def query_knowledge_graph(query: str, limit: int = 10) -> str
```

The `query_knowledge_graph` tool SHALL:
- Use the existing `GraphitiClient` instance (already wired as a dependency via `graphiti_client`)
- Perform a semantic search against the Neo4j knowledge graph
- Return entity nodes and their relationships relevant to the query
- Include entity names, types, and relationship descriptions in the output

#### spec-tools.11 -- query_knowledge_graph unavailability

When Neo4j is unavailable (connection refused, timeout), the tool SHALL return `"Error: query_knowledge_graph failed: Knowledge graph is currently unavailable"` rather than raising an exception.

This aligns with agentic-analysis.26 (memory backend unavailability) -- the specialist's LLM can then decide to rely on other tools instead.

## Analysis Specialist Tools

### detect_anomalies

#### spec-tools.12 -- detect_anomalies signature and behavior

```python
async def detect_anomalies(topic: str, days: int = 7, threshold: float = 2.0) -> str
```

The `detect_anomalies` tool SHALL:
- Query recent `Content` records from the database filtered by `topic` (matched against title and tags) within the specified `days` window
- Calculate the baseline content volume (average daily count over the preceding 30-day period)
- Identify days where content volume exceeds `baseline * threshold` as anomalous
- Return a summary including: baseline rate, anomalous dates, volume on those dates, and representative content titles

#### spec-tools.13 -- detect_anomalies result format

The return string SHALL be formatted as:
```
Anomaly detection for "<topic>" (last <days> days, threshold: <threshold>x):

Baseline: <N> items/day (30-day average)
Anomalies found: <count>

<date>: <volume> items (<multiplier>x baseline)
  - <title 1>
  - <title 2>
  ...

<date>: <volume> items (<multiplier>x baseline)
  - <title 1>
  ...
```

When no anomalies are detected, return `"No anomalies detected for '<topic>' in the last <days> days (threshold: <threshold>x, baseline: <N>/day)"`.

### compare_periods

#### spec-tools.14 -- compare_periods signature and behavior

```python
async def compare_periods(topic: str, period_a: str, period_b: str) -> str
```

The `compare_periods` tool SHALL:
- Parse period strings in the format `"Nd"` (days) or `"Nw"` (weeks), e.g., `"7d"`, `"2w"`
- `period_a` is the older (reference) period; `period_b` is the more recent period
- Both periods end at "now" and are contiguous: `period_b` covers the most recent N days/weeks, `period_a` covers the N days/weeks immediately before that
- Query `Content` records for each period filtered by `topic`
- Compare: total content count, unique sources, top themes (extracted from tags)
- Calculate percentage change in volume between periods

#### spec-tools.15 -- compare_periods period parsing

The period parser SHALL:
- Accept `"Nd"` where N is a positive integer representing days (e.g., `"7d"` = 7 days)
- Accept `"Nw"` where N is a positive integer representing weeks (e.g., `"2w"` = 14 days)
- Reject invalid formats with: `"Error: compare_periods failed: Invalid period format '<input>'. Use Nd (days) or Nw (weeks), e.g., '7d' or '2w'"`
- `period_a` and `period_b` need not be the same duration

#### spec-tools.16 -- compare_periods result format

The return string SHALL be formatted as:
```
Period comparison for "<topic>":

Period A (<start_a> to <end_a>): <count_a> items from <sources_a> sources
  Top themes: <theme1>, <theme2>, <theme3>

Period B (<start_b> to <end_b>): <count_b> items from <sources_b> sources
  Top themes: <theme1>, <theme2>, <theme3>

Volume change: <+/-N%> (<count_a> -> <count_b>)
New themes in Period B: <theme_x>, <theme_y>
Themes dropped from Period A: <theme_z>
```

## Tool Registration

#### spec-tools.17 -- Tool definition schema

Each tool SHALL be registered with the specialist via a `ToolDefinition` that includes:
- `name: str` -- the function name used in LLM tool calls
- `description: str` -- a concise description for the LLM's tool selection reasoning
- `parameters: dict` -- JSON Schema describing the function parameters
- `function: Callable` -- the async function reference

The `parameters` schema SHALL use standard JSON Schema types and mark required parameters accordingly. Default values SHALL be specified in the schema so the LLM can omit optional parameters.

#### spec-tools.18 -- Tool-to-specialist mapping

Tools SHALL be assigned to specialists as follows:

| Tool | Specialist | Rationale |
|------|-----------|-----------|
| `search_web` | ResearchSpecialist | External web research |
| `fetch_url` | ResearchSpecialist | Deep-dive into specific URLs |
| `search_content` | ResearchSpecialist | Query ingested content corpus |
| `query_knowledge_graph` | ResearchSpecialist | Entity and relationship lookup |
| `detect_anomalies` | AnalysisSpecialist | Statistical anomaly detection |
| `compare_periods` | AnalysisSpecialist | Temporal trend comparison |

The SynthesisSpecialist and IngestionSpecialist have their own tools (`create_report`, `generate_insight`, `draft_digest`, `create_briefing`, `ingest_source`, `scan_sources`, `ingest_url`) which are defined in separate specialist-specific specs.

#### spec-tools.19 -- Persona tool filtering

When a persona configuration includes `restricted_tools`, the specialist's tool set SHALL be filtered before the reasoning loop begins. A restricted tool SHALL NOT appear in the LLM's available tools list and SHALL NOT be callable.

If a specialist has zero available tools after filtering, the specialist SHALL return an error result: `"No tools available under persona '<name>' restrictions"` and the Conductor SHALL re-plan using a different specialist or approach.

## Dependency Injection

#### spec-tools.20 -- Service dependencies

Tools that depend on existing services SHALL receive them via constructor injection on the specialist, NOT by importing and instantiating services directly. This enables testing with mocks.

Required service dependencies:
- `search_content` requires `HybridSearchService`
- `query_knowledge_graph` requires `GraphitiClient`
- `search_web` requires `WebSearchProvider` (resolved via `get_web_search_provider()`)
- `detect_anomalies` requires `Session` (database session)
- `compare_periods` requires `Session` (database session)
- `fetch_url` has no service dependency (uses `httpx.AsyncClient` directly)

#### spec-tools.21 -- Database session lifecycle

Tools that require a database `Session` (`detect_anomalies`, `compare_periods`) SHALL receive the session from the specialist's execution context. The session lifecycle is managed by the Conductor (via `get_db()` context manager), NOT by individual tools.

Tools SHALL NOT call `db.commit()` or `db.close()`. They perform read-only queries. Write operations (storing insights, updating task status) are the responsibility of the service layer, not tools.
