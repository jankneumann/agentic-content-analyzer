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
| Worker entry point | ✅ Complete | `src/worker.py` |
| URL content extractor | ✅ Complete | `src/services/url_extractor.py` |
| Railway deployment config | ✅ Complete | `Dockerfile`, `railway.toml` |
| iOS Shortcuts documentation | ✅ Complete | `shortcuts/README.md` |
| Mobile save template | ✅ Complete | `src/templates/save.html` |
| Alembic migration for PGQueuer | ⏳ Pending | — |
| pg_cron scheduled jobs | ⏳ Pending | — |

### Key Implementation Decisions

**Provider Abstraction**: Extended `DatabaseProvider` protocol with queue-specific methods:
- `get_queue_url()` - Returns direct connection URL (bypasses pooler)
- `get_queue_options()` - Returns optimized engine config for workers
- `supports_pg_cron()` - Indicates pg_cron availability

This abstraction means the queue code works identically across local, Supabase, and Neon backends.

**Content Extraction**: Uses `trafilatura` for HTML-to-markdown conversion instead of a custom parser. Trafilatura provides academic-quality content extraction with better handling of article content.

**Graceful Degradation**: If PGQueuer is unavailable, falls back to FastAPI BackgroundTasks (non-durable but functional).

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
┌─────────────────────────────────────────────────────────────┐
│                        Railway                               │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │   FastAPI Web       │    │   FastAPI Worker            │ │
│  │   (Service 1)       │    │   (Service 2)               │ │
│  │                     │    │                             │ │
│  │ • API endpoints     │    │ • PGQueuer consumer         │ │
│  │ • AI chat streaming │    │ • Uses DIRECT connection    │ │
│  │ • Uses POOLED conn  │    │ • Processes background jobs │ │
│  └──────────┬──────────┘    └──────────────┬──────────────┘ │
└─────────────┼──────────────────────────────┼─────────────────┘
              │                              │
              ▼                              ▼
┌─────────────────────────────────────────────────────────────┐
│           PostgreSQL (via DatabaseProvider)                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ Content tables  │  │ pgqueuer_jobs   │  │ pg_cron      │ │
│  │ (application)   │  │ (task queue)    │  │ (scheduler)  │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
│                                                              │
│  Provider: local | supabase | neon (auto-selected)          │
└─────────────────────────────────────────────────────────────┘
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

#### Task Queue: PGQueuer
**Rationale:**
- Pure Python library, no extensions required (works with Neon)
- Uses Postgres `SELECT FOR UPDATE SKIP LOCKED` pattern
- Built-in support for:
  - Job priorities
  - Retry logic
  - Deferred execution (`execute_after`)
  - Job cancellation
  - Dashboard CLI for monitoring
- Async-native, works with FastAPI
- No additional infrastructure (Redis) required

**Why not pgmq/Supabase Queues:**
- pgmq extension is not available on Neon
- Would require migrating database to Supabase

#### Scheduler: pg_cron (Neon-native)
**Rationale:**
- Runs inside Postgres, independent of worker uptime
- Neon supports pg_cron natively
- Scheduled jobs fire even if worker is temporarily down
- Worker can scale to zero between jobs (cost savings)
- pg_cron inserts jobs into PGQueuer table; worker processes them

**Why not PGQueuer's built-in scheduler:**
- Requires worker to run 24/7 just to check schedules
- Worker downtime = missed scheduled jobs

### Hybrid Scheduler Pattern

pg_cron handles the "when" (scheduling), PGQueuer handles the "what" (job processing):

```sql
-- pg_cron job (runs in Neon, always available)
SELECT cron.schedule(
    'daily-newsletter-scan',
    '0 6 * * *',  -- 6 AM UTC daily
    $$
    SELECT pgqueuer.enqueue('scan_newsletters', '{}'::jsonb, 0);
    $$
);
```

```python
# PGQueuer worker (runs on Railway, processes jobs)
@pgq.entrypoint("scan_newsletters")
async def scan_newsletters(job: Job) -> None:
    emails = await fetch_unread_newsletters()
    for email in emails:
        await queries.enqueue(
            "process_newsletter",
            payload={"email_id": email.id},
            priority=0
        )

@pgq.entrypoint("process_newsletter")
async def process_newsletter(job: Job) -> None:
    content = await fetch_email_content(job.payload["email_id"])
    summary = await summarize_with_ai(content)
    await save_summary(job.payload["email_id"], summary)
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

### Railway Service Configuration

**Service 1: Web API**
- Name: `web`
- Start Command: `uvicorn src.api.app:app --host 0.0.0.0 --port $PORT`
- Environment Variables:
  - `DATABASE_PROVIDER`: `neon` (or `supabase`, `local`)
  - `DATABASE_URL`: Connection string
  - `ALLOWED_ORIGINS`: `*` (for iOS Shortcuts)

**Service 2: Worker**
- Name: `worker`
- Start Command: `python -m src.worker`
- Environment Variables: Same as web
- Note: No public domain needed (internal only)

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

## Cost Estimate

### Railway (Monthly)
- Web service: ~$3-5 (low traffic, scales to zero possible)
- Worker service: ~$2-5 (mostly idle, wakes for jobs)
- **Total: ~$5-10/month**

### Neon (Monthly)
- Current plan (likely free tier or Launch): $0-19
- pg_cron: Included, no extra cost
- **Total: Existing cost, no change**

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Worker downtime misses jobs | Jobs persist in Postgres; processed when worker restarts |
| pg_cron fires but worker is down | Job queued in DB; worker catches up when available |
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

- [PGQueuer Documentation](https://pgqueuer.readthedocs.io/)
- [PGQueuer GitHub](https://github.com/janbjorge/pgqueuer)
- [Neon pg_cron Documentation](https://neon.tech/docs/extensions/pg_cron)
- [Railway Documentation](https://docs.railway.app/)
- [FastAPI BackgroundTasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
