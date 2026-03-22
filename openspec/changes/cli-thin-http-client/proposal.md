# Proposal: CLI as Thin HTTP Client

## Summary

Refactor the `aca` CLI from direct service calls to a thin HTTP client that calls the backend API via `httpx`. The CLI uses profile-based `api_base_url` to target local dev (`localhost:8000`) or cloud Railway backends.

## Problem

The CLI and API are two separate implementations of the same business logic:

1. **CLI path**: `ingest_commands.py` → `orchestrator.py` → services (synchronous, inline, no job tracking)
2. **API path**: `content_routes.py` → `enqueue_queue_job()` → `worker.py` → `orchestrator.py` (async, tracked in `pgqueuer_jobs`)

This dual-path causes:

- **Invisible CLI operations**: `aca ingest gmail` creates no `pgqueuer_jobs` entries — the job tracker shows nothing
- **Config ignored**: Gmail orchestrator defaults to `max_results=10` instead of reading `sources.d/gmail.yaml` (`max_results: 50`)
- **Code duplication**: Business logic (source mapping, error handling, progress) exists in both CLI commands and API endpoints
- **Inconsistent behavior**: API respects job queue concurrency/retry; CLI does not

## Solution

Make the CLI a thin HTTP client that calls the same API endpoints the web frontend uses:

```
Before:  CLI → orchestrator → services (inline)
After:   CLI → httpx → API → job queue → worker → orchestrator → services
```

### Key Design Decisions

1. **Profile-aware targeting**: `api_base_url` in Settings + profiles routes CLI to local or cloud backend
2. **`--direct` fallback**: Global flag preserves current direct-call behavior for offline/dev use
3. **Auto-fallback**: If API unreachable and no `--direct`, warn and execute directly (never worse than today)
4. **SSE progress**: CLI streams `GET /api/v1/contents/ingest/status/{task_id}` for Rich progress display
5. **Server-side config**: `sources.d/*.yaml` defaults applied by orchestrator (server-side), not CLI (client-side)

## Scope

### In Scope

- **41 CLI commands** converted to HTTP wrappers (see audit below)
- New `api_base_url` Settings field + profile wiring
- Shared `ApiClient` class in `src/cli/api_client.py`
- Extended `IngestRequest` for all source types (xsearch, perplexity, url, podcast options)
- Extended worker `source_map` for missing sources
- New `POST /api/v1/pipeline/run` endpoint
- Pipeline runner extracted to shared `src/pipeline/runner.py`
- Gmail orchestrator reads `sources.d/gmail.yaml` defaults

### Out of Scope

- **30 CLI commands** that remain direct (profiles, neon, sync, worker, graph)
- `substack-sync` (writes config files — not a job queue operation)
- Frontend changes
- New database migrations

## CLI Command Audit

| Category | Convert | Add API + Convert | Keep Direct |
|----------|:-------:|:-----------------:|:-----------:|
| Ingest (10) | 8 | 2 (xsearch, perplexity) | 0 |
| Summarize (3) | 1 | 2 | 0 |
| Digest (2) | 2 | 0 | 0 |
| Pipeline (2) | 0 | 2 | 0 |
| Review (3) | 3 | 0 | 0 |
| Analyze (1) | 1 | 0 | 0 |
| Podcast (2) | 2 | 0 | 0 |
| Jobs (6) | 5 | 1 (cleanup) | 0 |
| Settings (3) | 3 | 0 | 0 |
| Prompts (7) | 5 | 2 (export/import) | 0 |
| Profile (5) | 0 | 0 | 5 |
| Neon (5) | 0 | 0 | 5 |
| Sync (3) | 0 | 0 | 3 |
| Worker (1) | 0 | 0 | 1 |
| Graph (2) | 0 | 0 | 2 |
| Manage (5) | 1 | 1 | 3 |
| **Total (60)** | **31** | **10** | **19** |

## Success Criteria

1. All `aca ingest *` commands create visible `pgqueuer_jobs` entries
2. `aca ingest gmail` with no flags ingests 50 items (from `sources.d/gmail.yaml`)
3. `aca pipeline daily` creates a trackable pipeline job
4. `aca --direct ingest gmail` preserves current behavior
5. `PROFILE=railway aca ingest gmail` targets the Railway backend
6. All existing CLI tests pass (direct mode)
7. New tests verify HTTP client path with mocked API
