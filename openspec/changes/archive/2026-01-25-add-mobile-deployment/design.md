# Design: Mobile Cloud Deployment

## Context

The application needs cloud deployment to enable mobile access and durable background task processing. Key stakeholders:
- Mobile users capturing content via iOS Shortcuts
- Scheduled jobs for newsletter scanning
- Development workflow with existing DatabaseProvider abstraction

## Goals / Non-Goals

### Goals
- Enable HTTPS access from mobile devices (iOS Shortcuts)
- Implement durable task queue that survives restarts
- Support scheduled recurring jobs (daily newsletter scan)
- Minimize infrastructure complexity (avoid Redis/Celery)
- Work with existing DatabaseProvider abstraction (local/Supabase/Neon)

### Non-Goals
- Complex multi-region deployment
- Auto-scaling beyond Railway's built-in scaling
- Real-time push notifications to mobile
- Multi-tenant architecture

## Decisions

### Decision 1: Railway for Hosting

**Choice**: Railway over Cloudflare Workers, Fly.io, or Vercel

**Rationale**:
- Native support for multiple services (web + worker) in one project
- No timeout issues for long-running AI API calls (unlike CF Workers)
- Simplest deployment from existing Docker setup
- Usage-based pricing fits light workload (~$5-10/month)

**Alternatives Considered**:
- Cloudflare Workers: Python in beta, timeout issues with AI calls, different programming model
- Fly.io: Good option but more configuration needed
- Vercel: Serverless timeouts problematic for AI streaming

### Decision 2: PGQueuer for Task Queue

**Choice**: PGQueuer over Celery/Redis, pgmq, or cloud queues

**Rationale**:
- Pure Python library, no extensions required (works with Neon)
- Uses PostgreSQL `SELECT FOR UPDATE SKIP LOCKED` pattern
- Built-in priorities, retries, deferred execution
- No additional infrastructure (reuses existing Postgres)
- Async-native, works with FastAPI

**Alternatives Considered**:
- Celery/Redis: Additional infrastructure, operational complexity
- pgmq/Supabase Queues: Extension not available on Neon
- SQS/Cloud Queues: Vendor lock-in, separate service to manage

### Decision 3: pg_cron for Scheduling

**Choice**: pg_cron (Neon-native) over APScheduler or worker-based scheduling

**Rationale**:
- Runs inside Postgres, independent of worker uptime
- Neon supports pg_cron natively
- Scheduled jobs fire even if worker is temporarily down
- Worker can scale to zero between jobs (cost savings)

**Pattern**: Hybrid scheduling where pg_cron handles "when" and PGQueuer handles "what":
```sql
SELECT cron.schedule(
    'daily-newsletter-scan',
    '0 6 * * *',
    $$SELECT pgqueuer_enqueue('scan_newsletters', '{}')$$
);
```

### Decision 4: Direct vs Pooled Connections

**Choice**: Provider abstraction for connection type selection

**Implementation**:
| Use Case | Connection Type | Reason |
|----------|----------------|--------|
| Web API | Pooled | Short-lived requests, efficient sharing |
| Queue Worker | Direct | Long-lived, uses LISTEN/NOTIFY |
| Migrations | Direct | Schema changes need direct access |

The `DatabaseProvider.get_queue_url()` method handles this automatically per provider.

### Decision 5: Trafilatura for Content Extraction

**Choice**: Trafilatura over custom HTML parser or Readability.js

**Rationale**:
- Academic-quality content extraction
- Better handling of article structure
- Python-native, no Node.js dependency
- Handles metadata extraction (author, date, etc.)

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Worker downtime misses jobs | Jobs persist in Postgres; processed when worker restarts |
| pg_cron fires but worker is down | Job queued in DB; worker catches up when available |
| Long-running AI tasks timeout | Railway has no hard timeout for containers |
| Database connection limits | Use connection pooling (asyncpg pool) |
| Cost overruns | Railway usage-based; set spending alerts |
| Neon cold start delay | First mobile capture may be slower (2-5s); acceptable tradeoff |

## Migration Plan

### Phase 1: Core Infrastructure (Complete)
1. Extend DatabaseProvider with queue methods
2. Set up PGQueuer configuration
3. Create worker entry point
4. Implement content extraction tasks

### Phase 2: API Endpoints (Complete)
1. Create save URL API endpoint
2. Add mobile-optimized save template
3. Configure CORS for mobile clients
4. Document iOS Shortcuts setup

### Phase 3: Deployment (Complete)
1. Configure Railway deployment (railway.toml, Dockerfile)
2. Set up environment variables
3. Deploy web and worker services
4. Test end-to-end mobile capture

### Phase 4: Scheduled Jobs (Pending)
1. Create Alembic migration for PGQueuer tables
2. Enable pg_cron extension on Neon
3. Create pgqueuer_enqueue helper function
4. Schedule daily newsletter scan job

### Rollback
- Railway supports instant rollback to previous deploy
- PGQueuer tables can be dropped if needed
- pg_cron jobs can be unscheduled with `cron.unschedule()`

## Open Questions

1. **pg_cron timezone**: Should scheduled jobs use UTC or local timezone?
   - Current assumption: UTC for consistency
2. **Worker scaling**: Do we need multiple worker instances?
   - Current assumption: Single worker sufficient for current load
3. **Job retention**: How long to keep completed job records?
   - Current assumption: 7 days, then archive/delete
