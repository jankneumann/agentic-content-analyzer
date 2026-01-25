# pg_cron Setup for Scheduled Jobs

This document describes how to set up pg_cron for scheduled task execution with the PGQueuer durable task queue.

## Overview

The system uses a **hybrid scheduling pattern**:
- **pg_cron** handles the "when" (scheduling) - runs inside Postgres, independent of worker uptime
- **PGQueuer** handles the "what" (job processing) - runs as a separate worker process

This separation means scheduled jobs fire even if the worker is temporarily unavailable.

## Prerequisites

- Neon PostgreSQL database with pg_cron extension enabled
- PGQueuer tables created via Alembic migration
- Worker process running to consume jobs

## Neon pg_cron Setup

### 1. Enable the Extension

pg_cron is available on Neon but must be enabled:

```sql
-- Run this in the Neon SQL Editor or via psql
CREATE EXTENSION IF NOT EXISTS pg_cron;
```

> **Note**: pg_cron is only available on Neon's Scale plan and above. Check your plan if the extension fails to create.

### 2. Verify the Helper Function

The `pgqueuer_enqueue` function should be created by the Alembic migration. Verify it exists:

```sql
-- Should return the function signature
\df pgqueuer_enqueue
```

If missing, create it manually:

```sql
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
```

### 3. Schedule the Daily Newsletter Scan

```sql
-- Schedule newsletter scan at 6 AM UTC daily
SELECT cron.schedule(
    'daily-newsletter-scan',      -- job name (must be unique)
    '0 6 * * *',                  -- cron expression: 6:00 AM UTC daily
    $$SELECT pgqueuer_enqueue('scan_newsletters', '{}')$$
);
```

### 4. Verify the Schedule

```sql
-- List all scheduled jobs
SELECT * FROM cron.job;

-- Check job execution history
SELECT * FROM cron.job_run_details ORDER BY start_time DESC LIMIT 10;
```

## Common Cron Expressions

| Expression | Meaning |
|------------|---------|
| `0 6 * * *` | Daily at 6:00 AM UTC |
| `0 */4 * * *` | Every 4 hours |
| `*/15 * * * *` | Every 15 minutes |
| `0 6 * * 1` | Every Monday at 6:00 AM UTC |
| `0 6 1 * *` | First day of month at 6:00 AM UTC |

## Managing Scheduled Jobs

### Unschedule a Job

```sql
-- Remove the daily newsletter scan
SELECT cron.unschedule('daily-newsletter-scan');
```

### Update a Schedule

```sql
-- First unschedule, then reschedule with new time
SELECT cron.unschedule('daily-newsletter-scan');
SELECT cron.schedule(
    'daily-newsletter-scan',
    '0 7 * * *',  -- Changed to 7 AM UTC
    $$SELECT pgqueuer_enqueue('scan_newsletters', '{}')$$
);
```

### Run a Job Manually

```sql
-- Manually trigger newsletter scan (bypasses schedule)
SELECT pgqueuer_enqueue('scan_newsletters', '{}');
```

## Monitoring

### Check Job Status

```sql
-- View recent job executions
SELECT
    jobid,
    runid,
    job_pid,
    database,
    username,
    command,
    status,
    return_message,
    start_time,
    end_time
FROM cron.job_run_details
WHERE command LIKE '%scan_newsletters%'
ORDER BY start_time DESC
LIMIT 10;
```

### Check Pending Queue Jobs

```sql
-- View queued jobs waiting for processing
SELECT
    id,
    entrypoint,
    status,
    created_at,
    execute_after,
    priority
FROM pgqueuer_jobs
WHERE status = 'queued'
ORDER BY priority DESC, created_at;
```

### Check Failed Jobs

```sql
-- View failed jobs with error messages
SELECT
    id,
    entrypoint,
    error,
    created_at,
    completed_at,
    retry_count
FROM pgqueuer_jobs
WHERE status = 'failed'
ORDER BY completed_at DESC
LIMIT 20;
```

## Troubleshooting

### pg_cron Extension Not Found

If `CREATE EXTENSION pg_cron` fails:
1. Verify you're on a Neon plan that supports pg_cron (Scale or above)
2. Contact Neon support to enable the extension for your project

### Scheduled Job Not Running

1. Check the job exists: `SELECT * FROM cron.job;`
2. Check job history: `SELECT * FROM cron.job_run_details WHERE jobid = <your_job_id>;`
3. Verify the cron expression is correct
4. Check if `pgqueuer_enqueue` function exists

### Jobs Queued But Not Processing

1. Verify the worker is running: Check Railway logs for `src/worker.py`
2. Check database connectivity from worker
3. Look for errors in worker logs

### Jobs Failing Repeatedly

1. Check the error message: `SELECT error FROM pgqueuer_jobs WHERE status = 'failed';`
2. Review worker logs for stack traces
3. Manually test the task: `SELECT pgqueuer_enqueue('scan_newsletters', '{}');`

## Example: Adding More Scheduled Jobs

```sql
-- Weekly summary generation (Sundays at midnight)
SELECT cron.schedule(
    'weekly-summary',
    '0 0 * * 0',
    $$SELECT pgqueuer_enqueue('generate_weekly_digest', '{"type": "weekly"}')$$
);

-- Hourly content refresh (every hour on the hour)
SELECT cron.schedule(
    'hourly-content-refresh',
    '0 * * * *',
    $$SELECT pgqueuer_enqueue('refresh_content', '{}', 1)$$  -- priority 1
);
```

## References

- [Neon pg_cron Documentation](https://neon.tech/docs/extensions/pg_cron)
- [PGQueuer Documentation](https://pgqueuer.readthedocs.io/)
- [Cron Expression Generator](https://crontab.guru/)
