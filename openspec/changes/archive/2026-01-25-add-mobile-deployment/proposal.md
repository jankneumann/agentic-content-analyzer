# Change: Add Mobile Cloud Deployment with Durable Background Tasks

## Why

The application currently runs locally, which prevents mobile access and lacks durable task processing:

1. **No mobile access**: iPhone cannot reach localhost for content capture
2. **Tasks not durable**: FastAPI BackgroundTasks are lost on server restart/deploy
3. **No scheduled jobs**: No mechanism for recurring tasks like daily email scans
4. **No retry logic**: Failed tasks are lost without recovery

## What's Included

### Railway Cloud Deployment
- Two-service architecture: Web API + Worker process
- Docker-based deployment from existing Dockerfile
- HTTPS endpoint for iOS Shortcuts compatibility
- Usage-based pricing (~$5-10/month)

### Durable Task Queue (PGQueuer)
- Postgres-based queue using `SELECT FOR UPDATE SKIP LOCKED` pattern
- Job priorities, retry logic, deferred execution
- No additional infrastructure (no Redis required)
- DatabaseProvider abstraction for queue-specific connection handling

### Scheduled Jobs (pg_cron)
- Database-native scheduling independent of worker uptime
- Neon pg_cron support for recurring newsletter scans
- Hybrid pattern: pg_cron schedules, PGQueuer processes

### Connection Management
- Pooled connections for web API (short-lived requests)
- Direct connections for queue workers (LISTEN/NOTIFY)
- DatabaseProvider.get_queue_url() abstraction per provider

## What Changes

- **NEW**: `src/queue/setup.py` - PGQueuer configuration
- **NEW**: `src/tasks/content.py` - Content extraction task definitions
- **NEW**: `src/worker.py` - Worker process entry point
- **NEW**: `src/services/url_extractor.py` - URL content extraction
- **NEW**: `src/api/save_routes.py` - Mobile save API endpoints
- **NEW**: `src/templates/save.html` - Mobile-optimized save page
- **NEW**: `shortcuts/README.md` - iOS Shortcuts documentation
- **ENHANCED**: `src/storage/providers/*.py` - Queue URL methods
- **NEW**: `railway.toml` - Railway deployment configuration
- **PENDING**: Alembic migration for PGQueuer tables
- **PENDING**: pg_cron setup for scheduled jobs

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Railway                               │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │   FastAPI Web       │    │   FastAPI Worker            │ │
│  │   (Service 1)       │    │   (Service 2)               │ │
│  │                     │    │                             │ │
│  │ • API endpoints     │    │ • PGQueuer consumer         │
│  │ • AI chat streaming │    │ • Uses DIRECT connection    │
│  │ • Uses POOLED conn  │    │ • Processes background jobs │
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
└─────────────────────────────────────────────────────────────┘
              ▲
              │
┌─────────────┴─────────────┐
│     iOS Shortcuts         │
│     (HTTPS requests)      │
└───────────────────────────┘
```

## Impact

- **New spec**: `mobile-cloud-infrastructure` - Cloud deployment and task queue
- **Affected code**:
  - `src/queue/` - Task queue infrastructure
  - `src/tasks/` - Task definitions
  - `src/worker.py` - Worker process
  - `src/api/save_routes.py` - Save URL endpoints
  - `src/services/url_extractor.py` - Content extraction
  - `src/storage/providers/` - Queue URL methods
- **Dependencies**: PGQueuer library, trafilatura for content extraction
- **Cost**: Railway (~$5-10/month), Neon pg_cron (included)

## Related Proposals

- **add-mobile-content-capture** - iOS Shortcuts and API key auth (overlaps with mobile capture features)
- **content-capture** - Browser extensions and bookmarklets (web-based capture)
- **add-deployment-pipeline** - CI/CD pipeline (deployment automation)

## Success Criteria

1. **Mobile access works**: iOS Shortcuts can hit API endpoints via HTTPS
2. **Tasks are durable**: Server restart doesn't lose pending jobs
3. **Daily scan runs**: Newsletter scan executes on schedule via pg_cron
4. **Observability**: Can view job status via dashboard or API
5. **Cost reasonable**: Total hosting under $15/month
