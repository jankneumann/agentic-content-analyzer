# CLAUDE.md

Quick reference for Claude Code. Detailed docs in `/docs` directory.

## Documentation Index

| Doc | Purpose |
|-----|---------|
| [**User Guide**](docs/USER_GUIDE.md) | End-user documentation: setup, features, workflows, deployment |
| [Setup](docs/SETUP.md) | Environment setup, providers, configuration |
| [Profiles](docs/PROFILES.md) | Profile-based configuration, inheritance, secrets |
| [Architecture](docs/ARCHITECTURE.md) | System design, ingestion, parsers, data models |
| [Development](docs/DEVELOPMENT.md) | Commands, patterns, database, testing |
| [Testing](docs/TESTING.md) | Test categories, factories, E2E, Hoverfly, integration fixtures |
| [Model Config](docs/MODEL_CONFIGURATION.md) | LLM selection, providers, costs |
| [Content Guidelines](docs/CONTENT_GUIDELINES.md) | Digest quality standards |
| [Review System](docs/REVIEW_SYSTEM.md) | Digest/script review workflow, audio digests |
| [UX Design](docs/UX_DESIGN.md) | Frontend patterns |
| [Markdown Pipeline](docs/MARKDOWN_PIPELINE_DESIGN.md) | End-to-end markdown flow |
| [Case Studies](docs/CASE_STUDIES.md) | Refactoring lessons, migration patterns |
| [Content Capture](docs/CONTENT_CAPTURE.md) | Chrome extension, bookmarklet, canonical ingestions |
| [Mobile Capture](docs/MOBILE_CAPTURE.md) | iOS Shortcut, bookmarklet, web save page |
| [API consumers](docs/API_CONSUMERS.md) | Independently deployed clients and compatibility windows |
| [Unified workflow cutover](docs/UNIFIED_WORKFLOW_CUTOVER.md) | July 2026 `/api/v1` contract 2.0.0 production evidence |
| [Obsidian Vault Ingest](docs/OBSIDIAN_VAULT_INGEST.md) | Web Clipper vault ingress: allowed roots, clip contract, privacy, troubleshooting |
| [Search](docs/SEARCH.md) | Hybrid BM25+vector search, embedding providers, chunking |
| [Deployment](docs/MOBILE_DEPLOYMENT.md) | Railway deployment, Docker, migrations, CORS |
| [**Backup & Restore**](docs/BACKUP_RESTORE.md) | gx-10 off-site backup: `aca backup`, age encryption, key escrow, multi-store restore runbook |
| [Deploy Secrets](docs/DEPLOY_SECRETS.md) | `aca deploy sync-secrets`: push local secrets to Railway (allowlist, dry-run) |
| [Desktop](docs/DESKTOP_DEPLOYMENT.md) | Tauri desktop app: build, distribute, remote backend, CORS |
| [**ACA Agents**](docs/ACA-AGENTS.md) | Agentic analysis: personas, specialists, memory, approvals, scheduling |
| [Gotchas](docs/GOTCHAS.md) | Comprehensive list of pitfalls organized by area |
| [OpenBao](docs/OPENBAO.md) | OpenBao secrets management: setup, AppRole, seeding, audit events |
| [Improvement Roadmap](docs/IMPROVEMENT_ROADMAP.md) | Ingestion-reliability diagnosis + phased engineering roadmap (2026-07) |

**Always use Context7 MCP** for library/API documentation, code generation, or setup steps for external libraries.

## Project Overview

An agentic AI solution for aggregating and summarizing AI newsletters into daily and weekly digests.

- **Purpose**: Help technical leaders and developers stay informed on AI/Data trends
- **Sources**: Gmail newsletters, Substack RSS feeds, YouTube playlists, X/Twitter (via Grok), Perplexity Sonar API, file uploads, direct URLs
- **Output**: Structured digests with knowledge graph-powered historical context

## Essential Commands

```bash
# Setup
source .venv/bin/activate && docker compose up -d && alembic upgrade head

# Development servers
make dev-bg        # Start frontend + backend in background
make dev-logs      # View logs
make dev-stop      # Stop servers

# Full durable pipeline
aca pipeline run --period daily --period-start 2026-07-15T00:00:00Z --period-end 2026-07-16T00:00:00Z --wait

# Content ingestion
aca ingest gmail|rss|substack|youtube-playlist|podcast|x-search|perplexity-search|scholar-search
aca ingest files <path...>             # Local files
aca ingest url <url>                   # Direct URL

# Processing
aca summarize run --wait               # Summarize pending content
aca digest create --type daily --period-start 2026-07-15T00:00:00Z --period-end 2026-07-16T00:00:00Z
aca operations list                    # Observe durable work

# Agentic analysis
aca agent task "prompt"                # Submit analysis task
aca agent status [task-id]             # Check task status
aca agent insights --type trend        # Browse insights
aca agent personas                     # List personas
aca agent schedule                     # Manage schedules

# LLM Router Evaluation
aca evaluate list-datasets             # List evaluation datasets
aca evaluate create-dataset --step summarization  # Create dataset
aca evaluate run <dataset-id>          # Run judge evaluation
aca evaluate calibrate --step summarization       # Calibrate threshold
aca evaluate report                    # Cost savings report

# Off-site backup (gx-10)
aca backup run                         # capture every store; non-zero if any failed
aca backup verify                      # preflight binaries + prove the canary decrypts
aca backup list                        # read-only listing under the configured prefix
python scripts/backup_retention.py     # lifecycle rules; DRY RUN unless --apply

# Model registry freshness
aca models discover                    # Catalog models not yet in the registry
aca models refresh [--apply]           # Pricing diffs (dry-run default; --apply writes models.yaml)
aca models propose-default --step <step> --candidate <model> [--approve]  # Gated default swap

# Testing
pytest                                  # All tests
pytest tests/api/ -v                   # API tests
cd web && pnpm test:e2e                # Playwright E2E tests
make test-regression-all               # All regression tests
pytest -m hoverfly -v                  # Hoverfly HTTP simulation
pytest tests/contract/ -m contract -v --no-cov  # Contract & fuzz tests
```

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the full command reference including profile-based dev, stack management, E2E live tests, neon branching, and job management.

## Configuration

**Profiles** (recommended): `export PROFILE=local` then see [docs/PROFILES.md](docs/PROFILES.md)

**Traditional .env** (still supported):
```bash
DATABASE_URL=postgresql://localhost/newsletters
NEO4J_URL=bolt://localhost:7687
GRAPHDB_PROVIDER=neo4j|falkordb
GRAPHDB_MODE=local|cloud|embedded
ANTHROPIC_API_KEY=sk-ant-...
ADMIN_API_KEY=your-admin-key
ENVIRONMENT=development
```

**Providers** — each has multiple backends, configured via `*_PROVIDER` env vars:
- **Database**: `local` | `supabase` | `neon` | `railway` — see [docs/SETUP.md](docs/SETUP.md)
- **Storage**: `local` | `s3` | `supabase` | `railway` — see [docs/SETUP.md](docs/SETUP.md)
- **Graph DB**: `neo4j` | `falkordb` — modes: `local` | `cloud` | `embedded` — see [docs/SETUP.md](docs/SETUP.md)
- **Observability**: `noop` | `opik` | `braintrust` | `langfuse` | `otel` — see [docs/SETUP.md](docs/SETUP.md)

**Models** — configurable per pipeline step:
```bash
MODEL_SUMMARIZATION=claude-haiku-4-5
MODEL_THEME_ANALYSIS=claude-sonnet-4-5
MODEL_DIGEST_CREATION=claude-sonnet-4-5
MODEL_YOUTUBE_PROCESSING=gemini-2.5-flash
```

See [docs/MODEL_CONFIGURATION.md](docs/MODEL_CONFIGURATION.md) for full list.

**Gemini batch infrastructure** — Disabled by default. `GEMINI_BATCH_ENABLED`
must be true and the relevant `settings/models.yaml` `batch_execution` mode must
be `batch` before collection is enabled. No production step opts in yet. Worker
maintenance is internal and protected by a PostgreSQL advisory lock; the CLI
exposes read-only `aca batch status` and `aca evaluate batch-savings` commands.
Phase 0 supports inline requests below 18 MiB only. See
[docs/MODEL_CONFIGURATION.md#gemini-batch-infrastructure](docs/MODEL_CONFIGURATION.md#gemini-batch-infrastructure).

**Settings** — YAML defaults in `settings/`: `prompts.yaml` (prompt templates), `models.yaml` (model registry + defaults), `voice.yaml` (TTS config), `notifications.yaml` (event toggles), `filtering.yaml` (ingestion filter). Loaded via `ConfigRegistry` (`src/config/config_registry.py`). Override precedence: env var > DB override > YAML default.

**Ingestion filter** — Three-tier (heuristic → embedding → LLM) post-persist filter in `src/services/ingestion_filter.py`. Runs automatically after every adapter via the orchestrator hook (`src/ingestion/filter_hook.py`). Writes `filter_score`, `filter_decision`, `filter_tier`, `priority_bucket` on `Content`; skipped items get `status=FILTERED_OUT`. Distinct from `src/services/content_filter.py`, which is the pre-persist adapter-side keyword filter. CLI: `aca filter explain|rerun|stats`; `aca ingest --no-filter | --filter-dry-run`.

**Sources** — YAML files in `sources.d/`: `rss.yaml`, `youtube_playlist.yaml`, `youtube_channel.yaml` (channels via paginated Data API — uploads-playlist path, no 15-item cap), `podcasts.yaml`, `gmail.yaml`, `websearch.yaml`, `scholar.yaml`. The `youtube_rss` source type still works (Atom feeds, capped ~15, no API key) but ships with no default file. Each supports `name`, `url`/`id`, `tags`, `enabled`, `max_entries`. See [docs/SETUP.md](docs/SETUP.md) for source-specific options.

**Source DB overrides** — Sources can also be added/edited/disabled at runtime (no YAML commit) via database overrides merged on top of the YAML defaults inside `load_sources_config()` (`src/config/sources.py`). Precedence is DB over YAML, keyed by the natural key `<type>:<locator>` (`source_key()`); a DB row with `enabled:false` shadows its YAML twin. Storage: `source_overrides` table + `SourceOverrideService` (validates each `config` against the `Source` union). Manage via CLI `aca sources add|list|remove|enable|disable`, the `/api/v1/sources` write endpoints (admin-key), or the web **Settings → Sources** tab. The merge fails open to YAML-only when the DB is unavailable.

**Canonical workflows** — CLI, HTTP, MCP, and frontend mutations submit the same eight operation types to `OperationService`; none may execute ingestion, summarization, digest, pipeline, or audio work inline. Extend ingestion only through `src/ingestion/registry.py`, then update the generated contracts and the exact-key fixture registry in `tests/fixtures/sources/`. Digest and podcast code must consume the immutable `ResolvedContentSet` and persisted content/summary IDs rather than re-querying a period.

## Critical Gotchas (Top 10)

The full list is in [docs/GOTCHAS.md](docs/GOTCHAS.md). These are the ones that waste the most time:

| Issue | Solution |
|-------|----------|
| Alembic multiple heads | Run `alembic heads` to detect; fix with `alembic merge heads -m "..."` |
| PG enum + Python StrEnum mismatch | Adding to StrEnum requires `ALTER TYPE ... ADD VALUE` migration |
| `autoflush=False` + dedup loop | `db.add()` without `db.flush()` — rows invisible to subsequent SELECTs |
| Settings tests pick up .env | Pass `_env_file=None` to `Settings()` to isolate tests |
| Prompt API auth header | `X-Admin-Key` (NOT `X-Admin-API-Key` or `Authorization`) |
| `.secrets.yaml` uses YAML syntax | Must use `:` not `=`; `KEY=value` silently fails |
| Playwright strict mode | Use `.first()`, `{ exact: true }`, or scope to parent when multiple matches |
| Railway PORT is dynamic | Use `${PORT:-8000}` in CMD; never hardcode in Dockerfile |
| pgvector not in ORM | `DocumentChunk.embedding` is raw SQL only; `embedding_provider`/`embedding_model` ARE mapped |
| Mock patch lazy imports | Patch at SOURCE module (`src.X.Y`), not consumer — lazy `from X import Y` creates local vars |
| `content_references` dual uniqueness | Refs with `external_id` use `uq_content_reference` constraint; URL-only refs use partial index `uq_content_reference_url` — `store_references()` handles both paths |
| `neo4j_provider` deprecated | Use `graphdb_provider` + `graphdb_mode` instead — old field auto-mapped with deprecation warning |
| Middleware order is LIFO (outer-first-call) | `app.add_middleware(X)` PREPENDS X to the outer stack. Order-in-code = trace, audit, auth, CORS ⇒ runtime outer→inner = trace → audit → auth → CORS. Getting this wrong means 401/403 audit-log rows go missing. See `src/api/app.py` + `tests/api/test_audit_ordering.py`. |
| pg_cron + Railway managed PG | `current_setting('app.*')` GUC variables are restricted. For values that must persist across restarts (e.g., retention days), interpolate the value into the SQL at Alembic migration time — see `alembic/versions/b7a1c9d5e2f0_add_audit_log_table.py` for the pattern. |
| `admin_key_fp` is always-fingerprint | Compute SHA-256 last-8 from the raw `X-Admin-Key` header whenever present, including invalid keys. NULL only when the header is absent. Lets you correlate credential-probing attempts from a single attacker. |
| MCP tools use canonical structured contracts | All MCP toolsets select one transport mode for the process, return native OpenAPI-aligned objects, and raise typed protocol errors. HTTP mode must never fall back to local persistence. External consumers (only `agentic-assistant`) must migrate from legacy response shapes — see `openspec/changes/cloud-db-source-of-truth/MIGRATION.md`. |
| Workflow mutations are always durable | Use `OperationService` or the canonical `/api/v1/*` submission routes. Do not restore direct CLI execution, `BackgroundTasks`, legacy `/contents/*` mutations, or transport-owned source maps. |
| Optional query parameters at HTTP boundaries | `httpx` serializes `None` values as empty query values. Build cursor-page params so absent values are omitted; keep strict server cursor validation and assert the actual serialized URL in transport tests. |
| CLI JSON output purity | Stdout contains one JSON document; logging and diagnostics belong on stderr. Tests for auto-selected external transports must pass the transport flag explicitly (for example `--via-rss`) so local credentials cannot trigger live calls. |
| The pg_cron backup never worked | `railway/postgres/init-backup-job.sql` failed at four independent points and never produced a backup. Backups are `aca backup run` + a systemd timer. `railway_backup_schedule` / `railway_backup_retention_days` are **inert** — no Python consumer, ever. See [GOTCHAS](docs/GOTCHAS.md#the-pg_cron-backup-never-produced-a-backup). |
| A backup that reports success is the failure mode | A shell pipeline reports the LAST stage's status, so `pg_dump` dying halfway still yields zero from the uploader. `src/services/backup/executor.py` checks EVERY stage, reads the stored size back, and refuses to record a store with no digest. Never replace it with `sh -c 'a \| b \| c'`. |
| Widening `WorkflowTerminalSourceKind` is never enough | A new source kind is rejected at **13** closed points: 3 CHECK constraints (in three copies of the DDL), 7 in `workflow_alert_models.py`, 4 on the emission path in `workflow_terminal_event_service.py` (including `_event_from_row`), plus `_validate_event_key` in `src/telemetry/workflow_events.py` and `WorkflowTerminalEventDiagnostic.source_kind` (regenerate from `openapi/v1.yaml`, never hand-edit). Each fails SILENTLY and DIFFERENTLY: the first eleven as `classification_status='rejected'` with no delivery; the telemetry one as `emitted=False`, so the alert ships with no log line, no metric, and no `telemetry_emitted_at`; the diagnostic one as a 500 on the very URL the alert carries as its `diagnostic_url`. Prove a new kind end to end with the REAL emitter and the REAL diagnostic projection (`tests/unit/test_system_check_alert_emission.py`) — a stubbed `telemetry_emitter` hid the twelfth point through three review rounds. |
| `ruff S608` on multi-line SQL strings | `# noqa: S608` span is single-line. Prefer single-line f-strings so the noqa covers the violation line, OR put the noqa on the LINE where `SELECT`/`DELETE` appears — not the closing paren line. Otherwise you get a RUF100 "unused noqa" flip-flop. |

## Quick Links by Task

### Writing Code
- [Database patterns](docs/DEVELOPMENT.md#database-patterns) | [Frontend patterns](docs/DEVELOPMENT.md#reactfrontend-patterns) | [Error handling](docs/DEVELOPMENT.md#error-handling)

### Working with Content
- [Ingestion services](docs/ARCHITECTURE.md#ingestion-services) | [Parser ecosystem](docs/ARCHITECTURE.md#parser-ecosystem) | [Data models](docs/ARCHITECTURE.md#data-models)
- **Content References**: `src/services/reference_extractor.py` (extraction), `src/services/reference_resolver.py` (resolution), `src/services/reference_hook.py` (ingestion hooks)
- CLI: `aca manage extract-refs` (backfill), `aca manage resolve-refs` (resolve batch)

### Testing
- [Testing guide](docs/TESTING.md) | [E2E Playwright](docs/TESTING.md#e2e-testing-playwright) | [Hoverfly simulation](docs/TESTING.md#hoverfly-api-simulation) | [Contract tests](tests/contract/)
- E2E infrastructure: `web/tests/e2e/fixtures/` (page objects, API mocks, mock data factories)
- Regression: `tests/regression/` (API), `tests/cli/test_regression_daily_pipeline.py` (CLI), `web/tests/e2e/regression/` (UX)

### Deployment
- [Railway guide](docs/MOBILE_DEPLOYMENT.md) | [Desktop/Tauri](docs/DESKTOP_DEPLOYMENT.md) | [Docker entrypoint](docs/MOBILE_DEPLOYMENT.md#docker-entrypoint-pattern)

### Agentic Analysis
- [ACA Agents guide](docs/ACA-AGENTS.md) | [Personas](docs/ACA-AGENTS.md#personas) | [Schedules](docs/ACA-AGENTS.md#schedules) | [Approval gates](docs/ACA-AGENTS.md#approval-gates)
- Key files: `src/agents/conductor.py` (orchestrator), `src/agents/specialists/` (4 specialists), `src/services/agent_service.py` (CRUD)
- Config: `settings/personas/` (persona YAML), `settings/schedule.yaml` (cron), `settings/approval.yaml` (risk levels)

### Review & Delivery
- [Digest review](docs/REVIEW_SYSTEM.md) | [Podcast generation](docs/REVIEW_SYSTEM.md#podcast-scripts) | [Audio digests](docs/REVIEW_SYSTEM.md#audio-digests)
