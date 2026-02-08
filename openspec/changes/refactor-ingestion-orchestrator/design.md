## Context

Ingestion services are wired identically in three places:

| Call site | File | Pattern |
|-----------|------|---------|
| CLI | `src/cli/ingest_commands.py` | Import service → instantiate → call → return count |
| Pipeline | `src/cli/pipeline_commands.py` | Import service → instantiate → call → return count (inside `asyncio.to_thread`) |
| Task worker | `src/tasks/content.py` | Import service → instantiate → call → return count (inside `asyncio.to_thread`) |

Each site must know:
- Which service classes to import for each source
- How to instantiate them (constructor args like `use_oauth`, `session_cookie`)
- Which methods to call and in what order (e.g., YouTube requires 3 calls across 2 service classes)
- How to normalize return types (RSS returns `IngestionResult`, others return `int`)

The YouTube RSS bug proved this is fragile: `YouTubeRSSIngestionService.ingest_all_feeds()` was missing from pipeline and task worker because each file was maintained independently.

## Goals / Non-Goals

**Goals:**
- Single source of truth for "how to ingest from source X"
- Adding a new source means editing one file (orchestrator) + one test file
- CLI, pipeline, and task worker remain independently testable
- No change to user-facing CLI interface or API contract

**Non-Goals:**
- Requiring the CLI to use the job queue (CLI stays synchronous)
- Abstracting away source-specific options (e.g., Gmail's `query` parameter)
- Changing the ingestion service class interfaces themselves
- Adding new ingestion sources (that's a separate concern)

## Decisions

### Decision: Plain functions in `src/ingestion/orchestrator.py`

Each source gets one orchestrator function:

```python
def ingest_gmail(*, query: str = "label:newsletters-ai", max_results: int = 10,
                 after_date: datetime | None = None, force_reprocess: bool = False) -> int:
    ...

def ingest_rss(*, max_entries_per_feed: int = 10, after_date: datetime | None = None,
               force_reprocess: bool = False) -> int:
    ...

def ingest_youtube(*, max_videos: int = 10, after_date: datetime | None = None,
                   force_reprocess: bool = False, use_oauth: bool = True) -> int:
    ...

def ingest_podcast(*, max_entries_per_feed: int = 10, after_date: datetime | None = None,
                   force_reprocess: bool = False) -> int:
    ...

def ingest_substack(*, max_entries_per_source: int = 10, after_date: datetime | None = None,
                    force_reprocess: bool = False, session_cookie: str | None = None) -> int:
    ...
```

**Why plain functions instead of a class:**
- No shared state between sources — each function is independent
- Easier to mock in tests (`@patch("src.ingestion.orchestrator.ingest_gmail")`)
- No framework coupling — works equally in sync CLI and async task worker contexts

**Why not a registry/plugin pattern:**
- Only 5 sources, no external plugin need
- Explicit functions are easier to read and type-check than dynamic dispatch
- Source-specific parameters (Gmail `query`, YouTube `use_oauth`) don't fit a uniform interface

### Decision: Lazy imports inside orchestrator functions

Each orchestrator function imports its service classes inside the function body (not at module level). This preserves the current lazy-loading pattern that prevents circular imports and avoids loading heavy dependencies (Google API clients, httpx) until actually needed.

### Decision: Uniform `int` return type

All orchestrator functions return `int` (number of items ingested). Source-specific metadata (RSS `failed_sources`, `redirected_sources`) is handled by:
- The orchestrator function logs warnings/errors internally
- The CLI can call the underlying service directly when it needs rich result data (e.g., RSS redirects display)

**Alternative considered:** Return a `SourceIngestionResult` dataclass with `items_ingested`, `warnings`, `errors`. Rejected as over-engineering for now — the CLI's RSS command is the only consumer that needs rich results, and it can access the service directly for that.

**Compromise:** The RSS orchestrator function returns `int` but also accepts an optional callback for redirect/failure reporting:

```python
def ingest_rss(*, ..., on_result: Callable[[IngestionResult], None] | None = None) -> int:
    result = service.ingest_content(...)
    if on_result:
        on_result(result)
    return result.items_ingested
```

This keeps the uniform return type while allowing the CLI to capture the full `IngestionResult` when needed.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Orchestrator becomes a "god module" | Keep functions thin (~10 lines each): import → instantiate → call → return |
| Source-specific CLI options bypass orchestrator | Accept: CLI commands that need non-standard behavior (e.g., podcast `--no-transcribe` with custom sources) can still call services directly |
| Test mocking changes break existing tests | Migrate tests incrementally: update call sites one at a time, not all at once |

## Open Questions

- Should the `on_result` callback pattern for RSS be used from the start, or deferred until the CLI is refactored to use orchestrator functions? (Recommend: include from the start — it's 3 lines of code.)
