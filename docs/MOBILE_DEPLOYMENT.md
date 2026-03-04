# Mobile Access Deployment with Durable Background Tasks

> **Status: Implemented** (January 2025)
>
> This document started as a proposal and now serves as architectural documentation
> for the mobile content capture system.

## Implementation Status

### What Was Built

| Component | Status | Files |
|-----------|--------|-------|
| DatabaseProvider queue abstraction | ✅ Complete | `src/storage/providers/*.py` |
| PGQueuer setup module | ✅ Complete | `src/queue/setup.py` |
| Content extraction tasks | ✅ Complete | `src/tasks/content.py` |
| Save URL API endpoints | ✅ Complete | `src/api/save_routes.py` |
| Worker (embedded + standalone) | ✅ Complete | `src/queue/worker.py` |
| URL content extractor | ✅ Complete | `src/services/url_extractor.py` |
| Railway deployment config | ✅ Complete | `Dockerfile`, `railway.toml` |
| iOS Shortcuts documentation | ✅ Complete | `shortcuts/README.md` |
| Mobile save template | ✅ Complete | `src/templates/save.html` |
| Alembic migration for PGQueuer | ✅ Complete | `alembic/versions/f1a2b3c4d5e6_add_pgqueuer_jobs_table.py` |
| Docker entrypoint with auto-migrations | ✅ Complete | `docker-entrypoint.sh` |
| Frontend deployment (RAILPACK) | ✅ Complete | `web/railway.json` |
| Watch paths for selective deploys | ✅ Complete | `railway.toml`, `web/railway.json` |
| CORS for cross-origin frontend | ✅ Complete | `ALLOWED_ORIGINS` env var |
| pg_cron scheduled jobs | ⏳ Pending | — |

### Key Implementation Decisions

**Provider Abstraction**: Extended `DatabaseProvider` protocol with queue-specific methods:
- `get_queue_url()` - Returns direct connection URL (bypasses pooler)
- `get_queue_options()` - Returns optimized engine config for workers
- `supports_pg_cron()` - Indicates pg_cron availability

This abstraction means the queue code works identically across local, Supabase, and Neon backends.

**Content Extraction**: Uses `trafilatura` for HTML-to-markdown conversion instead of a custom parser. Trafilatura provides academic-quality content extraction with better handling of article content.

**Embedded Worker**: The queue worker runs as an async task inside the FastAPI lifespan by default (`WORKER_ENABLED=true`). For scaled deployments, disable the embedded worker and run a separate service via `aca worker start`.

---

## Summary

Deploy the content capture and AI analysis app to Railway for mobile access (iOS Shortcuts), replacing in-process FastAPI BackgroundTasks with a durable Postgres-based queue system using PGQueuer and pg_cron.

## Context

### Current State
- FastAPI application running locally on laptop
- Background tasks run via FastAPI's built-in `BackgroundTasks` (in-process, not durable)
- Database: Neon Postgres (also supports Supabase and local)
- Features include:
  - AI chat about captured content
  - Background tasks for content processing
  - Need for scheduled jobs (e.g., daily newsletter scanning)

### Problem
1. **No mobile access**: iPhone cannot reach localhost
2. **Tasks not durable**: Background tasks lost on server restart/deploy
3. **No scheduled jobs**: No mechanism for recurring tasks like daily email scans
4. **No retry logic**: Failed tasks are lost

### Goals
- Enable mobile access via HTTPS endpoint (iOS Shortcuts compatible)
- Implement durable task queue that survives restarts
- Support scheduled/recurring jobs (daily newsletter scan)
- Minimize infrastructure complexity (avoid Redis/Celery if possible)

## Architecture

### Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                            Railway                                    │
│                                                                       │
│  Option A: Single Service (default)                                  │
│  ┌─────────────────────────────────┐                                 │
│  │   FastAPI Web + Embedded Worker │                                 │
│  │                                 │                                 │
│  │ • API endpoints                 │                                 │
│  │ • AI chat streaming             │                                 │
│  │ • Embedded queue worker         │   WORKER_ENABLED=true (default) │
│  │ • Uses DIRECT conn for worker   │                                 │
│  └──────────────┬──────────────────┘                                 │
│                                                                       │
│  Option B: Scaled Deployment                                         │
│  ┌─────────────────────┐    ┌─────────────────────────────┐          │
│  │   FastAPI Web       │    │   Standalone Worker         │          │
│  │   (Service 1)       │    │   (Service 2)               │          │
│  │                     │    │                             │          │
│  │ • API endpoints     │    │ • aca worker start          │          │
│  │ • WORKER_ENABLED=   │    │ • Uses DIRECT connection    │          │
│  │   false             │    │ • Processes background jobs │          │
│  └──────────┬──────────┘    └──────────────┬──────────────┘          │
└─────────────┼──────────────────────────────┼─────────────────────────┘
              │                              │
              ▼                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│           PostgreSQL (via DatabaseProvider)                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐         │
│  │ Content tables  │  │ pgqueuer_jobs   │  │ pg_cron      │         │
│  │ (application)   │  │ (task queue)    │  │ (scheduler)  │         │
│  └─────────────────┘  └─────────────────┘  └──────────────┘         │
│                                                                      │
│  Provider: local | supabase | neon (auto-selected)                   │
└──────────────────────────────────────────────────────────────────────┘
              ▲
              │
┌─────────────┴─────────────┐
│     iOS Shortcuts         │
│     (HTTPS requests)      │
└───────────────────────────┘
```

### Why Direct vs Pooled Connections Matter

| Use Case | Connection Type | Reason |
|----------|----------------|--------|
| **Web API** | Pooled | Short-lived requests, efficient sharing |
| **Queue Worker** | Direct | Long-lived, uses LISTEN/NOTIFY |
| **Migrations** | Direct | Schema changes need direct access |

The `DatabaseProvider.get_queue_url()` method handles this automatically per provider.

### Technology Choices

#### Hosting: Railway
**Rationale:**
- Simplest deployment from existing Docker setup
- Native support for multiple services (web + worker) in one project
- No timeout issues for long-running AI API calls (unlike Cloudflare Workers)
- Usage-based pricing (~$5-10/month for this workload)
- Built-in HTTPS, environment management, and deploy previews

**Rejected alternatives:**
- **Cloudflare Workers**: Python support in beta, timeout issues with AI API calls, different programming model for background tasks
- **Fly.io**: Good option but slightly more config; Railway is simpler for this use case

#### Task Queue: Custom PostgreSQL Worker
**Rationale:**
- Custom async worker loop (`src/queue/worker.py`) using `SELECT FOR UPDATE SKIP LOCKED`
- Jobs stored in `pgqueuer_jobs` table (created via Alembic migration) with custom columns for progress tracking and batch reconciliation
- LISTEN/NOTIFY on `pgqueuer` channel for immediate job wakeup
- Embedded in FastAPI lifespan by default — no separate process needed
- No additional infrastructure (no Redis, no Celery) required
- Supports:
  - Job priorities
  - Deferred execution (`execute_after`)
  - Progress tracking and batch reconciliation
  - Concurrent processing with configurable concurrency (1-20)
  - Graceful shutdown with active task draining

**Why not pgmq/Supabase Queues:**
- pgmq extension is not available on Neon
- Would require migrating database to Supabase

#### Scheduler: pg_cron (Neon-native)
**Rationale:**
- Runs inside Postgres, independent of worker uptime
- Neon supports pg_cron natively
- Scheduled jobs fire even if worker is temporarily down
- pg_cron inserts jobs into `pgqueuer_jobs` table; worker processes them when API starts

### Hybrid Scheduler Pattern

pg_cron handles the "when" (scheduling), the queue worker handles the "what" (job processing):

```sql
-- pg_cron job (runs in Postgres, always available)
SELECT cron.schedule(
    'daily-newsletter-scan',
    '0 6 * * *',  -- 6 AM UTC daily
    $$
    SELECT pgqueuer_enqueue('scan_newsletters', '{}');
    $$
);
```

```python
# Queue worker (embedded in FastAPI or standalone via `aca worker start`)
# Handlers registered in src/queue/worker.py

@register_handler("scan_newsletters")
async def scan_newsletters(job_id: int, payload: dict) -> None:
    from src.ingestion.gmail import GmailContentIngestionService
    service = GmailContentIngestionService()
    service.ingest_content(query="label:newsletters-ai")

@register_handler("summarize_content")
async def summarize_content(job_id: int, payload: dict) -> None:
    from src.processors.summarizer import ContentSummarizer
    summarizer = ContentSummarizer()
    summarizer.summarize_content(payload["content_id"])
```

## API Endpoints

### POST /api/v1/content/save-url

Save a URL for background content extraction.

**Request:**
```json
{
  "url": "https://example.com/article",
  "title": "Optional title",
  "excerpt": "Optional selected text",
  "source": "ios_shortcut"
}
```

**Response (201 Created):**
```json
{
  "content_id": 123,
  "status": "queued",
  "message": "URL saved. Content extraction in progress.",
  "duplicate": false
}
```

### GET /api/v1/content/{id}/status

Check extraction status.

**Response:**
```json
{
  "content_id": 123,
  "status": "parsed",
  "title": "Article Title",
  "word_count": 1500
}
```

## Deployment

### Configuration Options

You have two options for configuring Railway deployments:

**Option A: Profile-Based Configuration (Recommended)**

Use the pre-configured `railway` profile which sets all providers and references Railway-injected environment variables:

```bash
# In Railway service settings, set:
PROFILE=railway

# Railway auto-injects these (referenced by the profile):
# - RAILWAY_DATABASE_URL
# - MINIO_ROOT_USER, MINIO_ROOT_PASSWORD
# - NEO4J_AURADB_URI, NEO4J_AURADB_PASSWORD

# You must set these secrets manually:
ANTHROPIC_API_KEY=sk-ant-...
BRAINTRUST_API_KEY=sk-...  # For observability
```

The `profiles/railway.yaml` profile configures:
- `database: railway` — Uses Railway's PostgreSQL
- `storage: railway` — Uses Railway's MinIO
- `neo4j: auradb` — Uses Neo4j AuraDB (cloud)
- `observability: braintrust` — Enables Braintrust telemetry

See [Profiles Guide](PROFILES.md) for customization options.

**Option B: Traditional Environment Variables**

Set all variables directly in Railway's service settings (legacy approach).

### Railway Service Configuration

**Service 1: Web API**
- Name: `web`
- Start Command: `uvicorn src.api.app:app --host 0.0.0.0 --port $PORT`
- Environment Variables:
  - `PROFILE`: `railway` (recommended) OR set individual providers:
  - `DATABASE_PROVIDER`: `railway` (or `neon`, `supabase`, `local`)
  - `DATABASE_URL`: Connection string
  - `ALLOWED_ORIGINS`: `*` (for iOS Shortcuts)

**Worker** (embedded by default — no separate service needed):
- The queue worker runs embedded in the API process via FastAPI lifespan
- Set `WORKER_ENABLED=true` (default) and `WORKER_CONCURRENCY=5` (default)
- No separate Railway service is required for most deployments

**Service 2: Standalone Worker** (optional — for scaled deployments):
- Name: `worker`
- Start Command: `aca worker start --concurrency 10`
- Environment Variables: Same as web, plus `WORKER_ENABLED=false` on Service 1
- Note: No public domain needed (internal only)
- Both embedded and standalone workers can run simultaneously (safe via `SKIP LOCKED`)

**Automated Backups** (Railway custom image only):
- Backups are handled automatically via pg_cron → MinIO when using the custom PostgreSQL image
- Configure with `RAILWAY_BACKUP_ENABLED`, `RAILWAY_BACKUP_SCHEDULE`, `RAILWAY_BACKUP_RETENTION_DAYS`
- See [Automated Backups](SETUP.md#automated-backups-pg_cron--minio) in SETUP.md for full configuration and restore procedures

### pg_cron Setup (Neon)

```sql
-- Enable the extension
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Create helper function to enqueue PGQueuer jobs
CREATE OR REPLACE FUNCTION pgqueuer_enqueue(
    p_entrypoint TEXT,
    p_payload JSONB DEFAULT '{}'::jsonb,
    p_priority INTEGER DEFAULT 0
) RETURNS BIGINT AS $$
DECLARE
    v_job_id BIGINT;
BEGIN
    INSERT INTO pgqueuer_jobs (entrypoint, payload, priority, status, created_at, execute_after)
    VALUES (p_entrypoint, p_payload, p_priority, 'queued', NOW(), NOW())
    RETURNING id INTO v_job_id;

    PERFORM pg_notify('pgqueuer', p_entrypoint);
    RETURN v_job_id;
END;
$$ LANGUAGE plpgsql;

-- Schedule daily newsletter scan at 6 AM UTC
SELECT cron.schedule(
    'daily-newsletter-scan',
    '0 6 * * *',
    $$SELECT pgqueuer_enqueue('scan_newsletters', '{}')$$
);
```

## Agent Skills for Deployment

Four complementary agent skills provide deployment and infrastructure automation:

### `aca-deployment` — Stack Orchestration

Custom skill for multi-provider stack management (Railway + Neon + AuraDB). Profile-aware.

```bash
/aca-deployment stack:verify           # Full-stack health check
/aca-deployment railway:deploy         # Deploy via Railway CLI
/aca-deployment neon:create claude/xyz # Create Neon branch
/aca-deployment auradb:status          # Check AuraDB instance
```

Location: `skills/aca-deployment/`

### `use-railway` — Railway Platform Operations

Official Railway Skills ([railwayapp/railway-skills](https://github.com/railwayapp/railway-skills)). Provides deeper Railway-specific knowledge: project/service creation, build troubleshooting, domain/networking, environment variables, metrics, and Railway GraphQL API access.

Location: `.agents/skills/use-railway/`

### `neon-postgres` — Neon Platform Knowledge

Official Neon Skills ([neondatabase/agent-skills](https://github.com/neondatabase/agent-skills)). Comprehensive Neon Serverless Postgres guidance: connection methods and drivers, branching strategies, autoscaling, scale-to-zero, Neon CLI/API reference, and SDK integration.

Location: `.agents/skills/neon-postgres/`

### `claimable-postgres` — Instant Throwaway Databases

Also from `neondatabase/agent-skills`. Provisions instant temporary Postgres databases via `pg.new` (no account required, 72h expiry). Useful for prototyping and ephemeral test environments.

Location: `.agents/skills/claimable-postgres/`

### When to use which

| Scenario | Skill |
|---|---|
| Deploy the stack, verify providers, manage AuraDB | `aca-deployment` |
| Railway build config, domains, troubleshooting, metrics | `use-railway` |
| Neon connection methods, branching strategies, SDK docs | `neon-postgres` |
| Quick throwaway database for prototyping | `claimable-postgres` |

## Deployment Lessons Learned

Collected during the initial Railway deployment (January 2026).

### Database Migrations Must Be Run Against Production

Cloud database providers (Supabase, Neon) give you an **empty database**. Your application schema lives in Alembic migrations and must be explicitly applied:

```bash
# Run against production via Railway CLI
railway run alembic upgrade head

# Or check current state first
railway run alembic current
```

The Docker entrypoint (`docker-entrypoint.sh`) now runs `alembic upgrade head` automatically on every container startup, ensuring the schema is always in sync with the deployed code.

### Docker Entrypoint Pattern

The container uses an entrypoint script instead of a direct `CMD`:

```bash
#!/bin/bash
set -e
echo "Running database migrations..."
alembic upgrade head
echo "Starting application..."
exec uvicorn src.api.app:app --host 0.0.0.0 --port ${PORT:-8000}
```

Key details:
- `set -e` ensures the container fails fast if migrations fail
- `exec` replaces the shell process so signals (SIGTERM) reach uvicorn
- `${PORT:-8000}` uses Railway's dynamic PORT or defaults to 8000

### Railway Dynamic PORT

Railway assigns a PORT environment variable dynamically. The Dockerfile must **not** hardcode the port:

```dockerfile
# ✅ Correct: shell form expands $PORT
CMD ["./docker-entrypoint.sh"]

# ❌ Wrong: hardcoded port ignores Railway's assignment
CMD ["uvicorn", "src.api.app:app", "--port", "8000"]
```

### Frontend as Separate Service

The React/Vite frontend (`web/`) deploys as a separate Railway service using RAILPACK (auto-detects Vite, serves with Caddy). Key configuration:

- **`VITE_API_URL`**: Must be set as a Railway env var pointing to the backend URL (e.g., `https://aca-production-410f.up.railway.app`)
- **Trailing slash bug**: The API client strips trailing slashes from `VITE_API_URL` to prevent double-slash paths (`//api/v1/...`)
- **CORS**: Backend must set `ALLOWED_ORIGINS` to include the frontend URL

```bash
# Backend env vars for CORS
ALLOWED_ORIGINS=https://your-frontend.up.railway.app,http://localhost:5173
```

### Watch Paths for Monorepo

Both services use watch paths to avoid unnecessary rebuilds:

| Config | Watch Paths | Triggers On |
|--------|-------------|-------------|
| `railway.toml` (backend) | `src/**`, `alembic/**`, `Dockerfile`, `pyproject.toml`, etc. | Backend code changes |
| `web/railway.json` (frontend) | `web/**` | Frontend code changes |

### Idempotent Migrations

Migrations that create tables or objects that might already exist (e.g., PGQueuer creates its own tables) must check first:

```python
def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT table_name FROM information_schema.tables WHERE table_name = 'my_table'"
    ))
    if result.fetchone():
        return  # Already exists
    op.create_table("my_table", ...)
```

### Alembic Multiple Heads

Migration relinearization can create orphan branches (multiple heads). Diagnose with:

```bash
alembic heads     # Should show exactly ONE head
alembic branches  # Shows where forks occurred
```

Fix by updating the orphan migration's `down_revision` to point to the correct parent in the main chain.

## Cost Estimate

### Railway (Monthly)
- Web service (with embedded worker): ~$3-7 (low traffic, scales to zero possible)
- Optional standalone worker service: ~$2-5 (only if scaling beyond embedded worker)
- **Total: ~$3-7/month** (single service) or **~$5-12/month** (with standalone worker)

### Neon (Monthly)
- Current plan (likely free tier or Launch): $0-19
- pg_cron: Included, no extra cost
- **Total: Existing cost, no change**

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Worker downtime misses jobs | Jobs persist in Postgres; processed when API restarts (embedded worker auto-starts) |
| pg_cron fires but worker is down | Job queued in DB; worker catches up when API restarts |
| Long-running AI tasks timeout | Railway has no hard timeout for containers |
| Database connection limits | Use connection pooling (asyncpg pool) |
| Cost overruns | Railway usage-based; set spending alerts |

## Success Criteria

1. **Mobile access works**: iOS Shortcuts can hit API endpoints via HTTPS
2. **Tasks are durable**: Server restart doesn't lose pending jobs
3. **Daily scan runs**: Newsletter scan executes at 6 AM daily
4. **Observability**: Can view job status via dashboard or API
5. **Cost reasonable**: Total hosting under $15/month

## Future Enhancements

- Add job status API endpoint for polling from iOS Shortcuts
- Implement webhook notifications when jobs complete
- Add retry policies with exponential backoff
- Create admin dashboard for job management
- Add metrics/alerting for failed jobs

## References

- [PostgreSQL SELECT FOR UPDATE SKIP LOCKED](https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE)
- [Neon pg_cron Documentation](https://neon.tech/docs/extensions/pg_cron)
- [Railway Documentation](https://docs.railway.app/)
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
