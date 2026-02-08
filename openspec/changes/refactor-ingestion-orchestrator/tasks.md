## 1. Create orchestrator module

- [x] 1.1 Create `src/ingestion/orchestrator.py` with `ingest_gmail()`, `ingest_rss()`, `ingest_youtube()`, `ingest_podcast()`, `ingest_substack()` functions
- [x] 1.2 Each function: lazy-imports its service classes, instantiates, calls, returns `int`
- [x] 1.3 YouTube function encapsulates the 3-call pattern: playlists + channels + RSS feeds (across 2 service classes)
- [x] 1.4 RSS function accepts optional `on_result` callback for rich result reporting
- [x] 1.5 Substack function handles `service.close()` in a `try/finally` block

## 2. Write orchestrator unit tests

- [x] 2.1 Create `tests/ingestion/test_orchestrator.py`
- [x] 2.2 Test each orchestrator function with mocked service classes (patch at source module)
- [x] 2.3 Test YouTube function calls all 3 methods across both service classes
- [x] 2.4 Test RSS `on_result` callback receives the `IngestionResult`
- [x] 2.5 Test Substack calls `service.close()` even on exception
- [x] 2.6 Test each function returns `int` (not `IngestionResult` or other types)

## 3. Migrate pipeline to use orchestrator

- [x] 3.1 Refactor `_run_ingestion_stage_async()` in `pipeline_commands.py` to call orchestrator functions via `asyncio.to_thread()`
- [x] 3.2 Remove direct service imports from `pipeline_commands.py`
- [x] 3.3 Update `tests/cli/test_pipeline_commands.py` — mock orchestrator functions instead of individual services
- [x] 3.4 Update `tests/cli/test_pipeline_integration.py` — mock orchestrator functions instead of individual services
- [x] 3.5 Verify all pipeline tests pass

## 4. Migrate task worker to use orchestrator

- [x] 4.1 Refactor `ingest_content` entrypoint in `tasks/content.py` to call orchestrator functions via `asyncio.to_thread()`
- [x] 4.2 Remove direct service imports from the `ingest_content` entrypoint
- [x] 4.3 Update task worker tests if any exist for `ingest_content`
- [x] 4.4 Verify task worker tests pass

## 5. Migrate CLI ingest commands to use orchestrator

- [x] 5.1 Refactor `gmail`, `rss`, `youtube`, `podcast`, `substack` commands to call orchestrator functions
- [x] 5.2 RSS command: use `on_result` callback to capture `IngestionResult` for redirect/failure display
- [x] 5.3 Podcast command: for `--no-transcribe`, continue calling service directly (orchestrator doesn't handle custom source overrides)
- [x] 5.4 Update `tests/cli/test_ingest_commands.py` — mock orchestrator functions instead of individual services
- [x] 5.5 Verify all CLI ingest tests pass

## 6. Final verification and cleanup

- [x] 6.1 Run full test suite (`pytest`)
- [x] 6.2 Run `ruff check` and `mypy` — no new warnings
- [x] 6.3 Verify no direct service imports remain in pipeline_commands.py or tasks/content.py (except for non-ingestion uses)
- [x] 6.4 Manual smoke test: `aca ingest rss --max 1 --days 1`
