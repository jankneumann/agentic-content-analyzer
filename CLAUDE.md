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
| [Content Capture](docs/CONTENT_CAPTURE.md) | Chrome extension, bookmarklet, save URL API |
| [Search](docs/SEARCH.md) | Hybrid BM25+vector search, embedding providers, chunking |
| [Deployment](docs/MOBILE_DEPLOYMENT.md) | Railway deployment, Docker, migrations, CORS |
| [Desktop](docs/DESKTOP_DEPLOYMENT.md) | Tauri desktop app: build, distribute, remote backend, CORS |
| [**ACA Agents**](docs/ACA-AGENTS.md) | Agentic analysis: personas, specialists, memory, approvals, scheduling |
| [Gotchas](docs/GOTCHAS.md) | Comprehensive list of pitfalls organized by area |
| [OpenBao](docs/OPENBAO.md) | OpenBao secrets management: setup, AppRole, seeding, audit events |

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

# Full pipeline
aca pipeline daily                     # Ingest -> summarize -> digest

# Content ingestion
aca ingest gmail|rss|substack|youtube|podcast|xsearch|perplexity-search|scholar
aca ingest files <path...>             # Local files
aca ingest url <url>                   # Direct URL

# Processing
aca summarize pending                  # Summarize pending content
aca create-digest daily|weekly         # Create digest

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

**Settings** — YAML defaults in `settings/`: `prompts.yaml` (prompt templates), `models.yaml` (model registry + defaults), `voice.yaml` (TTS config), `notifications.yaml` (event toggles). Loaded via `ConfigRegistry` (`src/config/config_registry.py`). Override precedence: env var > DB override > YAML default.

**Sources** — YAML files in `sources.d/`: `rss.yaml`, `youtube_playlist.yaml`, `youtube_rss.yaml`, `podcasts.yaml`, `gmail.yaml`, `websearch.yaml`, `scholar.yaml`. Each supports `name`, `url`/`id`, `tags`, `enabled`, `max_entries`. See [docs/SETUP.md](docs/SETUP.md) for source-specific options.

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
| MCP tools use new OpenAPI shapes | Breaking change from legacy `{scanned, references_found, dry_run}` etc. The 4 refactored tools return OpenAPI-aligned shapes in BOTH HTTP and in-process modes. External consumers (only `agentic-assistant`) must migrate — see `openspec/changes/cloud-db-source-of-truth/MIGRATION.md`. |
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
