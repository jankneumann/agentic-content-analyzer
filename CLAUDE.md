
# CLAUDE.md

Quick reference for Claude Code. Detailed docs in `/docs` directory.

## Documentation Index

| Doc | Purpose |
|-----|---------|
| [**User Guide**](docs/USER_GUIDE.md) | **End-user documentation: setup, features, workflows, deployment** |
| [Setup](docs/SETUP.md) | Environment setup, configuration |
| [Profiles](docs/PROFILES.md) | Profile-based configuration, inheritance, migration |
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

**Always use Context7 MCP** for library/API documentation, code generation, or setup steps for external libraries.

## Project Overview

An agentic AI solution for aggregating and summarizing AI newsletters into daily and weekly digests.

- **Purpose**: Help technical leaders and developers stay informed on AI/Data trends
- **Sources**: Gmail newsletters, Substack RSS feeds, YouTube playlists, X/Twitter (via Grok), Perplexity Sonar API, file uploads, direct URLs
- **Output**: Structured digests with knowledge graph-powered historical context

## Key Commands

```bash
# Setup
source .venv/bin/activate && docker compose up -d && alembic upgrade head

# Development servers
make dev-bg        # Start frontend + backend in background
make dev-logs      # View logs
make dev-stop      # Stop servers

# Profile-based development
make dev-local     # Start with PROFILE=local (no observability)
make dev-opik      # Start with PROFILE=local-opik (requires: make opik-up)
make dev-supabase  # Start with PROFILE=local-supabase (requires: make supabase-up)
make dev-staging   # Start with PROFILE=staging (remote backends + Braintrust)

# Opik observability stack
make opik-up       # Start Opik stack (waits for health)
make opik-down     # Stop Opik stack
make opik-logs     # Tail Opik logs

# Langfuse observability stack
make langfuse-up       # Start Langfuse stack (waits for health)
make langfuse-down     # Stop Langfuse stack
make langfuse-logs     # Tail Langfuse logs
make dev-langfuse      # Start with PROFILE=local-langfuse (requires: make langfuse-up)

# Local Supabase stack (alternative to core postgres)
make supabase-up   # Start Supabase stack (DB + storage)
make supabase-down # Stop Supabase stack
make supabase-logs # Tail Supabase logs
make dev-supabase  # Start with PROFILE=local-supabase (requires: make supabase-up)

# Crawl4AI browser server (JS content extraction)
make crawl4ai-up   # Start Crawl4AI Docker server (port 11235)
make crawl4ai-down # Stop Crawl4AI server
make crawl4ai-logs # Tail Crawl4AI logs
make test-crawl4ai # Run Crawl4AI integration tests

# Full stack management
make full-up       # Start core services + Opik
make full-down     # Stop all services (including Supabase if running)

# Verification
make verify-profile  # Verify API health and current profile
make verify-opik     # Verify Opik receives traces
make verify-staging  # Verify staging profile connectivity

# Content Ingestion (aca CLI)
aca ingest gmail                       # Gmail newsletters
aca ingest rss                         # RSS feeds
aca ingest substack                    # Substack paid subscriptions
aca ingest substack-sync               # Sync subs: paid→substack.yaml, free→rss.yaml
aca ingest youtube                     # YouTube (all: playlists + RSS)
aca ingest youtube-playlist            # YouTube playlists only (OAuth)
aca ingest youtube-rss                 # YouTube RSS feeds only
aca ingest podcast                     # Podcast feeds
aca ingest xsearch                     # X/Twitter via Grok API search
aca ingest xsearch --prompt "..."      # Custom search prompt
aca ingest perplexity-search           # Perplexity Sonar API search
aca ingest perplexity-search -p "..."  # Custom search prompt
aca ingest perplexity-search -m 20     # Limit results
aca ingest perplexity-search --recency week  # Recency filter
aca ingest scholar                     # Academic papers (Semantic Scholar)
aca ingest scholar-paper <id>          # Single paper by DOI/arXiv/S2 ID
aca ingest scholar-paper <id> --with-refs  # Paper + its references
aca ingest scholar-refs                # Extract & ingest refs from existing content
aca ingest scholar-refs --after 2025-01-01 --dry-run  # Preview extraction
aca ingest files <path...>             # Local file ingestion
aca ingest url <url>                   # Direct URL ingestion

# Processing
aca summarize pending                  # Summarize pending content
aca summarize pending --source gmail,rss  # Filter by source type
aca summarize pending --status pending    # Filter by status
aca summarize pending --after 2025-01-01 --before 2025-01-31  # Date range
aca summarize pending --publication "AI Weekly"  # Filter by publication
aca summarize pending --search "LLM"     # Search by title
aca summarize pending --dry-run          # Preview without executing
aca create-digest daily                # Create daily digest
aca create-digest weekly               # Create weekly digest
aca create-digest daily --source gmail   # Filter content by source
aca create-digest daily --dry-run        # Preview matching content
aca pipeline daily                     # Full daily pipeline (ingest → summarize → digest)

# Review & Delivery
aca review list                        # List pending reviews
aca review view <id>                   # View digest content
aca analyze themes                     # Analyze themes across content
aca podcast generate --digest-id <id>  # Generate podcast script

# Prompt Management
aca prompts list                       # List all prompts grouped by category
aca prompts list --category pipeline   # Filter by category
aca prompts list --overrides-only      # Show only overridden prompts
aca prompts show <key>                 # View prompt value and metadata
aca prompts set <key> --value "..."    # Set prompt override
aca prompts set <key> --file path.txt  # Set from file
aca prompts reset <key>                # Reset to default
aca prompts test <key> --var k=v       # Test template rendering
aca prompts export --output prompts.yaml  # Export all prompts
aca prompts import --file prompts.yaml    # Import overrides

# Management
aca manage verify-setup                # Check service connectivity
aca manage check-profile-secrets       # Find unresolved secrets
aca manage backfill-chunks             # Index existing content for search
aca manage backfill-chunks --dry-run   # Preview what would be indexed
aca manage backfill-chunks --embed-only # Fill missing embeddings only
aca manage switch-embeddings            # Switch embedding provider (interactive)
aca manage switch-embeddings --dry-run  # Preview switch without changes

# Job Queue Workers (embedded worker runs automatically with API)
aca worker start                       # Standalone worker (optional, 5 concurrent tasks)
aca worker start --concurrency 10      # Custom concurrency (max 20)

# Job Management
aca jobs list                          # List all jobs
aca jobs list --status failed          # Filter by status
aca jobs show <id>                     # View job details
aca jobs retry <id>                    # Retry a failed job
aca jobs retry --failed                # Retry all failed jobs
aca jobs cleanup --older-than 30d      # Clean up old completed jobs

# Neon Database Branching (agent workflows)
aca neon list                          # List all branches
aca neon create <name>                 # Create branch (e.g., claude/feature-xyz)
aca neon create <name> --parent main   # Create from specific parent
aca neon delete <name>                 # Delete a branch
aca neon connection <name>             # Print connection string
aca neon connection <name> --direct    # Direct URL (for migrations)
aca neon clean                         # Delete stale claude/ branches (>24h)
make neon-list                         # Shortcut: list branches
make neon-create NAME=claude/xyz       # Shortcut: create branch
make neon-clean                        # Shortcut: clean stale branches
make test-neon                         # Run Neon integration tests

# Testing
pytest                                  # All tests
pytest tests/api/ -v                   # API tests only
pytest -m hoverfly -v                  # Hoverfly HTTP simulation tests

# Hoverfly API Simulation (HTTP-level integration tests)
make hoverfly-up                        # Start Hoverfly (webserver mode)
make hoverfly-down                      # Stop Hoverfly
make test-hoverfly                      # Run Hoverfly integration tests

# Contract & Fuzz Testing (Schemathesis)
pytest tests/contract/ -m contract -v --no-cov  # All contract tests
pytest tests/contract/test_schema_conformance.py -m contract -v --no-cov  # Schema only
pytest tests/contract/test_fuzz.py -m contract -v --no-cov               # Fuzz only

# E2E Testing (Playwright)
cd web && pnpm test:e2e                 # All E2E tests (mocked, no backend needed)
cd web && pnpm test:e2e:ui             # Visual Playwright inspector
cd web && pnpm test:e2e:smoke          # Smoke tests (requires real backend)
cd web && pnpm test:e2e:regression     # Regression workflow tests (mocked, no backend)
cd web && pnpm exec playwright test tests/e2e/layout/  # Run specific folder
cd web && pnpm exec playwright show-report             # View HTML report

# Regression Testing (workflow consistency)
make test-regression                    # Python CLI + API contract regression tests
make test-regression-e2e               # Playwright UX workflow regression tests
make test-regression-all               # All regression tests (Python + Playwright)
pytest -m regression -v --no-cov       # Run regression tests directly

# Live E2E Pipeline Tests (requires running backend + LLM keys)
make test-e2e-live                      # Run live pipeline tests with LLM validation
E2E_EVALUATOR=opik make test-e2e-live   # Use Opik for evaluation scoring
E2E_EVALUATOR=langfuse make test-e2e-live # Use Langfuse for evaluation scoring
E2E_BASE_URL=http://localhost:8000 make test-e2e-live  # Custom backend URL
```

## Source Configuration

Configure ingestion sources via YAML files in `sources.d/` directory:

```bash
# sources.d/ structure
sources.d/
  _defaults.yaml         # Global defaults (max_entries, enabled)
  rss.yaml               # RSS feed sources
  youtube_playlist.yaml  # YouTube playlists (OAuth, Gemini video extraction)
  youtube_rss.yaml       # YouTube RSS feeds (public, no OAuth)
  podcasts.yaml          # Podcast feeds (with transcript settings)
  gmail.yaml             # Gmail query sources
  websearch.yaml         # Web search sources (Perplexity, Grok)
  scholar.yaml           # Academic paper sources (Semantic Scholar)
```

Each source supports: `name`, `url`/`id`, `tags`, `enabled`, `max_entries`.

**YouTube playlist sources** support:
- `visibility: public|private` — private sources require OAuth and are skipped if OAuth fails
- `gemini_summary: true` — enable Gemini native video content extraction (default: true)
- `gemini_resolution: default` — video frame resolution (`low`=66 tok/frame, `default`=258, `medium`, `high`)
- `proofread: true` — LLM-based caption proofreading for auto-generated transcripts (transcript fallback path)
- `hint_terms: [...]` — per-source proper nouns merged with built-in AI terminology defaults

**YouTube RSS sources** support:
- `gemini_summary: true` — enable Gemini native video content extraction
- `gemini_resolution: low` — defaults to low resolution for cost savings

**Podcast sources** use a 3-tier transcript strategy:
1. Feed-embedded text (>=500 chars)
2. Linked transcript page (regex URL detection)
3. Audio transcription via STT (gated by `transcribe: true`)

**Web search sources** (`websearch.yaml`) support two providers:
- `provider: perplexity` — Perplexity Sonar API for AI-powered web search with citations
  - `prompt` (required), `max_results`, `recency_filter` (day/week/month), `context_size` (low/medium/high), `domain_filter`
- `provider: grok` — X/Twitter search via xAI Grok API
  - `prompt` (required), `max_threads`
- Both support: `name`, `tags`, `enabled`
- Used by `aca pipeline daily` for scheduled ingestion from `sources.d/websearch.yaml`

**Migration from legacy config:**
```bash
python -m src.config.migrate_sources --output-dir sources.d
```

## Profile Configuration

Profiles provide named configuration bundles that replace scattered `.env` variables with structured YAML files. Each profile defines provider choices (database, storage, neo4j, observability) and their settings.

```bash
# Activate a profile
export PROFILE=local           # Use profiles/local.yaml

# CLI Commands
aca profile list                    # List available profiles
aca profile show local              # Show resolved settings
aca profile validate local          # Validate configuration
aca profile inspect                 # Show effective Settings
aca profile migrate --dry-run       # Preview .env migration
```

**Profile structure** (`profiles/local.yaml`):
```yaml
name: local
extends: base                    # Inherit from base.yaml
description: Docker Compose local development

providers:
  database: local
  neo4j: local
  storage: local
  observability: noop

settings:
  database_url: postgresql://localhost:5432/newsletters
  neo4j_uri: bolt://localhost:7687
  anthropic_api_key: ${ANTHROPIC_API_KEY}  # Reference secrets
```

**Secrets management** (`.secrets.yaml` - gitignored):
```yaml
ANTHROPIC_API_KEY: sk-ant-...
OPENAI_API_KEY: sk-...
NEO4J_PASSWORD: secret123
```

**Precedence order** (highest to lowest):
1. Environment variables (always win)
2. Profile settings (from `profiles/{name}.yaml`)
3. Secrets file (`.secrets.yaml`)
4. `.env` file (fallback when no profile active)
5. Default values

**Migration from `.env`**:
```bash
aca profile migrate --env-file .env --output my-profile
```

See [docs/PROFILES.md](docs/PROFILES.md) for complete guide.

## Model Configuration

```bash
# .env - Configure per pipeline step
MODEL_SUMMARIZATION=claude-haiku-4-5              # Fast, cost-effective
MODEL_THEME_ANALYSIS=claude-sonnet-4-5            # Quality reasoning
MODEL_DIGEST_CREATION=claude-sonnet-4-5           # Customer-facing
MODEL_YOUTUBE_PROCESSING=gemini-2.5-flash         # Playlist video extraction (Gemini)
MODEL_YOUTUBE_RSS_PROCESSING=gemini-2.5-flash-lite # RSS video extraction (cost-optimized)
MODEL_CAPTION_PROOFREADING=gemini-2.5-flash-lite  # Auto-caption proofreading
```

## Database Providers

Four PostgreSQL providers are supported. **Set `DATABASE_PROVIDER` explicitly** in your `.env`:

| Provider | `DATABASE_PROVIDER` | Use Case |
|----------|---------------------|----------|
| Local | `local` (default) | Development, Docker |
| Supabase | `supabase` | Cloud hosting, local dev with `SUPABASE_LOCAL=true` |
| Neon | `neon` | Agent workflows, branching |
| Railway | `railway` | Single-platform deployment with extensions |

```bash
# .env - explicit provider selection (required for cloud)
DATABASE_PROVIDER=railway  # or "supabase", "neon", or "local"
DATABASE_URL=postgresql://...

# Optional: Provider-specific URL overrides (take precedence over DATABASE_URL)
# LOCAL_DATABASE_URL=postgresql://...   # Override for local
# NEON_DATABASE_URL=postgresql://...    # Override for neon

# Local Supabase development (auto-configures URLs and keys)
SUPABASE_LOCAL=true
DATABASE_PROVIDER=supabase
```

**Neon Branching for Agents**: Create isolated database branches for feature work or testing:
```bash
# Create ephemeral branch
neonctl branches create --name claude/feature-xyz --project-id $NEON_PROJECT_ID

# Get connection string and work with isolated database
DATABASE_URL=$(neonctl connection-string claude/feature-xyz)

# Delete when done
neonctl branches delete claude/feature-xyz
```

See [docs/SETUP.md#neon-serverless-postgresql](docs/SETUP.md#neon-serverless-postgresql-bring-your-own) for full setup.

## File Storage Providers

Unified file storage supporting multiple buckets (images, podcasts, audio-digests):

| Provider | `STORAGE_PROVIDER` | Use Case |
|----------|-------------------|----------|
| Local | `local` (default) | Development, local storage |
| S3 | `s3` | AWS S3 or S3-compatible (MinIO) |
| Supabase | `supabase` | Supabase Storage (S3-compatible) |
| Railway | `railway` | Railway MinIO (single-platform deployment) |

```bash
# .env - Local storage (default)
STORAGE_PROVIDER=local
# Default paths: data/images, data/podcasts, data/audio-digests

# .env - S3 storage
STORAGE_PROVIDER=s3
IMAGE_STORAGE_BUCKET=newsletter-images
AWS_REGION=us-east-1

# .env - Supabase storage (uses S3-compatible API)
STORAGE_PROVIDER=supabase
SUPABASE_STORAGE_BUCKET=images
SUPABASE_ACCESS_KEY_ID=your-access-key      # From Dashboard > Settings > API > S3 Access Keys
SUPABASE_SECRET_ACCESS_KEY=your-secret-key  # From Dashboard > Settings > API > S3 Access Keys
SUPABASE_STORAGE_PUBLIC=false               # true for public URLs

# .env - Per-bucket provider overrides (optional)
STORAGE_BUCKET_PROVIDERS='{"podcasts": "s3"}'  # Use S3 for podcasts only

# Legacy image storage config (still works for backward compatibility)
IMAGE_STORAGE_PROVIDER=local
IMAGE_STORAGE_PATH=data/images
```

**API Endpoints**:
- `GET /api/v1/files/{bucket}/{path}` - Retrieve files with range request support
- Buckets: `images`, `podcasts`, `audio-digests`

**Important**: Supabase Storage uses S3-compatible credentials (not the service role key). Get these from **Supabase Dashboard > Project Settings > API > S3 Access Keys**.

See [docs/SETUP.md#image-storage-variables-optional](docs/SETUP.md#image-storage-variables-optional) for full setup.

## Neo4j Providers

Two Neo4j providers are supported for the knowledge graph. **Set `NEO4J_PROVIDER` explicitly** in your `.env`:

| Provider | `NEO4J_PROVIDER` | Use Case |
|----------|------------------|----------|
| Local | `local` (default) | Development, Docker |
| AuraDB | `auradb` | Production cloud (free tier available) |

```bash
# .env - Local Neo4j (Docker or local installation)
NEO4J_PROVIDER=local
NEO4J_LOCAL_URI=bolt://localhost:7687
NEO4J_LOCAL_USER=neo4j
NEO4J_LOCAL_PASSWORD=your-local-password

# .env - Neo4j AuraDB (cloud)
NEO4J_PROVIDER=auradb
NEO4J_AURADB_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_AURADB_USER=neo4j
NEO4J_AURADB_PASSWORD=your-auradb-password

# Legacy settings (still work as fallbacks for local provider)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=newsletter_password
```

**Setting up Neo4j AuraDB (Free Tier)**:
1. Go to [console.neo4j.io](https://console.neo4j.io/)
2. Create a free AuraDB instance
3. Save the connection URI and generated password
4. Set `NEO4J_PROVIDER=auradb` with the credentials above

## Observability

Two-layer architecture: **LLM observability** (provider-abstracted) + **infrastructure telemetry** (OpenTelemetry auto-instrumentation).

| Provider | `OBSERVABILITY_PROVIDER` | SDK | Use Case |
|----------|--------------------------|-----|----------|
| Noop | `noop` (default) | None | Zero overhead, disabled state |
| Opik | `opik` | OTel + gen_ai.* | Self-hosted or Comet Cloud |
| Braintrust | `braintrust` | Native SDK | Evaluations, scoring, prompt mgmt |
| Langfuse | `langfuse` | OTel + gen_ai.* | Open-source LLM tracing (self-hosted or cloud) |
| OTel | `otel` | Pure OTel | Generic OTLP backend (Jaeger, Grafana, etc.) |

```bash
# .env - Enable observability
OBSERVABILITY_PROVIDER=braintrust   # or "opik", "langfuse", "otel", "noop"
BRAINTRUST_API_KEY=sk-xxx           # Required for Braintrust
OTEL_ENABLED=true                   # Enable infrastructure auto-instrumentation
OTEL_EXPORTER_OTLP_ENDPOINT=https://api.braintrust.dev/otel/v1/traces

# Langfuse (Cloud or self-hosted)
# LANGFUSE_PUBLIC_KEY=pk-lf-...           # From Langfuse Settings → API Keys
# LANGFUSE_SECRET_KEY=sk-lf-...           # From Langfuse Settings → API Keys
# LANGFUSE_BASE_URL=https://cloud.langfuse.com  # Override for self-hosted

# Frontend OTel (in web/.env or passed at build time)
VITE_OTEL_ENABLED=true              # Enable browser trace propagation + Web Vitals
```

**Key files (backend):**
- `src/telemetry/__init__.py` — `setup_telemetry()`, `get_provider()`, `shutdown_telemetry()`
- `src/telemetry/providers/` — Provider implementations (factory pattern)
- `src/telemetry/providers/langfuse.py` — Langfuse provider (OTel + Basic Auth)
- `src/telemetry/otel_setup.py` — OTel infrastructure (FastAPI, SQLAlchemy, httpx)
- `src/telemetry/log_setup.py` — OTel log bridge (trace-log correlation, OTLP log export)
- `src/telemetry/metrics.py` — OTel meters (LLM requests, tokens, duration)
- `src/utils/logging.py` — `JsonFormatter`, `TraceContextFormatter`, `setup_logging()`
- `src/api/health_routes.py` — `/health` (liveness) and `/ready` (readiness)
- `src/api/middleware/telemetry.py` — X-Trace-Id response header
- `src/api/middleware/error_handler.py` — Structured JSON errors with trace_id
- `src/api/otel_proxy_routes.py` — Frontend OTLP proxy (`/api/v1/otel/v1/traces`)

**Key files (frontend):**
- `web/src/lib/telemetry/index.ts` — Public API (`initTelemetry`, `getTracer`, `isOtelEnabled`)
- `web/src/lib/telemetry/setup.ts` — OTel SDK init (WebTracerProvider, FetchInstrumentation)
- `web/src/lib/telemetry/web-vitals.ts` — Core Web Vitals → OTel spans bridge
- `web/src/components/ErrorBoundary.tsx` — React Error Boundary with OTel span creation

## Critical Gotchas

⚠️ **These will bite you if ignored:**

| Issue | Solution |
|-------|----------|
| SQLAlchemy duplicate indexes | Don't use `index=True` AND explicit `Index()` with same name |
| Test DB fails on second run | Fixtures must drop tables before creating (handles interrupted runs) |
| feedparser dates are naive | Always add `tzinfo=UTC` when converting `published_parsed` |
| mypy + SQLAlchemy stubs | Don't install `sqlalchemy-stubs` - conflicts with 2.0 |
| Neon first connection slow | Scale-to-zero may take 2-5s to wake up; increase timeout |
| Supabase free tier IPv6 only | Direct connections use IPv6; use pooler if on IPv4-only network |
| DATABASE_PROVIDER required for cloud | Must explicitly set `DATABASE_PROVIDER=supabase` or `neon` |
| Local Supabase needs SUPABASE_LOCAL | Set `SUPABASE_LOCAL=true` for auto-configured local endpoints |
| Local Supabase DB needs init scripts | `supabase/postgres` image requires roles (`supabase_admin`, `anon`, etc.) via `supabase/docker/init/` SQL scripts |
| Local Supabase storage IPv6 health check | Use `127.0.0.1` not `localhost` in wget health checks — Node.js binds IPv4 only but `wget` resolves to IPv6 `::1` |
| Local Supabase storage needs DB grants | `supabase_storage_admin` needs `GRANT CREATE ON DATABASE postgres` to run migrations |
| PostgREST container has no curl/wget | Use `bash -c 'echo -n > /dev/tcp/localhost/3000'` for health checks |
| Supabase Storage uses S3 API | Use `SUPABASE_ACCESS_KEY_ID`/`SUPABASE_SECRET_ACCESS_KEY`, NOT service role key |
| datetime.utcnow() is deprecated | Use `datetime.now(UTC)` instead (Python 3.12+) |
| Settings tests pick up .env | Pass `_env_file=None` to `Settings()` to isolate tests |
| Pydantic property vs field conflict | Don't make a property with same name as a field in Pydantic models |
| Alembic migrations not idempotent | Use `IF EXISTS` for drops; check `information_schema` before FK operations |
| Model-schema drift breaks migrations | Don't assume columns exist in DB; check before creating FK constraints |
| Railway custom image build slow | Use GHCR pre-built image; Rust extensions take ~20 min to compile |
| Railway MinIO auto-discovery | Set `RAILWAY_PUBLIC_DOMAIN` or explicit `RAILWAY_MINIO_ENDPOINT` |
| Railway PORT is dynamic | Use `${PORT:-8000}` in shell form CMD; never hardcode port in Dockerfile |
| Railway extension version pinning | Pin git tags in Dockerfile (e.g., `--branch v0.7.4`); unpinned builds break on pgrx mismatches |
| Railway volumes not persistent by default | Attach a volume in Railway dashboard; without it, data lost on redeploy |
| Railway Hobby plan connection limits | Use `pool_size=3`, `max_overflow=2`; exceeding causes connection errors |
| Braintrust extra in Dockerfile | Must add `--extra braintrust` to `uv sync` in Dockerfile; without it `import braintrust` fails silently |
| Cloud DB has no tables | Supabase/Neon start empty; run `alembic upgrade head` against production |
| Alembic multiple heads block `upgrade head` | Run `alembic heads` to detect; fix with `alembic merge heads -m "..."` or use `alembic upgrade heads` (plural) |
| PG enum + Python StrEnum mismatch | Adding to Python `StrEnum` requires `ALTER TYPE ... ADD VALUE` migration; without it PG throws `InvalidTextRepresentation` |
| VITE_API_URL trailing slash | Causes double-slash (`//api/v1/`); strip with `.replace(/\/$/, "")` |
| CORS blocks cross-origin frontend | Set `ALLOWED_ORIGINS` env var on backend with frontend URL |
| Migrations create existing tables | Make idempotent: check `information_schema.tables` before `create_table` |
| Dialog `min-w-[600px]` breaks mobile | Use `md:min-w-[600px]` — CSS `min-width` overrides `max-width`, causing overflow |
| iOS status bar hides header | Apply `pt-[var(--safe-area-top)]` to AppShell root and fixed overlays |
| Fixed grid-cols-N in dialogs | Use responsive breakpoints: `grid-cols-2 md:grid-cols-4` |
| E2E tests need `--ignore-snapshots` | Default `test:e2e` script adds this flag; snapshot tests not used |
| E2E mock data must use snake_case | API responses use snake_case; mock factories in `fixtures/mock-data.ts` |
| E2E smoke tests need real backend | `pnpm test:e2e:smoke` requires backend running; excluded via `grepInvert: /@smoke/` |
| Import `test` from `../fixtures` | E2E tests must import custom `test` (not `@playwright/test`) for page objects and mocks |
| Playwright strict mode violations | Use `.first()`, `{ exact: true }`, or scope to parent (`.locator("main")`) when locators match multiple elements |
| Playwright route needs trailing `*` | Route patterns like `**/api/v1/items/*/nav` won't match query params; add trailing `*` |
| Mock data must include all array fields | Components accessing `obj.field.length` crash if `field` is undefined; include empty `[]` arrays |
| `getByText` matches substrings | `getByText("Content")` matches "Ingest Content" too; use `{ exact: true }` or `getByRole` |
| Sidebar text duplicates main content | Scope to `page.locator("main")` or `page.locator("aside")` to avoid matching both |
| VitePWA manifest not in dev mode | `/manifest.webmanifest` returns HTML in dev; manifest only generated in production builds |
| Route registration order is LIFO | Playwright matches last-registered route first; register specific routes after general ones |
| Podcast transcription needs STT key | Set `OPENAI_API_KEY` for Whisper; `transcribe: false` in source to skip |
| X search needs xAI API key | Set `XAI_API_KEY`; search prompt configurable via `aca prompts set pipeline.xsearch.search_prompt` |
| Perplexity search needs API key | Set `PERPLEXITY_API_KEY`; model defaults to `sonar`; search prompt configurable via `aca prompts set perplexity_search.search_prompt` |
| Scholar ingestion API key optional | Set `SEMANTIC_SCHOLAR_API_KEY` for higher rate limits (1-10 RPS vs ~20 req/min unauthenticated); free API, no key required for basic use |
| Perplexity uses OpenAI SDK | Zero new dependencies — `openai.OpenAI(base_url="https://api.perplexity.ai")` with `extra_body` for vendor params |
| WebSearchProvider lazy imports | Adapters use lazy imports in `__init__` and `search()` — mock at SOURCE module, not `src.services.web_search` |
| Telemetry mock patch target | Patch `src.telemetry.get_provider` (source module), NOT `src.services.llm_router.get_provider` — local imports aren't module attrs |
| Telemetry tests need anthropic_api_key | Pass `anthropic_api_key="test-key"` to `Settings(_env_file=None)` in observability tests |
| `logging.basicConfig()` only works once | OTel log bridge uses `addHandler()` directly — never call `basicConfig()` after `setup_logging()` |
| Log bridge needs both flags | Requires `OTEL_ENABLED=true` AND `OTEL_LOGS_ENABLED=true` — logs gate on the parent OTel flag |
| Export level ≠ console level | `OTEL_LOGS_EXPORT_LEVEL` controls OTLP export only; `LOG_LEVEL` still controls console output |
| Frontend OTel needs backend OTel | `VITE_OTEL_ENABLED=true` requires `OTEL_ENABLED=true` on backend for OTLP proxy to accept traces |
| Frontend OTel is no-op by default | Zero overhead when disabled; OTel SDK dynamically imported only when `VITE_OTEL_ENABLED=true` |
| initTelemetry must run before React | Called at module scope in `__root.tsx` so fetch instrumentation is active before TanStack Query fires |
| Profile not loading | Ensure `PROFILE` env var is set; profiles live in `profiles/` directory |
| Profile validation errors | Run `aca profile validate <name>` to see all errors |
| Secrets not interpolating | Check `.secrets.yaml` exists and key names match `${VAR}` references |
| Profile inheritance cycles | Profiles cannot extend themselves or form circular `extends` chains |
| Profile provider vs settings collision | `providers.*` must be authoritative; don't add `*_provider` keys in `settings.*` sections of child profiles |
| `.secrets.yaml` uses YAML syntax | Must use `:` not `=`; `KEY=value` silently parses as a string instead of a key-value pair |
| `.secrets.yaml` needs profile active | Without `PROFILE` env var, `.secrets.yaml` is never read; secrets only flow via `${VAR}` in profiles |
| New secrets need `base.yaml` wiring | Add `${VAR:-}` reference in `profiles/base.yaml` under the appropriate settings section |
| Tailwind v4 typography plugin overrides | Plugin styles are unlayered; custom `.prose` overrides must be OUTSIDE `@layer` blocks to win cascade |
| `autoflush=False` + dedup loop | `db.add()` without `db.flush()` leaves rows invisible to subsequent SELECTs; cross-feed duplicates pass dedup then collide on unique constraint at commit |
| Changing embedding provider | Use `aca manage switch-embeddings` — handles clearing, index rebuild, and backfill safely |
| Embedding provider asymmetry | Voyage/Cohere/local have different query vs document encoding — always pass `is_query=True` when embedding search queries |
| `embedding_trust_remote_code` | Defaults to `false` — must explicitly enable for instruction-tuned models like `gte-Qwen2-1.5B-instruct` |
| Embedding config mismatch | Startup warns if DB embeddings are from a different provider than configured — run `switch-embeddings` to fix |
| `index_content()` is fail-safe | Never raises exceptions — failures are logged. Content ingestion always succeeds even if search indexing fails |
| pgvector not mapped in ORM | `DocumentChunk.embedding` and `search_vector` are NOT SQLAlchemy columns — access via raw SQL only. `embedding_provider`/`embedding_model` ARE mapped |
| Prompt/settings API returns 500 | Must set `ADMIN_API_KEY` env var (or in `.secrets.yaml` with profile); fail-secure design blocks access when unconfigured |
| Prompt API auth header is `X-Admin-Key` | NOT `X-Admin-API-Key` or `Authorization` — defined in `src/api/dependencies.py:9` as `APIKeyHeader(name="X-Admin-Key")` |
| Worktree test DB naming | Each worktree auto-creates `newsletters_test_<worktree>` (sanitized, max 63 chars). `TEST_DATABASE_URL` env var overrides. Use `make test-clean` to drop all worktree test DBs |
| Test DB auto-created by conftest | Session-scoped fixtures auto-create via admin connection to `postgres` DB. No `make test-setup` needed for PG (still needed for Neo4j) |
| Production CORS returns empty list | When `ENVIRONMENT=production` and `ALLOWED_ORIGINS` is dev defaults (localhost), `get_allowed_origins_list()` returns `[]` — must set explicit origins |
| Production startup warns (doesn't fail) | Missing `ADMIN_API_KEY` or dev CORS in production logs warnings but does NOT prevent startup — intentional per design |
| Upload magic bytes validation | File uploads are validated against `FILE_SIGNATURES` mapping in `upload_routes.py` — mismatched extensions return 415 |
| Upload MIME cross-check | Client `Content-Type` is validated against `EXTENSION_MIME_MAP` — `application/octet-stream` and `None` bypass the check |
| `ENDPOINT_AUTH_MAP` in `dependencies.py` | Documentation-only constant — lists all routes and their auth requirements. Auth enforced by `AuthMiddleware` + `verify_admin_key` dependency |
| Auth: middleware + route dependency double-check | `AuthMiddleware` and `verify_admin_key` both verify session cookies AND X-Admin-Key — defense-in-depth, not conflicting |
| Auth: Secure cookies + TestClient | TestClient defaults to `http://testserver` — secure cookies are not sent back. Use `base_url="https://testserver"` in production fixtures |
| Auth: Cookie header dropped on redirect | httpx regenerates `Cookie` headers from its cookie jar on redirect — manually set `Cookie` headers are lost. Use trailing-slash URLs in tests to avoid 307 redirects |
| Auth: Invalid X-Admin-Key returns 403 (not 401) | Middleware distinguishes invalid keys (403 Forbidden) from missing auth (401 Unauthorized). Spec requires this for all environments |
| `APP_SECRET_KEY` is the login password | Used directly for `secrets.compare_digest()` against user input AND as HMAC input for JWT signing key derivation |
| Hoverfly webserver mode has no capture | Default `docker-compose.yml` runs `-webserver` flag — no upstream to record. Must restart in proxy mode for capture (see `tests/integration/README.md`) |
| Hoverfly simulation reset between tests | `hoverfly` fixture auto-resets; tests that load simulations should not depend on prior test state |
| Integration fixture env vars must use Settings | Use `get_settings()` not `os.getenv()` — fixtures must honor profile/secrets precedence chain |
| Contract tests excluded by default | `contract` marker excluded in `addopts` — run explicitly with `pytest tests/contract/ -m contract --no-cov` |
| Schemathesis NUL byte skip | Schemathesis generates `%00` in query params causing psycopg2 `ValueError` — contract tests skip these via try/except, tracked as separate input validation issue |
| Contract test savepoints | `tests/contract/conftest.py` uses `begin_nested()` (SAVEPOINTs) so failed API calls don't abort the entire test transaction |
| Langfuse keys are auto-generated | First start Langfuse, create account, get keys from Settings → API Keys |
| Langfuse self-hosted is resource-heavy | 6 services (PG, ClickHouse, Redis, MinIO, web, worker); use `make langfuse-up` only when needed |
| Langfuse uses Basic Auth for OTLP | `Authorization: Basic base64(public_key:secret_key)` — different from Opik/Braintrust auth |
| Langfuse port 3100 | Avoids conflict with web frontend (3000), Vite (5173), Opik (5174) |
| gitleaks pre-commit blocks commit | Check `.gitleaks.toml` allowlist; add path or regex exception for intentional test fixtures |
| pip-audit fails in CI | Check `pip-audit --desc on` locally; known advisories may need `--ignore-vuln` flag |
| Security headers break iframe embedding | `X-Frame-Options: DENY` prevents embedding; if embedding needed, switch to CSP `frame-ancestors` directive |
| Crawl4AI Docker needs `--shm-size=1g` | Chromium crashes without shared memory; docker-compose sets `shm_size: '1g'` |
| `crawl4ai_enabled` defaults to `False` | Must explicitly enable via env var or profile; prevents accidental browser launches |
| Remote mode needs Docker running | `make crawl4ai-up` first; connection refused errors are fail-safe (returns Trafilatura result) |
| CacheMode string must match enum names | Valid values: `bypass`, `enabled`, `disabled`, `read_only`, `write_only` |
| Crawl4AI lazy import in converter | `get_settings()` imported inside `__init__` — patch at `src.config.settings.get_settings`, not the converter module |

## Quick Links by Task

### Writing Code
- Database patterns: [docs/DEVELOPMENT.md#database-patterns](docs/DEVELOPMENT.md#database-patterns)
- Frontend patterns: [docs/DEVELOPMENT.md#reactfrontend-patterns](docs/DEVELOPMENT.md#reactfrontend-patterns)
- Error handling: [docs/DEVELOPMENT.md#error-handling](docs/DEVELOPMENT.md#error-handling)

### Working with Content
- Ingestion services: [docs/ARCHITECTURE.md#ingestion-services](docs/ARCHITECTURE.md#ingestion-services)
- Parser ecosystem: [docs/ARCHITECTURE.md#parser-ecosystem](docs/ARCHITECTURE.md#parser-ecosystem)
- Data models: [docs/ARCHITECTURE.md#data-models](docs/ARCHITECTURE.md#data-models)

### Testing
- Test commands: [docs/DEVELOPMENT.md#testing](docs/DEVELOPMENT.md#testing)
- Testing best practices: [docs/DEVELOPMENT.md#testing-best-practices](docs/DEVELOPMENT.md#testing-best-practices)
- Database provider tests: [docs/DEVELOPMENT.md#database-provider-testing](docs/DEVELOPMENT.md#database-provider-testing)
- Neon integration tests: [docs/SETUP.md#test-architecture](docs/SETUP.md#test-architecture)
- Supabase integration tests: [docs/SETUP.md#supabase-test-architecture](docs/SETUP.md#supabase-test-architecture)
- Hoverfly API simulation: [docs/TESTING.md#hoverfly-api-simulation](docs/TESTING.md#hoverfly-api-simulation)
- Integration test fixtures: [docs/TESTING.md#integration-test-fixtures](docs/TESTING.md#integration-test-fixtures)
- E2E testing guide: [docs/TESTING.md#e2e-testing-playwright](docs/TESTING.md#e2e-testing-playwright)
- E2E test infrastructure: `web/tests/e2e/fixtures/` (page objects, API mocks, mock data factories)
- E2E page objects: `web/tests/e2e/fixtures/pages/*.page.ts`
- Contract testing: `tests/contract/` (Schemathesis schema validation + fuzz testing)
- Regression testing: `tests/regression/` (API contracts), `tests/cli/test_regression_daily_pipeline.py` (CLI workflows), `web/tests/e2e/regression/` (UX workflows)
- Live E2E pipeline tests: `tests/e2e/` (sequential pipeline execution with LLM validation, Opik/Langfuse scoring)

### Configuration
- Profile guide: [docs/PROFILES.md](docs/PROFILES.md)
- Profile CLI reference: [docs/PROFILES.md#cli-commands](docs/PROFILES.md#cli-commands)
- Migrating from .env: [docs/PROFILES.md#migration-from-env](docs/PROFILES.md#migration-from-env)

### Storage & Infrastructure
- Image storage configuration: [docs/SETUP.md#image-storage-variables-optional](docs/SETUP.md#image-storage-variables-optional)
- Database providers: [docs/SETUP.md#environment-configuration](docs/SETUP.md#environment-configuration)
- Supabase storage setup: [docs/SETUP.md#supabase-storage-setup](docs/SETUP.md#supabase-storage-setup)

### Deployment
- Railway deployment guide: [docs/MOBILE_DEPLOYMENT.md#deployment](docs/MOBILE_DEPLOYMENT.md#deployment)
- Agent skills for deployment: [docs/MOBILE_DEPLOYMENT.md#agent-skills-for-deployment](docs/MOBILE_DEPLOYMENT.md#agent-skills-for-deployment)
- Deployment lessons learned: [docs/MOBILE_DEPLOYMENT.md#deployment-lessons-learned](docs/MOBILE_DEPLOYMENT.md#deployment-lessons-learned)
- Docker entrypoint pattern: [docs/MOBILE_DEPLOYMENT.md#docker-entrypoint-pattern](docs/MOBILE_DEPLOYMENT.md#docker-entrypoint-pattern)

### Review & Delivery
- Digest review workflow: [docs/REVIEW_SYSTEM.md](docs/REVIEW_SYSTEM.md)
- Podcast generation: [docs/REVIEW_SYSTEM.md#podcast-scripts](docs/REVIEW_SYSTEM.md#podcast-scripts)
- Audio digests (single-voice TTS): [docs/REVIEW_SYSTEM.md#audio-digests](docs/REVIEW_SYSTEM.md#audio-digests)

## Environment Configuration

**Option 1: Use profiles** (recommended for new setups):
```bash
export PROFILE=local           # Activates profiles/local.yaml
aca profile list    # See available profiles
```

**Option 2: Traditional .env** (still fully supported):
```bash
# Minimum required in .env
DATABASE_URL=postgresql://localhost/newsletters
NEO4J_URL=bolt://localhost:7687
ANTHROPIC_API_KEY=sk-ant-...
ADMIN_API_KEY=your-admin-key      # Protects settings/prompt management endpoints
ENVIRONMENT=development
```

See [Setup Guide](docs/SETUP.md#environment-configuration) for complete options, or [Profiles Guide](docs/PROFILES.md) for profile-based configuration.

## Getting Help

- **Setup issues**: [docs/SETUP.md#troubleshooting](docs/SETUP.md#troubleshooting)
- **Model configuration**: [docs/MODEL_CONFIGURATION.md#troubleshooting](docs/MODEL_CONFIGURATION.md#troubleshooting)
- **Development patterns**: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
