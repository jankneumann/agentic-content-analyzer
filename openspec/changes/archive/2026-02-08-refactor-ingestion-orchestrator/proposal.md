# Change: Extract shared ingestion orchestrator layer

## Why

Ingestion service wiring is duplicated across three call sites — CLI commands (`ingest_commands.py`), pipeline (`pipeline_commands.py`), and task worker (`tasks/content.py`). Each independently imports, instantiates, and calls the same ingestion services with slightly different code. This DRY violation directly caused the YouTube RSS bug (PR #7743230): `YouTubeRSSIngestionService` was missing from 2 of 3 call sites because each was maintained separately. When a new source or service class is added, all three files must be updated identically — and there is no mechanism to enforce this.

## What Changes

- **New module `src/ingestion/orchestrator.py`**: Shared orchestrator functions that encapsulate the "wire up and call" logic for each ingestion source. Each function accepts the same parameters (max_results, after_date, force_reprocess) and returns a uniform `int` (items ingested).
- **CLI `ingest_commands.py`**: Each `aca ingest <source>` command delegates to the corresponding orchestrator function instead of directly importing and calling service classes.
- **Pipeline `pipeline_commands.py`**: `_run_ingestion_stage_async()` delegates to orchestrator functions instead of duplicating service wiring.
- **Task worker `tasks/content.py`**: `ingest_content` entrypoint delegates to orchestrator functions instead of duplicating service wiring.
- **No job queue requirement for CLI**: The orchestrator functions are plain synchronous functions — CLI calls them directly, while pipeline and task worker wrap them in `asyncio.to_thread()`.

## Sequencing

This is a **prerequisite** for `split-youtube-playlist-rss-config`. The orchestrator centralizes ingestion wiring so the YouTube split only needs to add new orchestrator functions (`ingest_youtube_playlist()`, `ingest_youtube_rss()`) in one place — instead of modifying CLI, pipeline, and task worker independently.

**Order:** `refactor-ingestion-orchestrator` → `split-youtube-playlist-rss-config`

## Impact

- Affected specs: `cli-interface`, `pipeline`
- Affected code:
  - `src/ingestion/orchestrator.py` (new)
  - `src/cli/ingest_commands.py` (simplify to delegate)
  - `src/cli/pipeline_commands.py` (simplify `_run_ingestion_stage_async`)
  - `src/tasks/content.py` (simplify `ingest_content` entrypoint)
  - `tests/` — test mocks shift from patching individual services to patching orchestrator functions
- No breaking changes to CLI interface, API, or database
- No new dependencies
