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
| [Architecture](docs/ARCHITECTURE.md) | System design, ingestion, parsers, data models |
| [Development](docs/DEVELOPMENT.md) | Commands, patterns, database, testing |
| [Model Config](docs/MODEL_CONFIGURATION.md) | LLM selection, providers, costs |
| [Content Guidelines](docs/CONTENT_GUIDELINES.md) | Digest quality standards |
| [Review System](docs/REVIEW_SYSTEM.md) | Digest/script review workflow |
| [UX Design](docs/UX_DESIGN.md) | Frontend patterns |
| [Markdown Pipeline](docs/MARKDOWN_PIPELINE_DESIGN.md) | End-to-end markdown flow |
| [Case Studies](docs/CASE_STUDIES.md) | Refactoring lessons, migration patterns |

**Always use Context7 MCP** for library/API documentation, code generation, or setup steps for external libraries.

## Project Overview

An agentic AI solution for aggregating and summarizing AI newsletters into daily and weekly digests.

- **Purpose**: Help technical leaders and developers stay informed on AI/Data trends
- **Sources**: Gmail newsletters, Substack RSS feeds, YouTube playlists, file uploads
- **Output**: Structured digests with knowledge graph-powered historical context

## Key Commands

```bash
# Setup
source .venv/bin/activate && docker compose up -d && alembic upgrade head

# Development servers
make dev-bg        # Start frontend + backend in background
make dev-logs      # View logs
make dev-stop      # Stop servers

# Content Ingestion
python -m src.ingestion.gmail          # Gmail newsletters
python -m src.ingestion.substack       # RSS feeds
python -m src.ingestion.youtube        # YouTube playlists

# Processing
python -m src.processors.summarizer    # Summarize pending content
python -m src.processors.digest_creator --type daily

# Testing
pytest                                  # All tests
pytest tests/api/ -v                   # API tests only
```

## Model Configuration

```bash
# .env - Configure per pipeline step
MODEL_SUMMARIZATION=claude-haiku-4-5       # Fast, cost-effective
MODEL_THEME_ANALYSIS=claude-sonnet-4-5     # Quality reasoning
MODEL_DIGEST_CREATION=claude-sonnet-4-5    # Customer-facing
```

## Database Providers

Three PostgreSQL providers are supported. **Set `DATABASE_PROVIDER` explicitly** in your `.env`:

| Provider | `DATABASE_PROVIDER` | Use Case |
|----------|---------------------|----------|
| Local | `local` (default) | Development, Docker |
| Supabase | `supabase` | Cloud hosting |
| Neon | `neon` | Agent workflows, branching |

```bash
# .env - explicit provider selection (required for cloud)
DATABASE_PROVIDER=neon  # or "supabase" or "local"
DATABASE_URL=postgresql://...

# Optional: Provider-specific URL overrides (take precedence over DATABASE_URL)
# LOCAL_DATABASE_URL=postgresql://...   # Override for local
# NEON_DATABASE_URL=postgresql://...    # Override for neon
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

## Image Storage Providers

Three image storage providers are supported for extracted images (from newsletters, YouTube keyframes, etc.):

| Provider | `IMAGE_STORAGE_PROVIDER` | Use Case |
|----------|--------------------------|----------|
| Local | `local` (default) | Development, local storage |
| S3 | `s3` | AWS S3 or S3-compatible (MinIO) |
| Supabase | `supabase` | Supabase Storage (S3-compatible) |

```bash
# .env - Local storage (default)
IMAGE_STORAGE_PROVIDER=local
IMAGE_STORAGE_PATH=data/images

# .env - S3 storage
IMAGE_STORAGE_PROVIDER=s3
IMAGE_STORAGE_BUCKET=newsletter-images
AWS_REGION=us-east-1

# .env - Supabase storage (uses S3-compatible API)
IMAGE_STORAGE_PROVIDER=supabase
SUPABASE_STORAGE_BUCKET=images
SUPABASE_ACCESS_KEY_ID=your-access-key      # From Dashboard > Settings > API > S3 Access Keys
SUPABASE_SECRET_ACCESS_KEY=your-secret-key  # From Dashboard > Settings > API > S3 Access Keys
SUPABASE_STORAGE_PUBLIC=false               # true for public URLs
```

**Important**: Supabase Storage uses S3-compatible credentials (not the service role key). Get these from **Supabase Dashboard > Project Settings > API > S3 Access Keys**.

See [docs/SETUP.md#image-storage-variables-optional](docs/SETUP.md#image-storage-variables-optional) for full setup.

## Critical Gotchas

⚠️ **These will bite you if ignored:**

| Issue | Solution |
|-------|----------|
| Newsletter model is deprecated | Use `Content` model for all new code |
| SQLAlchemy duplicate indexes | Don't use `index=True` AND explicit `Index()` with same name |
| Test DB fails on second run | Fixtures must drop tables before creating (handles interrupted runs) |
| feedparser dates are naive | Always add `tzinfo=UTC` when converting `published_parsed` |
| mypy + SQLAlchemy stubs | Don't install `sqlalchemy-stubs` - conflicts with 2.0 |
| Neon first connection slow | Scale-to-zero may take 2-5s to wake up; increase timeout |
| Supabase free tier IPv6 only | Direct connections use IPv6; use pooler if on IPv4-only network |
| DATABASE_PROVIDER required for cloud | Must explicitly set `DATABASE_PROVIDER=supabase` or `neon` |
| Supabase Storage uses S3 API | Use `SUPABASE_ACCESS_KEY_ID`/`SUPABASE_SECRET_ACCESS_KEY`, NOT service role key |
| datetime.utcnow() is deprecated | Use `datetime.now(UTC)` instead (Python 3.12+) |
| Settings tests pick up .env | Pass `_env_file=None` to `Settings()` to isolate tests |
| Pydantic property vs field conflict | Don't make a property with same name as a field in Pydantic models |
| Alembic migrations not idempotent | Use `IF EXISTS` for drops; check `information_schema` before FK operations |
| Model-schema drift breaks migrations | Don't assume columns exist in DB; check before creating FK constraints |

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

### Storage & Infrastructure
- Image storage configuration: [docs/SETUP.md#image-storage-variables-optional](docs/SETUP.md#image-storage-variables-optional)
- Database providers: [docs/SETUP.md#environment-configuration](docs/SETUP.md#environment-configuration)
- Supabase storage setup: [docs/SETUP.md#supabase-storage-setup](docs/SETUP.md#supabase-storage-setup)

### Review & Delivery
- Digest review workflow: [docs/REVIEW_SYSTEM.md](docs/REVIEW_SYSTEM.md)
- Podcast generation: [docs/REVIEW_SYSTEM.md#podcast-scripts](docs/REVIEW_SYSTEM.md#podcast-scripts)

## Environment Configuration

Minimum required in `.env`:

```bash
DATABASE_URL=postgresql://localhost/newsletters
REDIS_URL=redis://localhost:6379
NEO4J_URL=bolt://localhost:7687
ANTHROPIC_API_KEY=sk-ant-...
ENVIRONMENT=development
```

See [Setup Guide](docs/SETUP.md#environment-configuration) for complete options.

## Getting Help

- **Setup issues**: [docs/SETUP.md#troubleshooting](docs/SETUP.md#troubleshooting)
- **Model configuration**: [docs/MODEL_CONFIGURATION.md#troubleshooting](docs/MODEL_CONFIGURATION.md#troubleshooting)
- **Development patterns**: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
