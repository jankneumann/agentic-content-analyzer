# Tasks: CLI as Thin HTTP Client

## Phase 1: Foundation

- [x] **T1.1** Add `api_base_url: str` and `api_timeout: int` fields to `Settings` class in `src/config/settings.py`
- [x] **T1.2** Add `api:` section to `profiles/base.yaml` with `api_base_url: "http://localhost:8000"` and `api_timeout: 300`
- [x] **T1.3** Add `api_base_url` override to `profiles/railway.yaml` using `${API_BASE_URL:-}` interpolation
- [x] **T1.4** Add `_direct_mode` flag to `src/cli/output.py` with `is_direct_mode()` / `_set_direct_mode()` functions
- [x] **T1.5** Add `--direct` global callback to `src/cli/app.py` that calls `_set_direct_mode(True)`
- [x] **T1.6** Create `src/cli/api_client.py` with `ApiClient` class (httpx sync client, auth headers, typed methods)
- [x] **T1.7** Create `get_api_client()` factory function that reads from `get_settings()`
- [x] **T1.8** Create `src/cli/progress.py` with `stream_job_progress()` SSE consumer (Rich spinner + JSON mode)
- [ ] **T1.9** Write tests: `tests/cli/test_api_client.py` (mock httpx transport), `tests/cli/test_progress.py`
- [ ] **T1.10** Write tests: `tests/config/test_settings_api_url.py` (verify field defaults and profile loading)

## Phase 2: API Extensions

- [x] **T2.1** Extend `IngestRequest` in `src/api/content_routes.py` with source-specific optional fields (query, prompt, max_threads, recency_filter, context_size, transcribe, session_cookie, public_only, url, title, tags, notes)
- [x] **T2.2** Change `IngestRequest.max_results` default from `50` to `None` (let server-side config decide)
- [x] **T2.3** Pass source-specific fields through `_enqueue_ingestion_job()` payload in `content_routes.py`
- [x] **T2.4** Extend worker `ingest_content` handler source map in `src/queue/worker.py` to add: xsearch, perplexity, url
- [x] **T2.5** Add orchestrator imports for `ingest_xsearch`, `ingest_perplexity_search`, `ingest_url` in worker
- [x] **T2.6** Fix `ingest_gmail()` in `src/ingestion/orchestrator.py` to read `get_gmail_sources()` defaults when params are None
- [x] **T2.7** Update `REQUIRED_PAYLOAD_FIELDS` in `src/queue/setup.py` — make `max_results` optional for `ingest_content`
- [ ] **T2.8** Write tests: `tests/api/test_ingest_extended.py` (new source types), `tests/queue/test_worker_extended.py`
- [ ] **T2.9** Write tests: `tests/ingestion/test_orchestrator_gmail_config.py` (verify sources.d reading)

## Phase 3: CLI Ingestion Conversion

- [x] **T3.1** Extract current `gmail()` direct implementation to `_gmail_direct()` in `src/cli/ingest_commands.py`
- [x] **T3.2** Refactor `gmail()` command: try API → auto-fallback → direct mode
- [x] **T3.3** Repeat extraction + refactor for: rss, substack, youtube, youtube-playlist, youtube-rss, podcast
- [x] **T3.4** Repeat extraction + refactor for: xsearch, perplexity-search
- [x] **T3.5** Repeat extraction + refactor for: url (map to POST /api/v1/contents/ingest with source=url)
- [x] **T3.6** Keep `files` and `substack-sync` as direct-only (file upload multipart / config write)
- [ ] **T3.7** Write tests: `tests/cli/test_ingest_http.py` (mock ApiClient, verify HTTP path for each source)
- [ ] **T3.8** Update existing CLI tests to use `--direct` flag where they test direct behavior

## Phase 4: Pipeline API

- [ ] **T4.1** Extract pipeline stage functions from `src/cli/pipeline_commands.py` to `src/pipeline/runner.py`
- [ ] **T4.2** Create `src/api/pipeline_routes.py` with `POST /run` and `GET /status/{job_id}` endpoints
- [ ] **T4.3** Register `run_pipeline` handler in `src/queue/worker.py` that calls `src/pipeline/runner.py`
- [ ] **T4.4** Register pipeline router in `src/api/app.py`
- [ ] **T4.5** Add `run_pipeline` entrypoint to `ENTRYPOINT_LABELS` in `src/models/jobs.py`
- [ ] **T4.6** Refactor `src/cli/pipeline_commands.py` daily/weekly to: try API → fallback → direct
- [ ] **T4.7** Write tests: `tests/api/test_pipeline_routes.py`, `tests/pipeline/test_runner.py`

## Phase 5: Summarize + Digest CLI

- [ ] **T5.1** Add `summarize()` and `stream_summarize_status()` methods to `ApiClient`
- [ ] **T5.2** Refactor `src/cli/summarize_commands.py` `summarize_pending` to call `POST /api/v1/contents/summarize`
- [ ] **T5.3** Refactor `src/cli/summarize_commands.py` `summarize_id` to call same endpoint with `content_ids=[id]`
- [ ] **T5.4** Add `create_digest()` method to `ApiClient`
- [ ] **T5.5** Refactor `src/cli/digest_commands.py` to call `POST /api/v1/digests/generate`
- [ ] **T5.6** Write tests for summarize and digest HTTP paths

## Phase 6: Remaining CLI Commands

- [ ] **T6.1** Convert `src/cli/review_commands.py` (list, view, revise) to API calls
- [ ] **T6.2** Convert `src/cli/analyze_commands.py` (themes) to API call
- [ ] **T6.3** Convert `src/cli/podcast_commands.py` (generate, list-scripts) to API calls
- [ ] **T6.4** Convert `src/cli/job_commands.py` (list, show, retry, history) to API calls
- [ ] **T6.5** Convert `src/cli/settings_commands.py` (list, get, set) to API calls
- [ ] **T6.6** Convert `src/cli/prompt_commands.py` (list, show, set, reset, test) to API calls
- [ ] **T6.7** Write tests for all converted commands
