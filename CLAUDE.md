<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# CLAUDE.md

Quick reference for Claude Code. Detailed docs in `/docs` directory.

## Documentation Index

| Doc | Purpose |
|-----|---------|
| [Setup](docs/SETUP.md) | Environment setup, configuration |
| [Profiles](docs/PROFILES.md) | Profile-based configuration, inheritance, migration |
| [Architecture](docs/ARCHITECTURE.md) | System design, ingestion, parsers, data models |
| [Development](docs/DEVELOPMENT.md) | Commands, patterns, database, testing |
| [Model Config](docs/MODEL_CONFIGURATION.md) | LLM selection, providers, costs |
| [Content Guidelines](docs/CONTENT_GUIDELINES.md) | Digest quality standards |
| [Review System](docs/REVIEW_SYSTEM.md) | Digest/script review workflow, audio digests |
| [UX Design](docs/UX_DESIGN.md) | Frontend patterns |
| [Markdown Pipeline](docs/MARKDOWN_PIPELINE_DESIGN.md) | End-to-end markdown flow |
| [Case Studies](docs/CASE_STUDIES.md) | Refactoring lessons, migration patterns |
| [Content Capture](docs/CONTENT_CAPTURE.md) | Chrome extension, bookmarklet, save URL API |
| [Deployment](docs/MOBILE_DEPLOYMENT.md) | Railway deployment, Docker, migrations, CORS |

**Always use Context7 MCP** for library/API documentation, code generation, or setup steps for external libraries.

## Project Overview

An agentic AI solution for aggregating and summarizing AI newsletters into daily and weekly digests.

- **Purpose**: Help technical leaders and developers stay informed on AI/Data trends
- **Sources**: Gmail newsletters, Substack RSS feeds, YouTube playlists, file uploads, direct URLs
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

# Local Supabase stack (alternative to core postgres)
make supabase-up   # Start Supabase stack (DB + storage)
make supabase-down # Stop Supabase stack
make supabase-logs # Tail Supabase logs
make dev-supabase  # Start with PROFILE=local-supabase (requires: make supabase-up)

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
aca ingest files <path...>             # Local file ingestion
aca ingest url <url>                   # Direct URL ingestion

# Processing
aca summarize pending                  # Summarize pending content
aca create-digest daily                # Create daily digest
aca create-digest weekly               # Create weekly digest
aca pipeline daily                     # Full daily pipeline (ingest → summarize → digest)

# Review & Delivery
aca review list                        # List pending reviews
aca review view <id>                   # View digest content
aca analyze themes                     # Analyze themes across content
aca podcast generate --digest-id <id>  # Generate podcast script

# Management
aca manage verify-setup                # Check service connectivity
aca manage check-profile-secrets       # Find unresolved secrets

# Job Queue Workers
aca worker start                       # Start worker (5 concurrent tasks)
aca worker start --concurrency 10      # Custom concurrency (max 20)

# Job Management
aca jobs list                          # List all jobs
aca jobs list --status failed          # Filter by status
aca jobs show <id>                     # View job details
aca jobs retry <id>                    # Retry a failed job
aca jobs retry --failed                # Retry all failed jobs
aca jobs cleanup --older-than 30d      # Clean up old completed jobs

# Testing
pytest                                  # All tests
pytest tests/api/ -v                   # API tests only

# E2E Testing (Playwright)
cd web && pnpm test:e2e                 # All E2E tests (mocked, no backend needed)
cd web && pnpm test:e2e:ui             # Visual Playwright inspector
cd web && pnpm test:e2e:smoke          # Smoke tests (requires real backend)
cd web && pnpm exec playwright test tests/e2e/layout/  # Run specific folder
cd web && pnpm exec playwright show-report             # View HTML report
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
| OTel | `otel` | Pure OTel | Generic OTLP backend (Jaeger, Grafana, etc.) |

```bash
# .env - Enable observability
OBSERVABILITY_PROVIDER=braintrust   # or "opik", "otel", "noop"
BRAINTRUST_API_KEY=sk-xxx           # Required for Braintrust
OTEL_ENABLED=true                   # Enable infrastructure auto-instrumentation
OTEL_EXPORTER_OTLP_ENDPOINT=https://api.braintrust.dev/otel/v1/traces

# Frontend OTel (in web/.env or passed at build time)
VITE_OTEL_ENABLED=true              # Enable browser trace propagation + Web Vitals
```

**Key files (backend):**
- `src/telemetry/__init__.py` — `setup_telemetry()`, `get_provider()`, `shutdown_telemetry()`
- `src/telemetry/providers/` — Provider implementations (factory pattern)
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
- E2E testing guide: [docs/TESTING.md#e2e-testing-playwright](docs/TESTING.md#e2e-testing-playwright)
- E2E test infrastructure: `web/tests/e2e/fixtures/` (page objects, API mocks, mock data factories)
- E2E page objects: `web/tests/e2e/fixtures/pages/*.page.ts`

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
REDIS_URL=redis://localhost:6379
NEO4J_URL=bolt://localhost:7687
ANTHROPIC_API_KEY=sk-ant-...
ENVIRONMENT=development
```

See [Setup Guide](docs/SETUP.md#environment-configuration) for complete options, or [Profiles Guide](docs/PROFILES.md) for profile-based configuration.

## Getting Help

- **Setup issues**: [docs/SETUP.md#troubleshooting](docs/SETUP.md#troubleshooting)
- **Model configuration**: [docs/MODEL_CONFIGURATION.md#troubleshooting](docs/MODEL_CONFIGURATION.md#troubleshooting)
- **Development patterns**: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
